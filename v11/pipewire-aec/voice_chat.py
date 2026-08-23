#!/usr/bin/env python3
"""
Voice Chat con GPT Realtime 2.1 (GA API)
─────────────────────────────────────────
Micro USB (C-Media) + altavoz USB (Jieli) con AEC de PipeWire.
Usa los nodos virtuales echo-cancel-source / echo-cancel-sink,
que expone el modulo module-echo-cancel (webrtc) cargado por aec-load.sh.

Uso:  python3 voice_chat.py [--input-device NOMBRE] [--output-device NOMBRE]
Salir: Ctrl+C
Voces: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar
"""

import os, sys, json, asyncio, base64, signal, subprocess, argparse, time
from pathlib import Path
import numpy as np
import websockets


def ts():
    """Timestamp compacto para el log: HH:MM:SS.mmm"""
    return time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"

# ─── Leer API Key ─────────────────────────────────────────────
env_path = Path(__file__).parent / '.env'
API_KEY = None
try:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('OPENAI_API_KEY='):
                API_KEY = line.split('=', 1)[1].strip()
except FileNotFoundError:
    pass

if not API_KEY:
    print("No se encontro OPENAI_API_KEY en .env")
    sys.exit(1)

# ─── Configuración ────────────────────────────────────────────
RATE = 24000
CHUNK_MS = 40
CHUNK_SIZE = int(RATE * CHUNK_MS / 1000)

# Nodos virtuales con cancelacion de eco (PipeWire).
# Se pueden sobreescribir por CLI con --input-device / --output-device.
INPUT_DEVICE = "echo-cancel-source"
OUTPUT_DEVICE = "echo-cancel-sink"
VOICE = "verse"
MODEL = "gpt-realtime-2.1"
WS_URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"

should_exit = False

# ─── Leer micrófono ───────────────────────────────────────────
async def mic_reader(device):
    proc = await asyncio.create_subprocess_exec(
        "parec", "--device=" + device,
        "--format=s16le", "--rate=" + str(RATE), "--channels=1",
        "--file-format=raw",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )
    try:
        while not should_exit:
            raw = await proc.stdout.readexactly(CHUNK_SIZE * 2)
            yield np.frombuffer(raw, dtype='<i2').reshape(-1, 1)
    except asyncio.IncompleteReadError:
        pass
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()

# ─── Escribir al parlante ─────────────────────────────────────
class SpeakerWriter:
    def __init__(self):
        self.proc = None
        self.device = None

    async def start(self, device):
        self.device = device
        self.proc = await asyncio.create_subprocess_exec(
            "paplay", "--device=" + device, "--latency-msec=50",
            "--raw", "--format=s16le", "--rate=" + str(RATE), "--channels=1",
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

    async def barge_in(self):
        """Corta el audio encolado: mata paplay y lo relanza limpio.
        Asi el parlante se calla al instante cuando el usuario habla."""
        if self.proc and self.proc.returncode is None:
            self.proc.kill()
            await self.proc.wait()
        if self.device:
            await self.start(self.device)

    async def write(self, data: np.ndarray):
        if self.proc and self.proc.stdin:
            self.proc.stdin.write(data.tobytes())
            await self.proc.stdin.drain()

    async def stop(self):
        if self.proc and self.proc.returncode is None:
            self.proc.kill()
            await self.proc.wait()

# ─── Tarea 1: enviar audio del mic ────────────────────────────
async def mic_sender(ws, speaker, input_device):
    async for chunk in mic_reader(input_device):
        if should_exit:
            break
        audio_b64 = base64.b64encode(chunk.tobytes()).decode()
        await ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }))

# ─── Tarea 2: recibir eventos y reproducir ────────────────────
async def ws_receiver(ws, speaker):
    muted = False  # True = descartar audio del asistente (interrupcion activa)
    while not should_exit:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.05)
        except asyncio.TimeoutError:
            continue
        except websockets.exceptions.ConnectionClosed:
            break

        event = json.loads(raw)
        t = event.get("type", "")

        if t == "response.output_audio.delta":
            if muted:
                # Audio que venia en vuelo cuando el usuario interrumpio: se descarta
                continue
            pcm = base64.b64decode(event["delta"])
            arr = np.frombuffer(pcm, dtype='<i2').reshape(-1, 1)
            await speaker.write(arr)

        elif t == "response.output_audio_transcript.done":
            transcript = event.get("transcript", "")
            if transcript.strip():
                print(f"\n[{ts()}] 🤖 {transcript}")

        elif t == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "")
            if transcript.strip():
                print(f"\n[{ts()}] 🎤 Tu: {transcript}")

        elif t == "input_audio_buffer.speech_started":
            print(f"\n[{ts()}] 🔴 [escuchando...]", end="", flush=True)
            # Cortar al instante cualquier audio del asistente que siga encolado
            muted = True
            await speaker.barge_in()

        elif t == "input_audio_buffer.speech_stopped":
            print(f" ✅ [{ts()}]", end="", flush=True)

        elif t == "response.created":
            if muted:
                print(f"\n[{ts()}] 🔊 Nueva respuesta (audio reanudado)", flush=True)
            muted = False

        elif t == "error":
            err = event.get("error", {})
            msg = err.get('message', 'desconocido')
            code = err.get('code', '')
            if any(w in (code + msg).lower() for w in ('rate', 'quota', 'limit')):
                print(f"\n⚠ Limite de API — revisa platform.openai.com")
            else:
                print(f"\n⚠ Error: {msg}")

        elif t in (
            "session.created", "session.updated",
            "conversation.created",
            "response.done",
            "response.output_audio.done",
            "conversation.item.created",
            "rate_limits.updated",
            "response.function_call_arguments.done",
            "conversation.item.deleted",
            "response.output_item.done",
            "response.content_part.added",
            "response.content_part.done",
        ):
            pass

# ─── Inicializar sesión ──────────────────────────────────────
async def init_session(ws):
    config = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "instructions": (
                "Eres un asistente conversacional amigable y natural. "
                "Respondes SIEMPRE en espanol, de forma directa y natural, "
                "como una conversacion entre amigos. "
                "RESPONDE CORTO: maximo 2 frases. Nada de monologos ni listas largas. "
                "Tu tono es calido y relajado."
            ),
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": RATE},
                    "noise_reduction": {"type": "near_field"},
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "silence_duration_ms": 300,
                        "create_response": True,
                        "interrupt_response": True
                    }
                },
                "output": {
                    "format": {"type": "audio/pcm", "rate": RATE},
                    "voice": VOICE
                }
            }
        }
    }
    await ws.send(json.dumps(config))

    while True:
        raw = await ws.recv()
        ev = json.loads(raw)
        t = ev.get("type", "")
        if t == "session.updated":
            print(f"✅ Sesion configurada — voz: {VOICE}")
            print("💬 Solo habla — GPT responde automaticamente")
            print("🛑 Ctrl+C para salir\n")
            return
        elif t == "session.created":
            continue
        elif t == "error":
            err = ev.get("error", {})
            print(f"❌ Error: {err.get('message', 'desconocido')}")
            sys.exit(1)

# ─── Ctrl+C ──────────────────────────────────────────────────
def handle_sigint(sig, frame):
    global should_exit
    should_exit = True
    print("\n\n👋 Hasta luego!")

# ─── Main ────────────────────────────────────────────────────
async def main():
    global should_exit
    parser = argparse.ArgumentParser(description="Voice Chat con GPT Realtime (AEC PipeWire)")
    parser.add_argument("--input-device", default=INPUT_DEVICE,
                        help="Dispositivo de entrada (fuente PipeWire, p.ej. echo-cancel-source)")
    parser.add_argument("--output-device", default=OUTPUT_DEVICE,
                        help="Dispositivo de salida (sink PipeWire, p.ej. echo-cancel-sink)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_sigint)

    headers = {"Authorization": f"Bearer {API_KEY}"}
    print(f"🔗 Conectando a {MODEL}...")
    print(f"🎙 {args.input_device}  →  🔊 {args.output_device}")
    print("═" * 45)

    speaker = SpeakerWriter()
    await speaker.start(args.output_device)

    try:
        async with websockets.connect(
            WS_URL, additional_headers=headers, open_timeout=15
        ) as ws:
            await init_session(ws)
            print("💬 Conversacion iniciada — puedes hablar")

            await asyncio.gather(
                mic_sender(ws, speaker, args.input_device),
                ws_receiver(ws, speaker)
            )

    except websockets.exceptions.InvalidStatus as e:
        code = e.response.status
        print(f"\n❌ Error HTTP {code}")
        if code == 401:   print("   API Key invalida.")
        elif code == 403: print("   Sin acceso al modelo.")
        elif code == 429: print("   Limite de tasa excedido.")
        else:             print(f"   {e}")
        sys.exit(1)
    except asyncio.TimeoutError:
        print("\n❌ Timeout de conexion")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        await speaker.stop()

if __name__ == "__main__":
    asyncio.run(main())
