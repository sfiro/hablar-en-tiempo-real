# Versión 12.0 — Raspberry Pi 5 + Pico: ciclo de expresiones + rastreo real 🍓👁️😀

**Objetivo:** conectar la Raspberry Pi 5 a la Raspberry Pi Pico por USB serial
(el mismo firmware de v9, sin cambios) y, con la webcam USB de la propia Pi 5,
hacer dos cosas a la vez: rastrear el rostro en tiempo real, y ciclar las 10
expresiones de la Pico cada 5 segundos con esa mirada real. **Todavía sin
conversación de voz** — pedido explícito, alcance acotado a propósito para
validar primero que la Pi 5 controla bien la Pico y su propia cámara, antes
de volver a añadir voz.

**Estado: código completo, sin validar todavía en hardware real.** Igual
situación que tuvo v10 al escribirse: sin una Raspberry Pi 5, cámara ni Pico
delante en este entorno. Verificado hasta donde el entorno lo permite (ver
"Cómo se verificó" más abajo).

## Por qué existe esta versión

v9 (y v10, su port a Pi 5) juntan cuatro piezas a la vez: voz, sentimiento,
rastreo facial y modo dormido — las cuatro dependen de que el navegador y
OpenAI estén de por medio. El usuario pidió aislar, antes de retomar la voz
en la Pi 5, solo dos piezas del sistema: el enlace USB serial con la Pico, y
el rastreo facial con la cámara física de la Pi 5. Sin voz todavía, no hace
falta navegador, servidor HTTP, `OPENAI_API_KEY` ni `pysentimiento` — v12 es
la versión con menos dependencias de todo el proyecto (`pyserial` +
`opencv-python`, nada más).

Es el mismo espíritu que separó v10 de v11: en vez de esperar a tener todas
las piezas listas para probar cualquier cosa, se aísla lo que sí se puede
validar ya. Aquí la pieza aislada es "Pi 5 habla con la Pico real y ve con su
propia cámara", sin las complicaciones de audio/WebRTC de por medio.

## Qué trae y qué no

| Pieza | En v12 |
|---|---|
| Firmware de la Pico (`main.py`) | Igual que v9, sin ningún cambio — modelo dirigido por eventos (EMOCION por serial, pulso de 5s) |
| Enlace serial (`pico_serial.py`) | Igual que v10 (Linux, `/dev/ttyACM*`, grupo `dialout`) |
| Rastreo facial (`face_tracker.py`) | Misma lógica que v9 (`FaceTracker`, `cv2.VideoCapture`) — cámara **USB**, no CSI, así que no hace falta `picamera2` como en v10 |
| Ciclo de expresiones cada 5s | **Nuevo**: `rastreo_expresiones.py`, del lado de la Pi 5, no del firmware |
| Voz en tiempo real | ❌ Fuera de alcance, a propósito |
| Análisis de sentimiento | ❌ Fuera de alcance, a propósito (no hay texto que analizar sin voz) |
| Modo dormido por inactividad | ❌ No aplica sin voz (no hay forma de medir "el usuario habló") |

## Por qué la cámara aquí no necesita `picamera2`

v10 tuvo que introducir `picamera2`/`libcamera` porque su cámara es **CSI**
(el conector de cinta plana de Raspberry Pi), que no habla el protocolo V4L2
que espera `cv2.VideoCapture`. La cámara de v12 es una **webcam USB**
conectada a la Pi 5, que sí enumera como dispositivo V4L2 genérico
(`/dev/video1` en esta máquina) — exactamente el mismo tipo de cámara que ya
sabía abrir `cv2.VideoCapture` desde v3 (en el Mac). Por eso `face_tracker.py`
en v12 no tiene ningún `abrir_camara_csi()` nuevo: solo cambia el índice por
defecto de la cámara (1 en vez de 0), y no necesita un venv con
`--system-site-packages` como v10 — un `python3 -m venv .venv` normal basta.

Si en algún momento se cambia a una cámara CSI, el patrón a seguir es el que
ya documentó v10 (`abrir_camara_csi()`/`leer_frame()` con import diferido de
`picamera2`), no reinventarlo aquí.

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
Webcam USB (/dev/video1)                Raspberry Pi Pico (main.py, igual que v9)
      │  cv2.VideoCapture                       ▲
      ▼                                          │  USB serial "LR,UD,EMOCION\n"
FaceTracker.procesar()                           │  (pico_serial.py, igual que v10)
      │  (hilo de fondo)                         │
      ▼                                          │
ULTIMA_MIRADA (lr, ud) ◄─────────────────────────┤
      │                                          │
      │  cada --interval segundos                │
      ▼                                          │
_ciclar_expresiones() (hilo principal) ──────────┘
      │  siguiente emoción del ciclo fijo
      ▼
CICLO_EMOCIONES: NEUTRAL → FELIZ → ENOJADO → TRISTE → SORPRENDIDO →
                 DORMIDO → DUDA → SOSPECHA → PENSATIVO → NERVIOSO → (repite)
```

## Instalación

```bash
cd v12
python3 -m venv .venv          # venv normal: sin picamera2, sin --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v     # 29 tests, sin hardware
```

En la Raspberry Pi 5 real, además:
- El usuario debe pertenecer al grupo `dialout` para abrir `/dev/ttyACM0` sin
  sudo: `sudo usermod -aG dialout $USER` y volver a iniciar sesión.
- Confirma el índice de la webcam con `v4l2-ctl --list-devices` o
  `ls /dev/video*` — si no es `/dev/video1`, usa `--camera-index`.

## Uso

```bash
python rastreo_expresiones.py                       # Pico + cámara real, ciclo cada 5s
python rastreo_expresiones.py --camera-index 0       # si tu webcam no es /dev/video1
python rastreo_expresiones.py --interval 2           # ciclo más rápido, para probar
python rastreo_expresiones.py --no-pico              # solo prueba cámara + ciclo en consola
python rastreo_expresiones.py --no-tracking          # solo el ciclo, mirada fija en 90,90
```

También puedes probar cada pieza por separado, igual que en versiones
anteriores:

```bash
python face_tracker.py            # solo cámara + rastreo, con ventana de depuración
python pico_serial.py             # solo enlace serial, manda un NEUTRAL de prueba
```

## Cómo se verificó

Sin hardware real (Raspberry Pi 5, Pico, webcam) en este entorno de
desarrollo:
- Sintaxis de los 5 ficheros `.py` del lado cliente.
- **29 tests** (8 de `FaceTracker`, 10 de `pico_serial.py`, 4 de
  `estado_base.py`, 7 de la lógica del ciclo en `rastreo_expresiones.py`),
  todos pasando en `v12/.venv`.
- Arranque real de `rastreo_expresiones.py` en este Mac: sin Pico conectada
  (avisa y sigue el ciclo sin mover servos, confirmado en el log
  imprimiendo `NEUTRAL → FELIZ → ENOJADO → TRISTE...` cada segundo con
  `--interval 1`); con `--tracking` y sin permiso de cámara concedido a este
  proceso (el mismo tipo de bloqueo de macOS que bloqueó a v3 en su día):
  degrada limpiamente con un mensaje claro, sin traceback, y el ciclo de
  expresiones sigue funcionando igual con la mirada fija en 90,90.

**No verificado, pendiente de la Raspberry Pi 5 real** (mismo punto en el
que quedó v10 al escribirse):
- Que `/dev/video1` sea de verdad el índice de la webcam USB en esa máquina
  concreta.
- Que la Pico reciba los 10 comandos por USB serial y cicle las expresiones
  sin caer a `NEUTRAL` entre medias.
- Que el rastreo real mueva la mirada de las 7 expresiones que la siguen,
  mientras `DUDA/PENSATIVO/NERVIOSO` la ignoran — ya validado con un Mac en
  v7/v9, pendiente de confirmar con la Pi 5 como cliente.

## Nota: `diagnostico_canal.py` sigue con el PCA9685, inconsistencia heredada

Al copiar `diagnostico_canal.py` de v9 se notó que sigue usando
`ControladorPCA9685` por I2C — el enfoque que `main.py`/`estado_base.py`
abandonaron desde v5 (ver `../v5/README-v5.md`, "por qué se abandonó el
PCA9685"). Esta inconsistencia ya existía en v9 y en todas las versiones
intermedias; no se ha tocado en v12 por estar fuera de alcance de esta
versión (nadie ha pedido usarlo ni reescribirlo, y no hay PCA9685 conectado
para validar un cambio). Queda documentado aquí para que no se confunda con
un error introducido por esta versión.

## Próximos pasos (fuera de alcance de v12, a propósito)

- Validar en la Raspberry Pi 5 real con la Pico física y la webcam USB.
- Retomar la conversación de voz (v13 o similar), reutilizando el mismo
  `main.py` sin cambios — ya quedó demostrado en v8/v9 que acepta EMOCION
  por serial sin que le importe si viene de un ciclo fijo, de sentimiento, o
  de function-calling.
- Si se cambia de webcam USB a cámara CSI en el futuro, reutilizar el patrón
  de `abrir_camara_csi()`/`leer_frame()` que ya documentó v10, no reinventar
  uno nuevo.
