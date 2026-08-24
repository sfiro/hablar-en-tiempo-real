#!/usr/bin/env python3
"""
Conversación de voz en tiempo real con la Realtime API de OpenAI (modelo GA `gpt-realtime`),
con rastreo facial real y control de la Pico — todavía sin análisis de sentimiento.

Captura el micrófono, lo envía por WebSocket a OpenAI, y reproduce por los altavoces
la respuesta de voz del modelo. Usa detección de turnos (server VAD): simplemente habla
y haz una pausa; el modelo te responderá. Puedes interrumpirlo hablando encima.

Base: copia de v11/realtime_voice.py (== v1/realtime_voice.py), sin cambios de
lógica en la parte de audio. Novedad de v13, pedida explícitamente: con
`--tracking`, este proceso también rastrea el rostro por cámara
(`face_tracker.py`, retomado de v12) en un hilo de fondo, y manda su posición
real a la Pico (`pico_serial.py`, retomado de v12) mientras dura la
conversación — la primera vez que `realtime_voice.py` (la vía de terminal)
hace esto en todo el proyecto; hasta v9/v10 solo `webrtc_server.py` rastreaba.

**Sin sentimiento todavía, a propósito** (ver README-v13.md): el rastreo
nunca manda un campo EMOCION junto con `LR,UD` — solo la posición real del
rostro. Como el firmware (`main.py`) solo cambia de expresión al recibir un
EMOCION válido, `emocion_actual` se queda siempre en NEUTRAL durante toda la
sesión: el parpadeo periódico sigue activo con normalidad (no se desactiva
salvo con DORMIDO, que aquí nunca se manda) y los párpados quedan en su
posición de reposo — la mirada real del rastreo se ve con total libertad,
sin que ninguna de las tres expresiones que fijan la mirada (DUDA/PENSATIVO/
NERVIOSO) se dispare nunca.

`sounddevice`/PortAudio habla con el dispositivo de audio por defecto del
sistema, sea macOS o Raspberry Pi OS — en la Pi 5 hace falta fijar el
micro/parlante USB como predeterminados antes de arrancar esto (ver
README-v13.md). Esta es la alternativa de terminal, sin cancelación de eco
real (usa los paliativos de v1: `MicGate`, `BargeInDetector`, half-duplex) —
`webrtc_server.py`, con el navegador, es la vía recomendada (Hito B de v13).

**Nota tras validar en hardware (ver MODIFICACIONES-LOCALES.md):** en la vía
de navegador, combinar rastreo y voz en el mismo proceso demostró competir
por CPU con el audio en tiempo real lo bastante como para colar eco —
resuelto ahí corriendo `rastreo_expresiones.py` como proceso aparte. No se
midió el mismo problema en esta vía de terminal (no depende del mismo
mecanismo de cancelación de eco), pero el mismo principio de "cada pieza con
su propio recurso" aplica igual si notas audio entrecortado con
`--tracking` activo — en ese caso, usa `rastreo_expresiones.py` en un
proceso aparte.

Requisitos:  pip install -r requirements.txt
Variable de entorno:  OPENAI_API_KEY  (se lee del entorno o del fichero .env)

Uso:
    python realtime_voice.py
    python realtime_voice.py --voice cedar --model gpt-realtime
    python realtime_voice.py --tracking              # + rastreo facial y Pico
    python realtime_voice.py --tracking --no-pico    # rastreo sin mover servos
    python realtime_voice.py --tracking --camera-index 0  # respaldo USB si no hay CSI
"""

import argparse
import asyncio
import base64
import json
import os
import signal
import ssl
import sys
import threading
import time

import certifi
import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv

# Carga OPENAI_API_KEY desde el .env que hay junto a este fichero (no pisa lo ya exportado).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# --- Parámetros de audio ----------------------------------------------------
SAMPLE_RATE = 24_000          # Hz que espera/produce la Realtime API (PCM16 mono)
CHANNELS = 1
DTYPE = "int16"
BLOCKSIZE = 2_400             # 100 ms por bloque de micrófono
ECHO_TAIL_MS = 600            # margen tras callar antes de reabrir el micro (eco de sala)
MIN_BARGE_RMS = 600           # suelo absoluto de volumen para dar por buena una voz

REALTIME_URL = "wss://api.openai.com/v1/realtime?model={model}"

# --- Parámetros de rastreo facial (--tracking) ------------------------------
# Cadencia mínima entre envíos de mirada a la Pico: mismo valor calibrado en
# v12 en hardware real (a 20 envíos/s el buffer USB de la Pico se saturaba).
CADENCIA_ENVIO_S = 0.2

PICO = None


class Playback:
    """Búfer de reproducción alimentado por los deltas de audio del modelo.

    PortAudio llama a `callback` desde su propio hilo y va consumiendo el búfer.
    Si el usuario interrumpe, `clear()` vacía lo que quedaba por reproducir.
    """

    def __init__(self):
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self.stream = sd.RawOutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCKSIZE,
            callback=self._callback,
        )

    def _callback(self, outdata, frames, time_info, status):
        needed = frames * 2  # 2 bytes por muestra (int16)
        with self._lock:
            available = min(needed, len(self._buffer))
            outdata[:available] = self._buffer[:available]
            del self._buffer[:available]
        if available < needed:
            # Silencio si no hay suficiente audio en el búfer (underrun controlado).
            outdata[available:needed] = b"\x00" * (needed - available)

    def add(self, pcm_bytes: bytes):
        with self._lock:
            self._buffer.extend(pcm_bytes)

    def clear(self):
        with self._lock:
            self._buffer.clear()

    def pending_bytes(self) -> int:
        with self._lock:
            return len(self._buffer)

    def start(self):
        self.stream.start()

    def stop(self):
        self.stream.stop()
        self.stream.close()


class MicGate:
    """Compuerta half-duplex: descarta el micro mientras suena la voz del asistente.

    Sin cancelación de eco acústico (AEC), el altavoz vuelve a entrar por el micro y el
    VAD del servidor lo toma por voz del usuario, así que el modelo se interrumpe solo.
    Cortar el micro en local es la forma fiable de evitarlo cuando no hay auriculares;
    el precio es que no se puede interrumpir al asistente mientras habla.
    """

    def __init__(self, playback: Playback, tail_ms: int = ECHO_TAIL_MS):
        self._playback = playback
        self._tail = tail_ms / 1000
        self._response_active = False
        self._quiet_since = None
        self._forced_open = False

    def response_started(self):
        self._response_active = True
        self._forced_open = False

    def response_finished(self):
        self._response_active = False

    def force_open(self):
        """Abre el micro ya, sin esperar la cola: el usuario ha cortado al asistente."""
        self._forced_open = True

    def is_muted(self) -> bool:
        if self._forced_open:
            return False
        # Sigue sonando si el modelo genera audio o si queda algo en el búfer.
        if self._response_active or self._playback.pending_bytes() > 0:
            self._quiet_since = None
            return True
        # Ya calló: esperamos el rebote de la sala antes de volver a escuchar.
        if self._quiet_since is None:
            self._quiet_since = time.monotonic()
        return (time.monotonic() - self._quiet_since) < self._tail


class BargeInDetector:
    """Detecta que el usuario habla por encima del asistente, sin AEC.

    Truco: mientras el micro está cerrado, lo que entra ES el eco del altavoz, así que
    sirve para medir su nivel. Aprendido ese nivel, se considera voz del usuario solo lo
    que lo supere con holgura durante varios bloques seguidos. No es cancelación de eco,
    pero se adapta solo al volumen del altavoz y a la acústica de la sala.
    """

    WARMUP_BLOCKS = 5   # bloques que solo escuchan, para medir el eco antes de juzgar

    def __init__(self, factor: float, sustain_blocks: int = 3):
        self._factor = factor
        self._sustain = sustain_blocks
        self._echo_rms = 0.0
        self._hits = 0
        self._seen = 0

    def feed(self, pcm: bytes) -> bool:
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(samples * samples)))
        self._seen += 1

        # Arranque: aún no sabemos cuánto eco hay, así que solo medimos.
        if self._seen <= self.WARMUP_BLOCKS:
            self._echo_rms = (0.5 * self._echo_rms + 0.5 * rms) if self._echo_rms else rms
            return False

        if rms > max(self._echo_rms * self._factor, MIN_BARGE_RMS):
            self._hits += 1
            if self._hits >= self._sustain:
                self._hits = 0
                return True
            return False

        # No parece voz: refinamos despacio la estimación del eco. Lento a propósito,
        # para que una voz sostenida no acabe adoptada como «nivel normal».
        self._hits = 0
        self._echo_rms = 0.95 * self._echo_rms + 0.05 * rms
        return False


def build_session_config(voice: str, instructions: str, vad_threshold: float,
                         half_duplex: bool, noise_reduction: str, vad_type: str,
                         push_to_talk: bool) -> dict:
    """Configuración de sesión con el esquema GA (audio anidado)."""
    if push_to_talk:
        # Sin detección de turnos: el turno lo cierra el usuario con Enter. Es la única
        # forma de garantizar que el eco jamás abra un turno.
        turn_detection = None
    elif vad_type == "semantic_vad":
        # Decide el fin de turno con un modelo, no por energía: mucho menos sensible
        # al eco y al ruido. "low" = espera más antes de dar por terminado tu turno.
        turn_detection = {
            "type": "semantic_vad",
            "eagerness": "low",
            "interrupt_response": not half_duplex,
        }
    else:
        turn_detection = {
            "type": "server_vad",
            "threshold": vad_threshold,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 500,
            # En half-duplex el micro ya está cerrado mientras habla el modelo:
            # esto es la red de seguridad por si se cuela algo de eco.
            "interrupt_response": not half_duplex,
        }

    return {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "output_modalities": ["audio"],
            "instructions": instructions,
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                    "turn_detection": turn_detection,
                    # Filtra el audio ANTES del VAD y del modelo. Viene desactivado por
                    # defecto en la API; `far_field` es el modo para micro de portátil
                    # o manos libres, que es donde aparece el eco del altavoz.
                    "noise_reduction": (
                        None if noise_reduction == "off" else {"type": noise_reduction}
                    ),
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                    "voice": voice,
                },
            },
        },
    }


def _hilo_rastreo(leer, detener: threading.Event):
    """Rastrea el rostro por cámara y manda su posición real a la Pico, en
    paralelo a la conversación de voz que corre en el hilo principal (dentro
    de `asyncio.run`). Nunca manda un campo EMOCION — retomado de v12, sin
    cambios de lógica.

    Recibe un *callable* `leer` (sin argumentos) que devuelve `(ret, frame)`,
    para servir igual a la cámara CSI (`lambda: leer_frame(picam2)`) que a una
    webcam USB de respaldo (`cap.read`). La cámara se abre en `main()` (hilo
    principal) y se libera ahí también, no en este hilo — mismo patrón que
    v9/v12 documentaron (imprescindible en macOS/AVFoundation; en Linux/Pi 5
    no está confirmado que haga falta, se mantiene por consistencia).
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


def _iniciar_tracking(camera_index: int, usar_pico: bool):
    """Conecta la Pico (si corresponde) y abre la cámara (CSI primero, con
    respaldo a webcam USB), y lanza `_hilo_rastreo` en un hilo daemon.
    Devuelve (camara, detener_rastreo) para que el llamador los libere/pare
    al terminar — `camara` es None si no se pudo abrir ninguna."""
    global PICO
    if usar_pico:
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

    camara = None
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
            return None, None
        print(f"🔍 Probando webcam USB (índice {camera_index})...")
        cap = cv2.VideoCapture(camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
        if not cap.isOpened():
            print(f"⚠️  No se pudo abrir la cámara (índice {camera_index}). "
                  "El rastreo facial no estará activo.")
            cap.release()
        else:
            camara = cap
            leer = cap.read
            print("✅ Webcam USB lista.")

    if leer is None:
        print("⚠️  Sin cámara disponible: la conversación sigue igual, sin rastreo.")
        return None, None

    detener_rastreo = threading.Event()
    threading.Thread(target=_hilo_rastreo, args=(leer, detener_rastreo), daemon=True).start()
    return camara, detener_rastreo


async def run(model: str, voice: str, instructions: str, vad_threshold: float,
              half_duplex: bool, noise_reduction: str, vad_type: str, debug: bool,
              echo_tail_ms: int, push_to_talk: bool, barge_in: bool,
              barge_in_factor: float):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: falta OPENAI_API_KEY. Ponla en el fichero .env "
            '(OPENAI_API_KEY="sk-...") o expórtala en tu shell.'
        )

    url = REALTIME_URL.format(model=model)
    headers = {"Authorization": f"Bearer {api_key}"}

    playback = Playback()
    gate = MicGate(playback, echo_tail_ms) if half_duplex else None
    mic_queue: asyncio.Queue[bytes] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    talking = threading.Event()          # solo en push-to-talk
    response_active = threading.Event()  # hay una respuesta generándose ahora mismo
    turn_bytes = [0]                     # audio capturado en el turno actual
    interrupt_cb = [None]                # se rellena al conectar
    detector = (BargeInDetector(barge_in_factor)
                if barge_in and half_duplex and not push_to_talk else None)

    def mic_callback(indata, frames, time_info, status):
        # Decidimos AQUÍ, en el instante de la captura, no al enviar: si se decidiera al
        # enviar, los bloques grabados mientras hablaba el asistente seguirían en la cola
        # y saldrían igual —con el eco dentro— en cuanto se abriera la compuerta.
        if push_to_talk:
            if not talking.is_set():
                return
        elif gate is not None and gate.is_muted():
            # Micro cerrado por eco, pero seguimos escuchando: si el usuario habla por
            # encima del asistente con suficiente holgura, lo cortamos.
            if detector is not None and detector.feed(bytes(indata)) and interrupt_cb[0]:
                loop.call_soon_threadsafe(interrupt_cb[0])
            return
        turn_bytes[0] += len(indata)
        # PortAudio llama desde otro hilo: pasamos los bytes a la cola de asyncio.
        loop.call_soon_threadsafe(mic_queue.put_nowait, bytes(indata))

    mic_stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=BLOCKSIZE,
        callback=mic_callback,
    )

    # certifi trae su propio bundle de raíces CA: evita depender de que el sistema
    # (macOS o, aquí, Raspberry Pi OS) tenga los certificados TLS bien configurados.
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    print(f"Conectando a {model} …")
    async with websockets.connect(
        url, additional_headers=headers, max_size=None, ssl=ssl_context
    ) as ws:
        await ws.send(json.dumps(build_session_config(
            voice, instructions, vad_threshold, half_duplex, noise_reduction, vad_type,
            push_to_talk,
        )))

        playback.start()
        mic_stream.start()
        if push_to_talk:
            print("🎙️  Modo pulsar-para-hablar. El micro está CERRADO salvo cuando grabas,")
            print("    así que es imposible que se interrumpa con su propia voz.")
            print("    Pulsa Enter para empezar a hablar y Enter otra vez para enviar.")
        else:
            print("🎙️  Listo. Habla con naturalidad; haz una pausa y el modelo responderá.")
            print(f"    VAD: {vad_type} · reducción de ruido: {noise_reduction} · "
                  f"half-duplex: {'sí' if half_duplex else 'no'}"
                  + (f" (cola {echo_tail_ms} ms)" if half_duplex else ""))
            if half_duplex:
                print("    El micro se cierra mientras el asistente habla."
                      + (" Córtale hablando por encima." if detector else ""))
                print("    Pulsa Enter en cualquier momento para cortarle."
                      + ("" if detector else " (o prueba --barge-in)"))
        print("    (Ctrl+C para salir)\n")

        async def interrupt():
            """Corta al asistente: calla el altavoz y aborta la generación en curso."""
            if not response_active.is_set() and playback.pending_bytes() == 0:
                return
            playback.clear()
            if gate is not None:
                gate.force_open()
            if response_active.is_set():
                await ws.send(json.dumps({"type": "response.cancel"}))
            print("\n⏹️  Interrumpido.")

        def request_interrupt():
            asyncio.create_task(interrupt())

        interrupt_cb[0] = request_interrupt

        async def keyboard_loop():
            """Enter interrumpe al asistente. Siempre funciona: no depende del audio."""
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if line == "":
                    return  # stdin cerrado: sin teclado, nada que hacer
                await interrupt()

        # La API rechaza un commit con menos de 100 ms de audio.
        min_turn_bytes = SAMPLE_RATE * 2 // 10

        async def push_to_talk_loop():
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if line == "":  # stdin cerrado: sin teclado no hay push-to-talk
                    print("\n⚠️  stdin cerrado: push-to-talk necesita un terminal "
                          "interactivo.", file=sys.stderr)
                    return

                if not talking.is_set():
                    # Descartamos lo que hubiera quedado del turno anterior antes de abrir.
                    while not mic_queue.empty():
                        mic_queue.get_nowait()
                    turn_bytes[0] = 0
                    talking.set()
                    print("🔴 Grabando… (Enter para enviar)")
                    continue

                talking.clear()
                if turn_bytes[0] < min_turn_bytes:
                    print("… demasiado corto, no se envía. Enter para hablar de nuevo.")
                    continue
                # Esperamos a que el sender vacíe la cola: si no, el commit llegaría
                # antes que el audio y el servidor lo rechazaría por búfer vacío.
                while not mic_queue.empty():
                    await asyncio.sleep(0.01)
                await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                if response_active.is_set():
                    print("… esperando a que termine la respuesta anterior.")
                    continue
                await ws.send(json.dumps({"type": "response.create"}))
                print("⏳ Enviado.")

        async def sender():
            while True:
                chunk = await mic_queue.get()
                event = {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(chunk).decode("ascii"),
                }
                await ws.send(json.dumps(event))

        async def receiver():
            async for message in ws:
                event = json.loads(message)
                etype = event.get("type", "")

                if debug and not etype.endswith(".delta"):
                    muted = gate.is_muted() if gate is not None else False
                    print(f"\n[debug] {etype}  (micro {'cerrado' if muted else 'abierto'})",
                          file=sys.stderr)

                if etype == "response.created":
                    response_active.set()
                    if gate is not None:
                        gate.response_started()
                    # Tiramos lo que el micro tuviera pendiente y vaciamos también el
                    # búfer de entrada del servidor: cualquier resto de ahí es eco.
                    while not mic_queue.empty():
                        mic_queue.get_nowait()
                    if half_duplex:
                        await ws.send(json.dumps({"type": "input_audio_buffer.clear"}))

                elif etype == "response.output_audio.delta":
                    playback.add(base64.b64decode(event["delta"]))

                elif etype == "response.done":
                    response_active.clear()
                    # Generación terminada; la compuerta sigue cerrada hasta vaciar el búfer.
                    if gate is not None:
                        gate.response_finished()
                    # Si la frase se cortó, aquí se ve el motivo real.
                    status = event.get("response", {}).get("status")
                    if status and status != "completed":
                        details = event.get("response", {}).get("status_details", {})
                        print(f"\n✂️  Respuesta {status}: {json.dumps(details)}", file=sys.stderr)

                elif etype == "response.output_audio_transcript.delta":
                    print(event.get("delta", ""), end="", flush=True)

                elif etype == "response.output_audio_transcript.done":
                    print()  # salto de línea al terminar la frase del asistente

                elif etype == "conversation.item.input_audio_transcription.completed":
                    print(f"\n🗣️  Tú: {event.get('transcript', '').strip()}")

                elif etype == "input_audio_buffer.speech_started":
                    # Con la compuerta cerrada esto NO debería llegar mientras suena el
                    # asistente: si llega, es eco que se ha colado y va a abrir un turno.
                    if gate is not None and gate.is_muted():
                        print("\n⚠️  Eco detectado: el servidor ha oído voz con el micro "
                              "cerrado. Sube --vad-threshold o usa --push-to-talk.",
                              file=sys.stderr)
                    # El usuario empezó a hablar: cortamos la reproducción (barge-in).
                    if not half_duplex:
                        playback.clear()

                elif etype == "error":
                    print(f"\n⚠️  Error de la API: {event.get('error')}", file=sys.stderr)

        tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
        if push_to_talk:
            tasks.append(asyncio.create_task(push_to_talk_loop()))
        else:
            tasks.append(asyncio.create_task(keyboard_loop()))
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            mic_stream.stop()
            mic_stream.close()
            playback.stop()


def main():
    parser = argparse.ArgumentParser(description="Conversación de voz en tiempo real con OpenAI Realtime API.")
    parser.add_argument("--model", default="gpt-realtime", help="Modelo de voz (por defecto: gpt-realtime).")
    parser.add_argument("--voice", default="marin",
                        help="Voz: marin, cedar, alloy, echo, shimmer… (por defecto: marin).")
    parser.add_argument("--instructions", default=(
        "Eres un asistente de voz amable y conversacional. Responde de forma breve y natural, "
        "en el mismo idioma que use la persona."
    ), help="Instrucciones de sistema para el asistente.")
    parser.add_argument("--half-duplex", action=argparse.BooleanOptionalAction, default=True,
                        help="Cierra el micro mientras habla el asistente para que no se "
                             "interrumpa con su propia voz. Úsalo sin auriculares. "
                             "Con --no-half-duplex recuperas la interrupción por voz "
                             "(barge-in), pero necesitas auriculares.")
    parser.add_argument("--vad-threshold", type=float, default=0.75,
                        help="Sensibilidad del detector de voz, 0-1 (por defecto: 0.75). "
                             "Súbelo si el ruido o el eco disparan turnos falsos.")
    parser.add_argument("--noise-reduction", choices=("far_field", "near_field", "off"),
                        default="far_field",
                        help="Reducción de ruido de entrada, aplicada antes del VAD. "
                             "far_field para altavoces/micro de portátil (por defecto), "
                             "near_field para auriculares con micro.")
    parser.add_argument("--vad", dest="vad_type", choices=("server_vad", "semantic_vad"),
                        default="server_vad",
                        help="Detector de fin de turno. semantic_vad usa un modelo en vez "
                             "de energía: aguanta mucho mejor el ruido y el eco.")
    parser.add_argument("--push-to-talk", action="store_true",
                        help="Desactiva la detección de turnos: pulsa Enter para hablar y "
                             "Enter para enviar. Elimina la autointerrupción por completo.")
    parser.add_argument("--barge-in", action="store_true",
                        help="Permite cortar al asistente hablando por encima. Mide el "
                             "nivel del propio eco y solo cuenta la voz que lo supera "
                             "con holgura. Sin auriculares puede dar falsos positivos.")
    parser.add_argument("--barge-in-factor", type=float, default=3.0,
                        help="Cuánto debe superar tu voz al eco para cortarle "
                             "(por defecto: 3.0). Súbelo si te corta solo.")
    parser.add_argument("--echo-tail-ms", type=int, default=ECHO_TAIL_MS,
                        help=f"Margen tras callar antes de reabrir el micro, en ms "
                             f"(por defecto: {ECHO_TAIL_MS}). Súbelo si la sala tiene eco.")
    parser.add_argument("--debug", action="store_true",
                        help="Imprime los eventos de la API para diagnosticar cortes.")

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

    camara = None
    detener_rastreo = None
    if args.tracking:
        camara, detener_rastreo = _iniciar_tracking(args.camera_index, args.usar_pico)

    try:
        asyncio.run(run(args.model, args.voice, args.instructions,
                        args.vad_threshold, args.half_duplex,
                        args.noise_reduction, args.vad_type, args.debug,
                        args.echo_tail_ms, args.push_to_talk,
                        args.barge_in, args.barge_in_factor))
    except KeyboardInterrupt:
        print("\n👋 Adiós.")
    finally:
        if detener_rastreo is not None:
            detener_rastreo.set()
        if camara is not None:
            try:
                camara.stop()
            except AttributeError:
                camara.release()
        if PICO is not None:
            PICO.stop()


if __name__ == "__main__":
    # Permite salir limpiamente con Ctrl+C incluso durante la conexión.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    main()
