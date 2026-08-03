# Instalación y uso — Versión 1.0

Guía rápida para instalar y ejecutar la Versión 1 en macOS.

## Requisitos previos

- macOS 10.13+
- Python 3.9+ instalado (recomendado: python.org)
- Una clave de OpenAI con acceso a Realtime API
- Micrófono y altavoces (o auriculares)

## Instalación

### 1. Crear entorno virtual

```bash
cd v1
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

Si falla `sounddevice`, instala PortAudio primero:
```bash
brew install portaudio
pip install sounddevice
```

### 3. Configurar clave de API

```bash
cp .env.example .env
# Edita .env y pon tu clave: OPENAI_API_KEY="sk-..."
```

O exporta en el terminal:
```bash
export OPENAI_API_KEY="sk-..."
```

## Uso

### Versión WebRTC (recomendada)

Navegador, con cancelación de eco real:

```bash
python webrtc_server.py
```

- Se abre `http://localhost:8000/` automáticamente
- Pulsa **Conectar**
- Acepta el permiso de micrófono
- Habla

Opciones:
```bash
python webrtc_server.py --voice cedar           # Otra voz
python webrtc_server.py --port 8080             # Otro puerto
python webrtc_server.py --no-browser            # No abre pestaña
```

### Versión de terminal

Por WebSocket, sin navegador:

```bash
python realtime_voice.py
```

- Habla cuando estés listo
- Haz pausa y el modelo responde
- Ctrl+C para salir
- Enter para cortar

Opciones:
```bash
python realtime_voice.py --voice cedar
python realtime_voice.py --no-half-duplex --barge-in    # Con auriculares
```

## Troubleshooting

**`ERROR: falta OPENAI_API_KEY`**
- Copia `.env.example` a `.env` y pon tu clave real

**`SSL: CERTIFICATE_VERIFY_FAILED`**
- Usa el Python del venv: `.venv/bin/python`, no `/usr/bin/python3`

**`invalid_api_key`**
- Tu clave no es válida o no tiene acceso a Realtime API
- Revisa en https://platform.openai.com/api-keys

**El modelo se interrumpe solo** (versión terminal)
- Usa auriculares, o prueba `--no-half-duplex --barge-in`

**No hay audio**
- Revisa que Terminal tiene permiso de micrófono en Ajustes del Sistema

## Documentación completa

- [README-v1.md](README-v1.md) — Guía detallada
- [CLAUDE-v1.md](CLAUDE-v1.md) — Detalles técnicos
- ../docs/RASPBERRY-PI.md — Para Raspberry Pi 5

---

**¿Necesitas ayuda?** Ver [README-v1.md](README-v1.md), sección "Problemas frecuentes".
