# CLAUDE.md

Guía para trabajar en este repositorio.

## Qué es

Dos programas independientes que conversan por voz contra la **Realtime API de OpenAI**.
No hay paquetes, ni tests, ni build: son ficheros ejecutables sueltos.

- [webrtc_server.py](webrtc_server.py) + [static/index.html](static/index.html) —
  **la versión recomendada**. Servidor local mínimo (solo stdlib + certifi/dotenv) que
  sirve la página y reenvía la oferta SDP del navegador a
  `https://api.openai.com/v1/realtime/calls`. El audio va por **WebRTC** directamente entre
  navegador y OpenAI; este proceso solo interviene en el apretón de manos.
- [realtime_voice.py](realtime_voice.py) — versión de terminal por **WebSocket**, con el
  audio en PCM16 crudo vía sounddevice.

**La diferencia que importa:** el navegador captura el micro con `echoCancellation: true`,
o sea cancelación de eco acústico real, y por eso la versión WebRTC no se autointerrumpe y
permite barge-in natural con altavoces. La de terminal no tiene AEC y todo lo que hace al
respecto (`MicGate`, `BargeInDetector`, umbrales) son paliativos que estiman el eco desde
fuera. Antes de tocar esos paliativos, pregunta si no conviene usar la versión WebRTC.

## Entorno

- Entorno virtual en `.venv/` (Python 3.14, framework de python.org).
- **Usa siempre `.venv/bin/python`**, no el `python3` del sistema: las dependencias y el
  bundle de certificados están solo en el venv.

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python realtime_voice.py
```

Recrear el entorno desde cero:

```bash
rm -rf .venv && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Configuración

`OPENAI_API_KEY` se carga con `python-dotenv` desde el `.env` de la raíz, resuelto
relativo al fichero del script (funciona desde cualquier directorio de trabajo).
Una variable ya exportada en el entorno **tiene prioridad** sobre el `.env`.

`.env` contiene un secreto y está en `.gitignore`. Nunca lo leas en voz alta, lo copies a
otro fichero, ni lo incluyas en salidas, commits o mensajes. `.env.example` es la
plantilla pública.

## Ejecutar y verificar

Ambos necesitan micrófono y una persona hablando, así que **la parte acústica no se puede
validar de forma automatizada**. Lo que sí se puede verificar está descrito abajo y en la
sección de la versión WebRTC.

```bash
.venv/bin/python webrtc_server.py --no-browser   # navegador, recomendada
.venv/bin/python realtime_voice.py               # terminal
```

Lo que sí se puede comprobar sin hablar es que arranca, conecta y que la API **acepta la
configuración de sesión**. Lánzalo en segundo plano redirigiendo la salida, espera unos
segundos y lee el log; luego mátalo (no lo dejes vivo consumiendo cuota):

```bash
.venv/bin/python -u realtime_voice.py > /tmp/rt.log 2>&1 &
sleep 10; cat /tmp/rt.log; pkill -f realtime_voice.py
```

Un arranque sano termina en `🎙️  Listo.` **sin más líneas**. Ojo: los errores de esquema
de sesión no abortan el proceso, solo imprimen `⚠️ Error de la API`, así que el script
parece funcionar aunque el modelo nunca vaya a responder. Hay que leer el log siempre.

Con una clave inválida el fallo es `ConnectionClosedError: … invalid_api_key`; eso indica
que el audio, el `.env` y el TLS están bien y el problema es solo la credencial.

Dispositivos de audio disponibles:

```bash
.venv/bin/python -c "import sounddevice as sd; print(sd.query_devices())"
```

## Detalles de la versión WebRTC

**Estado: verificada funcionando** con altavoces, sin autointerrupción y con interrupción
libre mientras el asistente habla. Es la configuración buena; no la cambies de transporte.

- **Cómo se usa.** `python webrtc_server.py` levanta el servidor y abre la pestaña. Hace
  falta un navegador moderno y conceder el permiso de micrófono una vez (el navegador lo
  recuerda por origen). No hacen falta certificados: `localhost` es contexto seguro, que es
  la condición que `getUserMedia` exige.
- **El servidor NO está en la ruta del audio.** Solo hace el apretón de manos SDP; después
  el audio y el canal `oai-events` van directos entre navegador y OpenAI. Por eso el
  proceso local no añade latencia, y por eso cerrar la terminal no corta una conversación
  ya establecida. Tenlo en cuenta al depurar: una vez conectado, este proceso no ve nada.
- **El modelo por defecto es `gpt-realtime-2.1`**, distinto del `gpt-realtime` de la versión
  de terminal. La lista real se consulta con `GET /v1/models` filtrando por `realtime`.
- **El endpoint espera `multipart/form-data`** con dos campos: `sdp` (la oferta en texto) y
  `session` (JSON con `type`, `model`, `instructions`, `audio`). Responde con la respuesta
  SDP en texto plano. `build_multipart` lo arma a mano para no meter dependencias.
- **No pongas formatos de audio PCM en `session`**: en WebRTC el códec lo negocia el
  transporte (Opus). Eso solo aplica a la versión WebSocket.
- **El servidor escucha solo en `127.0.0.1`** y `do_GET` no sirve nada fuera de `static/`.
  La clave vive en este proceso y nunca llega al navegador; no la expongas a la página.
- **Cómo probarlo sin micrófono:** desde la consola del navegador, un `RTCPeerConnection`
  con `addTransceiver('audio', {direction:'recvonly'})` produce una oferta SDP válida sin
  pedir permisos. Si `connectionState` llega a `connected` y el canal `oai-events` queda
  `open`, la negociación completa funciona. Para validar solo el campo `session`, basta
  mandar un SDP inválido: si el error es `invalid_offer`, el resto se aceptó.

## Detalles de la versión de terminal

- **Certificados TLS.** El Python de python.org no trae raíces de CA, así que
  `websockets.connect` recibe un `ssl.create_default_context(cafile=certifi.where())`.
  Si lo quitas, vuelve `SSL: CERTIFICATE_VERIFY_FAILED`. No lo sustituyas por
  `verify_mode = CERT_NONE`.
- **Hilos.** PortAudio invoca `mic_callback` y `Playback._callback` desde sus propios
  hilos, no desde el bucle de asyncio. El micro cruza al bucle con
  `loop.call_soon_threadsafe`; el búfer de reproducción se protege con un `threading.Lock`.
  Cualquier código nuevo en esos callbacks debe respetarlo y no bloquear.
- **Formato de audio.** PCM16 mono a 24 kHz en ambos sentidos, bloques de 2400 muestras
  (100 ms). Es lo que espera la API: no lo cambies sin ajustar `SAMPLE_RATE` en la
  configuración de sesión.
- **Esquema GA de la sesión.** `build_session_config` usa el esquema nuevo, con `audio`
  anidado (`audio.input.format`, `audio.output.voice`). Los ejemplos antiguos de la
  Realtime API usan campos planos y **no** funcionan con este modelo.
- **Eco y autointerrupción.** No hay cancelación de eco acústico: PortAudio entrega el
  micro en crudo, así que con altavoces la voz del modelo vuelve a entrar y el VAD la toma
  por voz del usuario. Cuatro defensas, todas por defecto: `noise_reduction: far_field`
  (la API lo trae **desactivado**; filtra antes del VAD), umbral 0.75,
  `interrupt_response=False`, y `MicGate`, que descarta los bloques de micro mientras el
  asistente suena (`response.created` → `response.done` + búfer vacío + 300 ms de cola).
  El coste del half-duplex es que **no hay barge-in**; con auriculares conviene
  `--no-half-duplex --noise-reduction near_field`. Si reaparece, `--vad semantic_vad`
  decide el turno con un modelo en vez de por energía. La solución de verdad sería AEC,
  que exige cambiar el transporte a WebRTC.
- **La compuerta se consulta al CAPTURAR, en `mic_callback`, no al enviar.** Es el detalle
  que hace que funcione: si se decide en el `sender`, los bloques grabados mientras hablaba
  el asistente ya están en `mic_queue` y se envían igual —con el eco dentro— en cuanto la
  compuerta se abre. El servidor los oye, abre un turno y encadena una segunda respuesta
  sobre la que aún suena. No muevas esa comprobación al `sender`.
- **Push-to-talk** (`--push-to-talk`) manda `turn_detection: null` y cierra el turno con
  `input_audio_buffer.commit` + `response.create`. Es la única garantía absoluta contra la
  autointerrupción. Ojo con tres cosas que la API rechaza: commits con menos de 100 ms de
  audio, `response.create` con otra respuesta activa, y hacer commit antes de que el
  `sender` haya vaciado `mic_queue`. Las tres están protegidas; no las quites.
- **Diagnóstico.** `--debug` imprime cada evento de la API y si el micro está abierto.
  Un `input_audio_buffer.speech_started` con el micro cerrado imprime un aviso de eco: eso
  significa que se está colando audio pese a la compuerta.
  Toda respuesta con `status != "completed"` imprime `✂️` con `status_details`: ahí se ve
  si el corte lo causó el servidor (`cancelled` por VAD) o algo local (reproducción).
- **Interrupción.** Tres vías. Enter (`keyboard_loop`) siempre funciona y no depende del
  audio. `--barge-in` activa `BargeInDetector`, que estima el nivel del eco con lo que
  entra por el micro **mientras está cerrado** —que es justo el eco— y exige superarlo
  ×factor durante 3 bloques; tiene 5 bloques de calentamiento y adapta la estimación
  despacio (α=0.05) para que una voz sostenida no se adopte como nivel normal. Con
  `--no-half-duplex` la interrupción la maneja el VAD del servidor vía
  `input_audio_buffer.speech_started`. Las tres acaban en `interrupt()`, que vacía la
  reproducción, hace `gate.force_open()` y manda `response.cancel`.
- `numpy` solo se usa para el RMS de `BargeInDetector`.

## Estilo

Código y comentarios en español, igual que el resto del fichero. Comentarios escasos y
solo donde el porqué no sea evidente.
