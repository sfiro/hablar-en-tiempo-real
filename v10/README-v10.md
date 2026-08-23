# Versión 10.0 — Todo lo de v9, ahora en la Raspberry Pi 5 🎙️👁️📷🍓

**Objetivo:** llevar la pila completa de v9 (voz por navegador + análisis de
sentimiento + rastreo facial real + modo dormido, controlando la Pico) desde
el Mac a una **Raspberry Pi 5**, con micrófono y parlante USB conectados y
cámara CSI para el rastreo. El código de negocio (sentimiento, protocolo
serial, firmware) no cambia: lo que cambia es el hardware de captura —
cámara y audio— y el sistema operativo cliente.

**Estado: código completo, sin validar todavía en hardware real.** Este
código se escribió en un Mac, sin una Raspberry Pi 5, cámara CSI ni Pico
delante — a diferencia de v9, que sí llegó a probarse de punta a punta.
Verificado hasta donde este entorno lo permite (ver "Cómo se verificó" más
abajo); la validación con hardware real de la Pi 5 queda pendiente,
exactamente en la misma situación en la que estuvo v3 antes de que el
usuario la probara con cámara y Pico reales.

## Por qué cambia de máquina

Hasta v9, el "cliente" (el proceso que habla con OpenAI, analiza sentimiento,
rastrea la cámara y manda comandos a la Pico) era un Mac. Desde v10 es una
Raspberry Pi 5, con:

- **Micrófono y parlante USB** en vez del micro/altavoz integrados del Mac.
- **Cámara CSI** (el conector de cinta plana de Raspberry Pi) en vez de la
  webcam USB/integrada del Mac.
- **Chromium corriendo en la propia Pi 5** (con pantalla conectada) en vez
  del navegador del Mac — necesario para conservar la cancelación de eco
  acústico real (AEC) de `webrtc_server.py`, la misma razón por la que v1/v8/
  v9 prefieren esa vía sobre `realtime_voice.py`.
- **La Raspberry Pi Pico se mantiene sin cambios**, hablando por el mismo
  protocolo USB serial de siempre (`LR,UD,EMOCION\n`) — la Pi 5 sustituye al
  Mac como cliente, no a la Pico como controlador de servos.

## Nota: por qué esta versión no sigue `docs/RASPBERRY-PI.md`

Este proyecto ya tenía una especificación aparcada para Raspberry Pi 5,
[`../docs/RASPBERRY-PI.md`](../docs/RASPBERRY-PI.md), escrita para el mismo
hardware (micro y parlante USB independientes) desde la época de v1. Esa
spec elige un enfoque **headless**: `realtime_voice.py` + cancelación de eco
de PipeWire a nivel de sistema, sin pantalla ni navegador — y con buenas
razones (menos CPU/RAM/pantalla, y advierte de un problema real con dos
dispositivos USB de reloj independiente que el AEC de un navegador no tiene
por qué resolver mejor). Se le presentó ese contraste al usuario
explícitamente al planificar v10, y se decidió **no** seguirla esta vez:
esta versión prioriza traer las cuatro piezas de v9 (voz + sentimiento +
rastreo + sueño) sin perder ninguna, y `webrtc_server.py` ya las tenía todas
integradas — reescribir sobre `realtime_voice.py` habría significado
añadirle rastreo facial, algo que ninguna versión anterior construyó ahí a
propósito (ver v9/README-v9.md, "Alcance"). La spec de PipeWire sigue siendo
válida y queda como referencia si una versión futura prioriza headless sobre
tener las cuatro piezas.

## Decisión de arquitectura: navegador en la propia Pi 5, no terminal

`realtime_voice.py` (la alternativa de terminal, sin AEC real, con los
paliativos de v1 — `MicGate`, `BargeInDetector`, medio-dúplex) seguiría
funcionando en la Pi 5 tal cual, porque `sounddevice`/PortAudio funcionan
igual en Linux que en macOS. Pero con micrófono y parlante USB **sin
auriculares** — la situación exacta para la que esos paliativos existen—, la
cancelación de eco real del navegador sigue siendo preferible: por eso
`webrtc_server.py` se mantiene como la vía recomendada también en la Pi 5, y
`realtime_voice.py` se conserva sin cambios de lógica, como alternativa de
prueba (igual que en v8/v9).

Esto implica que la Pi 5 necesita **pantalla y un navegador** (Chromium),
no solo micro/parlante — ver "Instalación en la Raspberry Pi 5" para cómo
dejarlo arrancando en modo kiosk.

## Qué cambió respecto a v9, fichero por fichero

| Fichero | Cambio |
|---|---|
| `webrtc_server.py` | Cámara: `Picamera2` en vez de `cv2.VideoCapture` (`_hilo_rastreo()`, `main()`). Pico: `encontrar_puerto_pico()` en vez de `encontrar_puerto_mac()`. Sin cambios en la lógica de sentimiento, modo dormido, ni en cómo se sirve la página o se negocia WebRTC — esa parte nunca tocó audio en Python, así que migrar de Mac a Pi 5 no la afectó. |
| `face_tracker.py` | `FaceTracker` (la lógica pura: EMA, zona muerta, mapeo a grados) **no cambió ni una línea**. Solo cambió cómo se capturan los frames: `abrir_camara_csi()`/`leer_frame()`, nuevas, envuelven `picamera2` con el mismo contrato `(ret, frame)` que tenía `cv2.VideoCapture.read()`, para no tener que tocar el resto del pipeline. |
| `pico_serial.py` | `encontrar_puerto_mac()` → `encontrar_puerto_pico()`: busca `/dev/ttyACM*` (Linux) en vez de `/dev/cu.usbmodem*`/`/dev/tty.usbmodem*` (macOS). Resto sin cambios. |
| `realtime_voice.py` | Mismo cambio de `encontrar_puerto_pico()`. Sin cambios de lógica de audio (`sounddevice` habla con el dispositivo por defecto del sistema, sea cual sea el SO). |
| `main.py`, `estado_base.py`, `diagnostico_canal.py` (firmware) | **Sin cambios de lógica.** Corren en la Pico, no en el cliente — no les importa si quien les habla por serial es un Mac o una Pi 5. |
| `sentiment_analyzer.py`, `static/index.html` | Copias idénticas. El análisis de sentimiento es Python puro (vía `pysentimiento`) y el navegador es JavaScript — ninguno de los dos sabe en qué máquina corre el servidor. |
| `requirements.txt` | Mismas dependencias de v9, **menos `picamera2`** (deliberadamente fuera de este fichero — se instala por `apt`, no por `pip`, ver más abajo). |

## Por qué `picamera2` no está en `requirements.txt`

La cámara CSI en Raspberry Pi OS (Bookworm en adelante) se accede por
`libcamera`, no por el driver V4L2 genérico que espera `cv2.VideoCapture`.
`picamera2` es el binding oficial de Raspberry Pi para `libcamera`, y la
propia documentación de Raspberry Pi recomienda instalarlo vía `apt`
(paquete del sistema, con las bibliotecas nativas de `libcamera` ya
compiladas para la placa) en vez de `pip install picamera2` — que puede
fallar o quedar incompleto porque esas bibliotecas nativas no se distribuyen
como wheel genérico. Ver "Instalación en la Raspberry Pi 5" para los pasos
exactos.

`face_tracker.py` importa `picamera2` de forma diferida, solo dentro de
`abrir_camara_csi()` — así los tests, y cualquier uso de `FaceTracker`/
`_mapear` sin cámara, no necesitan tenerlo instalado. Confirmado corriendo
los 79 tests en un Mac sin `picamera2` disponible (ver "Cómo se verificó").

## Instalación en la Raspberry Pi 5

```bash
# 1. Cámara CSI: habilitarla y confirmar que el sistema la ve, ANTES de tocar Python.
sudo raspi-config   # Interface Options → Camera → habilitar, reiniciar
libcamera-hello     # debería abrir una vista previa unos segundos; Ctrl+C para salir

# 2. picamera2, vía apt (no pip) — trae las bibliotecas nativas de libcamera.
sudo apt update
sudo apt install -y python3-picamera2 --no-install-recommends

# 3. Micrófono y parlante USB como dispositivos por defecto del sistema.
#    Raspberry Pi OS (Bookworm+) usa PipeWire/WirePlumber. Lista los dispositivos:
wpctl status
#    Identifica el Sink (parlante) y Source (micrófono) USB en la lista, y fíjalos
#    como los que usa el sistema por defecto (los IDs los da `wpctl status`):
wpctl set-default <ID_DEL_PARLANTE_USB>
wpctl set-default <ID_DEL_MICROFONO_USB>
#    El navegador (getUserMedia) y sounddevice/PortAudio (realtime_voice.py) usan
#    ambos el dispositivo por defecto del sistema, así que basta con dejarlo fijado
#    aquí una vez — no hace falta seleccionar nada dentro de la página ni pasarle
#    flags a Python.

# 4. Permiso serial para hablar con la Pico sin sudo.
sudo usermod -aG dialout $USER
# cerrar sesión y volver a entrar (o reiniciar) para que el grupo tenga efecto

# 5. El venv, con --system-site-packages para que vea el picamera2 instalado por apt.
cd v10
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y pon tu OPENAI_API_KEY real

# 6. Chromium en modo kiosk, apuntando al servidor local (ver más abajo por qué
#    conviene separarlo del `webbrowser.open()` automático del script).
```

**Por qué `--system-site-packages` y no `pip install picamera2` a secas:**
sin esa opción, un venv normal no ve los paquetes instalados por `apt` en el
Python del sistema, así que `import picamera2` fallaría dentro del venv
aunque `apt` lo haya instalado correctamente. Si el venv ya existe sin esa
opción, no hay forma de añadírsela después — hay que borrarlo
(`rm -rf .venv`) y crearlo de nuevo con el flag.

### Chromium en modo kiosk

`webrtc_server.py` intenta abrir el navegador por defecto con
`webbrowser.open()` (comportamiento heredado de v1-v9, sin cambios). En un
Mac con escritorio eso basta. En una Pi 5 pensada para arrancar sola (sin
que alguien abra Chromium a mano cada vez), es más fiable separar las dos
cosas: arrancar el servidor con `--no-browser` y lanzar Chromium en modo
kiosk apuntando a esa URL, por ejemplo como dos servicios `systemd`, o desde
el autostart del escritorio:

```bash
python webrtc_server.py --sentiment --tracking --no-browser &
chromium-browser --kiosk --autoplay-policy=no-user-gesture-required http://localhost:8000
```

`--autoplay-policy=no-user-gesture-required` evita que Chromium bloquee la
reproducción de audio del asistente por no haber un clic de por medio —
relevante en kiosk, donde no hay interacción manual antes de que llegue la
primera respuesta hablada.

## Arquitectura

Sin cambios respecto a v9 más allá de qué produce los frames y qué máquina
ejecuta el proceso — ver [`../v9/README-v9.md`](../v9/README-v9.md), sección
"Arquitectura", para el diagrama completo (rastreo en hilo de fondo,
`ULTIMA_MIRADA` compartida con el endpoint de sentimiento, por qué hay una
sola conexión a la Pico). Aquí solo cambia la fuente de los frames:

```
Hilo de fondo: rastreo facial
  Picamera2 (abierta y arrancada en el hilo principal — ver más abajo)
  → leer_frame(picam2)  # mismo contrato (ret, frame) que cv2.VideoCapture.read()
  → FaceTracker.procesar(frame)     [sin cambios desde v7]
  → PICO.enviar(lr, ud)             [sin cambios desde v9]
```

## Sobre abrir la cámara en el hilo principal

v9 encontró un bug real en macOS: abrir `cv2.VideoCapture` dentro del hilo de
rastreo fallaba porque AVFoundation necesita negociar el permiso de cámara
desde el hilo principal (ver
[`../v9/README-v9.md`](../v9/README-v9.md#hallazgo-real-la-cámara-debe-abrirse-en-el-hilo-principal-no-en-el-de-rastreo)).
Este código mantiene la misma estructura defensiva — `abrir_camara_csi()` se
llama en `main()`, y el hilo de rastreo solo recibe el objeto ya arrancado —
**pero, siendo honestos, no hay un problema equivalente confirmado en
Linux/picamera2.** Se mantiene por consistencia y porque no cuesta nada
arriesgar, no porque se haya reproducido un fallo en esta plataforma: eso
solo se puede confirmar (o descartar) probando de verdad en la Pi 5.

## Cómo probarlo

**1. Firmware (Pico):** sin cambios desde v8 — despliega `main.py` con
Thonny, `Archivo → Guardar como → Raspberry Pi Pico`, reinicia físicamente.

**2. Servidor (Raspberry Pi 5):** ver "Instalación en la Raspberry Pi 5"
arriba para el setup de una sola vez (cámara, audio, permisos, venv), luego:

```bash
cd v10
source .venv/bin/activate
python webrtc_server.py --sentiment --tracking --no-browser &
chromium-browser --kiosk http://localhost:8000
```

Usa `--tracking` solo, `--sentiment` solo, o ambos juntos (el caso pensado
para esta versión, igual que en v9). `--no-pico` para probar sin tocar la
Pico. `python face_tracker.py --no-window` (fuera de `webrtc_server.py`)
sirve para validar solo la cámara y el rastreo, sin voz de por medio, igual
que en versiones anteriores.

**Qué observar:** lo mismo que en v9 — los ojos y el cuello deberían seguir
el rostro en tiempo real durante `NEUTRAL/FELIZ/ENOJADO/TRISTE/SORPRENDIDO/
DORMIDO/SOSPECHA`, y una frase con carga emocional clara debería cambiar la
expresión sin que la mirada saltara al centro. Además, ahora por primera vez:
que hablar por el micrófono USB y escuchar la respuesta por el parlante USB
funcione tan bien como con el hardware integrado del Mac — nada en el código
lo garantiza distinto, pero es la pieza que más depende del hardware
concreto y de cómo quede configurado el audio del sistema (paso 3 de la
instalación).

## Cómo se verificó

**Sin hardware real de la Raspberry Pi 5** (este código se escribió en un
Mac, sin Pi 5, cámara CSI, micro/parlante USB ni Pico delante — la primera
vez que una versión de este proyecto llega a este punto sin ninguna pieza
de hardware nueva verificada):

- Sintaxis de los 9 ficheros `.py` (`ast.parse`)
- 79 tests: los 73 heredados de v9 sin cambios de lógica (`test_face_tracker`,
  `test_main_math`, `test_estado_base`, `test_pico_serial` con la ruta fake
  actualizada a `/dev/ttyACM_FAKE`, `test_webrtc_server`) más 6 de
  `test_sentiment.py` que se saltan sin `pysentimiento` instalado — mismo
  patrón que en máquinas sin `torch` desde v2. Corridos dentro de un venv en
  este Mac, **sin `picamera2` instalado**, para confirmar que su import
  diferido no rompe nada que no dependa de la cámara.
- Arranque real de `webrtc_server.py --tracking --no-browser` (sin
  `picamera2` instalado, sin Pico conectada, con una clave de API falsa):
  degrada limpiamente en ambos casos — imprime el mensaje de instalación de
  `picamera2` y sigue sirviendo la página sin rastreo, en vez de fallar con
  una excepción sin manejar.

**Lo que esto NO verifica**, y que solo se puede confirmar con la Pi 5 real:
- Que `picamera2`/`libcamera` capturen frames de verdad y que
  `format="BGR888"` entregue el orden de canal esperado por
  `FaceTracker.procesar()` (asumido a partir de la documentación de
  `picamera2`, no ejecutado contra una cámara real)
- Que el micrófono y el parlante USB, una vez fijados como dispositivos por
  defecto (paso 3 de la instalación), funcionen con `getUserMedia` en
  Chromium igual de bien que el hardware integrado del Mac en v9 — en
  particular, que la cancelación de eco del navegador siga funcionando bien
  con un parlante y un micrófono USB físicamente separados (no un headset),
  que es una configuración acústica distinta a la que se validó en v9 (Mac
  con micro/altavoz integrados, muy cerca uno del otro)
- Que el enlace serial con la Pico funcione igual desde una Pi 5 que desde
  un Mac (debería, mismo `pyserial`, mismo protocolo — pero no probado)
- Que no haya un problema de threading al abrir la cámara CSI desde un hilo
  de fondo, análogo al de AVFoundation en macOS (ver la sección de arriba)
- Rendimiento general: la Pi 5 es más limitada que un Mac de escritorio,
  sobre todo para `pysentimiento`/`torch` (ver la nota en `requirements.txt`)
  y para correr Chromium + rastreo por cámara + inferencia de sentimiento a
  la vez

## Ficheros de esta versión

- **`webrtc_server.py`** — copia de v9, cámara vía `Picamera2` en vez de
  `cv2.VideoCapture`, Pico vía `encontrar_puerto_pico()`.
- **`face_tracker.py`** — `FaceTracker` sin cambios; `abrir_camara_csi()` y
  `leer_frame()` nuevas, envuelven `picamera2`.
- **`pico_serial.py`** — `encontrar_puerto_pico()` en vez de
  `encontrar_puerto_mac()`, busca `/dev/ttyACM*`.
- **`realtime_voice.py`** — mismo cambio de `encontrar_puerto_pico()`, sin
  cambios de lógica de audio.
- **`sentiment_analyzer.py`, `static/index.html`, `main.py`,
  `estado_base.py`, `diagnostico_canal.py`** — copias idénticas de v9, sin
  cambios.

Mapeo de pines (igual que en versiones anteriores, sin cambios — vive en la
Pico, no en el cliente):

```
LR=GP2   UD=GP3   TL=GP4   BL=GP5   TR=GP6   BR=GP7   PAN=GP8   TILT=GP9
```

## Próximos pasos (fuera de esta versión)

1. **Validar en hardware real de la Raspberry Pi 5** — el paso que falta
   para que esta versión pase de "código completo" a "completa y validada",
   como todas las anteriores.
2. Sincronía de párpados con la mirada, joystick, modo autónomo — pendientes
   heredados de versiones anteriores.
3. Si el rendimiento de `pysentimiento`/`torch` resulta pesado en la Pi 5,
   considerar un modelo de sentimiento más ligero o cuantizado — no
   anticipar esto sin datos reales de la propia Pi 5 primero.

## Referencias

- [`../v9/README-v9.md`](../v9/README-v9.md) — arquitectura de voz +
  sentimiento + rastreo real (base de la que parte esta versión; el
  diagrama completo y el hallazgo del hilo de cámara en macOS viven ahí)
- [`../v8/README-v8.md`](../v8/README-v8.md) — voz + sentimiento + Pico
- [`../v3/README-v3.md`](../v3/README-v3.md) — primera vez que se documentó
  un bloqueo de permiso de cámara (en macOS, sandboxed) en este proyecto
- [PLAN-v10.md](PLAN-v10.md) — hitos
