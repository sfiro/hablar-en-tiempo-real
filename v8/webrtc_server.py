#!/usr/bin/env python3
"""
Servidor local para hablar con la Realtime API de OpenAI **por WebRTC**, igual que hace
el modo de voz de ChatGPT — con análisis de sentimiento y control de la Pico, nuevo en v8.

La diferencia con `realtime_voice.py` está en quién captura el micro. Aquí lo hace el
navegador con `echoCancellation: true`, así que aplica cancelación de eco acústico real:
conoce la señal que sale por el altavoz y la resta de la que entra por el micro. Por eso
el modelo no se oye a sí mismo y puedes interrumpirlo hablando, con altavoces y sin trucos
— sin los paliativos (medio-dúplex, Enter para interrumpir) que necesita la versión de
terminal. Pedido explícito: la conversación de voz vive en el navegador, sin lag; a este
proceso de Python solo debe llegarle el texto ya transcrito, para el análisis de
sentimiento y el envío a la Pico.

Este proceso hace tres cosas:
  1. Sirve la página `static/index.html`.
  2. Reenvía la oferta SDP del navegador a OpenAI firmándola con tu clave, que nunca
     sale de tu equipo ni llega al navegador.
  3. (Nuevo en v8, con --sentiment) Recibe por `POST /api/analyze-sentiment` el texto de
     cada frase completa (el navegador lo transcribe vía el canal de datos WebRTC, que
     este proceso no ve — solo negocia la conexión), lo clasifica con
     `sentiment_analyzer.py` (igual que v2/v8/realtime_voice.py) y, si hay una Pico
     conectada, envía la expresión correspondiente por serial con `pico_serial.py`.

Uso:
    python webrtc_server.py
    python webrtc_server.py --sentiment
    python webrtc_server.py --sentiment --no-pico   # sentimiento sin tocar la Pico
    python webrtc_server.py --voice cedar --port 8080
"""

import argparse
import json
import os
import ssl
import sys
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

# Analizador de sentimiento y enlace con la Pico — None si --sentiment no está
# activo, o si --sentiment está activo pero no hay Pico conectada (--no-pico o
# no se detectó ninguna). Rellenos por main(), leídos por el handler.
ANALYZER = None
PICO = None

# Mismo mapeo que v8/realtime_voice.py — ver ese fichero para el razonamiento
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
        corresponde, la envía a la Pico. Nuevo en v8 — no existía en v1.

        `ThreadingHTTPServer` atiende cada petición en su propio hilo: que
        `analyzer.analyze()` tarde unos cientos de ms no bloquea la negociación SDP
        de otra conexión ni otra llamada a este mismo endpoint.
        """
        if ANALYZER is None:
            self._send(503, b'{"error":"sentiment no activo (falta --sentiment)"}',
                       "application/json")
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            role = payload.get("role", "")
            text = (payload.get("text") or "").strip()
        except (ValueError, AttributeError):
            self._send(400, b'{"error":"JSON invalido"}', "application/json")
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
                PICO.enviar(90, 90, emocion_pico)

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
                        help="No abrir el navegador automáticamente.")
    parser.add_argument("--verbose", action="store_true", help="Registra cada petición HTTP.")

    # --- Opciones de v8: análisis de sentimiento + control de la Pico ----------
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
                        help="No envíes la emoción detectada a la Pico aunque haya una "
                             "conectada. Solo tiene efecto con --sentiment.")
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

    global ANALYZER, PICO
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
        import threading
        threading.Thread(target=ANALYZER._load, daemon=True).start()

        if args.usar_pico:
            from pico_serial import PicoLink, encontrar_puerto_mac
            puerto_pico = encontrar_puerto_mac()
            if puerto_pico:
                PICO = PicoLink(port=puerto_pico)
                PICO.start()
                print(f"✅ Pico detectada en {puerto_pico}: la expresión facial "
                      "seguirá la emoción detectada en la conversación.")
            else:
                print("⚠️  No se detectó ninguna Pico. La conversación sigue "
                      "igual, sin control de expresión facial.")

    url = f"http://localhost:{args.port}/"
    # Solo escuchamos en localhost: la clave está en este proceso y no debe salir del equipo.
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"🎙️  Abre {url} y pulsa «Conectar».")
    print(f"    Modelo {args.model} · voz {args.voice}")
    print("    El navegador cancela el eco, así que puedes usar altavoces e interrumpirle.")
    if args.sentiment:
        print(f"    Emociones: ACTIVO ({args.language}) — el modelo se descarga la "
              "primera vez, puede tardar.")
    print("    (Ctrl+C para parar)\n")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Adiós.")
        server.shutdown()
    finally:
        if PICO is not None:
            PICO.stop()


if __name__ == "__main__":
    main()
