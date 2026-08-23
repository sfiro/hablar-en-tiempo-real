# Versión 11.0 — Solo conversación de voz, en la Raspberry Pi 5 🎙️🍓

**Objetivo:** validar la pieza de voz sola —sin sentimiento, sin rastreo
facial, sin Pico— corriendo en una Raspberry Pi 5, antes de sumar el resto
(eso es v10, que sí tiene las cuatro piezas juntas pero cuya cámara aún no
se ha podido probar). Alcance deliberadamente mínimo: es v1, en la Pi 5 en
vez del Mac.

**Estado: validada con una conversación real en la Raspberry Pi 5 del
usuario, por las dos vías.** `realtime_voice.py --barge-in` (terminal) y
`webrtc_server.py` + Firefox en modo kiosko (navegador) confirmaron
conversación fluida e interrupción por voz funcionando. Por el camino
aparecieron tres hallazgos reales que no estaban anticipados ni en el
código ni en la documentación previa de esta versión — ver "Validado en
hardware real" más abajo — y ahora hay un sistema de arranque automático
(`systemd` + autostart de escritorio) para que la Pi 5 quede lista sola al
encenderse, sin intervención manual. Hay además una **tercera vía**,
también validada en hardware real, con cancelación de eco de verdad a
nivel de sistema (no los paliativos de `BargeInDetector`) — ver
[`pipewire-aec/`](pipewire-aec/) más abajo.

## Por qué existe esta versión, además de v10

v10 junta voz + sentimiento + rastreo facial + Pico, pero su validación en
hardware real está bloqueada: la cámara CSI de la Pi 5 todavía no está
disponible. En vez de esperar a tener todas las piezas para probar cualquier
cosa, v11 aísla la parte que sí se puede validar ya —la conversación de
voz— para confirmarla por separado. Si algo falla en v10 más adelante, esto
también sirve para saber si el problema está en la voz (ya validada aquí) o
en alguna de las piezas nuevas de v10 (cámara, sentimiento, Pico).

**No es un reemplazo de v10** ni un paso obligatorio previo — es una versión
más pequeña y paralela, pensada para probarse primero por disponibilidad de
hardware, no porque v10 dependa de ella.

## Alcance: qué NO tiene esta versión, a propósito

- Sin análisis de sentimiento (`pysentimiento`/`torch`)
- Sin rastreo facial (`opencv-python`/`picamera2`)
- Sin control de la Pico (`pyserial`)

Exactamente el alcance de v1. `realtime_voice.py` es copia de v1 sin ningún
cambio de lógica. `webrtc_server.py` y `static/index.html` sí necesitaron un
cambio real cada uno, encontrados al validar en hardware — ver la siguiente
sección — pero ninguno tiene que ver con sentimiento, rastreo o la Pico.

## Validado en hardware real

Tres hallazgos reales, ninguno anticipado antes de probar en la Pi 5 física,
en el orden en que aparecieron:

### 1. Sample rate: `realtime_voice.py` (vía terminal)

`realtime_voice.py` fallaba al arrancar con

```
Expression 'paInvalidSampleRate' failed in 'src/hostapi/alsa/pa_linux_alsa.c'
```

**Causa:** la Realtime API trabaja a **24 kHz** PCM, y `sounddevice`
(PortAudio) le pide esa tasa directamente al dispositivo ALSA. El micro y
el parlante USB de esta Pi 5 solo aceptan de forma nativa 44.1/48 kHz, y
PortAudio con ALSA **no resamplea** — fijar el micro/parlante como
dispositivo por defecto de PipeWire (`wpctl set-default`) **no basta** para
esta vía: PortAudio abre ALSA directo, sin pasar por el resampling de
PipeWire.

**Solución real, confirmada:** un `~/.asoundrc` que envuelve cada
dispositivo en un `type plug` de ALSA, que sí resamplea automáticamente
24kHz↔48kHz — ver [`asoundrc.example`](asoundrc.example), y el paso 1 de
"Instalación" más abajo. **No hizo falta tocar ninguna línea de
`realtime_voice.py`**: el fix es enteramente de configuración del sistema.

**Interrupción por voz — aclaración sobre un flag que ya existía pero no se
había resaltado lo suficiente:** por defecto, `realtime_voice.py` corre en
half-duplex sin `BargeInDetector` — el micro se cierra mientras habla el
asistente, y solo se puede cortar pulsando Enter, no hablando por encima.
Para interrupción por voz de verdad hace falta `--barge-in` explícito (ver
"Cómo probarlo" más abajo).

### 2. Chromium no funciona en esta Pi (vía navegador)

**Chromium 149 tiene la pila de red rota en esta Pi**: no carga ninguna
página, ni local ni externa (`about:blank` permanente; `--dump-dom` vacío;
las peticiones nunca salen del navegador). Hay errores ANGLE/EGL al
arrancar — el display es Xwayland. **No se investigó la causa raíz más allá
de estos síntomas**, así que esto se documenta como confirmado en esta Pi
en concreto, no como un defecto general de Chromium en Raspberry Pi 5 —
podría ser algo de esta imagen de SO, del paquete instalado, o del propio
Xwayland en esta placa.

**Decisión de despliegue:** usar **Firefox** (ya instalado en esta Pi, la
151), que carga la página y hace WebRTC sin problema. Todo lo que sigue en
esta versión asume Firefox, no Chromium, para la vía navegador.

### 3. WebRTC necesitaba STUN (vía navegador)

`static/index.html` (heredado de v1 sin cambios hasta este punto) creaba
`RTCPeerConnection` **sin `iceServers`** → solo candidatos "host" (IP local
192.168.x.x), inalcanzables para OpenAI a través de la red de esta Pi → la
negociación SDP daba 200, pero **ICE nunca llegaba a `connected`** y no
había audio. Por qué esto nunca hizo falta en v1-v9 sobre Mac no está
confirmado — puede depender del NAT/router concreto de cada red, no de la
plataforma — así que se trata como una mejora general de robustez, no como
"siempre estuvo roto sin que nadie se diera cuenta".

**Fix aplicado en `static/index.html`:**
1. `iceServers`: `stun:stun.l.google.com:19302` + `stun:global.stun.twilio.com:3478`
2. Esperar a que `iceGatheringState === 'complete'` antes de mandar el offer
3. Logging de `iceconnectionstatechange`, más un heartbeat `report()` que
   manda el estado por `GET /st?msg=...` — no hay un endpoint real que lo
   atienda (`webrtc_server.py` responde 404), pero con `--verbose` el 404
   igual queda en el log de acceso, que es lo único que hace falta para
   poder comprobar el estado de ICE desde fuera del navegador (ver
   `start_browser.sh`)

**Segundo bug, más pequeño, encontrado al añadir la autoconexión para modo
kiosko:** `webrtc_server.py`'s `do_GET` comparaba `self.path` completo
contra `"/"`/`"/index.html"`. En cuanto la URL lleva una query string
(`/?auto=1`, necesaria para conectar sola sin clic en modo kiosko), esa
comparación falla y el servidor responde 404 en vez de servir la página.
Arreglado parseando la URL con `urllib.parse.urlparse` y quedándose solo
con `.path` antes de comparar.

**Confirmado con hardware real, las dos vías:** conversación fluida e
interrupción por voz funcionando, tanto por `realtime_voice.py --barge-in`
(terminal) como por Firefox en modo kiosko con autoconexión (navegador).

## Instalación en la Raspberry Pi 5

```bash
# 1. Resampling ALSA — imprescindible para realtime_voice.py, confirmado
#    en hardware real (ver "Validado en hardware real" arriba).
aplay -l    # identifica la tarjeta,dispositivo de tu parlante USB
arecord -l  # identifica la tarjeta,dispositivo de tu micrófono USB
cp asoundrc.example ~/.asoundrc
#    Edita ~/.asoundrc y ajusta los "hw:X,Y" a los tuyos.

# 2. Micrófono y parlante USB como dispositivos por defecto de PipeWire —
#    relevante para el navegador (getUserMedia); no resuelve por sí solo
#    el problema de sample rate de PortAudio del paso 1.
wpctl status
wpctl set-default <ID_DEL_PARLANTE_USB>
wpctl set-default <ID_DEL_MICROFONO_USB>

# 3. Firefox, no Chromium — confirmado que Chromium 149 no carga páginas
#    en esta Pi (ver "Validado en hardware real"). Si no lo tienes:
sudo apt install -y firefox-esr   # o el paquete de Firefox que uses

# 4. El venv, sin nada especial (a diferencia de v10, no hace falta
#    --system-site-packages: no hay ningún paquete que solo exista
#    instalado por apt).
cd v11
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y pon tu OPENAI_API_KEY real
chmod 600 .env          # la clave no debe ser legible por otros usuarios
chmod +x start_browser.sh stop_browser.sh
```

### Vía terminal, sin pantalla (`realtime_voice.py`)

```bash
python realtime_voice.py --barge-in
```

`--barge-in` es necesario para poder interrumpir al asistente hablando por
encima — sin él, solo se puede cortar pulsando Enter. Otras opciones útiles:
`--voice marin|cedar|alloy`, `--barge-in-factor 2.0|4.0` (sensibilidad de la
interrupción — súbelo si se corta solo, bájalo si no corta), `--debug`.

Para correrlo en segundo plano con log:

```bash
setsid nohup .venv/bin/python realtime_voice.py --barge-in \
    > /tmp/v11_voice.log 2>&1 < /dev/null &
tail -f /tmp/v11_voice.log
```

### Vía navegador, con pantalla (`webrtc_server.py` + Firefox) — recomendada

Un solo comando, valida solo, y confirma cuándo quedó conectado:

```bash
./start_browser.sh
```

Internamente: arranca `webrtc_server.py --no-browser --verbose` si no está
ya corriendo, copia el perfil de Firefox si hace falta, lanza Firefox en
`--kiosk` con autoconexión (`?auto=1`, no hace falta pulsar nada), y espera
hasta 40s a ver `ICE: connected` en el log antes de confirmar. Para parar
todo:

```bash
./stop_browser.sh
```

Ver "Sistema que arranca solo" más abajo para dejar esto corriendo sin
intervención manual desde que enciendes la Pi.

## Cómo probarlo

**Vía terminal:**
```bash
cd v11 && source .venv/bin/activate
python realtime_voice.py --barge-in
```
Habla con naturalidad tras el mensaje de arranque; deberías poder
interrumpir al asistente hablando por encima.

**Vía navegador:**
```bash
cd v11 && ./start_browser.sh
```
Sin pulsar nada: se conecta sola en unos segundos. Verifica con
`grep "msg=ICE" /tmp/v11_webrtc.log`, que debe mostrar `connected`.

## Sistema que arranca solo (autostart)

Pensado para que la Pi 5 quede lista para conversar en cuanto enciende,
sin que nadie tenga que teclear nada — la vía navegador es la elegida para
esto, por tener cancelación de eco real. Dos piezas, cada una gestionada
por su mecanismo estándar de Linux:

**1. El servidor Python, como servicio `systemd`** (no depende de que haya
sesión gráfica, arranca en cuanto hay red):

```bash
sudo cp systemd/v11-webrtc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now v11-webrtc.service
```

Se reinicia solo si cae (`Restart=always`). Log en vivo:
`journalctl -u v11-webrtc -f`. Para pararlo de verdad (no solo un
`kill`, que `systemd` deshace al instante):
`sudo systemctl stop v11-webrtc.service`.

**2. Firefox en modo kiosko, como autostart del escritorio** (necesita
sesión gráfica activa, así que se dispara al iniciar el escritorio, no
antes):

```bash
mkdir -p ~/.config/autostart
cp autostart/v11-firefox-kiosk.desktop ~/.config/autostart/
```

Esto asume que la Pi 5 arranca directo al escritorio con inicio de sesión
automático (`sudo raspi-config` → System Options → Boot / Auto Login →
Desktop Autologin). Al cargar el escritorio, se ejecuta
`start_browser.sh`, que ve el servidor ya corriendo (por el paso 1) y solo
lanza Firefox.

**No verificado todavía en esta Pi 5 en concreto** — a diferencia del resto
de esta versión, el arranque automático completo (apagar, encender, y que
todo quede conectado sin tocar nada) no se ha probado de punta a punta.
`start_browser.sh` y `stop_browser.sh` sí están validados como comandos
manuales; lo que falta confirmar es que `systemd` y el autostart del
escritorio los disparen correctamente en el orden esperado tras un
reinicio real. Es el siguiente paso lógico, no una limitación conocida.

## Tercera vía: cancelación de eco real de PipeWire (`pipewire-aec/`)

Las dos vías de arriba resuelven el eco de forma distinta a como lo
planteaba la spec aparcada [`docs/RASPBERRY-PI.md`](../docs/RASPBERRY-PI.md):
el navegador con su AEC nativo, y el terminal con los paliativos de v1
(`BargeInDetector`, que mide el eco pero no lo cancela de verdad). Existe
además una **tercera implementación**, escrita desde cero (no deriva de
`v1`/`v11`) y validada en la misma Pi 5, que sí sigue el enfoque de esa
spec: cancelación de eco real a nivel de sistema, con PipeWire.

**Qué es:** [`pipewire-aec/voice_chat.py`](pipewire-aec/voice_chat.py) —
un cliente de la Realtime API que captura y reproduce audio con
`parec`/`paplay` contra los nodos virtuales `echo-cancel-source`/
`echo-cancel-sink` que expone `module-echo-cancel` de PipeWire (cargado
por [`pipewire-aec/aec-load.sh`](pipewire-aec/aec-load.sh)), en vez de
`sounddevice` contra el hardware directo. La interrupción por voz corta el
audio en curso matando y relanzando `paplay`, no midiendo el nivel de eco
como hace `BargeInDetector`.

**Dos hallazgos reales de esta vía, confirmados en la Pi 5:**
1. La forma "oficial" de cargar el módulo (`pipewire.conf.d`, la que
   describe `docs/RASPBERRY-PI.md`) **crashea en esta build** con
   `Error initialising webrtc audio processing module: -9`. Funciona en
   cambio cargándolo a mano con `pactl load-module module-echo-cancel`
   (lo que hace `aec-load.sh`).
2. El micro y el parlante USB de esta Pi son dos dispositivos con relojes
   independientes (el mismo problema que anticipaba `docs/RASPBERRY-PI.md`,
   apartado 2) — compensado con los parámetros `webrtc.extended_filter` y
   `webrtc.delay_agnostic` al cargar el módulo.

**Cómo se desplegó (validado tal cual, no re-probado en otra ubicación):**
`voice-chat.service` corre `voice_chat.py` desde `/home/pi/voice-chat/`
—una carpeta **distinta** de `/home/pi/v11/`— con el Python del sistema
(`/usr/bin/python3`, sin venv, a diferencia del resto del proyecto). Si
prefieres tenerlo todo bajo `v11/`, copia esta carpeta a
`/home/pi/v11/pipewire-aec/` y ajusta las tres rutas del `.service`
(`ExecStartPre`, `ExecStart`, `WorkingDirectory`) — no probado en esa
ubicación nueva.

**`voice_rest.py`**, en la misma carpeta, es un enfoque distinto y más
simple: no usa la Realtime API en absoluto — graba un turno fijo de 5s,
transcribe con Whisper, pide una respuesta a `gpt-4o-mini`, la convierte a
voz con TTS, y la reproduce (cuatro llamadas HTTP secuenciales por turno,
más lento que un stream de voz continuo). Se conserva como referencia, no
es la vía recomendada de esta carpeta. Llegó con la lectura de la clave de
API corrompida (`API_KEY = ***`, código inválido) — corregida aquí para
que lea `.env` igual que `voice_chat.py`: siempre desde ese fichero, nunca
hardcodeada, y `.env` sigue sin subirse al repositorio (cubierto por el
`.gitignore` de la raíz). **Nota de formato, distinta del resto del
proyecto:** este `.env` va sin comillas (`OPENAI_API_KEY=sk-...`), porque
ambos scripts lo parsean a mano con `line.split('=', 1)`, que no quita
comillas — con comillas, se colarían en la clave y romperían la
autenticación. Ver [`pipewire-aec/.env.example`](pipewire-aec/.env.example).

**Sin `requirements.txt` en la exportación original** — reconstruido a
partir de los imports reales de los dos scripts
([`pipewire-aec/requirements.txt`](pipewire-aec/requirements.txt)), no es
una lista literal confirmada por el usuario.

**Confirmado con hardware real:** `voice_chat.py` corriendo como servicio,
con cancelación de eco real (no los paliativos de `BargeInDetector`).
**No verificado por este documento:** rendimiento/estabilidad de sesión
larga, ni el comportamiento tras mover la carpeta a `v11/pipewire-aec/`
(cambio de ubicación hecho aquí, no vuelto a probar).

## Cómo se verificó

**Con hardware real de la Raspberry Pi 5**, las tres vías:

- `realtime_voice.py --barge-in`: conversación completa en español,
  transcripción visible en el log, interrupción por voz funcionando
- `webrtc_server.py` + Firefox kiosko: `ICE: connected`, audio
  bidireccional, conversación fluida e interrupción por voz — confirmado
  por el usuario (22/08/2026)
- `pipewire-aec/voice_chat.py`: corriendo como servicio (`voice-chat.service`),
  con cancelación de eco real de PipeWire — confirmado por el usuario

**Lo que esto todavía NO verifica:**
- El arranque automático completo tras un reinicio real (`systemd` +
  autostart de escritorio) — ver "Sistema que arranca solo" arriba
- Sesión larga sin reinicios, con ninguna de las tres vías
- Si el mismo síntoma de Chromium en esta Pi aparece en otras Raspberry Pi
  5 o es específico de esta imagen/instalación
- `pipewire-aec/` funcionando desde `v11/pipewire-aec/` — se validó en
  `/home/pi/voice-chat/`, una ubicación distinta (ver esa sección)

## Ficheros de esta versión

- **`realtime_voice.py`** — copia de v1, sin cambios de lógica.
- **`webrtc_server.py`** — copia de v1 con un fix real: `do_GET` ahora
  ignora la query string (`urllib.parse.urlparse`) para poder servir la
  página con `?auto=1`; y la URL impresa/abierta usa `127.0.0.1` en vez de
  `localhost` (en esta Pi, `localhost` resuelve a IPv6 primero y el
  navegador se queda esperando).
- **`static/index.html`** — ya no es la copia de v1: reescrita a partir de
  la implementación validada en la Pi 5, con `iceServers` (STUN),
  autoconexión (`?auto=1`) y diagnóstico de ICE. Ver "Validado en hardware
  real" para el porqué de cada pieza.
- **`asoundrc.example`** — plantilla de `~/.asoundrc` con el fix de
  resampling ALSA (para `realtime_voice.py`).
- **`start_browser.sh` / `stop_browser.sh`** — scripts de operación de 1
  comando para la vía navegador, validados en hardware real.
- **`firefox-profile/user.js`** — plantilla del perfil de Firefox para
  kiosko (sin preguntar permiso de micro, autoplay libre); `start_browser.sh`
  lo copia a `/tmp/ff-v11-profile` si no existe.
- **`systemd/v11-webrtc.service`** — unidad `systemd` para que el servidor
  de la vía navegador arranque solo y se reinicie si cae.
- **`autostart/v11-firefox-kiosk.desktop`** — entrada de autostart de
  escritorio (XDG) para que Firefox arranque en kiosko al iniciar sesión.
- **`pipewire-aec/`** — tercera vía, con AEC real de PipeWire: `voice_chat.py`
  (Realtime API), `voice_rest.py` (alternativa más simple, Whisper→GPT→TTS,
  no Realtime API), `aec-load.sh`, `voice-chat.service`, `requirements.txt`
  (reconstruido, no venía en la exportación original), `.env.example` (sin
  comillas, a propósito — ver esa sección). Escrita desde cero, no deriva
  de `v1`.
- Sin `main.py`, `pico_serial.py`, `face_tracker.py`,
  `sentiment_analyzer.py`, `estado_base.py`, `diagnostico_canal.py` — no
  aplican, esta versión no toca la Pico ni la cámara, a propósito.
- Sin `tests/` — igual que v1, no hay lógica pura nueva que testear sin
  hardware; los hallazgos reales fueron de configuración de sistema o de
  comportamiento del navegador/PipeWire, no de lógica que un test hubiera
  podido atrapar.

## Próximos pasos (fuera de esta versión)

1. **Confirmar el arranque automático de punta a punta** (vía navegador) —
   apagar, encender, y que la conversación quede lista sin tocar nada.
2. **Decidir el destino de `pipewire-aec/`** — ¿se consolida dentro de
   `v11/pipewire-aec/` (mover el despliegue real desde
   `/home/pi/voice-chat/`), o se mantiene como una carpeta aparte en la Pi?
   Cualquiera de las dos es válida; solo hace falta decidirlo y, si se
   mueve, volver a confirmar que arranca desde la nueva ruta.
3. Cuando llegue la cámara CSI, evaluar si conviene aplicar a `v10/` los
   mismos hallazgos de esta versión: el fix de STUN en `static/index.html`
   (idéntico al que usaría v10, mismo bug), la preferencia por Firefox
   sobre Chromium en esta Pi, y el `~/.asoundrc` si `v10/realtime_voice.py`
   llega a usarse con audio real. **No aplicado todavía a v10** — decisión
   pendiente, no un olvido.
4. Investigar la causa raíz del fallo de Chromium en esta Pi, si en algún
   momento hace falta usarlo (por ejemplo, si Firefox no soportara algo que
   sí necesite v10 más adelante).

## Referencias

- [`../v1/README-v1.md`](../v1/README-v1.md) — versión original de la que
  parte esta (arquitectura WebRTC/WebSocket, paliativos de eco de la
  versión de terminal)
- [`../v10/README-v10.md`](../v10/README-v10.md) — la versión hermana con
  las cuatro piezas juntas, bloqueada en la validación por la cámara
- [`../docs/RASPBERRY-PI.md`](../docs/RASPBERRY-PI.md) — spec headless
  aparcada, alternativa si el AEC del navegador dejara de bastar
- [PLAN-v11.md](PLAN-v11.md) — hitos
