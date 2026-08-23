# Plan de desarrollo — v11.0.0 Solo conversación de voz, en la Raspberry Pi 5

---

## Hito 1: Copiar v1 sin cambios de lógica ✅ (completado)

- [x] Copiados `webrtc_server.py`, `realtime_voice.py`, `static/index.html`
      desde `v1/`
- [x] Revisado el código en busca de referencias específicas de macOS: solo
      un comentario sobre certificados TLS (`certifi`), generalizado para no
      mencionar una plataforma en concreto
- [x] Confirmado que `webrtc_server.py` no toca audio en Python en absoluto
      (el navegador habla directo con OpenAI) — no necesitaba ningún cambio
- [x] Confirmado que `realtime_voice.py` usa `sounddevice`/PortAudio contra
      el dispositivo por defecto del sistema, sin nada específico de macOS
- [x] `v11/requirements.txt`: mismas dependencias ligeras que v1 (sin
      torch/opencv/pyserial — esta versión no los necesita)
- [x] `.env.example` con el placeholder correcto desde el principio
- [x] Sin `tests/`, igual que v1: no hay lógica pura nueva que valga la pena
      testear sin hardware real

## Hito 2: Documentar el setup de audio de la Pi 5 ✅ (completo, sin validar en hardware)

**Objetivo:** que alguien pueda instalar y arrancar esta versión en una
Raspberry Pi 5 sin tener que adivinar nada sobre el audio USB.

- [x] Documentado en README-v11.md: fijar micro/parlante USB como
      dispositivos por defecto del sistema vía PipeWire (`wpctl status` +
      `wpctl set-default`) — el mismo paso que v10 documenta, reutilizado
      aquí porque el mecanismo es idéntico (ninguna de las dos versiones
      necesita tocar código para usar el dispositivo por defecto)
- [x] Documentado Chromium en modo kiosk como vía recomendada, igual
      razonamiento que v10 (separar servidor y navegador para un
      dispositivo que arranca solo)
- [x] Documentada la alternativa de terminal (`realtime_voice.py`) para
      cuando no hay pantalla, con la advertencia de que sin AEC real el
      riesgo de autointerrupción es mayor con micro/parlante USB separados
      — y un puntero a la spec headless de PipeWire
      (`docs/RASPBERRY-PI.md`) como alternativa no descartada, solo no
      elegida todavía (mismo razonamiento que en v10)

**Por qué se reutiliza el razonamiento de v10 en vez de repetir la
investigación:** la pieza de audio es exactamente la misma decisión de
arquitectura que ya se tomó explícitamente con el usuario al planificar
v10 (navegador con pantalla, no headless) — no tiene sentido volver a
plantearla desde cero para una versión que es un subconjunto de la misma
pila.

## Hito 3: Validación en hardware real ✅ (completo, vía terminal — vía navegador parcial)

**Objetivo:** confirmar que el código funciona de verdad en la Raspberry
Pi 5 física del usuario, con el micro/parlante USB reales.

- [x] **Bug real encontrado y corregido: sample rate.** `realtime_voice.py`
      fallaba al arrancar (`paInvalidSampleRate`): la Realtime API pide 24
      kHz PCM, el hardware USB solo acepta nativamente 44.1/48 kHz, y
      PortAudio con ALSA no resamplea. Fijar el dispositivo por defecto de
      PipeWire (`wpctl set-default`, lo único documentado en el Hito 2) **no
      bastaba** — PortAudio abre ALSA directo, sin pasar por PipeWire
- [x] **Solución real:** `~/.asoundrc` con un `type plug` de ALSA por canal
      (resampling automático). Sin tocar ninguna línea de código — el fix es
      enteramente de configuración del sistema. Añadido
      [`asoundrc.example`](asoundrc.example) como plantilla
- [x] **Aclarado un flag ya existente, pero subdocumentado:**
      `realtime_voice.py --barge-in` es necesario para poder interrumpir al
      asistente hablando por encima — sin él, solo Enter corta. El Hito 2 no
      lo mencionaba con suficiente claridad
- [x] **Confirmado con una conversación real:** `realtime_voice.py
      --barge-in` conectó a la API, mantuvo una conversación completa en
      español por el micro/parlante USB, con transcripción visible en el
      log, y permitió interrumpir al asistente hablando por encima
- [x] `webrtc_server.py`: confirmado que sirve la página (HTTP 200) y
      negocia SDP con OpenAI correctamente

**Cómo se hizo:** el usuario delegó la implementación en hardware real a
otro agente de código corriendo directamente en la Pi 5, que documentó el
proceso en un README de implementación aparte. Esa documentación se usó
para corregir `README-v11.md`/`PLAN-v11.md` con los hallazgos reales, sin
inventar ni suponer nada que no estuviera confirmado ahí.

## Hito 4: Vía navegador operativa — Firefox + STUN ✅ (completo, validado en hardware real)

**Objetivo:** confirmar la vía navegador (la recomendada, por tener AEC
real) de punta a punta con una conversación hablada de verdad.

- [x] **Bug real encontrado: Chromium roto en esta Pi.** Chromium 149 no
      carga ninguna página (local o externa) — pila de red rota, errores
      ANGLE/EGL con el display Xwayland. No se investigó la causa raíz más
      allá del síntoma; se documenta como confirmado en esta Pi concreta,
      no como un defecto general de Chromium en Raspberry Pi 5
- [x] **Decisión de despliegue:** usar Firefox (ya instalado), que sí
      carga la página y hace WebRTC sin problema
- [x] **Bug real encontrado y corregido: WebRTC sin STUN.**
      `static/index.html` creaba `RTCPeerConnection` sin `iceServers` →
      solo candidatos host (IP local), inalcanzables para OpenAI → ICE
      nunca llegaba a `connected` (SDP 200, pero sin audio). Corregido:
      `iceServers` (STUN de Google + Twilio), esperar
      `iceGatheringState === 'complete'` antes de mandar el offer, y
      logging de `iceconnectionstatechange`. `static/index.html` deja de
      ser una copia de v1 sin cambios — es la primera vez en esta versión
      que hace falta tocar ese fichero
- [x] **Bug real encontrado y corregido: query string en `do_GET`.** Para
      la autoconexión en modo kiosko (`?auto=1`, sin clic humano),
      `webrtc_server.py` necesitaba parsear la URL con `urllib.parse.urlparse`
      antes de comparar el path — si no, cualquier query string hacía que
      la comparación fallara y sirviera 404 en vez de la página
- [x] `start_browser.sh` / `stop_browser.sh`: scripts de operación de 1
      comando, con espera activa de `ICE: connected` (hasta 40s) antes de
      confirmar
- [x] Perfil de Firefox (`firefox-profile/user.js`): sin preguntar permiso
      de micro, autoplay libre — necesario para que el kiosko conecte solo
- [x] **Confirmado con hardware real:** ICE conectado, audio bidireccional,
      conversación fluida e interrupción por voz — validado por el usuario
      (22/08/2026)

**Tests:** ninguno nuevo — los tres bugs de este hito fueron de
configuración de sistema (Chromium/Firefox) o de comportamiento del
navegador (STUN, query string), no de lógica pura testeable sin hardware.

## Hito 5: Sistema que arranca solo (autostart) ✅ (instalado y activo en la Pi real, ciclo completo de reinicio sin confirmar explícitamente)

**Objetivo, pedido explícito del usuario tras validar la vía navegador:**
que la Pi 5 quede lista para conversar en cuanto se enciende, sin
intervención manual.

- [x] `systemd/v11-webrtc.service`: unidad `systemd` para el servidor
      Python — `Restart=always`, no depende de sesión gráfica
- [x] `autostart/v11-firefox-kiosk.desktop`: entrada de autostart de
      escritorio (XDG) para Firefox en kiosko — depende de que la Pi
      arranque con inicio de sesión automático en el escritorio
- [x] `start_browser.sh` ampliado (sobre la versión validada tal cual) con
      un paso de autorreparación: si el perfil de Firefox no existe en
      `/tmp` (por ejemplo, tras un reinicio si `/tmp` se limpia), lo copia
      desde `firefox-profile/user.js` en el propio repo
- [x] `stop_browser.sh` ampliado para reconocer si el servidor lo gestiona
      `systemd` (en cuyo caso `systemctl stop`, no un `kill` que
      `Restart=always` deshace al instante) o si corre suelto (`kill`
      manual, como antes)
- [x] **Actualización 23/08/2026:** instalado en la Pi real —
      `v11-webrtc.service` está `enable`d y corriendo (escucha en
      `127.0.0.1:8000` desde el arranque, log por `journalctl -u
      v11-webrtc -f`), y la entrada de autostart de Firefox está en
      `~/.config/autostart/`. Ver
      [`README-IMPLEMENTACION.md`](README-IMPLEMENTACION.md), sección 11
- [ ] **Sigue pendiente:** confirmar explícitamente el ciclo completo de
      apagar/encender la Pi de punta a punta. Es el único punto de esta
      versión que no se ha probado así de verdad todavía
- [x] **Hallazgo real, 23/08:** `~/.asoundrc` puede desaparecer (le pasó a
      esta Pi ese día durante la sincronización con GitHub, causa no
      diagnosticada) — sin autorreparación como la del perfil de Firefox;
      si desaparece, `realtime_voice.py` vuelve a fallar con
      `paInvalidSampleRate` hasta recrearlo a mano
      (`cp asoundrc.example ~/.asoundrc`)

## Hito 6: Tercera vía — AEC real de PipeWire (`pipewire-aec/`) ✅ (validada en hardware real, en una ubicación distinta)

**Objetivo:** documentar e incorporar al repo una implementación adicional,
escrita desde cero por el usuario/otro agente (no deriva de `v1`), que sí
sigue el enfoque de la spec aparcada `docs/RASPBERRY-PI.md`: cancelación de
eco real a nivel de sistema con PipeWire, no los paliativos de
`BargeInDetector`.

- [x] `voice_chat.py`: cliente de la Realtime API que usa `parec`/`paplay`
      contra los nodos virtuales `echo-cancel-source`/`echo-cancel-sink` de
      PipeWire, en vez de `sounddevice` contra el hardware directo. La
      interrupción por voz mata y relanza `paplay`, no mide el nivel de eco
- [x] **Hallazgo real 1:** la vía "oficial" de cargar `module-echo-cancel`
      (`pipewire.conf.d`) crashea en esta build
      (`Error initialising webrtc audio processing module: -9`) — funciona
      cargándolo a mano por `pactl` (`aec-load.sh`)
- [x] **Hallazgo real 2:** el micro y el parlante USB tienen relojes
      independientes (mismo problema anticipado por `docs/RASPBERRY-PI.md`)
      — compensado con `webrtc.extended_filter`/`webrtc.delay_agnostic`
- [x] `voice-chat.service`: despliega `voice_chat.py` como servicio,
      `Restart=always`, con el Python del sistema (sin venv, a diferencia
      del resto del proyecto)
- [x] **Bug real encontrado y corregido, 23/08, en el propio `.service`:**
      corría como root (sin `User=`) — sin acceso a los sockets de
      PipeWire de la sesión del usuario `pi`, fallaba con
      `Permission denied`. Corregido con `User=pi`, `Group=pi`, y
      `Environment=XDG_RUNTIME_DIR=/run/user/1000`. Un segundo problema en
      el mismo archivo: `StandardOutput/StandardError=append:...` hacía
      fallar el arranque del servicio (`status=209/STDOUT`) — quitado,
      logs al journal (`journalctl -u voice-chat -f`)
- [x] **Bug encontrado en la exportación, corregido:** `voice_rest.py`
      (un segundo script, más simple, Whisper→GPT→TTS sin Realtime API)
      llegó con la lectura de `OPENAI_API_KEY` corrompida
      (`API_KEY = ***`, Python inválido) — reconstruida con el mismo patrón
      de `voice_chat.py`, a petición explícita del usuario ("la API siempre
      debe ser de .env y que no se suba al repositorio")
- [x] `requirements.txt` y `.env.example` nuevos, reconstruidos (no venían
      en la exportación) — `.env.example` sin comillas a propósito, porque
      estos scripts parsean `.env` a mano y no las quitarían
- [x] **Confirmado con hardware real:** `voice_chat.py` corriendo como
      servicio, con AEC real de PipeWire, validado por el usuario

**Decisión pendiente, no tomada en este hito:** el despliegue real vive en
`/home/pi/voice-chat/`, una carpeta distinta de `/home/pi/v11/`. Se
documentó tal cual (rutas del `.service` sin tocar) en vez de moverlo a
`v11/pipewire-aec/` sin poder volver a probarlo ahí.

**Tests:** ninguno — mismo criterio que el resto de v11, esta vía tampoco
tiene lógica pura testeable sin hardware real (audio, PipeWire, procesos
externos).

---

## Definición de listo

v11.0.0 está lista cuando:

1. [x] Copiada de v1 sin cambios de lógica, confirmando que no había nada
   específico de macOS que adaptar
2. [x] Documentado el setup de audio USB de la Pi 5 y las dos formas de
   arrancar (navegador, terminal)
3. [x] **Validada con hardware real, vía terminal** —
   `realtime_voice.py --barge-in`, conversación hablada de verdad e
   interrupción confirmada. Bug de sample rate encontrado y corregido.
4. [x] **Validada con hardware real, vía navegador** — Firefox (no
   Chromium, roto en esta Pi) + fix de STUN + autoconexión en kiosko.
   Conversación fluida e interrupción por voz confirmadas.
5. [x] **Validada con hardware real, tercera vía (AEC real de PipeWire)** —
   `pipewire-aec/voice_chat.py`, corriendo como servicio en
   `/home/pi/voice-chat/`.
6. [x] **Arranque automático instalado y activo** (vía navegador) —
   `v11-webrtc.service` corriendo, autostart de Firefox instalado (23/08).
   [ ] Sigue pendiente confirmar explícitamente el ciclo completo de
   apagar/encender de punta a punta. Único punto que queda abierto.

---

**Última actualización:** Agosto 23, 2026
**Estado actual:** v11.0.0 **validada con una conversación real en
hardware real, por las tres vías** (terminal con `--barge-in`, navegador
con Firefox + STUN, y una tercera con AEC real de PipeWire). Cuatro bugs
reales encontrados y corregidos en el proceso de las dos primeras vías
(sample rate, Chromium roto en esta Pi → Firefox, WebRTC sin STUN, query
string en `do_GET`), más uno más en la tercera (lectura de API key
corrompida en `voice_rest.py`, reconstruida). Sistema de arranque
automático (`systemd` + autostart de escritorio) instalado y corriendo en
la Pi real desde el 23/08; un hallazgo real de ese día — `~/.asoundrc`
puede desaparecer, sin autorreparación, hay que recrearlo a mano. Queda
abierta solo por confirmar el ciclo completo de apagar/encender de punta
a punta.
