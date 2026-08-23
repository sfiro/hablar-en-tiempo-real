#!/usr/bin/env python3
"""
Servidor local para hablar con la Realtime API de OpenAI **por WebRTC**, igual que hace
el modo de voz de ChatGPT — con análisis de sentimiento, rastreo facial real y control
de la Pico.

Desde v10 este proceso corre en una **Raspberry Pi 5**, no en un Mac (ver
README-v10.md para el porqué y el detalle de hardware). El código de este fichero
apenas cambió respecto a v9 — la arquitectura entera ya era "Python solo negocia
WebRTC, nunca toca audio" (ver el párrafo siguiente), así que migrar de cliente no
tocó esa parte. Lo que sí cambió: la cámara (CSI vía `picamera2`, no la webcam del
Mac vía `cv2.VideoCapture` — ver `_hilo_rastreo()` y `main()`) y la detección del
puerto serial de la Pico (`encontrar_puerto_pico()`, en `pico_serial.py`, busca
`/dev/ttyACM*` en vez de los nombres de macOS).

La diferencia con `realtime_voice.py` está en quién captura el micro. Aquí lo hace el
navegador (Chromium, corriendo en la propia Pi 5, con pantalla conectada — ver
README-v10.md) con `echoCancellation: true`, así que aplica cancelación de eco
acústico real: conoce la señal que sale por el altavoz USB y la resta de la que
entra por el micro USB. Por eso el modelo no se oye a sí mismo y puedes
interrumpirlo hablando, con altavoz y sin trucos — sin los paliativos (medio-dúplex,
Enter para interrumpir) que necesita la versión de terminal. A este proceso de
Python solo debe llegarle el texto ya transcrito, para el análisis de sentimiento y
el envío a la Pico; el audio en sí viaja directo entre el navegador y OpenAI por el
canal WebRTC, este proceso nunca lo toca — por eso migrar de Mac a Pi 5 no tuvo que
tocar nada de audio aquí: el micro/parlante USB los usa el navegador, no Python.

Con --tracking, este proceso también rastrea el rostro por cámara CSI
(`face_tracker.py`) en un hilo de fondo, y manda la posición real —no un valor
fijo— junto con cada comando a la Pico. --sentiment y --tracking son
independientes entre sí: se puede rastrear sin sentimiento, tener sentimiento sin
rastreo, o las dos juntas (el caso pensado para esta versión, igual que en v9).

Modo dormido por inactividad (heredado de v9, sin cambios): si pasan
--sleep-timeout segundos (60 por defecto) sin que el usuario diga nada, la Pico
entra en DORMIDO — se mantiene mientras dure el silencio, no solo 5 segundos,
reenviando el comando cada segundo (mismo mecanismo ya probado de "la misma
emoción repetida extiende el pulso", sin ningún cambio en el firmware). En
cuanto el usuario vuelve a hablar, se manda DUDA una sola vez — "se despierta
confundido" — y el propio pulso de 5s de la Pico la lleva sola de vuelta a
NEUTRAL, sin que este proceso tenga que hacer nada más. Activo siempre que haya
una Pico conectada (con --sentiment y/o --tracking), sin necesitar un flag
propio para activarlo.

Este proceso hace hasta cinco cosas:
  1. Sirve la página `static/index.html`.
  2. Reenvía la oferta SDP del navegador a OpenAI firmándola con tu clave, que nunca
     sale de tu equipo ni llega al navegador.
  3. (Con --sentiment) Recibe por `POST /api/analyze-sentiment` el texto de cada frase
     completa (el navegador lo transcribe vía el canal de datos WebRTC, que este
     proceso no ve — solo negocia la conexión), lo clasifica con `sentiment_analyzer.py`
     y, si hay una Pico conectada, envía la expresión correspondiente por serial.
  4. (Con --tracking) Rastrea el rostro por cámara CSI en un hilo de fondo y manda su
     posición real por serial mientras haya cambios significativos — independiente
     de si --sentiment está activo.
  5. Vigila cuánto hace que el usuario habló por última vez (cada frase transcrita
     del navegador cuenta, tenga o no --sentiment activo) y, si pasa demasiado
     tiempo, manda a la Pico a dormir y la despierta con DUDA cuando vuelve la
     actividad — ver el hilo `_hilo_vigia_sueno()`.

**No verificado todavía contra hardware real de la Pi 5** — este código se escribió
sin una Raspberry Pi 5 delante (ver README-v10.md, sección "Cómo se verificó"), a
diferencia de v9, que sí llegó a probarse en la máquina real del usuario.

Uso:
    python webrtc_server.py
    python webrtc_server.py --sentiment
    python webrtc_server.py --tracking
    python webrtc_server.py --sentiment --tracking   # el caso pensado para esta versión
    python webrtc_server.py --sentiment --no-pico    # sentimiento sin tocar la Pico
    python webrtc_server.py --voice cedar --port 8080
"""

import argparse
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import certifi
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
load_dotenv(BASE_DIR / ".env")

CALLS_URL = "https://api.openai.com/v1/realtime/calls"

# Relleno por main(); el handler los lee al atender cada petición.
CONFIG = {}

# Analizador de sentimiento y enlace con la Pico — None si ni --sentiment ni
# --tracking están activos, o si están activos pero no hay Pico conectada
# (--no-pico o no se detectó ninguna). Rellenos por main(), leídos por el
# handler y por el hilo de rastreo.
ANALYZER = None
PICO = None

# Última posición real del rostro detectado por el hilo de rastreo (grados de
# servo, 40-140), actualizada solo con --tracking activo. Con --tracking
# apagado, se queda en el centro (90,90) — mismo valor fijo que usaba v8 para
# todas las expresiones. La usa _handle_analyze_sentiment() para que el
# comando que dispara un EMOCION lleve la mirada real, no un salto al centro.
ULTIMA_MIRADA = {"lr": 90, "ud": 90}
_LOCK_MIRADA = threading.Lock()

# Modo dormido por inactividad. ULTIMA_ACTIVIDAD se actualiza cada vez que el
# navegador manda una frase del usuario ya transcrita (en
# _handle_analyze_sentiment, con o sin --sentiment activo — la actividad no
# depende del análisis de sentimiento, solo de que haya habido una frase
# real). DORMIDO refleja si _hilo_vigia_sueno() considera que el robot está
# dormido en este momento, para saber cuándo mandar el gesto de "despertar".
SLEEP_TIMEOUT_S = 60.0  # sobreescrito por --sleep-timeout en main()
ULTIMA_ACTIVIDAD = time.time()
DORMIDO = False
_LOCK_SUENO = threading.Lock()

# Mismo mapeo que v10/realtime_voice.py — ver ese fichero para el razonamiento
# completo de cada correspondencia (incluye por qué DORMIDO/DUDA/PENSATIVO no
# se usan aquí: pysentimiento no tiene categoría que les corresponda).
EMOTION_TO_PICO = {
    "joy": "FELIZ",
    "sadness": "TRISTE",
    "anger": "ENOJADO",
    "fear": "NERVIOSO",
    "surprise": "SORPRENDIDO",
    "disgust": "SOSPECHA",
    "others": "NEUTRAL",
}


def _hilo_rastreo(picam2, detener: threading.Event):
    """Rastrea el rostro por cámara CSI y manda su posición real a la Pico mientras
    haya cambios significativos. Corre en un hilo de fondo, en paralelo al
    servidor HTTP — igual patrón que `face_tracker.py` usaba en su bucle
    standalone, pero sin ventana y sin su propio PicoLink (usa el PICO
    compartido de este proceso, si hay uno).

    Recibe un `Picamera2` ya abierto y arrancado, en vez de abrirlo aquí — mismo
    patrón defensivo que usaba v9 con `cv2.VideoCapture` en macOS (donde abrir la
    cámara desde un hilo de fondo fallaba de verdad: "can not spin main run loop
    from other thread", porque AVFoundation necesita negociar el permiso desde el
    hilo principal). En Linux/Raspberry Pi OS con picamera2 **no se ha confirmado
    un problema equivalente** — se mantiene la misma estructura (abrir en
    `main()`, leer aquí) por consistencia y porque no hay motivo para arriesgarlo,
    no porque se haya reproducido un fallo en esta plataforma.
    """
    import cv2
    from face_tracker import FaceTracker, leer_frame

    print("✅ Cámara lista: el rastreo facial está activo.")
    tracker = FaceTracker()
    try:
        while not detener.is_set():
            ret, frame = leer_frame(picam2)
            if not ret:
                break
            frame = cv2.flip(frame, 1)  # efecto espejo
            resultado = tracker.procesar(frame)
            if resultado["detectado"] and resultado["cambio_significativo"]:
                lr, ud = resultado["grado_x"], resultado["grado_y"]
                with _LOCK_MIRADA:
                    ULTIMA_MIRADA["lr"], ULTIMA_MIRADA["ud"] = lr, ud
                if PICO is not None:
                    PICO.enviar(lr, ud)
    finally:
        picam2.stop()


def _decidir_sueno(ahora: float, ultima_actividad: float, timeout: float,
                    dormido_previo: bool) -> tuple[bool, bool]:
    """Decisión pura del modo dormido, aislada de threading/tiempo real para
    poder probarla directamente (ver test_webrtc_server.py). Devuelve
    (dormir_ahora, despertando):
      - dormir_ahora: si toca estar en DORMIDO en este instante
      - despertando: si justo en este instante se pasa de dormido a despierto
        (dispara el gesto de DUDA una sola vez, no en cada vuelta)
    """
    dormir_ahora = (ahora - ultima_actividad) >= timeout
    despertando = dormido_previo and not dormir_ahora
    return dormir_ahora, despertando


def _hilo_vigia_sueno(detener: threading.Event):
    """Manda la Pico a dormir tras SLEEP_TIMEOUT_S de silencio, y la despierta
    con DUDA en cuanto vuelve la actividad.

    No hace falta ningún cambio en main.py (el firmware): DORMIDO se mantiene
    reenviándolo cada segundo — la misma emoción repetida extiende su pulso de
    5s en vez de dejarlo expirar (mecanismo ya probado en el firmware desde
    v8, ver test_main_math.py). Al despertar, DUDA se manda una sola vez; su
    propio pulso de 5s la devuelve sola a NEUTRAL, sin que este hilo tenga que
    hacer nada más — es indistinguible, para la Pico, de recibir DUDA por
    cualquier otro motivo.
    """
    global DORMIDO
    while not detener.is_set():
        time.sleep(1)
        if PICO is None:
            continue
        with _LOCK_SUENO:
            dormido_previo = DORMIDO
            dormir_ahora, despertando = _decidir_sueno(
                time.time(), ULTIMA_ACTIVIDAD, SLEEP_TIMEOUT_S, dormido_previo
            )
            DORMIDO = dormir_ahora
        if dormir_ahora and not dormido_previo:
            print(f"😴 Sin actividad por {SLEEP_TIMEOUT_S:.0f}s: la Pico se duerme.")
        if dormir_ahora:
            PICO.enviar(90, 90, "DORMIDO")
        elif despertando:
            print("👀 Actividad detectada tras el silencio: despertando (DUDA).")
            PICO.enviar(90, 90, "DUDA")


def build_multipart(sdp: str, session: dict) -> tuple[bytes, str]:
    """Arma el multipart/form-data con los campos `sdp` y `session` que espera OpenAI."""
    boundary = f"----realtime{uuid.uuid4().hex}"
    parts = []
    for name, value, content_type in (
        ("sdp", sdp, "application/sdp"),
        ("session", json.dumps(session), "application/json"),
    ):
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
            f"{value}\r\n"
        )
    parts.append(f"--{boundary}--\r\n")
    return "".join(parts).encode("utf-8"), f"multipart/form-data; boundary={boundary}"


def negotiate(sdp_offer: str) -> str:
    """Entrega la oferta SDP a OpenAI y devuelve la respuesta SDP."""
    session = {
        "type": "realtime",
        "model": CONFIG["model"],
        "instructions": CONFIG["instructions"],
        "audio": {
            "input": {"transcription": {"model": "gpt-4o-mini-transcribe"}},
            "output": {"voice": CONFIG["voice"]},
        },
    }
    body, content_type = build_multipart(sdp_offer, session)
    request = urllib.request.Request(
        CALLS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {CONFIG['api_key']}",
            "Content-Type": content_type,
        },
    )
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, context=ctx, timeout=30) as response:
        return response.read().decode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if CONFIG.get("verbose"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        name = "index.html" if self.path in ("/", "/index.html") else self.path.lstrip("/")
        target = (STATIC_DIR / name).resolve()
        # No servimos nada fuera de static/.
        if not str(target).startswith(str(STATIC_DIR)) or not target.is_file():
            self._send(404, b"No encontrado", "text/plain; charset=utf-8")
            return
        kind = {".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8"}.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), kind)

    def do_POST(self):
        if self.path == "/session":
            self._handle_session()
        elif self.path == "/api/analyze-sentiment":
            self._handle_analyze_sentiment()
        else:
            self._send(404, b"No encontrado", "text/plain; charset=utf-8")

    def _handle_session(self):
        length = int(self.headers.get("Content-Length", 0))
        sdp_offer = self.rfile.read(length).decode("utf-8")
        try:
            answer = negotiate(sdp_offer)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            print(f"\n⚠️  OpenAI devolvió {e.code}: {detail}", file=sys.stderr)
            self._send(502, detail.encode("utf-8"), "text/plain; charset=utf-8")
        except Exception as e:  # red caída, DNS, timeout…
            print(f"\n⚠️  Error conectando con OpenAI: {e}", file=sys.stderr)
            self._send(502, str(e).encode("utf-8"), "text/plain; charset=utf-8")
        else:
            self._send(200, answer.encode("utf-8"), "application/sdp")

    def _handle_analyze_sentiment(self):
        """Recibe el texto de una frase completa (el navegador la transcribió vía el
        canal de datos WebRTC, que este proceso nunca ve), la clasifica y, si
        corresponde, la envía a la Pico.

        También marca la actividad para el modo dormido (`ULTIMA_ACTIVIDAD`),
        con o sin `--sentiment` activo — el navegador manda aquí cada frase
        transcrita independientemente de si hay análisis de sentimiento, así
        que es el punto natural para saber "el usuario acaba de hablar".

        `ThreadingHTTPServer` atiende cada petición en su propio hilo: que
        `analyzer.analyze()` tarde unos cientos de ms no bloquea la negociación SDP
        de otra conexión ni otra llamada a este mismo endpoint.
        """
        global ULTIMA_ACTIVIDAD
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            role = payload.get("role", "")
            text = (payload.get("text") or "").strip()
        except (ValueError, AttributeError):
            self._send(400, b'{"error":"JSON invalido"}', "application/json")
            return

        if role == "user" and text:
            with _LOCK_SUENO:
                ULTIMA_ACTIVIDAD = time.time()

        if ANALYZER is None:
            self._send(503, b'{"error":"sentiment no activo (falta --sentiment)"}',
                       "application/json")
            return
        if not text:
            self._send(200, b'{"skipped":"texto vacio"}', "application/json")
            return

        result = ANALYZER.analyze(text)
        respuesta = {
            "role": role, "label": result["label"], "emoji": result["emoji"],
            "confidence": result["confidence"], "pico": None,
        }
        if result["confidence"] >= CONFIG["confidence_threshold"]:
            emocion_pico = EMOTION_TO_PICO.get(result["emotion"], "NEUTRAL")
            respuesta["pico"] = emocion_pico
            if PICO is not None:
                # La mirada real del rastreo (o 90,90 si --tracking no está
                # activo) — no un salto al centro cada vez que cambia la
                # expresión. Ver ULTIMA_MIRADA más arriba.
                with _LOCK_MIRADA:
                    lr, ud = ULTIMA_MIRADA["lr"], ULTIMA_MIRADA["ud"]
                PICO.enviar(lr, ud, emocion_pico)

        self._send(200, json.dumps(respuesta).encode("utf-8"), "application/json")


def main():
    parser = argparse.ArgumentParser(
        description="Conversación de voz por WebRTC con la Realtime API (con cancelación "
                    "de eco del navegador).")
    parser.add_argument("--model", default="gpt-realtime-2.1",
                        help="Modelo de voz (por defecto: gpt-realtime-2.1).")
    parser.add_argument("--voice", default="marin",
                        help="Voz: marin, cedar, alloy, echo, shimmer… (por defecto: marin).")
    parser.add_argument("--instructions", default=(
        "Eres un asistente de voz amable y conversacional. Responde de forma breve y "
        "natural, en el mismo idioma que use la persona."
    ), help="Instrucciones de sistema para el asistente.")
    parser.add_argument("--port", type=int, default=8000, help="Puerto local (por defecto: 8000).")
    parser.add_argument("--no-browser", action="store_true",
                        help="No abrir el navegador automáticamente. Útil si Chromium ya "
                             "está abierto en modo kiosk apuntando a esta URL (ver "
                             "README-v10.md).")
    parser.add_argument("--verbose", action="store_true", help="Registra cada petición HTTP.")

    # --- Análisis de sentimiento + control de la Pico ---------------------------
    parser.add_argument("--sentiment", action="store_true",
                        help="Clasifica la emoción de cada frase (tuya y del asistente) y, "
                             "si hay una Pico conectada, controla su expresión facial. "
                             "Necesita 'pysentimiento' instalado.")
    parser.add_argument("--language", choices=("es", "en", "it", "pt"), default="es",
                        help="Idioma del modelo de emociones (por defecto: es).")
    parser.add_argument("--confidence-threshold", type=float, default=0.5,
                        help="Solo envía la emoción a la Pico si su confianza supera este "
                             "valor, 0-1 (por defecto: 0.5).")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No envíes nada a la Pico aunque haya una conectada. Solo "
                             "tiene efecto con --sentiment y/o --tracking.")

    # --- Rastreo facial real, por cámara CSI -------------------------------------
    parser.add_argument("--tracking", action="store_true",
                        help="Rastrea el rostro por la cámara CSI y manda su posición real "
                             "a la Pico. Independiente de --sentiment: se puede usar solo, "
                             "o junto con --sentiment (el caso pensado para esta versión). "
                             "Necesita 'opencv-python' y 'picamera2' instalados.")
    parser.add_argument("--sleep-timeout", type=float, default=60.0,
                        help="Segundos sin que el usuario hable antes de que la Pico "
                             "entre en modo DORMIDO; al volver la actividad, se "
                             "despierta con DUDA (por defecto: 60). Activo siempre que "
                             "haya una Pico conectada.")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: falta OPENAI_API_KEY. Ponla en el fichero .env "
            '(OPENAI_API_KEY="sk-...") o expórtala en tu shell.'
        )

    CONFIG.update(api_key=api_key, model=args.model, voice=args.voice,
                  instructions=args.instructions, verbose=args.verbose,
                  confidence_threshold=args.confidence_threshold)

    global ANALYZER, PICO, SLEEP_TIMEOUT_S, ULTIMA_ACTIVIDAD
    SLEEP_TIMEOUT_S = args.sleep_timeout
    ULTIMA_ACTIVIDAD = time.time()  # cuenta desde que arranca el servidor, no desde 0
    if args.sentiment:
        try:
            import pysentimiento  # noqa: F401
        except ImportError:
            sys.exit(
                "ERROR: --sentiment necesita 'pysentimiento'. Instala con:\n"
                "  pip install -r requirements.txt"
            )
        from sentiment_analyzer import SentimentAnalyzer
        ANALYZER = SentimentAnalyzer(language=args.language)
        # Precarga en un hilo aparte: igual motivo que en realtime_voice.py — si se
        # deja para la primera frase, esa frase tarda varios segundos extra.
        threading.Thread(target=ANALYZER._load, daemon=True).start()

    if args.tracking:
        try:
            import cv2  # noqa: F401
        except ImportError:
            sys.exit(
                "ERROR: --tracking necesita 'opencv-python'. Instala con:\n"
                "  pip install -r requirements.txt"
            )

    # Una sola conexión a la Pico, compartida por el endpoint de sentimiento,
    # el hilo de rastreo y el hilo vigía de sueño — todos la necesitan, y solo
    # puede haber un proceso con el puerto serial abierto a la vez.
    detener_rastreo = threading.Event()
    detener_sueno = threading.Event()
    if (args.sentiment or args.tracking) and args.usar_pico:
        from pico_serial import PicoLink, encontrar_puerto_pico
        puerto_pico = encontrar_puerto_pico()
        if puerto_pico:
            PICO = PicoLink(port=puerto_pico)
            PICO.start()
            print(f"✅ Pico detectada en {puerto_pico}.")
            threading.Thread(
                target=_hilo_vigia_sueno, args=(detener_sueno,), daemon=True
            ).start()
        else:
            print("⚠️  No se detectó ninguna Pico. La conversación sigue "
                  "igual, sin mover los servos. (En Linux, confirma que tu "
                  "usuario está en el grupo 'dialout' si la Pico está "
                  "enchufada y aun así no aparece.)")

    if args.tracking:
        # La cámara CSI se abre AQUÍ, en el hilo principal — no dentro de
        # _hilo_rastreo(). Mismo patrón defensivo que usaba v9 en macOS (donde
        # abrirla desde un hilo de fondo sí fallaba de verdad, por
        # AVFoundation); en Linux/picamera2 no hay un problema equivalente
        # confirmado, pero no hay motivo para arriesgarlo — ver la cabecera de
        # _hilo_rastreo().
        from face_tracker import abrir_camara_csi
        print("🔍 Iniciando cámara CSI para el rastreo facial...")
        try:
            picam2 = abrir_camara_csi()
        except ImportError:
            print("⚠️  Falta 'picamera2'. El rastreo facial no estará activo. "
                  "Instálalo con: sudo apt install -y python3-picamera2 "
                  "--no-install-recommends (ver README-v10.md).")
            args.tracking = False
        except Exception as e:
            print(f"⚠️  No se pudo abrir la cámara CSI ({e}). El rastreo facial "
                  "no estará activo.")
            args.tracking = False
        else:
            threading.Thread(
                target=_hilo_rastreo, args=(picam2, detener_rastreo), daemon=True
            ).start()

    url = f"http://localhost:{args.port}/"
    # Solo escuchamos en localhost: la clave está en este proceso y no debe salir del equipo.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"🎙️  Abre {url} y pulsa «Conectar» (en el navegador de la propia Pi 5).")
    print(f"    Modelo {args.model} · voz {args.voice}")
    print("    El navegador cancela el eco, así que puedes usar el parlante USB e "
          "interrumpirle.")
    if args.sentiment:
        print(f"    Emociones: ACTIVO ({args.language}) — el modelo se descarga la "
              "primera vez, puede tardar.")
    if args.tracking:
        print("    Rastreo facial: ACTIVO (cámara CSI)")
    if PICO is not None:
        print(f"    Modo dormido: tras {args.sleep_timeout:.0f}s sin hablar "
              "(se despierta con DUDA)")
    print("    (Ctrl+C para parar)\n")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Adiós.")
        server.shutdown()
    finally:
        detener_rastreo.set()
        detener_sueno.set()
        if PICO is not None:
            PICO.stop()


if __name__ == "__main__":
    main()
