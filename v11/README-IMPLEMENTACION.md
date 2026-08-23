# v11 — Implementación en Raspberry Pi 5 🎙️🍓

**Conversación de voz en tiempo real con la Realtime API de OpenAI, corriendo en la Raspberry Pi 5 de Debbie.**

Este README documenta **lo que se hizo para que la spec v11 funcionara en hardware real**
(la Pi 5), incluyendo los arreglos que fueron necesarios y que la spec no contemplaba.

---

## 1. Qué es

Dos vías para hablar con GPT por voz, en tiempo real:

| Vía | Script | Cómo captura el micro | Cancelación de eco |
|---|---|---|---|
| **Terminal** (sin pantalla) | `realtime_voice.py` | `sounddevice` (PortAudio) directo al hardware | No real: usa half-duplex + `MicGate` + `BargeInDetector` |
| **Navegador** (WebRTC) | `webrtc_server.py` + **Firefox** | `getUserMedia` del navegador | Real: `echoCancellation` del navegador |

> ⚠️ Desde el 22/08/2026 la vía navegador usa **Firefox** (Chromium 149 tiene la pila de
> red rota en esta Pi — ver sección 10). La conexión es **automática** (`?auto=1`), sin clic.

---

## 2. Hardware usado

- **Raspberry Pi 5** (Raspberry Pi OS Bookworm, PipeWire)
- **Micrófono USB** — "USB PnP Sound Device" (C-Media) → ALSA `hw:3,0`
- **Parlante USB** — "UACDemoV1.0" (Jieli) → ALSA `hw:2,0`
- Ambos dispositivos son **nativos de 44.1/48 kHz**

---

## 3. Estructura del proyecto

```
/home/pi/v11/
├── realtime_voice.py      # Vía terminal (de la spec, sin cambios)
├── webrtc_server.py       # Vía navegador (de la spec, +fix query string)
├── static/index.html      # CREADO — +auto-conexión (?auto=1) + STUN + heartbeat
├── start_browser.sh       # CREADO — arranca vía navegador en 1 comando (Firefox)
├── stop_browser.sh        # CREADO — detiene firefox + servidor
├── requirements.txt       # De la spec
├── README-v11.md          # Spec original de Debbie
├── README-IMPLEMENTACION.md  # Este documento
└── .env                   # OPENAI_API_KEY (permisos 600)
```

---

## 4. Lo que hubo que arreglar para que funcionara

### 4.1. Sample rate: 24 kHz vs 48 kHz (el fallo crítico)

**Síntoma:** al ejecutar `realtime_voice.py` fallaba al instante:

```
Expression 'paInvalidSampleRate' failed in 'src/hostapi/alsa/pa_linux_alsa.c'
```

**Causa:** la Realtime API de OpenAI trabaja con PCM a **24 kHz**, y `sounddevice`
(PortAudio) abre el dispositivo ALSA directo pidiéndole 24 kHz. Pero el parlante
Jieli y el mic C-Media **solo aceptan 44.1/48 kHz**, y PortAudio no pasa por
PipeWire (que sí resamplea), así que ALSA rechaza la tasa.

**Solución:** un `~/.asoundrc` que define el dispositivo ALSA por defecto como un
`plug` (resampling automático 24k→48k):

```ini
# /home/pi/.asoundrc
pcm.!default {
    type asym
    playback.pcm {
        type plug
        slave.pcm "hw:2,0"   # parlante Jieli
    }
    capture.pcm {
        type plug
        slave.pcm "hw:3,0"   # mic C-Media
    }
}
```

Con esto, `sounddevice` usa el dispositivo `default` y ALSA convierte la tasa
automáticamente. **No se tocó ni una línea del código de la spec.**

### 4.2. `static/index.html` faltante

La spec lista `static/index.html` como parte de v11, pero **no venía en los
archivos enviados** y `webrtc_server.py` lo necesita para servir la página.

**Solución:** se creó uno funcional desde cero:
- `getUserMedia` con `echoCancellation: true, noiseSuppression: true`
- `RTCPeerConnection` para hablar con OpenAI por WebRTC
- POST del SDP al endpoint local `/session` (el servidor lo firma con la API key)
- Botón "Conectar" + indicador de estado

### 4.3. Interrupción por voz (barge-in)

En modo terminal, la spec usa **half-duplex por defecto**: el micro se cierra
mientras el asistente habla (para no captar su propio eco). Eso impide cortarle
hablando. La solución de la spec es la bandera:

```bash
python realtime_voice.py --barge-in
```

El `BargeInDetector` mide el nivel del eco del parlante mientras el micro está
cerrado, y solo cuenta como voz del usuario lo que lo supere con holgura
(factor 3x por defecto, ~300 ms sostenidos) → corta al asistente al instante.

---

## 5. Instalación

```bash
cd /home/pi/v11
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # o crear .env con OPENAI_API_KEY="tu-clave"
chmod 600 .env
```

Dependencias instaladas (verificadas en la Pi 5): `websockets`, `sounddevice`,
`numpy`, `python-dotenv`, `certifi`.

---

## 6. Uso

### 6.1. Vía terminal (sin pantalla)

```bash
cd /home/pi/v11
.venv/bin/python realtime_voice.py                    # half-duplex (no interrumpe por voz)
.venv/bin/python realtime_voice.py --barge-in         # permite cortarle hablando
```

Ejecución en background con log:

```bash
setsid nohup .venv/bin/python realtime_voice.py --barge-in \
    > /tmp/v11_voice.log 2>&1 < /dev/null &
```

Opciones útiles: `--voice marin|cedar|alloy|echo|shimmer`, `--model gpt-realtime`,
`--vad semantic_vad`, `--barge-in-factor 2.0|4.0` (sensibilidad), `--debug`.

### 6.2. Vía navegador (WebRTC, con pantalla) — RECOMENDADA

Con Firefox + auto-conexión (no hay que pulsar nada):

```bash
/home/pi/v11/start_browser.sh      # arranca servidor + Firefox kiosk + auto-conecta
/home/pi/v11/stop_browser.sh       # detiene todo
```

Verificación rápida: `grep "msg=ICE" /tmp/v11_webrtc.log` debe mostrar `connected`.

---

## 7. Verificación en la Pi 5 (lo probado)

- ✅ `realtime_voice.py` conecta a la API (`session.created` → `session.updated`)
- ✅ Conversación real por mic/parlante USB, en español, con transcripción en el log
- ✅ `--barge-in` permite interrumpir al asistente hablando por encima
- ✅ `webrtc_server.py` sirve la página (HTTP 200) y negocia SDP con OpenAI
- ✅ Vía navegador (Firefox): ICE connected, audio bidireccional, probado por Debbie (22/08)

---

## 8. Solución de problemas

| Problema | Causa | Fix |
|---|---|---|
| `paInvalidSampleRate` | 24 kHz no soportado por el hardware | Verificar `~/.asoundrc` (sección 4.1) |
| No se oye nada | Parlante equivocado / volumen | `pactl set-sink-volume <sink> 90%` |
| No corta al asistente | Barge-in desactivado o muy exigente | Usar `--barge-in`, bajar `--barge-in-factor` |
| Se corta solo | Falsos positivos del eco | Subir `--barge-in-factor` (4.0) |
| Eco al hablar | Half-duplex insuficiente | Usar la vía WebRTC (AEC real del navegador) |
| Log vacío | Buffer de Python al redirigir | Esperar unos segundos o `stdbuf -oL` |
| Navegador se queda en `about:blank` | Chromium roto / localhost IPv6 | Usar Firefox + `http://127.0.0.1:8000` (sección 10) |
| Negocia SDP pero no hay audio | ICE sin STUN | Ver sección 10.2 (fix ya aplicado) |

---

## 9. Comandos de operación

```bash
# Ver log de la vía navegador en vivo
tail -f /tmp/v11_webrtc.log

# Ver log de la vía terminal en vivo
tail -f /tmp/v11_voice.log

# Detener el asistente (terminal)
pkill -f realtime_voice.py

# Detener la vía navegador (firefox + servidor)
/home/pi/v11/stop_browser.sh

# Probar micro (nivel de señal)
parec --device=echo-cancel-source --format=s16le --rate=24000 --channels=1 \
    --file-format=raw 2>/dev/null | head -c 96000 | od -An -i | awk '{s+=$1} END {print "nivel:", s}'
```

---

## 10. Actualización 22/08/2026 — Firefox + STUN (vía navegador operativa)

### 10.1. Por qué ya no se usa Chromium

- **Chromium 149 tiene la pila de red rota en esta Pi**: no carga ninguna página web
  (local o externa; `--dump-dom` vacío, las peticiones nunca salen del navegador).
  Errores ANGLE/EGL al arrancar; el display es Xwayland. No es un problema del proyecto.
- **Solución: Firefox 151** (ya instalado), que carga la página y hace WebRTC sin problema.

### 10.2. Bug de ICE corregido (causa del "le hablo y no funciona")

- `static/index.html` creaba `RTCPeerConnection` **sin `iceServers` (STUN)** → solo
  candidatos host (IP local 192.168.x.x), inalcanzables para OpenAI → **ICE nunca
  conectaba** (negociación SDP 200, pero 0 sockets UDP y sin audio).
- Fix aplicado:
  1. `iceServers`: `stun:stun.l.google.com:19302` + `stun:global.stun.twilio.com:3478`
  2. Esperar `iceGatheringState === 'complete'` antes de POSTear el offer
  3. Logging de `iceconnectionstatechange` + heartbeat `report()` → `GET /st?msg=...`
     (visible en el log del servidor con `--verbose`; útil porque BiDi de Firefox es inestable)

### 10.3. Auto-conexión (modo kiosko, sin clic)

- `static/index.html` acepta `?auto=1` → clic automático en "Conectar" al cargar.
- `webrtc_server.py` do_GET ignora query string (fix con `urlparse`).

### 10.4. Lanzamiento operativo (1 comando)

```bash
/home/pi/v11/start_browser.sh
```

Equivale a:

```bash
cd /home/pi/v11 && setsid nohup .venv/bin/python webrtc_server.py --no-browser --verbose \
    > /tmp/v11_webrtc.log 2>&1 < /dev/null &
DISPLAY=:0 setsid nohup firefox --profile /tmp/ff-v11-profile --kiosk \
    --remote-debugging-port 9222 --remote-allow-origins=* \
    http://127.0.0.1:8000/?auto=1 > /tmp/v11_firefox.log 2>&1 < /dev/null &
```

- Perfil Firefox: `/tmp/ff-v11-profile/user.js` (permiso de micro sin preguntar, autoplay libre).
- Audio verificado: source-output en mic C-Media, sink-input en parlante Jieli.
- Verificación: `grep "msg=ICE" /tmp/v11_webrtc.log` → `ICE: connected`.

*Estado 22/08: probado por Debbie ✅ — conversación fluida, interrupción por voz ok.*

---

## 11. Actualización 23/08/2026 — arranque automático y sincronización con GitHub

### 11.1 Servicio systemd `v11-webrtc` (servidor siempre arriba)
- `systemd/v11-webrtc.service` → instalado en `/etc/systemd/system/`, `enable` + `start`.
- El servidor WebRTC queda escuchando en `127.0.0.1:8000` desde el boot, sin intervención.
- Logs: `journalctl -u v11-webrtc -f` (bajo systemd ya no escribe en `/tmp/v11_webrtc.log`).
- `stop_browser.sh` detecta el servicio y lo detiene con `systemctl stop` — un `kill` directo no sirve (`Restart=always` lo relanza al instante).

### 11.2 Autostart del kiosk y script autorreparable
- `autostart/v11-firefox-kiosk.desktop` → `~/.config/autostart/` (Firefox kiosk al iniciar el escritorio).
- `start_browser.sh` copia `firefox-profile/user.js` a `/tmp/ff-v11-profile` si no existe (sobrevive a limpiezas de `/tmp`).

### 11.3 Sincronización con GitHub (sfiro/hablar-en-tiempo-real)
- La Pi quedó idéntica a `v11/` del repo: `webrtc_server.py` (URL con `127.0.0.1`, no `localhost`),
  `start/stop_browser.sh`, `static/index.html`, `firefox-profile/user.js`, `README-v11.md`.
- ⚠️ `~/.asoundrc` puede desaparecer (ocurrió el 23/08): si `realtime_voice.py` falla con
  `paInvalidSampleRate`, recrearlo con `cp v11/asoundrc.example ~/.asoundrc`.

---

*Implementado el 17/08/2026 en la Raspberry Pi 5 de Debbie. Spec: v11 (solo voz).*
