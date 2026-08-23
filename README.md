# Hablar en tiempo real 🎙️

Asistente de conversación por voz en tiempo real con la Realtime API de OpenAI, con
análisis de emociones y (en desarrollo) control de un rastreador facial mecánico.

**Estado:** v1 completa y respaldada · v2 completa en código, falta validar con voz
real · v3 con rastreador facial + enlace serial completos en código, falta validar
con cámara y hardware real · v4 completa y validada en hardware real (los ojos
siguen el rostro correctamente) · v5 completa y validada en hardware real (+
cuello y parpadeo, sin vibraciones, tras abandonar el PCA9685 por PWM directo) ·
v6 completa y validada en hardware real (utilidad de estado base + secuencia
de expresiones cada 5s, con ajustes de realismo tras la primera prueba —
reposo de párpados, SORPRENDIDO/FELIZ/SOSPECHA/DORMIDO recalculados, cabeza
gacha en TRISTE, mirada fija/errática en DUDA/PENSATIVO/NERVIOSO) · v7
completa y validada en hardware real (misma base de v6, junta el rastreo
facial real con la secuencia de expresiones activa) · v8 completa y validada
en conversación real (junta voz + sentimiento de v1/v2 con el firmware de
v6/v7: la emoción detectada en la conversación controla la expresión facial;
voz en el navegador por WebRTC, todavía sin rastreo facial — eso es v9) · v9
completa y validada en hardware real (junta voz + sentimiento de v8 con el
rastreo facial real de v7, en el mismo proceso; corregido un bug real de
threading al abrir la cámara) · v10 código completo, validación en hardware
pendiente (todo lo de v9, ahora en una Raspberry Pi 5 con cámara CSI y
micro/parlante USB en vez del Mac) · v11 **validada con una conversación
real en hardware real, por tres vías** (solo la conversación de voz
—alcance de v1— en la Raspberry Pi 5; terminal con `--barge-in`, navegador
con Firefox + STUN, y una tercera con cancelación de eco real de PipeWire;
corregidos varios bugs reales de sample rate ALSA, Chromium roto en esta
Pi, y WebRTC sin servidores STUN; añadido un sistema de arranque
automático, sin validar todavía el ciclo completo de reinicio) · v12
**validada en hardware real** (Pi 5 conectada por USB a la Pico —firmware
de v9, sin cambios— ciclando las 10 expresiones cada 5s con la mirada real
de la cámara CSI de la Pi 5; tres bugs reales corregidos tras validar
—cascada mal calibrada, falso positivo secuestrando la mirada, y el buffer
USB de la Pico desbordándose—; todavía sin conversación de voz, a
propósito).

## 📦 Versiones disponibles

Cada versión está en su propia carpeta con código, entorno y documentación
independientes. Cada una construye sobre la anterior.

### [v1](v1/) — Voz en tiempo real ✅
**Estado:** Completa y respaldada (tag `v1.0.0`).

- Conversación WebRTC en navegador (macOS), con cancelación de eco real del navegador
- Versión terminal por WebSocket, con paliativos contra eco (half-duplex, detector de
  nivel) para cuando no hay navegador
- Especificación para Raspberry Pi 5 (aparcada, ver [VERSIONS.md](VERSIONS.md))

```bash
cd v1 && source .venv/bin/activate
python webrtc_server.py       # recomendado: WebRTC con navegador
# o
python realtime_voice.py      # terminal, WebSocket
```

Ver [`v1/README-v1.md`](v1/README-v1.md).

### [v2](v2/) — + Análisis de emociones ✅ (código), 🔄 (validación con voz)
**Estado:** Implementado y con tests contra el modelo real; falta que alguien hable de
verdad con `--sentiment` para confirmar que las emociones mostradas tienen sentido.

- Clasifica cada frase (tuya y del asistente) en una de las 6 emociones de Ekman +
  neutral, usando [`pysentimiento`](https://github.com/pysentimiento/pysentimiento)
  (RoBERTuito para español)
- El análisis corre en un hilo aparte: nunca bloquea el audio
- `--stats` da un resumen de emociones al terminar la conversación
- Documentadas con datos reales, no inventados: el modelo acierta claro en frases
  elaboradas y falla más en exclamaciones cortas (ver limitaciones en
  [`v2/README-v2.md`](v2/README-v2.md))

```bash
cd v2 && source .venv/bin/activate
python realtime_voice.py --sentiment --stats
```

Ver [`v2/README-v2.md`](v2/README-v2.md) y [`v2/PLAN-v2.md`](v2/PLAN-v2.md).

### [v3](v3/) — + Rastreo facial y servos 🔄 (código completo, validación pendiente)
**Estado:** Rastreador facial (`FaceTracker`) y enlace serial (`PicoLink`) completos,
con 19 tests pasando. Falta la validación con cámara y hardware real, que no se pudo
hacer en un entorno sandboxed (macOS bloquea el acceso a cámara sin permiso concedido
interactivamente).

Se investigó a fondo un proyecto hermano (`ojosMecanicos`) antes de empezar, para
reusar lo que ya funciona ahí (protocolo serial hacia una Raspberry Pi Pico, patrón de
threading) y no repetir un bug de diseño real que se encontró (una integración de
voz+emoción+cámara que arrancaba los hilos pero nunca conectaba la emoción con el
movimiento).

- Objetivo: mostrar las coordenadas x,y del rostro en consola junto al sentimiento, y
  opcionalmente enviarlas (junto con la emoción, traducida a su vocabulario) por
  serial a una Pico que mueve servos
- Dos bugs reales encontrados en este hito: `opencv-python` 5.0 eliminó
  `CascadeClassifier` del paquete base (fijado a `<5`), y el chequeo de reconexión
  del enlace serial rompía con puertos de prueba inyectados (aislado para que solo
  aplique con hardware real)

```bash
cd v3 && source .venv/bin/activate
python face_tracker.py            # prueba solo la cámara, con ventana de depuración
python -m pytest tests/ -v        # 19 tests, sin necesitar cámara ni Pico
```

Ver [`v3/README-v3.md`](v3/README-v3.md) y [`v3/PLAN-v3.md`](v3/PLAN-v3.md).

### [v4](v4/) — Rastreo facial + servos, simplificado y autónomo ✅ (validado en hardware real)
**Estado:** Completa. Firmware `main.py` simplificado (párpados abiertos al
arrancar, sin parpadeo, + rastreo x,y por serial) **más su propia copia del lado
Mac** (`face_tracker.py`, `pico_serial.py`, con `.venv` propio). **Confirmado en
hardware real: el rastreo funciona y los ojos siguen el rostro correctamente.**

Antes de retomar la integración de voz de v3, se decidió apartar la complejidad del
`main.py` completo de `ojosMecanicos` (emociones, joystick, modo autónomo, parpadeo)
para confirmar primero que el rastreo x,y funciona bien con una base simple.

**Totalmente autónoma: no depende de ningún fichero de v1/v2/v3.** `face_tracker.py`
y `pico_serial.py` son copias de las de v3, no imports — puedes borrar `v3/` entero y
`v4/` sigue funcionando igual. Solo `v4/main.py` (el firmware) es distinto: no tiene
`.venv` porque corre en la Pico, no en el Mac.

```bash
cd v4 && source .venv/bin/activate
python face_tracker.py            # rastreo completo: cámara → x,y → servos
python -m pytest tests/ -v        # 19 tests, autónomos, sin tocar v3
```

Ver [`v4/README-v4.md`](v4/README-v4.md) para cómo desplegar el firmware
(Thonny/`mpremote`) y [`v4/PLAN-v4.md`](v4/PLAN-v4.md) para los hitos.

### [v5](v5/) — + Cuello y parpadeo, mientras rastrea ✅ (validado en hardware real)
**Estado:** Completa. Rotación de cabeza (PAN, amortiguada al 80%) + subir/bajar
cabeza (TILT, amortiguada al 60%) + parpadeo periódico cada 2-6s, todo mientras el
rastreo de ojos sigue funcionando igual que en v4. Sin emociones, joystick ni modo
autónomo todavía. **Confirmado por el usuario: "todos los motores se mueven y
parpadea sin vibraciones".**

**Cambio de arquitectura a mitad de la depuración:** el firmware empezó con el
mismo controlador PCA9685 (I2C) que usa `ojosMecanicos`, pero en hardware real dio
tres problemas (temblor al encender, temblor periódico al parpadear, y el eje PAN
sin moverse) que resultaron tener el mismo origen. Se abandonó el PCA9685 por
completo, generando el PWM de cada servo directamente desde los pines de la Pico
— y los tres problemas desaparecieron a la vez. La cronología completa, con cada
intento y cada error, está documentada en
[`v5/README-v5.md`](v5/README-v5.md#historial-de-depuración-completo).

**Totalmente autónoma, igual que v4:** copia propia de `face_tracker.py` y
`pico_serial.py` (sin cambios respecto a v4), `.venv` propio, 25 tests propios.

```bash
cd v5 && source .venv/bin/activate
python face_tracker.py            # rastreo de ojos, sin cambios respecto a v4
python -m pytest tests/ -v        # 25 tests
```

Ver [`v5/README-v5.md`](v5/README-v5.md) y [`v5/PLAN-v5.md`](v5/PLAN-v5.md).

### [v6](v6/) — Estado base + secuencia de expresiones ✅ (completa y validada en hardware real)
**Estado:** Dos cosas nuevas. `estado_base.py`: lleva los 8 servos a 90° (uno a
uno, con espaciado contra picos de corriente) y los mantiene ahí — posición
segura antes de desconectar la alimentación, o para recuperar un estado neutral
tras un error. Y en `main.py`: **secuencia de expresiones faciales**, cambiando
cada 5 segundos en un orden fijo (NEUTRAL → FELIZ → ENOJADO → ... → NERVIOSO →
NEUTRAL), sin depender de voz ni sentimiento todavía — primer paso, no la
versión final. **Confirmado por el usuario en la Pico real: "todo ha
funcionado bien".**

Tras la primera prueba, se ajustaron varias expresiones para verse más
realistas, y esos ajustes también se validaron en hardware: los párpados en
reposo ya no parten 100% abiertos sino a un 40% de cierre (esto resolvió de
raíz un hallazgo real anterior — SORPRENDIDO no se distinguía de NEUTRAL
porque su offset no tenía margen mecánico para abrir más), FELIZ y SOSPECHA se
recalcularon para notarse sobre el nuevo reposo, TRISTE fuerza la cabeza a su
mínimo mecánico (cabeza gacha), y DUDA/PENSATIVO/NERVIOSO ahora fijan o mueven
la mirada por su cuenta (barrido lateral, mirada arriba-izquierda, y saltos al
azar respectivamente) en vez de seguir el rastreo facial mientras duran.

**Trae toda la base funcional de v5**, sin cambios salvo `main.py`:
`face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`. `main.py` y
`estado_base.py` son programas independientes — desplegar uno no reemplaza al
otro.

```bash
cd v6 && source .venv/bin/activate
python -m pytest tests/ -v        # 49 tests
```

Ver [`v6/README-v6.md`](v6/README-v6.md) y [`v6/PLAN-v6.md`](v6/PLAN-v6.md).

### [v7](v7/) — Seguimiento visual real + secuencia de expresiones ✅ (completa y validada en hardware real)
**Estado:** Sin cambios de lógica respecto a v6 — el objetivo es juntar, por
primera vez, el rastreo facial real (`face_tracker.py`, en el Mac, enviando
`LR,UD` por serial) con la secuencia de expresiones activa. De las 10
emociones, 7 (`NEUTRAL/FELIZ/ENOJADO/TRISTE/SORPRENDIDO/DORMIDO/SOSPECHA`) no
tocan `LR`/`UD`, así que la mirada sigue al rostro real con el offset de cada
emoción aplicado encima; las otras 3 (`DUDA/PENSATIVO/NERVIOSO`) ignoran el
rastreo a propósito y fijan o mueven la mirada por su cuenta, tal como ya
estaban construidas en v6. **Confirmado por el usuario con cámara y Pico
funcionando a la vez: "funcionó perfecto".**

**Totalmente autónoma, igual que v6:** copia propia de `main.py`,
`face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`, `estado_base.py`
(sin cambios de lógica respecto a v6), `.venv` propio, mismos 49 tests.

```bash
cd v7 && source .venv/bin/activate
python -m pytest tests/ -v        # 49 tests
python face_tracker.py            # rastreo real + envío a la Pico, si hay una
```

Ver [`v7/README-v7.md`](v7/README-v7.md) y [`v7/PLAN-v7.md`](v7/PLAN-v7.md).

### [v8](v8/) — Voz + sentimiento controlando la expresión facial ✅ (completa y validada en conversación real)
**Estado:** Junta v1/v2 (conversación de voz + análisis de sentimiento) con
v6/v7 (firmware de la Pico + expresiones). Cambio de fondo en `main.py`: ya no
cicla sola las 10 expresiones cada 5s — la expresión cambia al recibir un
`EMOCION` válido por serial, se mantiene 5 segundos (pulso) y vuelve sola a
NEUTRAL si no llega una nueva. La emoción detectada (7 categorías de
`pysentimiento`, ninguna sin mapear) se traduce al vocabulario de la Pico y
se envía por serial si hay una conectada (autodetectada, `--no-pico` para
desactivarlo).

**Dos formas de hablar:** `webrtc_server.py` (recomendado, nuevo en v8) abre
la conversación en el navegador por WebRTC — cancelación de eco real,
interrupción natural hablando encima, sin el lag ni los paliativos de la
terminal. Como con WebRTC la transcripción va directo entre el navegador y
OpenAI, el navegador manda el texto de cada frase a un endpoint nuevo
(`POST /api/analyze-sentiment`) que hace el análisis y avisa a la Pico.
`realtime_voice.py` (terminal, heredado de v2) se mantiene como alternativa.

**Todavía sin rastreo facial, a propósito** — LR/UD van fijos a 90,90; eso es
lo siguiente (v9), pedido explícitamente para después de validar esta
integración. **Confirmado por el usuario con una conversación real** (clave
de API válida, hablando de verdad por el navegador, con la Pico física): "ha
funcionado muy bien y el robot también ha seguido todos los sentimientos".

```bash
cd v8 && source .venv/bin/activate
python -m pytest tests/ -v        # 65 tests
python webrtc_server.py --sentiment    # recomendado: voz en el navegador + Pico
# o
python realtime_voice.py --sentiment   # alternativa: terminal + Pico
```

Ver [`v8/README-v8.md`](v8/README-v8.md) y [`v8/PLAN-v8.md`](v8/PLAN-v8.md).

### [v9](v9/) — Voz + sentimiento + rastreo facial real, todo junto ✅ (completa y validada en hardware real)
**Estado:** Junta, en el mismo proceso, las tres piezas validadas por
separado hasta ahora: voz + sentimiento (v8) y rastreo facial real (v7).
Alcance acotado: solo `webrtc_server.py` recibe la cámara — `realtime_voice.py`
se queda igual que en v8, sin rastreo. Un hilo de fondo rastrea el rostro y
manda su posición real a la Pico; el endpoint de sentimiento ahora manda esa
misma posición real junto con la emoción, en vez del `90,90` fijo que usaba
v8. `main.py` (el firmware) no cambió — ya aceptaba mirada real desde v4.

**Bug real encontrado y corregido:** abrir la cámara dentro del hilo de
rastreo falla en macOS (`"can not spin main run loop from other thread"` —
AVFoundation necesita el hilo principal para negociar el permiso). Se
resolvió abriendo la cámara en el hilo principal y pasando el objeto ya
abierto al hilo de fondo. **Confirmado por el usuario, con permiso de cámara
concedido y una conversación real:** "funciona bien, hace el tracking
perfecto, y puedo hablar en tiempo real".

**Añadido después, pedido explícito: modo dormido por inactividad.** Tras
`--sleep-timeout` segundos (60 por defecto) sin que el usuario hable, la Pico
entra en `DORMIDO`; al volver la actividad, se despierta con `DUDA` y de ahí
pasa sola a `NEUTRAL` — sin ningún cambio en `main.py`, reutilizando que la
misma emoción repetida extiende el pulso de 5s ya probado desde v8. Validado
con hardware real (`--sleep-timeout 4`, para no esperar 60s).

```bash
cd v9 && source .venv/bin/activate
python -m pytest tests/ -v                       # 79 tests
python webrtc_server.py --sentiment --tracking    # las tres piezas juntas
```

Ver [`v9/README-v9.md`](v9/README-v9.md) y [`v9/PLAN-v9.md`](v9/PLAN-v9.md).

### [v10](v10/) — Todo lo de v9, en la Raspberry Pi 5 🔄 (código completo, validación en hardware pendiente)
**Estado:** Lleva la pila completa de v9 (voz por navegador + sentimiento +
rastreo facial real + modo dormido) de un Mac a una **Raspberry Pi 5**, con
cámara CSI (`picamera2`, en vez de la webcam del Mac) y micrófono/parlante
USB. La Pico se mantiene sin cambios como controlador de servos — la Pi 5
sustituye al Mac como cliente, no a la Pico. `FaceTracker` (la lógica de
rastreo) no cambió ni una línea; solo cambió cómo se capturan los frames.

**Decisión de arquitectura tomada con el usuario:** este proyecto ya tenía
una especificación aparcada desde v1
([`docs/RASPBERRY-PI.md`](docs/RASPBERRY-PI.md)) que proponía un enfoque
headless (sin pantalla) con cancelación de eco a nivel de PipeWire. Se le
presentó ese contraste al usuario, y v10 sigue en cambio con
`webrtc_server.py` + Chromium en la propia Pi 5 (necesita pantalla), para no
perder ninguna de las cuatro piezas de v9 de golpe — ver
[`v10/README-v10.md`](v10/README-v10.md), sección "Por qué esta versión no
sigue `docs/RASPBERRY-PI.md`".

**Sin validar todavía en hardware real** — este código se escribió sin una
Raspberry Pi 5, cámara CSI, ni Pico delante. Verificado hasta donde este
entorno lo permite: sintaxis, 79 tests (73 pasan, 6 se saltan por falta de
`pysentimiento`), y arranque real de `webrtc_server.py` degradando
limpiamente sin `picamera2` instalado.

```bash
cd v10 && source .venv/bin/activate
python -m pytest tests/ -v                       # 79 tests
python webrtc_server.py --sentiment --tracking --no-browser &
chromium-browser --kiosk http://localhost:8000
```

Ver [`v10/README-v10.md`](v10/README-v10.md) y [`v10/PLAN-v10.md`](v10/PLAN-v10.md).

### [v11](v11/) — Solo conversación de voz, en la Raspberry Pi 5 ✅ (validada con conversación real, tres vías)
**Estado:** Versión paralela a v10, no un reemplazo ni un requisito previo
suyo. La cámara CSI que necesita v10 todavía no está disponible, así que
v11 aísla la única pieza que sí se puede probar ya: la conversación de voz
sola, sin sentimiento, sin rastreo facial, sin Pico — exactamente el
alcance de v1, corriendo en la Raspberry Pi 5 en vez del Mac.

`realtime_voice.py` es copia de v1 sin ningún cambio de lógica.
`webrtc_server.py` y `static/index.html` sí necesitaron cambios reales,
encontrados al validar en hardware.

**Validada con una conversación real en la Raspberry Pi 5 del usuario, por
las dos vías.** Cuatro bugs reales encontrados y corregidos en el proceso:
(1) sample rate — la Realtime API pide 24kHz PCM, el hardware USB solo
acepta 44.1/48kHz nativo, y PortAudio no resamplea con ALSA directo; fix
sin tocar código, un `~/.asoundrc` con resampling (plantilla en
[`v11/asoundrc.example`](v11/asoundrc.example)); (2) **Chromium 149 tiene
la pila de red rota en esta Pi** (no carga ninguna página) — se usa
Firefox en su lugar; (3) `static/index.html` creaba WebRTC sin servidores
STUN, así que ICE nunca conectaba con OpenAI — corregido añadiendo STUN;
(4) el servidor no soportaba query string en la URL, necesaria para la
autoconexión en modo kiosko — corregido con `urllib.parse.urlparse`.

Ahora incluye un **sistema de arranque automático** (`systemd` para el
servidor, autostart de escritorio para Firefox), instalado y activo en la
Pi real desde el 23/08 — sigue sin confirmarse explícitamente el ciclo
completo de apagar/encender de punta a punta. Detalle completo, con los
comandos exactos usados en la Pi, en
[`v11/README-IMPLEMENTACION.md`](v11/README-IMPLEMENTACION.md).

Hay además una **tercera vía**, en [`v11/pipewire-aec/`](v11/pipewire-aec/):
`voice_chat.py`, escrito desde cero (no deriva de v1), con **cancelación de
eco real de PipeWire** en vez de los paliativos de `BargeInDetector` — el
enfoque de la spec aparcada [`docs/RASPBERRY-PI.md`](docs/RASPBERRY-PI.md).
También validada con hardware real, pero desplegada en
`/home/pi/voice-chat/`, una carpeta distinta de `/home/pi/v11/`. Su
`voice-chat.service` tuvo un bug real (corría como root, sin acceso a los
sockets de PipeWire del usuario `pi`) — corregido el 23/08 con
`User=pi`/`Group=pi`/`XDG_RUNTIME_DIR` y logs al journal.

```bash
cd v11
cp asoundrc.example ~/.asoundrc   # y ajusta los hw:X,Y a tu hardware (aplay -l / arecord -l)
source .venv/bin/activate
python realtime_voice.py --barge-in       # vía terminal, validada
# o
./start_browser.sh                        # vía navegador (Firefox), validada, 1 comando
```

Ver [`v11/README-v11.md`](v11/README-v11.md) y [`v11/PLAN-v11.md`](v11/PLAN-v11.md).

### [v12](v12/) — Pi 5 + Pico: ciclo de expresiones + rastreo real, sin voz ✅ (validada en hardware real)
**Estado:** Rama paralela a v10/v11, no una continuación de ninguna de las
dos. Conecta la Raspberry Pi 5 a la Pico por USB serial (el mismo firmware
de v9, `main.py`, sin ningún cambio) y, con la cámara de la propia Pi 5,
cicla las 10 expresiones cada 5 segundos con la mirada real del rastreo
facial — **todavía sin conversación de voz**, a propósito, para validar
primero que la Pi 5 controla bien la Pico y su propia cámara.

El firmware no vuelve a ciclar solo (como hacía en v6/v7): sigue siendo el
mismo modelo dirigido por eventos de v8/v9 (espera un `EMOCION` por serial,
la mantiene 5s). El ciclo vive ahora en un script nuevo del lado de la Pi 5,
[`rastreo_expresiones.py`](v12/rastreo_expresiones.py), que manda una
`EMOCION` nueva cada `--interval` segundos con la posición real del rostro
rastreado — el mismo firmware queda listo, sin tocar nada más, para cuando
se retome la voz.

La planificación original asumía una webcam USB (`/dev/video1`, V4L2), para
no necesitar `picamera2` como v10 — **la validación en hardware real
(23/08/2026) encontró que esta Pi 5 usa la cámara CSI OV5647**, igual que
v10. `face_tracker.py` incorporó el mismo soporte CSI de v10, con la webcam
USB como respaldo automático si no hay CSI disponible. La validación
encontró y corrigió **tres bugs reales**, ninguno anticipado por los tests
sin hardware: la cascada Haar casi no detectaba caras a 640×480 con la
OV5647 (resuelto subiendo a 1296×972 y relajando sus parámetros), un falso
positivo fijo del fondo secuestraba la mirada (resuelto eligiendo el rostro
de mayor área, no el primero), y el bug más importante — el firmware
imprime por cada comando recibido y nadie leía esa salida, así que el
buffer USB de la Pico se llenaba y su `print()` bloqueaba el firmware
entero (resuelto drenando esa salida en `pico_serial.py`). Sin voz, no hace
falta `.env`, `OPENAI_API_KEY` ni `pysentimiento`.

**✅ Completa y validada en hardware real** (33 tests, todos pasando; Pico
ciclando las 10 expresiones y rastreo facial siguiendo un rostro real de
forma sostenida en el tiempo tras los tres fixes) — detalle completo del
proceso de depuración en
[`v12/MODIFICACIONES-LOCALES.md`](v12/MODIFICACIONES-LOCALES.md).

```bash
cd v12 && source .venv/bin/activate
python -m pytest tests/ -v                 # 33 tests
python rastreo_expresiones.py              # Pico + cámara real, ciclo cada 5s
```

Ver [`v12/README-v12.md`](v12/README-v12.md) y [`v12/PLAN-v12.md`](v12/PLAN-v12.md).

## 📚 Documentación

- [CLAUDE.md](CLAUDE.md) — contexto técnico completo del proyecto (para trabajar en el código)
- [VERSIONS.md](VERSIONS.md) — hoja de ruta e historial de versiones
- [v1/README-v1.md](v1/README-v1.md) · [v1/CLAUDE-v1.md](v1/CLAUDE-v1.md)
- [v2/README-v2.md](v2/README-v2.md) · [v2/PLAN-v2.md](v2/PLAN-v2.md) · [v2/INSTALL-v2.md](v2/INSTALL-v2.md)
- [v3/README-v3.md](v3/README-v3.md) · [v3/PLAN-v3.md](v3/PLAN-v3.md)
- [v4/README-v4.md](v4/README-v4.md) · [v4/PLAN-v4.md](v4/PLAN-v4.md)
- [v5/README-v5.md](v5/README-v5.md) · [v5/PLAN-v5.md](v5/PLAN-v5.md) — incluye la cronología completa de depuración
- [v6/README-v6.md](v6/README-v6.md) · [v6/PLAN-v6.md](v6/PLAN-v6.md)
- [v7/README-v7.md](v7/README-v7.md) · [v7/PLAN-v7.md](v7/PLAN-v7.md)
- [v8/README-v8.md](v8/README-v8.md) · [v8/PLAN-v8.md](v8/PLAN-v8.md)
- [v9/README-v9.md](v9/README-v9.md) · [v9/PLAN-v9.md](v9/PLAN-v9.md)
- [v10/README-v10.md](v10/README-v10.md) · [v10/PLAN-v10.md](v10/PLAN-v10.md)
- [v11/README-v11.md](v11/README-v11.md) · [v11/PLAN-v11.md](v11/PLAN-v11.md)
- [v12/README-v12.md](v12/README-v12.md) · [v12/PLAN-v12.md](v12/PLAN-v12.md)
- [docs/RASPBERRY-PI.md](docs/RASPBERRY-PI.md) — especificación headless para Pi 5
  (aparcada; v10 y v11 tomaron un camino distinto — con navegador, no headless —
  ver [v10/README-v10.md](v10/README-v10.md))

## 🔧 Requisitos

- Python 3.9+
- Clave de API de OpenAI con acceso a la Realtime API (no aplica a v12: no
  toca voz)
- Micrófono y altavoces (v1/v2/v8/v9) — cámara adicional para v3/v4/v5/v6/v7/v9/v12
  (v8 no usa cámara, a propósito — ver v8/README-v8.md)
- v2, v3, v8, v9 y v10 instalan `pysentimiento` (torch + transformers): ~2GB,
  varios minutos la primera vez (más lento aún en la Pi 5 — ver
  v10/requirements.txt). **v4, v5, v6, v7 y v12 no** — son mucho más ligeros
  (solo `opencv-python` + `pyserial`), porque no tocan voz ni sentimiento
- `main.py`/`estado_base.py` de v4/v5/v6/v7/v8/v9/v10/v12 son firmware
  MicroPython: necesitan la Raspberry Pi Pico física; el resto es Python
  normal (de Mac en v1-v9, de una Raspberry Pi 5 en v10/v12)
- **v10 además necesita:** una Raspberry Pi 5 con cámara CSI, micrófono y
  parlante USB, y pantalla + Chromium (para la cancelación de eco real del
  navegador) — ver [`v10/README-v10.md`](v10/README-v10.md), sección
  "Instalación en la Raspberry Pi 5"
- **v11 necesita lo mismo que v10, salvo la cámara:** Raspberry Pi 5 con
  micrófono/parlante USB y pantalla + Chromium — sin `picamera2` ni
  `opencv-python`, no toca cámara. La versión pensada para probarse primero,
  mientras no llega la cámara de v10
- **v12 necesita:** una Raspberry Pi 5 conectada por USB a la Pico, y una
  cámara CSI (la validada en hardware real — `picamera2`, igual que v10; con
  webcam USB como respaldo automático si no hay CSI disponible). No necesita
  micrófono, parlante, pantalla ni navegador: no toca voz

## 📋 Comparativa de versiones

| | v1 | v2 | v3 | v4 | v5 | v6 | v7 | v8 | v9 | v10 | v11 | v12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dónde corre | Mac | Mac | Mac | Mac + **la Pico** | Mac + **la Pico** | Mac + **la Pico** | Mac + **la Pico** | Mac + **la Pico** | Mac + **la Pico** | **Raspberry Pi 5** + **la Pico** | **Raspberry Pi 5** (sin Pico) | **Raspberry Pi 5** + **la Pico** |
| Voz en tiempo real | ✅ | ✅ (hereda de v1) | ✅ (hereda de v2) | — (a propósito) | — (a propósito) | — (a propósito) | — (a propósito) | ✅ (hereda de v2) | ✅ (hereda de v8) | ✅ (hereda de v9) | ✅ validado en real (terminal, `--barge-in`) | — (a propósito, ver v12) |
| Cancelación de eco | Navegador (WebRTC) | igual que v1 | igual que v1 | n/a | n/a | n/a | n/a | igual que v1 | igual que v1 | igual que v1 (Chromium en la Pi 5) | Validada 3 formas: Firefox+STUN, `BargeInDetector`, y AEC real de PipeWire | n/a (sin voz) |
| Análisis de emociones | — | ✅ `pysentimiento`, en consola | ✅ (hereda de v2) | — | — | — | — | ✅ (hereda de v2) | ✅ (hereda de v8) | ✅ (hereda de v9) | — (a propósito, ver v11) | — (a propósito, sin voz) |
| Rastreo facial (ojos) | — | — | 🔄 falta cámara real | ✅ validado en real | ✅ (hereda de v4) | ✅ (hereda de v5) | ✅ (hereda de v6) | — (a propósito, ver v9) | ✅ validado en real | 🔄 cámara CSI, código completo | — (a propósito, ver v11) | ✅ validado en real (cámara CSI, tras 3 fixes) |
| Cuello (PAN/TILT) | — | — | — | — | ✅ validado en real | ✅ (hereda de v5) | ✅ (hereda de v6) | ✅ (hereda de v6/v7) | ✅ (hereda de v6/v7) | ✅ (hereda de v6/v7) | n/a (sin Pico) | ✅ (hereda de v6/v7, vía v9) |
| Parpadeo | — | — | — | — | ✅ validado en real | ✅ (hereda de v5) | ✅ (hereda de v6) | ✅ (hereda de v6/v7) | ✅ (hereda de v6/v7) | ✅ (hereda de v6/v7) | n/a (sin Pico) | ✅ (hereda de v6/v7, vía v9) |
| Utilidad de estado base | — | — | — | — | — | ✅ validada en real | ✅ (hereda de v6) | ✅ (hereda de v6/v7) | ✅ (hereda de v6/v7) | ✅ (hereda de v6/v7) | n/a (sin Pico) | ✅ (hereda de v9) |
| Expresiones faciales | — | — | — | — | — | ✅ secuencia fija, validada en real | ✅ (hereda de v6) | ✅ dirigidas por sentimiento (pulso 5s) | ✅ (hereda de v8) | ✅ (hereda de v8) | n/a (sin Pico) | ✅ ciclo fijo cada 5s, desde el cliente (no el firmware) |
| Modo dormido por inactividad | — | — | — | — | — | — | — | — | ✅ validado en real | ✅ (hereda de v9) | n/a (sin Pico) | — (a propósito, sin voz que mida actividad) |
| Rastreo real + expresiones a la vez | — | — | — | — | — | — | ✅ validado en real | n/a (sin rastreo aún) | ✅ validado en real | 🔄 código completo | n/a | ✅ validado en real, desde el cliente |
| Estado | ✅ Completa | Validación pendiente | Validación pendiente | ✅ Completa y validada | ✅ Completa y validada | ✅ Completa y validada | ✅ Completa y validada | ✅ Completa y validada | ✅ Completa y validada | 🔄 Código completo, validación pendiente (bloqueada por la cámara) | ✅ Validada (terminal y navegador); falta el ciclo de autoarranque | ✅ Completa y validada en hardware real |

**Nota sobre independencia:** cada carpeta de versión tiene sus propias copias de
cualquier código que reutilice de otra (nunca lo importa con una ruta cruzada). Por
eso `pico_serial.py` existe, con la misma lógica base, de `v3/` a `v12/` (adaptado
a Linux en v10; en v12, además, con `_drenar_entrada()` nuevo tras un bug real de
buffer USB), y `face_tracker.py` en `v3/` a `v7/`, en `v9/`, `v10/` y `v12/` (v8 no
lo incluye: no rastreaba el rostro todavía, a propósito; v12 porta de v10 el
soporte de cámara CSI, con webcam USB como respaldo). Puedes borrar cualquier
carpeta de versión anterior y las demás siguen funcionando.

## 📖 Estructura del proyecto

```
.
├── v1/                     # Voz en tiempo real (completa)
│   ├── realtime_voice.py   # Cliente WebSocket
│   ├── webrtc_server.py    # Servidor SDP (recomendado)
│   ├── static/
│   ├── README-v1.md
│   └── CLAUDE-v1.md
├── v2/                     # + Análisis de emociones
│   ├── realtime_voice.py   # v1 + --sentiment
│   ├── sentiment_analyzer.py
│   ├── tests/
│   ├── README-v2.md
│   ├── PLAN-v2.md
│   └── INSTALL-v2.md
├── v3/                     # + Rastreo facial y servos (código de Mac)
│   ├── face_tracker.py     # FaceTracker (headless) + script standalone con ventana
│   ├── pico_serial.py      # PicoLink: cola, reconexión, latido
│   ├── tests/
│   ├── README-v3.md
│   └── PLAN-v3.md
├── v4/                     # Rastreo facial + servos, simplificado y autónomo
│   ├── main.py             # Firmware Pico (MicroPython): ojos abiertos + rastreo x,y
│   ├── face_tracker.py     # Copia autónoma de v3 (Mac, con .venv propio)
│   ├── pico_serial.py      # Copia autónoma de v3 (Mac, con .venv propio)
│   ├── tests/
│   ├── README-v4.md
│   └── PLAN-v4.md
├── v5/                     # + Cuello (PAN/TILT) y parpadeo periódico
│   ├── main.py             # Firmware Pico: PWM directo (sin PCA9685), cuello + parpadeo
│   ├── main_pca9685.py     # Archivado: versión con PCA9685, no usar (ver README-v5.md)
│   ├── face_tracker.py     # Copia autónoma de v4, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v4, sin cambios
│   ├── diagnostico_canal.py # Herramienta: mueve un solo canal, aislado
│   ├── tests/              # 25 tests
│   ├── README-v5.md        # Incluye la cronología completa de depuración
│   └── PLAN-v5.md
├── v6/                     # Estado base + secuencia de expresiones
│   ├── estado_base.py      # Nuevo: centra los 8 servos y los mantiene
│   ├── main.py             # v5 + secuencia de expresiones cada 5s (nuevo)
│   ├── face_tracker.py     # Copia autónoma de v5, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v5, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v5, sin cambios
│   ├── tests/              # 49 tests
│   ├── README-v6.md
│   └── PLAN-v6.md
├── v7/                     # Seguimiento visual real + secuencia de expresiones
│   ├── main.py             # Copia idéntica de v6, sin cambios de lógica
│   ├── face_tracker.py     # Copia autónoma de v6, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v6, sin cambios
│   ├── estado_base.py      # Copia autónoma de v6, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v6, sin cambios
│   ├── tests/              # 49 tests (heredados de v6, sin cambios)
│   ├── README-v7.md
│   └── PLAN-v7.md
├── v8/                     # Voz + sentimiento controlando la expresión facial
│   ├── main.py             # v7 + expresión dirigida por EMOCION (pulso 5s)
│   ├── webrtc_server.py    # Copia de v1 + endpoint /api/analyze-sentiment (recomendado)
│   ├── static/index.html   # Copia de v1 + envío de transcripción a ese endpoint
│   ├── realtime_voice.py   # Copia de v2 + envío de la emoción a la Pico (alternativa)
│   ├── sentiment_analyzer.py # Copia autónoma de v2, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v7, sin cambios
│   ├── estado_base.py      # Copia autónoma de v7, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v7, sin cambios
│   ├── tests/              # 65 tests
│   ├── README-v8.md
│   └── PLAN-v8.md
├── v9/                     # Voz + sentimiento + rastreo facial real, todo junto
│   ├── main.py             # Copia de v8, sin cambios (ya aceptaba mirada real)
│   ├── webrtc_server.py    # v8 + hilo de rastreo, --tracking, ULTIMA_MIRADA
│   ├── face_tracker.py     # Retomado de v7, sin cambios de lógica
│   ├── static/index.html   # Copia de v8, sin cambios
│   ├── realtime_voice.py   # Copia de v8, sin cambios (sin rastreo, alcance acotado)
│   ├── sentiment_analyzer.py # Copia autónoma de v8, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v8, sin cambios
│   ├── estado_base.py      # Copia autónoma de v8, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v8, sin cambios
│   ├── tests/              # 79 tests
│   ├── README-v9.md
│   └── PLAN-v9.md
├── v10/                    # Todo lo de v9, en la Raspberry Pi 5 (cliente, no la Pico)
│   ├── main.py             # Copia de v9, sin cambios (firmware, no depende del cliente)
│   ├── webrtc_server.py    # v9 + cámara vía Picamera2 en vez de cv2.VideoCapture
│   ├── face_tracker.py     # FaceTracker sin cambios; abrir_camara_csi()/leer_frame() nuevas
│   ├── pico_serial.py      # encontrar_puerto_pico(): /dev/ttyACM* en vez de macOS
│   ├── static/index.html   # Copia de v9, sin cambios
│   ├── realtime_voice.py   # Copia de v9 + encontrar_puerto_pico(), sin rastreo (alcance acotado)
│   ├── sentiment_analyzer.py # Copia autónoma de v9, sin cambios
│   ├── estado_base.py      # Copia autónoma de v9, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v9, sin cambios
│   ├── tests/              # 79 tests
│   ├── README-v10.md       # Incluye el setup de hardware de la Pi 5 (cámara, audio, permisos)
│   └── PLAN-v10.md
├── v11/                    # Solo conversación de voz, VALIDADA en la Pi 5 (paralela a v10)
│   ├── webrtc_server.py    # Copia de v1 + fix de query string (urlparse) + 127.0.0.1
│   ├── realtime_voice.py   # Copia de v1, sin cambios (validada: --barge-in)
│   ├── static/index.html   # Reescrita: STUN + autoconexión (?auto=1) + diagnóstico ICE
│   ├── asoundrc.example    # Plantilla del fix real de sample rate (ALSA resampling)
│   ├── firefox-profile/user.js  # Perfil de Firefox para el kiosko
│   ├── start_browser.sh / stop_browser.sh  # Scripts de operación (1 comando), validados
│   ├── systemd/v11-webrtc.service          # Autostart del servidor
│   ├── autostart/v11-firefox-kiosk.desktop # Autostart de Firefox en kiosko
│   ├── pipewire-aec/       # 3ª vía: AEC real de PipeWire, escrita desde cero
│   ├── README-v11.md       # Por qué existe junto a v10, hallazgos de la validación real
│   ├── README-IMPLEMENTACION.md  # Diario de implementación en la Pi real (17/08, 22/08, 23/08)
│   └── PLAN-v11.md
├── v12/                    # Pi 5 + Pico: ciclo de expresiones + rastreo real, sin voz — VALIDADA
│   ├── main.py             # Copia de v9, sin cambios (firmware, dirigido por eventos)
│   ├── pico_serial.py      # v10 + _drenar_entrada() (fix real: buffer USB de la Pico se desbordaba)
│   ├── face_tracker.py     # FaceTracker + abrir_camara_csi()/leer_frame() (portadas de v10, cámara real)
│   ├── rastreo_expresiones.py  # Ciclo de 10 expresiones/5s + hilo de rastreo, CSI con respaldo USB
│   ├── rastreo_solo.py     # Nuevo: solo rastreo, sin ciclo de expresiones (para depurar aislado)
│   ├── estado_base.py      # Copia autónoma de v9, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v9, sin cambios
│   ├── diagnostico_rastreo.py, diagnostico_params.py, capturar_deteccion.py  # Herramientas de depuración en la Pi 5
│   ├── tests/              # 33 tests
│   ├── README-v12.md
│   ├── PLAN-v12.md
│   └── MODIFICACIONES-LOCALES.md  # Diario de validación en hardware real (23/08/2026)
├── docs/
│   └── RASPBERRY-PI.md     # Especificación headless, aparcada (v10/v11 tomaron otro camino)
├── CLAUDE.md               # Contexto técnico completo del proyecto
├── VERSIONS.md             # Hoja de ruta
└── README.md               # Este fichero
```

Cada versión es independiente: su propio venv, requirements y documentación, y sus
propias copias de cualquier código reutilizado de otra versión (nunca imports entre
carpetas). v1 no cambia mientras se trabaja en v2, v3, v4, v5, v6, v7, v8, v9, v10,
v11 o v12, y puedes borrar cualquier versión anterior sin romper las demás. v11 es
una excepción curiosa: es una copia de v1 (no de la versión inmediatamente
anterior), paralela a v10, no una continuación suya — ver la sección de v11 más
arriba. v12 retoma en cambio `main.py` de v9 y `pico_serial.py` de v10 — es una
rama paralela a v10/v11, no una continuación de ninguna de las dos.

## ❓ FAQ

**¿Puedo usar v1 o v2 mientras se trabaja en v3?**
Sí. Cada versión vive en su carpeta con su propio entorno; trabajar en v3 no toca v1 ni v2.

**¿Cómo bajo solo una versión?**
`git clone --branch v1.0.0 <repo>` para v1. v2 y v3 aún no tienen tag propio (ver
[VERSIONS.md](VERSIONS.md)).

**¿Por qué v2 dice "código completo, validación pendiente"?**
El análisis de emociones está probado contra el modelo real con tests automatizados,
pero falta que alguien mantenga una conversación de voz real con `--sentiment` para
confirmar que lo mostrado en consola tiene sentido con una conversación hablada, no
solo con texto de prueba.

**¿Qué es `ojosMecanicos`?**
Un proyecto hermano y anterior del mismo usuario: un sistema de servos (una Raspberry
Pi Pico moviendo "ojos" mecánicos) con su propio historial de intentos de integrar
voz y cámara. v3 reutiliza su protocolo serial y su patrón de threading, ya probados
ahí, en vez de reinventarlos. Ver [`v3/README-v3.md`](v3/README-v3.md).

---

**Última actualización:** Agosto 23, 2026 (v12: validada en hardware real — cámara CSI, tres bugs reales corregidos: cascada mal calibrada, falso positivo, y buffer USB de la Pico desbordado)
