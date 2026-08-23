# Handoff — Hablar en tiempo real

**Fecha:** 23 de agosto de 2026
**Repositorio en GitHub:** https://github.com/sfiro/hablar-en-tiempo-real
(público). v9, v10, v11 y toda la documentación actualizada ya están
commiteadas y subidas — ver sección 4 para el detalle de cómo se hizo
(auditoría de secretos, instalación de `gh` sin Homebrew, autenticación
con token).
**Última versión activa:** v11 — **validada con una conversación real en
la Raspberry Pi 5 del usuario, por tres vías** (terminal con
`realtime_voice.py --barge-in`; navegador con `webrtc_server.py` + Firefox
en kiosko; y una tercera con cancelación de eco real de PipeWire, escrita
desde cero, en `v11/pipewire-aec/`). Sistema de arranque automático
(`systemd` + autostart de escritorio) **instalado y activo en la Pi real**
desde el 23/08, ciclo completo de apagar/encender sin confirmar todavía
explícitamente. v10 sigue bloqueada por falta de la cámara CSI; v9 completa
y validada en hardware real (Mac).

---

## 1. Objetivo

Asistente de voz en tiempo real contra la **Realtime API de OpenAI**, integrado con un
robot animatrónico ("ojos mecánicos", Raspberry Pi Pico) cuya expresión facial y
mirada reaccionan a la conversación. El proyecto crece por **versiones aditivas**
(`v1/` … `v11/`), cada una en su propia carpeta, autónoma (sin imports entre
versiones, solo copias), documentada en su propio `README-vN.md`/`PLAN-vN.md`.

**Objetivo de la fase actual:** llevar la pila de v9 (voz + sentimiento + rastreo +
sueño) de un Mac a una Raspberry Pi 5. v10 hace esto con las cuatro piezas juntas,
pero su validación está bloqueada porque la cámara CSI todavía no está disponible.
v11 es una versión paralela, más pequeña a propósito: aísla solo la conversación de
voz (sin sentimiento, sin rastreo, sin Pico) para poder probarla ya, sin esperar a
la cámara.

---

## 2. Estado actual

| Versión | Estado |
|---|---|
| v1-v7 | ✅ Completas y validadas en hardware real (v3 es la única sin validar con cámara real, limitación del entorno de desarrollo, no del código) |
| v8 | ✅ Completa y validada con una conversación real |
| v9 | ✅ **Completa y validada en hardware real por el usuario** — "funciona bien, hace el tracking perfecto, y puedo hablar en tiempo real". **Sin commitear todavía** (ver sección 4) |
| v10 | 🔄 **Código completo, sin validar en hardware real** — escrita sin una Raspberry Pi 5, cámara CSI ni Pico delante. Bloqueada: la cámara CSI todavía no está disponible. 79 tests heredados de v9 pasan (73 passed, 6 skipped por falta de `pysentimiento` en esta máquina). **Sin commitear** |
| **v11** | ✅ **Validada con una conversación real en hardware real, por tres vías** (terminal `--barge-in`, navegador Firefox+STUN, y AEC real de PipeWire en `pipewire-aec/`) — copia de v1 (sin sentimiento/rastreo/Pico). Sistema de arranque automático añadido, ciclo de reinicio sin validar. **Sin commitear** (ver sección 4) |

**v9 en detalle:** voz por navegador (WebRTC) + análisis de sentimiento (7 categorías
de `pysentimiento`, mapeadas a la Pico) + rastreo facial real por cámara (hilo de
fondo) + modo dormido por inactividad, los cuatro funcionando a la vez, confirmado
con hardware real. 79 tests, todos pasando. El firmware de la Pico (`v9/main.py`) no
tuvo que cambiar en ningún momento de esta fase — todo lo nuevo se construyó del
lado del Mac reutilizando mecanismos que ya existían y estaban probados.

**v10 en detalle:** la misma pila de v9, pero el cliente pasa de ser un Mac a una
Raspberry Pi 5 (micrófono + parlante USB, cámara CSI). `FaceTracker` (la lógica de
rastreo) no cambió; solo cambió cómo se capturan los frames (`picamera2`/`libcamera`
en vez de `cv2.VideoCapture`) y cómo se detecta el puerto serial de la Pico
(`/dev/ttyACM*` en vez de los nombres de macOS). Decisión de arquitectura importante,
tomada explícitamente con el usuario: el proyecto ya tenía una especificación
aparcada desde v1 (`docs/RASPBERRY-PI.md`) para un enfoque headless con PipeWire; se
le presentó el contraste al usuario y se decidió mantener el navegador (Chromium en
la propia Pi 5) en su lugar — ver `v10/README-v10.md`. El firmware (`v10/main.py`) no
cambió. **Nada de esto se ha probado en una Raspberry Pi 5 real** — el usuario
mencionó que todavía no tiene la cámara CSI disponible, y preguntó por usar una
Raspberry Pi 3B como alternativa (se le explicó el riesgo real de RAM — 1GB frente a
los 4-8GB de la Pi 5, con Chromium + `pysentimiento`/`torch` a la vez — y el problema
del conector CSI de 15 pines de la 3B frente al de 22 pines de la Pi 5; no se llegó a
decidir nada sobre la 3B, el usuario prefirió pasar a v11 en su lugar).

**v11 en detalle:** versión paralela a v10, no un reemplazo ni un paso previo
obligatorio. Aísla la única pieza de v10 que sí se puede validar ya sin la cámara: la
conversación de voz sola. Es literalmente el alcance de v1, sin sentimiento/rastreo/
Pico. `realtime_voice.py` es copia de v1 sin ningún cambio de lógica;
`webrtc_server.py` y `static/index.html` sí necesitaron cambios reales (ver abajo).

**Implementada y validada en hardware real en dos rondas.** El usuario pidió a otro
agente de código (corriendo directamente en la Pi 5) que instalara v11 y le
documentara el proceso, primero para la vía terminal y luego para la vía navegador —
cada README de implementación se usó aquí para corregir `v11/README-v11.md`/
`PLAN-v11.md` con hallazgos reales, sin inventar nada no confirmado ahí. Resultado:

- **Ronda 1 (terminal) — confirmado:** `realtime_voice.py --barge-in` conectó a la
  API, mantuvo una conversación completa en español por el micro/parlante USB, y
  permitió interrumpir al asistente hablando por encima.
- **Bug real 1, corregido: sample rate.** `realtime_voice.py` fallaba con
  `paInvalidSampleRate` — la Realtime API pide 24kHz, el hardware USB solo acepta
  44.1/48kHz nativo, y PortAudio con ALSA no resamplea. Fijar el dispositivo por
  defecto de PipeWire (lo que yo había documentado antes) **no bastaba** — PortAudio
  abre ALSA directo. Fix real: un `~/.asoundrc` con resampling ALSA (`type plug`),
  sin tocar código. Añadido `v11/asoundrc.example` como plantilla. También se aclaró
  que `--barge-in` (ya existía desde v1) es necesario para interrumpir por voz — sin
  él, `realtime_voice.py` solo corta con Enter (no estaba suficientemente claro en
  mi documentación original).
- **Ronda 2 (navegador) — confirmado:** ICE conectado, audio bidireccional,
  conversación fluida e interrupción por voz, con Firefox en modo kiosko con
  autoconexión.
- **Bug real 2, encontrado: Chromium roto en esta Pi.** No carga ninguna página
  (pila de red rota, errores ANGLE/EGL con el display Xwayland) — causa raíz no
  investigada más allá del síntoma. Decisión de despliegue: usar Firefox.
- **Bug real 3, corregido: WebRTC sin STUN.** `static/index.html` (heredado de v1
  sin cambios hasta este punto) creaba `RTCPeerConnection` sin `iceServers` → solo
  candidatos host (IP local) → ICE nunca conectaba con OpenAI pese a que la
  negociación SDP daba 200. Corregido añadiendo STUN (Google + Twilio) y esperando
  a que termine de recolectar candidatos antes de mandar el offer.
- **Bug real 4, menor, corregido: query string en `do_GET`.** Necesario para la
  autoconexión en modo kiosko (`?auto=1`) — arreglado con `urllib.parse.urlparse`.
- **Añadido después, a petición del usuario:** sistema de arranque automático
  (`systemd/v11-webrtc.service` para el servidor, `autostart/v11-firefox-kiosk.desktop`
  para Firefox) — código completo, **sin validar todavía el ciclo completo de
  apagar/encender la Pi**, que es el único punto que queda abierto de esta versión.
- **Ronda 3 (tercera vía, AEC real de PipeWire) — confirmado:** el usuario pasó
  además `voice_chat.py`, `aec-load.sh`, `voice-chat.service` y `voice_rest.py`
  (carpeta `legacy-con-aec/` en la exportación), una implementación **escrita
  desde cero** (no deriva de v1) que sí sigue el enfoque de la spec aparcada
  `docs/RASPBERRY-PI.md`: cancelación de eco real con PipeWire
  (`module-echo-cancel`, nodos `echo-cancel-source`/`echo-cancel-sink`), ya
  validada corriendo como servicio en `/home/pi/voice-chat/`. Incorporada al
  repo en [`v11/pipewire-aec/`](v11/pipewire-aec/). Dos hallazgos reales:
  cargar el módulo por `pipewire.conf.d` crashea en esta build (funciona por
  `pactl`), y el micro/parlante USB tienen relojes independientes (compensado
  con `webrtc.extended_filter`/`delay_agnostic`). `voice_rest.py` (un segundo
  script, Whisper→GPT→TTS, no Realtime API) llegó con la lectura de
  `OPENAI_API_KEY` corrompida por la exportación (`API_KEY = ***`) —
  reconstruida con el mismo patrón de `.env` que usa `voice_chat.py`, a
  petición explícita del usuario.

---

## 3. Archivos

```
Hablar en tiempo real/
├── v1/  … v8/                 # Versiones anteriores, cerradas y validadas
├── v9/                        # Voz + sentimiento + rastreo + sueño (Mac + Pico)
│   ├── main.py                 # Firmware, sin cambios desde v8
│   ├── webrtc_server.py        # Voz navegador + --tracking + modo dormido
│   ├── face_tracker.py         # Retomado de v7, cámara vía cv2.VideoCapture
│   ├── realtime_voice.py       # Alternativa de terminal, sin rastreo
│   ├── sentiment_analyzer.py, pico_serial.py, estado_base.py, diagnostico_canal.py
│   ├── static/index.html
│   ├── tests/                  # 79 tests
│   ├── README-v9.md, PLAN-v9.md
│   └── .env.example             # tenía la clave real filtrada — ya corregido (ver sección 5)
├── v10/                       # Todo lo de v9, en una Raspberry Pi 5 (bloqueada por la cámara)
│   ├── main.py                 # Copia de v9, SIN cambios (firmware, no depende del cliente)
│   ├── webrtc_server.py        # v9 + cámara vía Picamera2, Pico vía /dev/ttyACM*
│   ├── face_tracker.py         # FaceTracker sin cambios; abrir_camara_csi()/leer_frame() nuevas
│   ├── pico_serial.py          # encontrar_puerto_pico(): /dev/ttyACM* (Linux)
│   ├── realtime_voice.py       # Copia de v9 + encontrar_puerto_pico(), sin rastreo
│   ├── sentiment_analyzer.py, estado_base.py, diagnostico_canal.py  # copias sin cambios
│   ├── static/index.html       # copia sin cambios
│   ├── tests/                  # 79 tests (73 pasan, 6 se saltan sin pysentimiento aquí)
│   ├── README-v10.md           # incluye setup de hardware de la Pi 5 (cámara, audio, permisos)
│   └── PLAN-v10.md
├── v11/                       # ★ Versión activa — solo voz, VALIDADA en la Pi 5 (3 vías)
│   ├── webrtc_server.py        # Copia de v1 + fix query string (urlparse) + 127.0.0.1
│   ├── realtime_voice.py       # Copia de v1, SIN cambios (validada: --barge-in)
│   ├── static/index.html       # Reescrita: STUN + autoconexión (?auto=1) + diagnóstico ICE
│   ├── asoundrc.example        # Fix real de sample rate (resampling ALSA)
│   ├── firefox-profile/user.js # Perfil de Firefox para el kiosko
│   ├── start_browser.sh, stop_browser.sh  # Scripts de operación (1 comando), validados
│   ├── systemd/v11-webrtc.service          # Autostart del servidor
│   ├── autostart/v11-firefox-kiosk.desktop # Autostart de Firefox en kiosko
│   ├── pipewire-aec/            # NUEVO: 3ª vía, AEC real de PipeWire (escrita desde cero)
│   │   ├── voice_chat.py, voice_rest.py (corregido), aec-load.sh, voice-chat.service
│   │   └── requirements.txt, .env.example (reconstruidos, sin comillas a propósito)
│   ├── requirements.txt        # Ligero: sin torch/opencv/pyserial
│   ├── README-v11.md           # Hallazgos de las tres rondas de validación real
│   └── PLAN-v11.md
├── CLAUDE.md                   # Mapa técnico de todo el proyecto (actualizado con v11)
├── README.md                   # Índice del proyecto (actualizado con v11)
├── VERSIONS.md                 # Hoja de ruta / changelog (actualizado con v11)
├── docs/RASPBERRY-PI.md        # Spec headless aparcada — v10/v11 no la siguieron, ver sección 4
└── HANDOFF.md                  # Este fichero
```

**Piezas nuevas dentro de `v10/face_tracker.py` que vale la pena conocer:**
- `abrir_camara_csi()` / `leer_frame()` — envuelven `picamera2`/`libcamera` con el
  mismo contrato `(ret, frame)` que tenía `cv2.VideoCapture.read()`. Import de
  `picamera2` diferido (dentro de la función), para que los tests no lo necesiten.
- `FaceTracker.procesar()` — sin cambios, sigue siendo agnóstica al origen del frame.

**Piezas nuevas dentro de `v10/pico_serial.py`:**
- `encontrar_puerto_pico()` (antes `encontrar_puerto_mac()`) — busca `/dev/ttyACM*`.
  Requiere que el usuario esté en el grupo `dialout` en la Pi 5 (no aplicaba en macOS).

---

## 4. Cosas que han cambiado (esta sesión)

1. **Corregido un incidente de seguridad heredado, encontrado al empezar:**
   `v9/.env.example` tenía la clave real de API en vez del placeholder `sk-...`
   (mismo tipo de incidente ya documentado como resuelto en `v8/.env.example` en la
   sesión anterior, pero repetido en v9). Nunca llegó a git (`v9/` sigue sin
   trackear) ni salió de la máquina. Corregido antes de tocar nada más.
2. **Decisión de arquitectura tomada con el usuario, antes de escribir código:**
   este repo ya tenía `docs/RASPBERRY-PI.md`, una especificación aparcada desde v1
   para un enfoque headless (sin pantalla, PipeWire para el eco). Se le presentó el
   contraste al usuario explícitamente; se decidió mantener el navegador (Chromium
   en la propia Pi 5) para no perder ninguna de las cuatro piezas de v9 de golpe.
3. **Creada v10 completa**: copiada de v9, con la cámara adaptada a `picamera2`
   (cámara CSI) y el puerto serial de la Pico adaptado a Linux (`/dev/ttyACM*`).
   `FaceTracker` y el firmware (`main.py`) no cambiaron de lógica.
4. **v10 quedó bloqueada:** el usuario todavía no tiene la cámara CSI de la Pi 5.
   Preguntó por usar una Raspberry Pi 3B como alternativa — se le explicó el riesgo
   real de RAM (1GB frente a los 4-8GB de la Pi 5, con Chromium + `pysentimiento`
   a la vez) y la incompatibilidad del conector CSI (15 pines en la 3B, 22 en la
   Pi 5). No se implementó nada para la 3B; el usuario prefirió avanzar a v11.
5. **Creada v11 completa**: copia de v1 (sin sentimiento/rastreo/Pico) sin ningún
   cambio de lógica — v1 no tenía código específico de macOS. Pensada para
   probarse en la Pi 5 real mientras v10 sigue bloqueada por la cámara.
6. **Tests y smoke tests:** 79 tests de v10 corridos dentro de `v10/.venv` (sin
   `picamera2` ni `pysentimiento` instalados, confirma que los imports diferidos
   no rompen nada); `webrtc_server.py --tracking --no-browser` de v10 degrada
   limpiamente sin cámara ni Pico; `webrtc_server.py --no-browser` de v11 sirve la
   página (`GET /` → 200) con una clave de API falsa.
7. Documentación actualizada en cascada: `CLAUDE.md`, `README.md`, `VERSIONS.md`,
   `v10/README-v10.md`/`PLAN-v10.md`, `v11/README-v11.md`/`PLAN-v11.md`, y este
   `HANDOFF.md`.
8. **v11 corregida con hallazgos reales de hardware (ronda 1, terminal):** el usuario
   hizo que otro agente implementara v11 en su Pi 5 real y le pidió un README
   documentando el proceso. Se revisó y se usó para corregir `v11/README-v11.md`/
   `PLAN-v11.md` con lo realmente confirmado: conversación completa validada vía
   `realtime_voice.py --barge-in`, un bug real de sample rate (fix: `~/.asoundrc`,
   sin tocar código — añadido `v11/asoundrc.example`), y la necesidad de `--barge-in`
   para interrumpir por voz (ya existía, pero no estaba suficientemente destacado).
9. **v11 corregida otra vez con hallazgos reales de hardware (ronda 2, navegador):**
   el usuario siguió la implementación y logró la vía navegador funcionando, con un
   segundo README de implementación (`~/Downloads/v11-archivos-20260822/`, con los
   ficheros reales: `static/index.html`, `webrtc_server.py`, `start_browser.sh`,
   `stop_browser.sh`, `profile/user.js`). Incorporados al repo tal cual, con solo un
   comentario de cabecera añadido en `index.html`. Tres bugs reales más encontrados
   y corregidos: Chromium roto en esta Pi (→ Firefox), WebRTC sin STUN en
   `static/index.html` (primera vez que ese fichero deja de ser copia de v1 sin
   cambios), y `do_GET` sin soporte de query string (`urllib.parse.urlparse`).
   Añadido, a petición explícita del usuario ("dejarlo implementado como un sistema
   que funcione"): `systemd/v11-webrtc.service` y
   `autostart/v11-firefox-kiosk.desktop` para arranque automático — sin validar
   todavía el ciclo completo de reinicio.
10. **v11 ampliada con una tercera vía (ronda 3, AEC real de PipeWire):** el usuario
    pasó `voice_chat.py`, `aec-load.sh`, `voice-chat.service` y `voice_rest.py`
    (`~/Downloads/v11-terminal-20260822/legacy-con-aec/`) — una implementación
    escrita desde cero (no deriva de v1) que sí sigue el enfoque de la spec aparcada
    `docs/RASPBERRY-PI.md`: AEC real con PipeWire. Incorporada en
    `v11/pipewire-aec/`. `voice_rest.py` llegó con la lectura de la API key
    corrompida por la exportación (`API_KEY = ***`) — corregida a petición
    explícita del usuario para que siempre lea de `.env` (nunca hardcodeada, `.env`
    fuera del repo). Documentado que el despliegue real vive en
    `/home/pi/voice-chat/`, no en `/home/pi/v11/` — decisión de consolidarlo o no,
    pendiente.

11. **Subido todo a GitHub** (`sfiro/hablar-en-tiempo-real`, público). Antes de
    commitear: auditoría completa de secretos — todo el historial de git
    revisado (`git log --all -p`) confirmando que nunca hubo una clave real,
    solo el placeholder `sk-...`; confirmado que ningún `.env` real (v1, v2,
    v8, v9) está trackeado ni se colaría con `git add -A`. `gh` (GitHub CLI)
    no estaba instalado ni había Homebrew en esta máquina — se descargó el
    binario oficial directo de GitHub Releases a la carpeta de scratchpad,
    sin instalación a nivel de sistema. El login por navegador (`--web`) no
    completó en este entorno no interactivo (se quedó solo mostrando el
    código); el usuario generó un token de acceso personal y se autenticó
    con `gh auth login --with-token` — el token no quedó en ningún archivo
    del repo. Un solo commit con v9+v10+v11+documentación (`c8f6df7`), y
    `git push -u origin main`.
12. **Añadido `v11/README-IMPLEMENTACION.md`**: el usuario pasó una versión
    actualizada de su diario de implementación en la Pi (secciones 10-11,
    que hasta ahora solo vivía localmente en `/home/pi/v11/`), documentando
    que el sistema de arranque automático ya quedó instalado y corriendo en
    la Pi real (no solo "código listo, sin probar" como yo lo había dejado),
    y un hallazgo real nuevo: `~/.asoundrc` puede desaparecer (le pasó el
    23/08 durante una sincronización con GitHub, causa no diagnosticada),
    sin autorreparación — hay que recrearlo a mano si reaparece el error
    `paInvalidSampleRate`. Se descartó a propósito `cdp_driver.py` (driver
    CDP de Chromium, obsoleto — recomendación del propio usuario de no
    subirlo). Documentación de `v11/README-v11.md`/`PLAN-v11.md` corregida
    para reflejar el estado real (instalado y activo, no solo "sin validar").
    Segundo commit y push pendientes de esta corrección — ver sección 6.

**Todo lo de los puntos 1-10 está commiteado y subido a GitHub** (commit
`c8f6df7`, rama `main`, remoto `origin`). El punto 11 (subida) y el 12
(README-IMPLEMENTACION.md + correcciones de estado) son de esta misma
sesión — el 12 todavía no tiene su propio commit, ver sección 6.

---

## 5. Lo que ha fallado (y cómo se resolvió)

- **Incidente de seguridad, esta sesión:** `v9/.env.example` tenía la clave real de
  API en vez del placeholder. Corregido de inmediato (ver sección 4, punto 1). Vale
  la pena que el usuario revise su flujo de `cp .env .env.example` al crear una
  versión nueva — es la segunda vez que pasa (la primera fue en v8, sesión anterior).
- **Heredado de v9, sin repetirse aquí:** el bug real de threading en macOS
  (`cv2.VideoCapture` dentro del hilo de rastreo fallaba por AVFoundation) no aplica
  en Linux/picamera2 — v10 mantiene el mismo patrón defensivo (abrir la cámara en el
  hilo principal) por consistencia, documentado explícitamente como "no confirmado
  en esta plataforma", no como un bug repetido.
- **Nada nuevo ha fallado en tiempo de ejecución en v10** — porque nada de esto se
  ha podido ejecutar contra hardware real todavía (sin Pi 5, cámara CSI ni Pico en
  este entorno). Ver sección 2 para el detalle de qué queda sin verificar.
- **Bug real en v11 (terminal), encontrado en la Pi 5 y ya corregido:**
  `realtime_voice.py` fallaba con `paInvalidSampleRate` — el micro/parlante USB
  solo aceptan 44.1/48kHz nativo, la Realtime API pide 24kHz, y PortAudio con
  ALSA no resamplea. `wpctl set-default` (lo que yo había documentado antes de
  la validación) no bastaba, porque PortAudio abre ALSA directo, sin pasar por
  PipeWire. **Resuelto** con un `~/.asoundrc` (resampling ALSA vía `type plug`),
  sin tocar ninguna línea de código — plantilla en `v11/asoundrc.example`.
- **Bug real en v11 (navegador), encontrado en la Pi 5 y ya corregido: Chromium
  roto.** Chromium 149 no carga ninguna página en esta Pi (pila de red rota,
  ANGLE/EGL con Xwayland). **Resuelto** cambiando a Firefox — no se investigó
  la causa raíz de Chromium más allá del síntoma.
- **Bug real en v11 (navegador), encontrado en la Pi 5 y ya corregido: WebRTC
  sin STUN.** `static/index.html` no traía `iceServers`, así que ICE nunca
  conectaba con OpenAI a través de la red de esta Pi (solo candidatos host, IP
  local). **Resuelto** añadiendo STUN de Google y Twilio, y esperando a que
  termine la recolección de candidatos antes de mandar el offer.

---

## 6. Pasos a seguir

1. **Commitear y subir el punto 12** (`v11/README-IMPLEMENTACION.md` +
   correcciones de estado en `README-v11.md`/`PLAN-v11.md`/`CLAUDE.md`/
   `README.md`/`VERSIONS.md`) — todavía no tiene commit propio. Preguntar
   antes de comitear, como siempre.
2. **Confirmar el ciclo completo de apagar/encender de v11 de punta a
   punta** — el servicio y el autostart ya están instalados y activos en
   la Pi real (23/08); falta el reinicio de verdad que lo confirme. Es el
   único punto que queda abierto de v11.
3. **Diagnosticar por qué `~/.asoundrc` desapareció el 23/08** (en vez de
   solo seguir recreándolo) — ¿lo borra algo al sincronizar con GitHub?
   ¿una limpieza del sistema? No investigado todavía.
4. **Decidir el destino de `v11/pipewire-aec/`** — ¿se consolida en
   `/home/pi/v11/pipewire-aec/` (moviendo el despliegue real desde
   `/home/pi/voice-chat/`), o se deja como carpeta aparte en la Pi? Cualquiera
   vale, solo falta decidir y, si se mueve, reconfirmar que arranca desde ahí.
5. **Validar v10 cuando llegue la cámara CSI** — micrófono/parlante USB, cámara,
   Pico física. Pasos de instalación completos en `v10/README-v10.md`. Al
   llegar a ese punto, considerar si aplicar a v10 los mismos hallazgos de v11
   (STUN en `static/index.html`, Firefox en vez de Chromium) — decisión
   pendiente, documentada como tal en `v11/README-v11.md`.
6. **Próximas mejoras ya identificadas, sin implementar todavía** (documentadas en
   `v10/README-v10.md`, sección "Próximos pasos"):
   - Sincronía de párpados con la mirada (pendiente desde v6)
   - Reintroducir joystick y/o modo autónomo, si hacen falta
   - Si `pysentimiento`/`torch` resulta pesado en la Pi 5, considerar un modelo
     más ligero — solo con datos reales de rendimiento en la propia Pi 5
7. **Validación adicional sugerida para v9, no bloqueante:** sesión larga sin
   reinicios, y el modo dormido con el `--sleep-timeout` por defecto (60s) en una
   conversación real y prolongada.

---

## Cómo retomar el trabajo

Repositorio: `git clone https://github.com/sfiro/hablar-en-tiempo-real.git`
(o `git pull` si ya está clonado localmente en la Pi/Mac que estés usando).

**v11 en la Pi 5 (vía terminal, YA VALIDADA — usar tal cual):**
```bash
cd v11
cp asoundrc.example ~/.asoundrc   # ajusta los hw:X,Y a tu hardware (aplay -l / arecord -l)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && chmod 600 .env   # y pon tu OPENAI_API_KEY real
python realtime_voice.py --barge-in
```

**v11 en la Pi 5 (vía navegador, YA VALIDADA — Firefox, no Chromium):**
```bash
cd v11 && source .venv/bin/activate
chmod +x start_browser.sh stop_browser.sh
./start_browser.sh   # 1 comando: servidor + Firefox kiosko + espera ICE connected
# ...
./stop_browser.sh    # para todo
```

**v11 arranque automático (código listo, ciclo de reinicio SIN validar — próximo paso):**
```bash
sudo cp systemd/v11-webrtc.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now v11-webrtc.service
mkdir -p ~/.config/autostart && cp autostart/v11-firefox-kiosk.desktop ~/.config/autostart/
# reiniciar la Pi y confirmar que queda conectada sola
```

**v11 tercera vía, AEC real de PipeWire (YA VALIDADA, desplegada en `/home/pi/voice-chat/`):**
```bash
cd v11/pipewire-aec
cp .env.example .env   # SIN comillas: OPENAI_API_KEY=sk-...  (ver el propio .env.example)
pip install -r requirements.txt   # sin venv en el despliegue validado — ver voice-chat.service
./aec-load.sh
python3 voice_chat.py
# o como servicio (ajustando las rutas si no vive en /home/pi/voice-chat/):
sudo cp voice-chat.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now voice-chat.service
```

**v10 (Raspberry Pi 5, pendiente de validar — bloqueada por la cámara CSI):**
```bash
cd v10
python3 -m venv --system-site-packages .venv   # --system-site-packages: ver README-v10.md
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y pon tu OPENAI_API_KEY real
python -m pytest tests/ -v                        # 79 tests
python webrtc_server.py --sentiment --tracking --no-browser &
chromium-browser --kiosk http://localhost:8000
```

**v9 (Mac, ya validada, referencia si algo en v10/v11 no se comporta igual):**
```bash
cd v9 && source .venv/bin/activate
python -m pytest tests/ -v
python webrtc_server.py --sentiment --tracking
```

Documentación de referencia, de más a menos detallada:
[`v11/README-v11.md`](v11/README-v11.md) → [`v10/README-v10.md`](v10/README-v10.md)
→ [`CLAUDE.md`](CLAUDE.md) (mapa de todo el proyecto) → [`VERSIONS.md`](VERSIONS.md)
(changelog).
