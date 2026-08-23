#!/usr/bin/env python3
"""
Voice Chat REST API (Whisper → GPT → TTS)
Ciclo: graba 4s → transcribe → GPT responde → TTS → reproduce

No es la Realtime API (a diferencia de voice_chat.py de esta misma carpeta):
graba un turno fijo de duración, transcribe con Whisper, pide una respuesta
de texto a gpt-4o-mini, la convierte a voz con TTS, y la reproduce — cuatro
llamadas HTTP secuenciales por turno en vez de un único stream de voz. Más
lento y con más turnos "fijos" que una conversación natural. Se conserva
como referencia de un enfoque más simple, no como la vía recomendada.
"""

import os, sys, json, subprocess, tempfile, time, base64
from pathlib import Path
import requests

# API Key: se lee siempre de .env, nunca hardcodeada — mismo patrón que
# voice_chat.py en esta misma carpeta. .env no se sube al repositorio
# (cubierto por el .gitignore de la raíz del proyecto).
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
    print("No API key")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {API_KEY}"}
MIC = "plughw:2,0"
SPK = "plughw:3,0"
RATE = 24000
DURATION = 5  # segundos de grabación

def record(duration=DURATION):
    """Graba audio del micrófono y devuelve ruta del WAV."""
    path = tempfile.mktemp(suffix='.wav')
    subprocess.run([
        "arecord", "-D", MIC, "-f", "S16_LE",
        "-r", str(RATE), "-c", "1", "-t", "wav",
        "-d", str(duration), path
    ], capture_output=True)
    return path

def transcribe(audio_path):
    """Whisper API: audio → texto."""
    with open(audio_path, 'rb') as f:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers=HEADERS,
            files={"file": ("audio.wav", f, "audio/wav")},
            data={"model": "whisper-1", "language": "es"}
        )
    result = resp.json()
    return result.get("text", "").strip()

def chat(text):
    """GPT: texto → texto."""
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=HEADERS,
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Responde en español, breve y natural."},
                {"role": "user", "content": text}
            ]
        }
    )
    return resp.json()["choices"][0]["message"]["content"].strip()

def tts(text, output_path):
    """TTS: texto → audio WAV."""
    resp = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers=HEADERS,
        json={
            "model": "tts-1",
            "input": text,
            "voice": "nova",
            "response_format": "wav"
        }
    )
    with open(output_path, 'wb') as f:
        f.write(resp.content)

def play(audio_path):
    """Reproduce WAV por el parlante."""
    subprocess.run(["aplay", "-D", SPK, audio_path], capture_output=True)

# --- Ciclo principal ---
print("🎙️ Chat de voz listo! (Ctrl+C para salir)")
print("Habla después del '🎤'...")

while True:
    print("\n🎤 Grabando {}s...".format(DURATION), end="", flush=True)
    audio = record()
    print(" ✅")

    print("📝 Transcribiendo...", end="", flush=True)
    texto = transcribe(audio)
    os.unlink(audio)
    print(f" \"{texto}\"")

    if not texto:
        print("(no se escuchó nada, repite)")
        continue

    print("🧠 GPT pensando...", end="", flush=True)
    respuesta = chat(texto)
    print(f" {respuesta[:60]}...")

    print("🔊 Generando voz...", end="", flush=True)
    voz = tempfile.mktemp(suffix='.wav')
    tts(respuesta, voz)
    print(" ✅")

    print("🔊 Reproduciendo...", flush=True)
    play(voz)
    os.unlink(voz)
