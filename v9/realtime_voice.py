#!/usr/bin/env python3
"""
Conversación de voz en tiempo real con la Realtime API de OpenAI (modelo GA `gpt-realtime`),
con análisis de emociones opcional y, nuevo en v8, control de la expresión facial
de la Pico ("ojos mecánicos") a partir de esa misma emoción.

Captura el micrófono, lo envía por WebSocket a OpenAI, y reproduce por los altavoces
la respuesta de voz del modelo. Usa detección de turnos (server VAD): simplemente habla
y haz una pausa; el modelo te responderá. Puedes interrumpirlo hablando encima.

Con --sentiment, cada frase (tuya y del asistente) se clasifica en una de seis
emociones de Ekman + neutral (alegría, tristeza, rabia, miedo, sorpresa, asco) y se
muestra en consola. Ver sentiment_analyzer.py para los detalles del modelo.

Novedad de v8, sin cambios aquí: con --sentiment activo, si hay una Pico
conectada (autodetectada, igual que face_tracker.py en versiones anteriores),
cada emoción detectada por encima de --confidence-threshold se traduce al
vocabulario de 10 emociones de la Pico (EMOTION_TO_PICO, más abajo) y se envía
por serial. El firmware (main.py) mantiene esa expresión 5 segundos y, si no
llega una nueva, vuelve solo a NEUTRAL — la cara reacciona a la conversación,
no a un temporizador ciego. Usa --no-pico para desactivar el envío aunque haya
una Pico conectada.

Este fichero, a diferencia de v9/webrtc_server.py, sigue sin rastreo facial —
decisión explícita de alcance: v9 solo le añadió la cámara a la versión
recomendada (navegador), no a esta alternativa de terminal. Sigue mandando un
LR,UD fijo (90,90) junto con cada EMOCION.

Requisitos:  pip install -r requirements.txt
Variable de entorno:  OPENAI_API_KEY  (se lee del entorno o del fichero .env)

Uso:
    python realtime_voice.py
    python realtime_voice.py --sentiment
    python realtime_voice.py --sentiment --stats --language es
    python realtime_voice.py --sentiment --no-pico   # sentimiento sin tocar la Pico
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

# Para el resumen de --stats: no es una separación científica, solo una forma de dar
# un tono aproximado sin inventar una emoción "positiva/negativa" que el modelo no da.
POSITIVE_LABELS = {"ALEGRÍA", "SORPRESA"}
NEGATIVE_LABELS = {"TRISTEZA", "RABIA", "MIEDO", "ASCO"}

# Traduce la emoción interna de pysentimiento (result["emotion"], no la etiqueta
# en español) al vocabulario de 10 emociones que entiende la Pico. Las 5
# primeras vienen razonadas desde v3 (ver CLAUDE.md): sin correspondencia 1 a 1
# perfecta a propósito — "fear" no tiene un "MIEDO" en la Pico, se degrada a
# NERVIOSO; no se inventa precisión que no existe.
#
# Pedido explícito en v8: las 7 categorías de pysentimiento deben mapear a
# alguna de las expresiones del robot, sin dejar ninguna sin enviar. Las dos
# que antes no tenían entrada:
#   - "disgust" → SOSPECHA: de las 10 expresiones, es la que más se parece
#     facialmente al asco (párpados entrecerrados, mirada de rechazo) — no hay
#     una "ASCO" en el vocabulario de la Pico, así que se degrada a la más
#     cercana, igual criterio que fear→NERVIOSO.
#   - "others" (neutral) → NEUTRAL: corresponde 1 a 1, no hay que degradar nada.
#
# DORMIDO, DUDA y PENSATIVO se quedan sin usar aquí: no hay ninguna de las 7
# categorías de pysentimiento que les corresponda ni de lejos — pysentimiento
# no puede detectar "duda" o "sueño" en una frase, solo las 6 de Ekman +
# neutral. Para que esas tres aparezcan en una conversación real hace falta
# otro mecanismo (p.ej. que el propio modelo de voz las elija por
# function-calling, como hacía ojosMecanicos — ver model.md), no forzar una
# correspondencia con pysentimiento que no existe.
#
# Efecto colateral aceptado de enviar NEUTRAL para "others": a diferencia de
# antes (donde no se enviaba nada y la expresión activa terminaba su pulso de
# 5s sin interrupción), ahora una frase neutra puede cortar antes de tiempo el
# pulso de una expresión real que estuviera en curso. Es la consecuencia
# esperada de que las 7 categorías manden algo, no un bug.
EMOTION_TO_PICO = {
    "joy": "FELIZ",
    "sadness": "TRISTE",
    "anger": "ENOJADO",
    "fear": "NERVIOSO",
    "surprise": "SORPRENDIDO",
    "disgust": "SOSPECHA",
    "others": "NEUTRAL",
}


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


class ConversationStats:
    """Acumula las emociones detectadas por turno para un resumen al final.

    El "tono general" es una heurística simple (cuenta positivas vs. negativas), no un
    veredicto del modelo: pysentimiento no produce una etiqueta de polaridad, solo la
    emoción dominante. Se declara así en la salida para no sugerir más precisión de la
    que hay.
    """

    ROLE_NAMES = {"user": "Tú", "assistant": "Asistente"}

    def __init__(self):
        self._data = {"user": {}, "assistant": {}}

    def add(self, role: str, result: dict):
        bucket = self._data[role].setdefault(result["label"], [])
        bucket.append(result["confidence"])

    def has_data(self) -> bool:
        return any(self._data[role] for role in self._data)

    def summarize(self) -> str:
        lines = ["📊 ESTADÍSTICAS DE CONVERSACIÓN", "─" * 33]
        pos_count = neg_count = 0

        for role in ("user", "assistant"):
            emotions = self._data[role]
            if not emotions:
                continue
            lines.append(f"{self.ROLE_NAMES[role]}:")
            for label, confidences in sorted(emotions.items(), key=lambda kv: -len(kv[1])):
                avg = sum(confidences) / len(confidences)
                lines.append(f"  {label}: {len(confidences)} turno(s) (promedio: {avg:.2f})")
                if label in POSITIVE_LABELS:
                    pos_count += len(confidences)
                elif label in NEGATIVE_LABELS:
                    neg_count += len(confidences)
            lines.append("")

        if pos_count or neg_count:
            if pos_count > neg_count:
                tono = "POSITIVO 😊"
            elif neg_count > pos_count:
                tono = "NEGATIVO 😢"
            else:
                tono = "MIXTO 😐"
            lines.append(f"Tono general (heurística, no del modelo): {tono}")

        return "\n".join(lines).rstrip()


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


async def run(model: str, voice: str, instructions: str, vad_threshold: float,
              half_duplex: bool, noise_reduction: str, vad_type: str, debug: bool,
              echo_tail_ms: int, push_to_talk: bool, barge_in: bool,
              barge_in_factor: float, sentiment: bool, language: str, stats: bool,
              no_emoji: bool, confidence_threshold: float, usar_pico: bool):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: falta OPENAI_API_KEY. Ponla en el fichero .env "
            '(OPENAI_API_KEY="sk-...") o expórtala en tu shell.'
        )

    analyzer = None
    pico = None
    conv_stats = ConversationStats() if (sentiment and stats) else None
    loop = asyncio.get_running_loop()

    if sentiment:
        # Falla ya, antes de conectar, en vez de a mitad de conversación cuando llegue
        # la primera frase y el import falle dentro del executor.
        try:
            import pysentimiento  # noqa: F401
        except ImportError:
            sys.exit(
                "ERROR: --sentiment necesita 'pysentimiento'. Instala con:\n"
                "  pip install -r requirements.txt"
            )
        from sentiment_analyzer import SentimentAnalyzer
        analyzer = SentimentAnalyzer(language=language)
        # Precarga el modelo en segundo plano: si se deja para la primera frase, esa
        # frase concreta tarda varios segundos extra (descarga + carga en memoria).
        # run_in_executor ya devuelve un Future agendado en el loop: no hay que (y no
        # se puede) envolverlo en create_task, que exige una corrutina.
        loop.run_in_executor(None, analyzer._load)

        if usar_pico:
            # Nuevo en v8: la emoción detectada también controla la expresión
            # facial de la Pico, si hay una conectada. Autodetección igual que
            # face_tracker.py en versiones anteriores — sin Pico, PicoLink sigue
            # funcionando y enviar() simplemente no hace nada.
            from pico_serial import PicoLink, encontrar_puerto_mac
            puerto_pico = encontrar_puerto_mac()
            if puerto_pico:
                pico = PicoLink(port=puerto_pico)
                pico.start()
                print(f"✅ Pico detectada en {puerto_pico}: la expresión facial "
                      "seguirá la emoción detectada en la conversación.")
            else:
                print("⚠️  No se detectó ninguna Pico. La conversación sigue "
                      "igual, sin control de expresión facial.")

    url = REALTIME_URL.format(model=model)
    headers = {"Authorization": f"Bearer {api_key}"}

    playback = Playback()
    gate = MicGate(playback, echo_tail_ms) if half_duplex else None
    mic_queue: asyncio.Queue[bytes] = asyncio.Queue()
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

    # El Python de python.org en macOS no trae raíces de CA propias: usamos el bundle de certifi.
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
        if sentiment:
            print(f"    Emociones: ACTIVO ({language}) — el modelo se descarga la "
                  "primera vez, puede tardar.")
        print("    (Ctrl+C para salir)\n")

        async def analyze_and_print(role: str, text: str):
            """Clasifica la emoción de una frase sin bloquear el resto de la conversación.

            Se agenda con create_task: la inferencia (cientos de ms) corre en un hilo
            aparte, así que nunca retrasa la lectura de eventos de audio del websocket.
            """
            text = text.strip()
            if not text or analyzer is None:
                return
            try:
                result = await loop.run_in_executor(None, analyzer.analyze, text)
            except Exception as e:
                print(f"\n⚠️  Error analizando emoción: {e}", file=sys.stderr)
                return
            if result["confidence"] < confidence_threshold:
                return
            if conv_stats is not None:
                conv_stats.add(role, result)
            emoji = "" if no_emoji else result["emoji"] + " "
            # Salto de línea inicial: esto se imprime desde una tarea aparte y puede
            # llegar mientras el otro lado sigue en pleno streaming de su transcripción
            # (print de deltas sin salto de línea). Sin el \n, el resultado queda
            # mezclado en medio de esa frase. Mismo patrón que el resto de avisos
            # asíncronos del script (⏹️, ⚠️, ✂️).
            print(f"\n   {emoji}{result['label']} ({result['confidence']:.2f})")
            if pico is not None:
                # Las 7 categorías de pysentimiento mapean a algo en
                # EMOTION_TO_PICO (ver la definición), así que .get() con
                # fallback a NEUTRAL es solo una red de seguridad, no la vía
                # normal de llegar ahí.
                emocion_pico = EMOTION_TO_PICO.get(result["emotion"], "NEUTRAL")
                # 90,90: este fichero no tiene cámara (a diferencia de
                # v9/webrtc_server.py), así que LR/UD van fijos al centro —
                # solo importa el campo EMOCION.
                pico.enviar(90, 90, emocion_pico)

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

        assistant_transcript = []  # acumula deltas hasta response.output_audio_transcript.done

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
                    delta = event.get("delta", "")
                    print(delta, end="", flush=True)
                    if sentiment:
                        assistant_transcript.append(delta)

                elif etype == "response.output_audio_transcript.done":
                    print()  # salto de línea al terminar la frase del asistente
                    if sentiment:
                        texto = "".join(assistant_transcript)
                        assistant_transcript.clear()
                        asyncio.create_task(analyze_and_print("assistant", texto))

                elif etype == "conversation.item.input_audio_transcription.completed":
                    texto = event.get("transcript", "").strip()
                    print(f"\n🗣️  Tú: {texto}")
                    if sentiment:
                        asyncio.create_task(analyze_and_print("user", texto))

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
            if pico is not None:
                pico.stop()
            if conv_stats is not None and conv_stats.has_data():
                print()
                print(conv_stats.summarize())


def main():
    parser = argparse.ArgumentParser(
        description="Conversación de voz en tiempo real con OpenAI Realtime API, con "
                    "análisis de emociones opcional.")
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

    # --- Opciones de v2: análisis de emociones ------------------------------
    parser.add_argument("--sentiment", action="store_true",
                        help="Clasifica la emoción de cada frase (tuya y del asistente) "
                             "y la muestra en consola. Necesita 'pysentimiento' instalado.")
    parser.add_argument("--language", choices=("es", "en", "it", "pt"), default="es",
                        help="Idioma del modelo de emociones (por defecto: es). "
                             "pysentimiento usa un modelo distinto por idioma.")
    parser.add_argument("--stats", action="store_true",
                        help="Muestra un resumen de emociones detectadas al terminar "
                             "la conversación. Solo tiene efecto con --sentiment.")
    parser.add_argument("--no-emoji", action="store_true",
                        help="No muestra emojis junto a la emoción, solo texto.")
    parser.add_argument("--confidence-threshold", type=float, default=0.5,
                        help="Solo muestra la emoción si su confianza supera este valor, "
                             "0-1 (por defecto: 0.5). Súbelo para reducir falsos positivos.")

    # --- Opciones de v8: expresión facial de la Pico dirigida por sentimiento --
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No envíes la emoción detectada a la Pico aunque haya una "
                             "conectada. Solo tiene efecto con --sentiment.")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.model, args.voice, args.instructions,
                        args.vad_threshold, args.half_duplex,
                        args.noise_reduction, args.vad_type, args.debug,
                        args.echo_tail_ms, args.push_to_talk,
                        args.barge_in, args.barge_in_factor,
                        args.sentiment, args.language, args.stats,
                        args.no_emoji, args.confidence_threshold, args.usar_pico))
    except KeyboardInterrupt:
        print("\n👋 Adiós.")


if __name__ == "__main__":
    # Permite salir limpiamente con Ctrl+C incluso durante la conexión.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    main()
