#!/usr/bin/env python3
"""
Servidor local para hablar con la Realtime API de OpenAI **por WebRTC**, igual que hace
el modo de voz de ChatGPT — con rastreo facial real y control de la Pico, todavía sin
análisis de sentimiento.

La diferencia con `realtime_voice.py` está en quién captura el micro. Aquí lo hace el
navegador con `echoCancellation: true`, así que aplica cancelación de eco acústico real:
conoce la señal que sale por el altavoz y la resta de la que entra por el micro. Por eso
el modelo no se oye a sí mismo y puedes interrumpirlo hablando, con altavoces y sin trucos.

Base: copia de v11/webrtc_server.py (== v1, con el fix real de query string en
`do_GET` ya incluido). Novedad de v13, pedida explícitamente — Hito B, tras
validar el rastreo con `realtime_voice.py` (Hito A): con `--tracking`, este
proceso también rastrea el rostro por cámara (`face_tracker.py`, retomado de
v12) en un hilo de fondo, y manda su posición real a la Pico
(`pico_serial.py`, retomado de v12) mientras dura la conversación — mismo
mecanismo que v9/v10 ya validaron para `webrtc_server.py`, aquí sin la parte
de sentimiento (v9 tenía `--sentiment` + `_handle_analyze_sentiment`; v13 no
la trae, a propósito).

Este proceso hace hasta tres cosas:
  1. Sirve la página `static/index.html`.
  2. Reenvía la oferta SDP del navegador a OpenAI firmándola con tu clave, que nunca
     sale de tu equipo ni llega al navegador.
  3. (Con --tracking) Rastrea el rostro por cámara en un hilo de fondo y manda su
     posición real por serial mientras haya un rostro detectado.

**Sin sentimiento todavía, a propósito:** el rastreo nunca manda un campo
EMOCION junto con `LR,UD`. El firmware (`main.py`) solo cambia de expresión
al recibir un EMOCION válido, así que `emocion_actual` se queda siempre en
NEUTRAL durante toda la sesión — parpadeo normal, sin que
DUDA/PENSATIVO/NERVIOSO se disparen nunca y sin que nada fije la mirada por
su cuenta.

Uso:
    python webrtc_server.py
    python webrtc_server.py --tracking
    python webrtc_server.py --tracking --no-pico    # rastreo sin mover servos
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
import urllib.parse
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

# Enlace con la Pico — None si --tracking no está activo, o si está activo
# pero no hay Pico conectada (--no-pico o no se detectó ninguna).
PICO = None

# Cadencia mínima entre envíos de mirada a la Pico: mismo valor calibrado en
# v12 en hardware real (a 20 envíos/s el buffer USB de la Pico se saturaba).
CADENCIA_ENVIO_S = 0.2


def _hilo_rastreo(leer, detener: threading.Event):
    """Rastrea el rostro por cámara y manda su posición real a la Pico mientras
    haya un rostro detectado. Corre en un hilo de fondo, en paralelo al
    servidor HTTP. Nunca manda un campo EMOCION — retomado de v12, sin
    cambios de lógica.

    Recibe un *callable* `leer` (sin argumentos) que devuelve `(ret, frame)`,
    para servir igual a la cámara CSI (`lambda: leer_frame(picam2)`) que a una
    webcam USB de respaldo (`cap.read`). La cámara se abre en `main()` (hilo
    principal) y se libera ahí también — mismo patrón que v9/v10/v12
    documentaron (imprescindible en macOS/AVFoundation; en Linux/Pi 5 no está
    confirmado que haga falta, se mantiene por consistencia).
    """
    import cv2
    from face_tracker import FaceTracker

    print("✅ Cámara lista: el rastreo facial está activo (sin sentimiento, siempre NEUTRAL).")
    tracker = FaceTracker()  # alpha=0.5, zona_muerta=0 por defecto (calibrado en v12)
    ultimo_envio = 0.0
    try:
        while not detener.is_set():
            ret, frame = leer()
            if not ret:
                print("⚠️  No se pudo leer el frame de la cámara")
                break
            frame = cv2.flip(frame, 1)  # efecto espejo
            resultado = tracker.procesar(frame)
            if not resultado["detectado"]:
                continue
            ahora = time.monotonic()
            if ahora - ultimo_envio < CADENCIA_ENVIO_S:
                continue
            ultimo_envio = ahora
            lr, ud = resultado["grado_x"], resultado["grado_y"]
            if PICO is not None:
                PICO.enviar(lr, ud)  # nunca con EMOCION: sin sentimiento todavía
    finally:
        pass  # la cámara se libera en main(), según su tipo (picam2.stop() / cap.release())


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
        path = urllib.parse.urlparse(self.path).path  # ignora la query string (?auto=1)
        name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
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
        if self.path != "/session":
            self._send(404, b"No encontrado", "text/plain; charset=utf-8")
            return

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


def main():
    parser = argparse.ArgumentParser(
        description="Conversación de voz por WebRTC con la Realtime API (con cancelación "
                    "de eco del navegador) + rastreo facial real, sin sentimiento todavía.")
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
                        help="No abrir el navegador automáticamente.")
    parser.add_argument("--verbose", action="store_true", help="Registra cada petición HTTP.")

    # --- Opciones de v13: rastreo facial real + Pico ----------------------------
    parser.add_argument("--tracking", action="store_true",
                        help="Rastrea el rostro por cámara y manda su posición real a la "
                             "Pico mientras dura la conversación. Sin sentimiento todavía: "
                             "nunca cambia de expresión (siempre NEUTRAL, con parpadeo "
                             "normal). Necesita 'opencv-python' (y 'picamera2' para la "
                             "cámara CSI real; cae a webcam USB si no está disponible).")
    parser.add_argument("--camera-index", type=int, default=1,
                        help="Índice de cámara para el respaldo por webcam USB (por "
                             "defecto: 1). Solo tiene efecto con --tracking y sin cámara "
                             "CSI disponible.")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No envíes nada a la Pico aunque haya una conectada (prueba "
                             "solo la cámara). Solo tiene efecto con --tracking.")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: falta OPENAI_API_KEY. Ponla en el fichero .env "
            '(OPENAI_API_KEY="sk-...") o expórtala en tu shell.'
        )

    CONFIG.update(api_key=api_key, model=args.model, voice=args.voice,
                  instructions=args.instructions, verbose=args.verbose)

    global PICO
    detener_rastreo = threading.Event()
    camara = None
    rastreo_activo = False

    if args.tracking:
        if args.usar_pico:
            from pico_serial import PicoLink, encontrar_puerto_pico
            puerto_pico = encontrar_puerto_pico()
            if puerto_pico:
                PICO = PicoLink(port=puerto_pico)
                PICO.start()
                print(f"✅ Pico detectada en {puerto_pico}.")
            else:
                print("⚠️  No se detectó ninguna Pico. El rastreo sigue igual, "
                      "sin mover los servos.")

        from face_tracker import ALTO, ANCHO, abrir_camara_csi, leer_frame

        leer = None
        print("🔍 Iniciando cámara CSI (picamera2)...")
        try:
            camara = abrir_camara_csi(ANCHO, ALTO)
            leer = lambda: leer_frame(camara)
            print("✅ Cámara CSI lista (OV5647).")
        except ImportError:
            print("⚠️  Falta 'picamera2'. En Raspberry Pi OS se instala con:")
            print("      sudo apt install -y python3-picamera2 --no-install-recommends")
        except Exception as e:
            print(f"⚠️  No se pudo abrir la cámara CSI: {e}")
            print("    Revisa que esté bien conectada y que 'rpicam-hello --list-cameras'")
            print("    la detecte fuera de este script.")

        if leer is None:
            try:
                import cv2
            except ImportError:
                print("⚠️  Falta 'opencv-python': sin cámara CSI ni webcam disponibles. "
                      "El rastreo no estará activo.")
                cv2 = None
            if cv2 is not None:
                print(f"🔍 Probando webcam USB (índice {args.camera_index})...")
                cap = cv2.VideoCapture(args.camera_index)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
                if not cap.isOpened():
                    print(f"⚠️  No se pudo abrir la cámara (índice {args.camera_index}). "
                          "El rastreo facial no estará activo.")
                    cap.release()
                else:
                    camara = cap
                    leer = cap.read
                    print("✅ Webcam USB lista.")

        if leer is not None:
            rastreo_activo = True
            threading.Thread(
                target=_hilo_rastreo, args=(leer, detener_rastreo), daemon=True
            ).start()
        else:
            print("⚠️  Sin cámara disponible: la conversación sigue igual, sin rastreo.")

    # 127.0.0.1 explícito, no "localhost": en la Raspberry Pi 5 real, "localhost"
    # resuelve primero a IPv6 (::1) y el navegador se queda esperando/en blanco
    # antes de probar IPv4, donde este servidor sí escucha (ver README-v11.md).
    url = f"http://127.0.0.1:{args.port}/"
    # Solo escuchamos en localhost: la clave está en este proceso y no debe salir del equipo.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"🎙️  Abre {url} y pulsa «Conectar».")
    print(f"    Modelo {args.model} · voz {args.voice}")
    print("    El navegador cancela el eco, así que puedes usar altavoces e interrumpirle.")
    if rastreo_activo:
        print("    Rastreo facial: ACTIVO, sin sentimiento (expresión siempre NEUTRAL)")
    elif args.tracking:
        print("    Rastreo facial: pedido con --tracking, pero sin cámara disponible")
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
        if camara is not None:
            try:
                camara.stop()
            except AttributeError:
                camara.release()
        if PICO is not None:
            PICO.stop()


if __name__ == "__main__":
    main()
