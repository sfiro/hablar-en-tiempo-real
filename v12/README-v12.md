# Versión 12.0 — Raspberry Pi 5 + Pico: ciclo de expresiones + rastreo real 🍓👁️😀

**Objetivo:** conectar la Raspberry Pi 5 a la Raspberry Pi Pico por USB serial
(el mismo firmware de v9, sin cambios) y, con la cámara de la propia Pi 5,
hacer dos cosas a la vez: rastrear el rostro en tiempo real, y ciclar las 10
expresiones de la Pico cada 5 segundos con esa mirada real. **Todavía sin
conversación de voz** — pedido explícito, alcance acotado a propósito para
validar primero que la Pi 5 controla bien la Pico y su propia cámara, antes
de volver a añadir voz.

**Estado: ✅ validada en hardware real** — Raspberry Pi 5, Pico física y
cámara CSI, tras corregir tres bugs reales encontrados en la validación (ver
"Validación en hardware real" más abajo, y el diario completo en
[`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md)). El ciclo de las 10
expresiones y el rastreo facial real funcionan juntos y de forma sostenida en
el tiempo.

## Por qué existe esta versión

v9 (y v10, su port a Pi 5) juntan cuatro piezas a la vez: voz, sentimiento,
rastreo facial y modo dormido — las cuatro dependen de que el navegador y
OpenAI estén de por medio. El usuario pidió aislar, antes de retomar la voz
en la Pi 5, solo dos piezas del sistema: el enlace USB serial con la Pico, y
el rastreo facial con la cámara física de la Pi 5. Sin voz todavía, no hace
falta navegador, servidor HTTP, `OPENAI_API_KEY` ni `pysentimiento`.

Es el mismo espíritu que separó v10 de v11: en vez de esperar a tener todas
las piezas listas para probar cualquier cosa, se aísla lo que sí se puede
validar ya. Aquí la pieza aislada es "Pi 5 habla con la Pico real y ve con su
propia cámara", sin las complicaciones de audio/WebRTC de por medio.

## Qué trae y qué no

| Pieza | En v12 |
|---|---|
| Firmware de la Pico (`main.py`) | Igual que v9, sin ningún cambio — modelo dirigido por eventos (EMOCION por serial, pulso de 5s) |
| Enlace serial (`pico_serial.py`) | Igual que v10 (Linux, `/dev/ttyACM*`, grupo `dialout`), + `_drenar_entrada()` nuevo (ver más abajo) |
| Rastreo facial (`face_tracker.py`) | Misma lógica base que v9 (`FaceTracker`); cámara **CSI** (OV5647, portado de v10) como vía principal, webcam USB como respaldo automático |
| Ciclo de expresiones cada 5s | **Nuevo**: `rastreo_expresiones.py`, del lado de la Pi 5, no del firmware |
| Rastreo sin ciclo de expresiones | **Nuevo**: `rastreo_solo.py`, para depurar el rastreo aislado |
| Voz en tiempo real | ❌ Fuera de alcance, a propósito |
| Análisis de sentimiento | ❌ Fuera de alcance, a propósito (no hay texto que analizar sin voz) |
| Modo dormido por inactividad | ❌ No aplica sin voz (no hay forma de medir "el usuario habló") |

## Cámara: CSI en el hardware real, USB como respaldo

La spec original de v12 asumía una webcam USB (`/dev/video1`, V4L2 genérico) —
la misma vía que ya sabía abrir `cv2.VideoCapture` desde v3 (Mac). La
validación en hardware real encontró que la Raspberry Pi 5 usa en cambio la
**cámara CSI OV5647** (conector CAM/DISP 1), que no habla ese protocolo — el
mismo motivo por el que v10 introdujo `picamera2`/`libcamera`.

`face_tracker.py` trae ahora, portadas literalmente de v10,
`abrir_camara_csi()`/`leer_frame()` (import diferido de `picamera2`, para que
los tests no lo necesiten instalado). `rastreo_expresiones.py`/`rastreo_solo.py`
intentan la cámara CSI primero y, solo si falla (sin `picamera2` instalado, o
cualquier otro error), caen automáticamente a `cv2.VideoCapture` (webcam USB)
como respaldo — así el mismo código sirve para una Pi 5 con CSI (el hardware
real validado) o con webcam USB (cualquier otra Pi 5 sin cámara CSI
conectada), sin flags que elegir a mano.

**Esto sí cambia el requisito de venv respecto a lo planeado originalmente:**
como la vía principal usa `picamera2` (instalado por `apt`, no por `pip`), el
venv de v12 debe crearse con `--system-site-packages`, igual que v10 — ver
"Instalación" más abajo. `picamera2` no está en `requirements.txt` a
propósito, con el mismo razonamiento que documentó v10.

## Por qué el ciclo de expresiones vive en la Pi 5, no en el firmware

Antes de v8, `main.py` ciclaba las 10 expresiones solo, cada 5 segundos, sin
depender de nada externo (v6/v7). Desde v8, eso se reemplazó por un modelo
dirigido por eventos: la Pico solo cambia de expresión cuando recibe un
`EMOCION` válido por serial, y la mantiene 5 segundos (el "pulso") antes de
volver sola a `NEUTRAL`. Ese cambio se hizo pensando en la voz+sentimiento
(v8/v9): cada frase de la conversación dispara un cambio real, no un reloj
ciego.

v12 no revierte ese cambio — sería un paso atrás justo cuando se necesita
ese mismo firmware, sin tocarlo, para cuando se retome la voz. En vez de
eso, [`rastreo_expresiones.py`](rastreo_expresiones.py) hace de "reloj
externo": manda una `EMOCION` nueva por serial cada `--interval` segundos (5
por defecto, igual al pulso del firmware, para que nunca haya un hueco donde
caiga a `NEUTRAL` entre un cambio y el siguiente). El efecto que se ve en el
robot es el mismo ciclo fijo de v6/v7 — pero el firmware que lo hace posible
es el mismo `main.py` de v9, sin ningún cambio adicional el día que se le
quiera enchufar sentimiento de verdad.

Cada expresión enviada lleva la posición **real** del rostro rastreado, no
un `90,90` fijo — mismo razonamiento que `ULTIMA_MIRADA` en
`v9/webrtc_server.py`, aquí sin necesitar un servidor HTTP: es un único
proceso con dos hilos (uno para la cámara, el hilo principal para el ciclo).

## Arquitectura

```
Cámara CSI OV5647 (picamera2)           Raspberry Pi Pico (main.py, igual que v9)
  ó webcam USB de respaldo (cv2)                   ▲
      │  leer_frame() / cap.read()                 │  USB serial "LR,UD,EMOCION\n"
      ▼                                             │  (pico_serial.py: escribe Y
FaceTracker.procesar()                              │   drena la respuesta de la Pico)
      │  (hilo de fondo, cadencia 200ms)            │
      ▼                                             │
ULTIMA_MIRADA (lr, ud) ◄────────────────────────────┤
      │                                             │
      │  cada --interval segundos                   │
      ▼                                             │
_ciclar_expresiones() (hilo principal) ─────────────┘
      │  siguiente emoción del ciclo fijo
      ▼
CICLO_EMOCIONES: NEUTRAL → FELIZ → ENOJADO → TRISTE → SORPRENDIDO →
                 DORMIDO → DUDA → SOSPECHA → PENSATIVO → NERVIOSO → (repite)
```

## Instalación

```bash
cd v12
python3 -m venv --system-site-packages .venv   # --system-site-packages: ver "Cámara" arriba
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v     # 33 tests, sin hardware
```

En la Raspberry Pi 5 real, además:
- `sudo apt install -y python3-picamera2 --no-install-recommends` (cámara CSI;
  ver la nota de `--system-site-packages` arriba — un venv normal no vería
  este paquete).
- El usuario debe pertenecer al grupo `dialout` para abrir `/dev/ttyACM0` sin
  sudo: `sudo usermod -aG dialout $USER` y volver a iniciar sesión.
- Si tu Pi 5 usa webcam USB en vez de CSI, confirma su índice con
  `v4l2-ctl --list-devices` o `ls /dev/video*` y pásalo con `--camera-index`.

## Uso

```bash
python rastreo_expresiones.py                       # Pico + cámara real, ciclo cada 5s
python rastreo_expresiones.py --camera-index 0       # respaldo USB, si tu webcam no es /dev/video1
python rastreo_expresiones.py --interval 2           # ciclo más rápido, para probar
python rastreo_expresiones.py --no-pico              # solo prueba cámara + ciclo en consola
python rastreo_expresiones.py --no-tracking          # solo el ciclo, mirada fija en 90,90
```

También puedes probar cada pieza por separado:

```bash
python rastreo_solo.py            # solo rastreo (sin ciclo de expresiones), cámara CSI o USB
python face_tracker.py            # solo webcam USB + rastreo, con ventana de depuración
python pico_serial.py             # solo enlace serial, manda un NEUTRAL de prueba
```

Y las herramientas de diagnóstico usadas durante la validación en hardware
(pensadas para correr directamente en la Pi 5, con la ruta del proyecto fija
en `/home/pi/v12` — ajusta el `sys.path.insert()` si tu clon vive en otra
ruta):

```bash
python diagnostico_rastreo.py     # mide tasa de detección y temblor del bbox, 12s
python diagnostico_params.py      # barrido de resolución/parámetros de la cascada
python capturar_deteccion.py      # guarda 3 frames con el bbox detectado, para inspección visual
```

## Validación en hardware real (23/08/2026)

Tres bugs reales encontrados y corregidos — detalle completo, con mediciones y
tablas, en [`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md):

**Bug 1 — la cascada casi no detectaba caras a 640×480.** Con la resolución y
parámetros originales (pensados para una webcam USB), la cascada Haar solo
detectaba el rostro en el 0.4% de los frames. La OV5647 a 640×480 hace un
crop del sensor que dejaba la cara mal encuadrada para la cascada. **Fix:**
`ANCHO=1296, ALTO=972` y `detectMultiScale(scaleFactor=1.2, minNeighbors=4)`
en `face_tracker.py` — de 0% a 100% de frames con rostro detectado, medido
con una persona real delante de la cámara.

**Bug 2 — un falso positivo fijo secuestraba la mirada.** La cascada a veces
detecta un objeto pequeño y estático del fondo, y tomar `rostros[0]` (el
primero de la lista) clavaba la mirada en ese objeto en vez de seguir la cara
real. **Fix:** `FaceTracker.procesar()` ahora elige el rostro de **mayor
área** entre todas las detecciones, y descarta las menores de 80px de lado.

**Bug 3 (el definitivo) — el buffer USB CDC de la Pico se desbordaba.** El
firmware imprime `Serial: LR=.., UD=..` por cada comando recibido, y este
lado nunca leía esa salida — el buffer de 256 bytes se llenaba en pocos
segundos y el `print()` de MicroPython bloqueaba el firmware, dejando de
procesar comandos (síntoma: "el rastreo empieza bien y muere a los ~10s").
**Fix:** nuevo método `_drenar_entrada()` en `PicoLink` (`pico_serial.py`),
que lee y descarta la salida de la Pico en cada ciclo del hilo de envío.

**Ajustes de calibración, también validados:** cadencia de envío a la Pico
limitada a 200ms (a 20 envíos/s el buffer volvía a saturarse), y
`FaceTracker(alpha=0.5, zona_muerta=0)` en el hilo de rastreo — la Pico ya
suaviza internamente, así que el cliente necesita mandar un flujo continuo de
objetivos, no comandos discretos que se cortan al converger un filtro propio.

**Confirmado en hardware real, con los cuatro fixes aplicados:** cámara CSI
OV5647 abierta sin errores; Pico detectada en `/dev/ttyACM0`; ciclo de las 10
expresiones enviándose en orden; rastreo facial siguiendo un rostro real de
forma continua y sostenida en el tiempo, sin volverse lento tras los primeros
segundos.

## Cómo se verificó

Sin hardware real, en el entorno de desarrollo original: sintaxis, y 33 tests
(8 de `FaceTracker` incluida la selección del rostro más grande y el filtro
de 80px, 12 de `pico_serial.py` incluido el drenado del buffer, 4 de
`estado_base.py`, 7 de la lógica del ciclo), todos pasando en `v12/.venv`
(sin `picamera2` instalado, confirmando que el import diferido no rompe
nada). Con hardware real: ver "Validación en hardware real" arriba.

## Nota: `diagnostico_canal.py` sigue con el PCA9685, inconsistencia heredada

Al copiar `diagnostico_canal.py` de v9 se notó que sigue usando
`ControladorPCA9685` por I2C — el enfoque que `main.py`/`estado_base.py`
abandonaron desde v5 (ver `../v5/README-v5.md`, "por qué se abandonó el
PCA9685"). Esta inconsistencia ya existía en v9 y en todas las versiones
intermedias; no se ha tocado en v12 por estar fuera de alcance de esta
versión (nadie ha pedido usarlo ni reescribirlo, y no hay PCA9685 conectado
para validar un cambio). Queda documentado aquí para que no se confunda con
un error introducido por esta versión.

## Próximos pasos

- Retomar la conversación de voz (v13 o similar), reutilizando el mismo
  `main.py` sin cambios — ya quedó demostrado en v8/v9 que acepta EMOCION
  por serial sin que le importe si viene de un ciclo fijo, de sentimiento, o
  de function-calling.
- Confirmar el rastreo en sesiones más largas (varios minutos u horas
  seguidas), más allá de lo ya validado.
