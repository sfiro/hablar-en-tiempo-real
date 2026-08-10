# CLAUDE.md

Guía de todo el proyecto para trabajar en este repositorio. Cada versión (`v1/`, `v2/`,
`v3/`, `v4/`, `v5/`, `v6/`, `v7/`, `v8/`) tiene su propia documentación detallada;
este fichero es el mapa general y recoge los hechos que cruzan versiones. Empieza
aquí, salta al `CLAUDE-vN.md` o `README-vN.md` de la versión concreta cuando
necesites el detalle de implementación.

## Qué es el proyecto

Un asistente de voz en tiempo real contra la **Realtime API de OpenAI**, que crece por
versiones aditivas: cada una construye sobre la anterior sin romperla.

- **v1** — conversación de voz, dos transportes (WebRTC en navegador, WebSocket en
  terminal). Completa, respaldada con tag `v1.0.0`.
- **v2** — v1 + análisis de emociones de cada frase (`pysentimiento`), mostrado en
  consola. Código completo y probado contra el modelo real; falta validar con una
  conversación hablada de verdad.
- **v3** — v2 + rastreo facial por cámara y (opcional) control de servos vía una
  Raspberry Pi Pico. Código completo (Hito 0 y 1), falta validar con cámara y
  hardware real.
- **v4** — rastreo facial + servos, simplificado y **completamente autónomo**:
  firmware de Pico (`main.py`, MicroPython) + su propia copia del lado Mac
  (`face_tracker.py`, `pico_serial.py`, con `.venv/` propio). Se apartó a propósito
  de la secuencia v1→v2→v3: antes de retomar la integración de voz, se decidió
  organizar el firmware con lo mínimo imprescindible (ojos abiertos + rastreo x,y),
  sin la complejidad de emociones/joystick/modo autónomo. **Completa y validada en
  hardware real**: el usuario confirmó que el rastreo funciona y los ojos siguen el
  rostro correctamente.
- **v5** — v4 + cuello (PAN/TILT, siguiendo a los ojos, amortiguado) + parpadeo
  periódico (cada 2-6s, sin depender de si hay rastreo activo). Sigue sin emociones,
  joystick ni modo autónomo — es el siguiente paso del propio plan que se dejó en
  v4 ("reintroducir complejidad por partes"). **Completa y validada en hardware
  real**, tras abandonar a mitad de la depuración el controlador PCA9685 por PWM
  directo desde la Pico — ver la sección de v5 más abajo.
- **v6** — trae completa la base funcional de v5 (`face_tracker.py`,
  `pico_serial.py`, `diagnostico_canal.py`, sin cambios de lógica) y añade dos
  cosas: `estado_base.py`, un programa independiente de `main.py` que centra
  los 8 servos a 90° y los mantiene ahí; y en `main.py`, una secuencia de
  expresiones faciales que cicla cada 5 segundos en orden fijo, sin depender de
  voz ni sentimiento todavía — primer paso, no la versión final. Tras la
  primera prueba en hardware real se pidieron ajustes de realismo (reposo de
  párpados menos abierto, SORPRENDIDO/FELIZ/SOSPECHA/DORMIDO recalculados,
  cabeza gacha en TRISTE, mirada fija/errática en DUDA/PENSATIVO/NERVIOSO en
  vez de seguir el rastreo). **Completa y validada en hardware real** por el
  usuario tras esos ajustes: "todo ha funcionado bien". Versión cerrada.
- **v7** — misma base de v6, sin cambios de lógica en el firmware. El objetivo
  es juntar, por primera vez, el rastreo facial real (`face_tracker.py`, Mac)
  con la secuencia de expresiones activa: 7 de las 10 emociones
  (NEUTRAL/FELIZ/ENOJADO/TRISTE/SORPRENDIDO/DORMIDO/SOSPECHA) siguen el rostro
  real porque no tocan `LR`/`UD`; las otras 3 (DUDA/PENSATIVO/NERVIOSO) lo
  ignoran a propósito, como ya estaban construidas desde v6. **Completa y
  validada en hardware real** por el usuario, con cámara y Pico funcionando a
  la vez: "funcionó perfecto". Versión cerrada.
- **v8** — junta v1/v2 (voz en tiempo real + análisis de sentimiento) con v6/v7
  (firmware de la Pico + expresiones): la emoción detectada en cada frase de la
  conversación controla ahora la expresión facial del robot. Cambio de fondo en
  `main.py`: ya no cicla sola las 10 expresiones cada 5s — la expresión cambia
  al recibir un `EMOCION` válido por serial, se mantiene 5s (pulso) y vuelve
  sola a NEUTRAL si no llega una nueva. Mapeo pysentimiento→Pico ampliado
  respecto a v3, a pedido explícito: cubre las 7 categorías, ninguna sin
  enviar (antes 5). Dos formas de hablar del lado del Mac: `webrtc_server.py`
  (nuevo, recomendado — voz en el navegador por WebRTC, cancelación de eco
  real, sin el lag ni los paliativos de la terminal; a Python solo le llega
  el texto transcrito, para sentimiento y Pico) y `realtime_voice.py` (v2,
  terminal, se mantiene como alternativa). **Todavía sin rastreo facial** — a
  propósito, pedido explícito del usuario para después (v9). **Completa y
  validada con una conversación real** por el usuario, hablando de verdad por
  el navegador con la Pico física: "ha funcionado muy bien y el robot también
  ha seguido todos los sentimientos". 65 tests. Versión cerrada.

**Regla del proyecto, válida para todas las versiones: ninguna versión importa
código de otra carpeta de versión.** v2 es una copia de v1 con el añadido de
sentimiento, no un import de v1. v4, v5, v6 y v7 tienen sus propias copias de
`face_tracker.py` y `pico_serial.py` (idénticas entre sí, y con v3), no las importan
con una ruta relativa cruzada. v8 sigue el mismo patrón para lo que sí reutiliza
(`pico_serial.py` de v7, `realtime_voice.py`/`sentiment_analyzer.py` de v2), pero
**no** copia `face_tracker.py`: v8 no rastrea el rostro todavía, a propósito (ver
sección de v8), así que ese fichero simplemente no aplica en esta versión —
ausencia deliberada, no un descuido. Esto es deliberado y se pidió
explícitamente: **cada versión debe poder ejecutarse borrando todas las demás
carpetas de versión.** Si añades una versión nueva que reutiliza algo de otra,
copia el fichero, no lo importes. Excepción deliberada: `v5/main_pca9685.py` (la
versión retirada del firmware) no se copió a v6 ni v7, porque no es "base
funcional" — es código explícitamente no usado, y su historial ya vive en
`v5/README-v5.md`.

Cada carpeta de versión de Mac (v1/v2/v3, y la parte Mac de v4/v5/v6/v7/v8) tiene
su propio `.venv/`, `requirements.txt` y `.env`.

**Las piezas que rompen el patrón de venv son `main.py` (v4/v5/v6/v7/v8) y
`estado_base.py` (v6/v7/v8):** no tienen entorno porque no son Python que corra
en el Mac — son firmware MicroPython que se copia a la Pico (con Thonny o
`mpremote`) y se ejecuta ahí. El resto de v4/v5/v6/v7/v8 (`pico_serial.py` y, en
v4-v7, `face_tracker.py`; sus tests) sí sigue el patrón normal de venv, igual
que v1/v2/v3.

## Entorno, por versión

Cada carpeta tiene su propio venv. Usa siempre el Python de ese venv, nunca el del
sistema (los certificados TLS y las dependencias están solo ahí):

```bash
cd v1 && .venv/bin/python realtime_voice.py
cd v2 && .venv/bin/python realtime_voice.py --sentiment
```

`OPENAI_API_KEY` se carga con `python-dotenv` desde el `.env` de cada carpeta de
versión (no hay un `.env` compartido en la raíz). Está en `.gitignore`; nunca lo leas
en voz alta, lo copies fuera de su carpeta, ni lo incluyas en salidas o commits.

## v1 — Voz en tiempo real

Dos programas: [`v1/webrtc_server.py`](v1/webrtc_server.py) (recomendado, WebRTC,
cancelación de eco real del navegador) y [`v1/realtime_voice.py`](v1/realtime_voice.py)
(terminal, WebSocket, sin AEC real — usa paliativos: `MicGate`, `BargeInDetector`,
half-duplex).

**El hecho más importante de v1:** el navegador tiene AEC real
(`getUserMedia({echoCancellation: true})`) y Python con PortAudio no. Por eso la
versión WebRTC no se autointerrumpe con altavoces y la de terminal necesita
compuertas y umbrales para aproximarse a lo mismo. Antes de tocar esos paliativos en
`realtime_voice.py`, pregunta si no conviene simplemente usar `webrtc_server.py`.

Detalle completo, con todos los bugs encontrados y por qué cada pieza está como está:
[`v1/CLAUDE-v1.md`](v1/CLAUDE-v1.md).

## v2 — + Análisis de emociones

[`v2/realtime_voice.py`](v2/realtime_voice.py) es v1 (versión terminal) con
`--sentiment` añadido. [`v2/sentiment_analyzer.py`](v2/sentiment_analyzer.py) es el
clasificador, independiente y reutilizable.

**El hecho más importante de v2:** el modelo (`pysentimiento`, RoBERTuito para
español) clasifica las **6 emociones de Ekman + neutral** (`joy`, `sadness`, `anger`,
`fear`, `surprise`, `disgust`, `others`) — nada más. La primera versión de este
proyecto prometía 10 emociones (incluyendo "esperanza", "empatía") y un modelo
(`bert-base-multilingual-uncased-sentiment`) que en realidad da estrellas de opinión
de producto, no emoción. Se corrigió tras verificar contra la documentación real de
los modelos. **No repitas ese error**: cualquier emoción o modelo nuevo que se
proponga añadir aquí debe verificarse contra su documentación real antes de escribir
código o documentación sobre él.

**Arquitectura de no-bloqueo:** el análisis de una frase (cientos de ms de inferencia)
corre en `loop.run_in_executor(None, analyzer.analyze, texto)`, agendado con
`asyncio.create_task(analyze_and_print(...))` desde `receiver()`. Esto es intencional:
si se llamara a `analyzer.analyze()` directamente dentro de `receiver()`, bloquearía
la lectura de más eventos del websocket (incluidos los deltas de audio) mientras
corre la inferencia, causando cortes de audio perceptibles.

**Dos bugs reales encontrados verificando con ejecución real** (no solo `py_compile`):
1. `asyncio.create_task(loop.run_in_executor(...))` fallaba con `TypeError`:
   `run_in_executor` devuelve un `Future`, no una corrutina — no se envuelve en
   `create_task`, se usa directamente.
2. Imprimir el resultado de la emoción sin un `\n` inicial hacía que apareciera en
   medio del streaming de texto del otro lado (`print(delta, end="")` de la
   transcripción en curso). Se corrigió con el mismo patrón de `\n` inicial que ya
   usan los demás avisos asíncronos del script (`⏹️`, `⚠️`, `✂️`).

**Precisión real del modelo, verificada, no supuesta:** acierta claro en frases
elaboradas con carga emocional explícita ("no puedo creerlo, es una sorpresa total" →
SORPRESA 0.98) y falla más en exclamaciones cortas ("qué sorpresa tan grande" →
ALEGRÍA 0.80, incorrecto). También da falsos positivos ocasionales en frases neutras
("el cielo es azul" → ALEGRÍA 0.57, que supera el umbral por defecto de 0.5). Tabla
completa en [`v2/README-v2.md`](v2/README-v2.md), sección "Limitaciones conocidas".

Tests: [`v2/tests/test_sentiment.py`](v2/tests/test_sentiment.py). Dos grupos: lógica
interna (con un analizador falso inyectado, no necesitan el modelo real) e integración
con el modelo real (una frase por cada una de las 6 emociones, marcadas
`@requiere_modelo_real`, se saltan si falta `pysentimiento`).

Detalle de hitos y estado: [`v2/PLAN-v2.md`](v2/PLAN-v2.md).

## v3 — + Rastreo facial y servos

Hito 0 (investigación) y Hito 1 (rastreador facial + enlace serial, ambos con tests)
completos. Falta validar con cámara y hardware real. Antes de escribir nada, se
investigó a fondo un **proyecto hermano y anterior del mismo usuario**,
[`ojosMecanicos`](/Users/debbie/Desktop/programacion/ojosMecanicos/) — un sistema de
servos (Raspberry Pi Pico) con varios intentos previos de integrar voz y cámara.
Léelo antes de tocar v3: [`v3/README-v3.md`](v3/README-v3.md), sección "Antes de
escribir código".

[`v3/face_tracker.py`](v3/face_tracker.py) tiene la clase `FaceTracker`
(detección + EMA + zona muerta, **headless por diseño** — nunca toca `cv2.imshow`,
para poder usarse desde un hilo de fondo en el Hito 2) y un script standalone con
ventana opcional (`--no-window`) para probar la cámara sola.
[`v3/pico_serial.py`](v3/pico_serial.py) tiene `PicoLink` (cola de comandos, hilo
`daemon=True`, reconexión, latido). Ninguno de los dos se ha probado todavía con
hardware real (cámara con permiso concedido, Pico física) — solo con dobles de
prueba inyectados. 19 tests en [`v3/tests/`](v3/tests/), todos pasan.

**Dos bugs reales encontrados en este hito, ninguno en la lógica de negocio en sí:**
1. `opencv-python` 5.0 (versión recién publicada al escribir esto) eliminó
   `cv2.CascadeClassifier` del paquete base — se movió a `opencv-contrib-python`.
   Se instaló primero sin fijar versión y falló con `AttributeError` al construir
   `FaceTracker`. Fijado `opencv-python>=4.9,<5` en `requirements.txt`.
2. El chequeo de reconexión de `PicoLink` (`glob.glob(puerto)` para ver si el
   `/dev/cu.usbmodem...` sigue existiendo) rompía los tests: con un puerto de prueba
   inyectado que no existe en el filesystem real, el hilo creía que la Pico se
   había desconectado justo después de "conectar". Se corrigió para que ese chequeo
   solo se haga con el driver real de pyserial, nunca con un `serial_factory`
   inyectado — `_puerto_sigue_existiendo()` lo aísla.

**Corrección menor adaptando el código de referencia:** `rastreoCara_Mac.py` convertía
a gris con `cv2.COLOR_RGB2GRAY` sobre un frame que en realidad viene en BGR de
`cv2.VideoCapture`. Cambiado a `COLOR_BGR2GRAY` en `face_tracker.py`. Efecto mínimo
(los pesos de canal son parecidos) pero es la conversión correcta.

**Cómo se probó la lógica sin hardware:** los Haar cascades no se pueden probar de
forma fiable contra una imagen sintética (necesitan rasgos faciales reales), así que
`tests/test_face_tracker.py` inyecta una cascada falsa (`FakeCascada`) que devuelve
bboxes fijas, y testea solo la matemática (mapeo a grados, suavizado EMA, zona
muerta) — no la precisión de detección en sí. Mismo patrón que
`tests/test_pico_serial.py` con un `serial_factory` falso. Esto separa "¿la lógica de
seguimiento es correcta?" (testeable sin hardware) de "¿detecta rostros de verdad?"
(solo verificable con cámara real).

**Confirmado en ejecución real, no solo supuesto:** al intentar abrir la cámara en
este entorno (sandboxed, no interactivo), macOS respondió
`OpenCV: not authorized to capture video` — el mismo tipo de bloqueo de permisos que
ya se dio con el micrófono en v1. El código respondió como estaba diseñado: mensaje
claro, sin traceback, `sys.exit(1)`. La verificación real de detección de rostro
necesita que el usuario conceda el permiso de cámara en su propia Terminal.

### Lo reutilizado de la investigación de ojosMecanicos

**Probado, no reinventar:**
- **Protocolo serial hacia la Pico:** `"{LR},{UD},{EMOCION}\n"` (o sin emoción,
  `"{LR},{UD}\n"`), enteros 40-140 para los grados de servo, `EMOCION` opcional en
  mayúsculas de un enum de 10 valores (`NEUTRAL`, `FELIZ`, `ENOJADO`, `TRISTE`,
  `SORPRENDIDO`, `DORMIDO`, `DUDA`, `SOSPECHA`, `PENSATIVO`, `NERVIOSO`), baud 115200.
- **Latido:** con control remoto activo, reenviar el último comando cada 1s o el
  firmware de la Pico vuelve a modo autónomo.
- **Reconexión:** en macOS, comprobar si el path `/dev/cu.usbmodem...` sigue
  existiendo para detectar la desconexión de la Pico.
- **Regla de threading:** `cv2.imshow`/`waitKey` bloqueante vive en su propio hilo
  `daemon=True`, nunca mezclado con `asyncio.run()`. Coincide con el patrón que v1/v2
  ya usan para PortAudio (hilos propios, cruzando al loop con
  `call_soon_threadsafe`) — la misma disciplina aplica al hilo de cámara y al de Pico.

**Lo que NO se reutiliza:** el análisis de sentimiento de `ojosMecanicos` (palabras
clave en español + `TextBlob`, que analiza en inglés por defecto y es casi inerte
sobre español). El `pysentimiento` de v2 ya es más sofisticado y ya está verificado.

**El bug a no repetir:** el único intento de puente voz+emoción+cámara en
`ojosMecanicos` (`08_voz_emociones_ojos_integrado.py`) arranca los hilos de cámara y
de posición, pero la función que debía conectar la emoción detectada con el comando
serial **nunca se invoca** — código muerto, los hilos corren pero la información real
nunca fluye entre ellos. Cuando se implemente el Hito 2.3 de
[`v3/PLAN-v3.md`](v3/PLAN-v3.md) (cablear sentimiento → comando serial), hace falta un
test explícito que verifique que la emoción llega de verdad al comando encolado, no
solo que los hilos arrancan sin excepción.

**Mapeo de emoción (pysentimiento → vocabulario de la Pico)**, sin correspondencia
1 a 1 perfecta — declarado así a propósito, no se inventa precisión que no existe:

| pysentimiento | Comando Pico | Nota |
|---|---|---|
| joy | FELIZ | directo |
| sadness | TRISTE | directo |
| anger | ENOJADO | directo |
| fear | NERVIOSO | no hay "MIEDO" en el vocabulario de la Pico |
| surprise | SORPRENDIDO | directo |
| disgust | NEUTRAL | no hay equivalente; se degrada en vez de inventar uno |
| others | NEUTRAL | directo |

**Nota:** esta es la tabla tal como se documentó en v3 (nunca llegó a
enviarse de verdad a una Pico en esa versión). v8, que sí la usa en vivo,
revisó la fila de `disgust` — ver la sección de v8 más abajo.

## v4 — Rastreo facial + servos, simplificado y autónomo

[`v4/main.py`](v4/main.py) es un **subconjunto deliberado** de
[`ojosMecanicos/main.py`](/Users/debbie/Desktop/programacion/ojosMecanicos/main.py):
solo párpados abiertos (una vez, al arrancar) + rastreo x,y con el mismo suavizado
EMA (`ALPHA=0.1`) y la misma fórmula de pulso PCA9685, copiadas literalmente del
original, no reinventadas. Quita a propósito: joystick, modo autónomo, las 10
emociones y su sincronía con la mirada, y el parpadeo automático/manual. Todo eso
sigue intacto en `ojosMecanicos/main.py` — v4 no lo reemplaza, es una rama de
desarrollo paralela y más simple, para confirmar el movimiento base antes de volver
a montar la complejidad encima.

**Motivo del pivote:** el usuario pidió expresamente organizar el firmware de la
Pico *antes* de retomar la integración de voz (Hito 2 de v3). La secuencia de
versiones no es v1→v2→v3→v4 en el sentido de "cada una añade sobre la última": v4 es
un desvío sobre una pieza distinta del sistema (el firmware, no el cliente de Mac),
que se debe resolver antes de continuar v3.

**v4 es autónoma, no solo el firmware.** [`v4/face_tracker.py`](v4/face_tracker.py) y
[`v4/pico_serial.py`](v4/pico_serial.py) son **copias** de las de `v3/` (no imports),
con su propio `v4/requirements.txt` (más ligero que el de v3: solo `opencv-python<5`
y `pyserial`, sin `pysentimiento`/`torch` porque v4 no toca voz ni sentimiento) y su
propio `.venv/`. Los 19 tests de v3 (`test_face_tracker.py`, `test_pico_serial.py`)
también están duplicados en `v4/tests/` y pasan igual, ejecutados enteramente dentro
de `v4/` sin tocar `v3/`. Esto se pidió explícitamente: cada versión debe poder
ejecutarse borrando todas las demás. Si tocas `face_tracker.py` o `pico_serial.py`
para arreglar algo en v4, ese arreglo **no** se propaga solo a v3 — hay que
replicarlo a mano en la otra copia si aplica también ahí.

**Compatibilidad de protocolo, verificada por diseño, no por casualidad:** v4 acepta
tanto `"LR,UD\n"` como `"LR,UD,EMOCION\n"` (ignorando el tercer campo), así que su
propio `pico_serial.py` —que ya sabe mandar ambos formatos— habla con esta Pico sin
ningún cambio.

**Cómo se verificó:**
- Antes de tener la Pico delante: `py_compile` + `ast.parse` (sintaxis), la fórmula
  de pulso del PCA9685 aislada (0°→102, 90°→307, 180°→512, idéntica al original), y
  el parseo de comandos (acepta ambos formatos, recorta 40-140, rechaza basura).
- **Con la Pico real, por el usuario:** confirmado que el PCA9685 responde por I2C,
  los párpados quedan abiertos, y el rastreo x,y funciona con el suavizado sintiéndose
  fluido — "los ojos lo siguen perfectamente". Las tres cosas que no se podían
  verificar desde este entorno quedaron confirmadas.
- Los 19 tests, corridos dentro de `v4/.venv` sin ninguna referencia a `v3/`.

**No refactorices esto para hacerlo "más testeable" sin que te lo pidan.** El
usuario pidió explícitamente "el main.py más simple posible" — envolver la lógica en
clases o abstracciones extra por facilidad de testing iría en contra de ese pedido.
La verificación de la matemática pura se hizo con scripts sueltos, no integrados al
fichero final, a propósito.

## v5 — + Cuello y parpadeo

[`v5/main.py`](v5/main.py) añade, sobre la base de v4, dos cosas pedidas
explícitamente por el usuario: "rotación de la cabeza, el subir y bajar de la
cabeza y el parpadeo, mientras hace el rastreo de los ojos".

- **Cuello (PAN/TILT):** dos ejes más en el mismo sistema
  `objetivo_actual`/`posicion_actual`/EMA que ya usaban LR/UD en v4. El objetivo de
  PAN/TILT se recalcula cada vuelta del bucle a partir del objetivo de LR/UD (no del
  valor ya suavizado), con los factores de amortiguación de `ojosMecanicos/main.py`
  (0.8 horizontal, 0.6 vertical) — copiados literalmente, no reinventados.
- **Parpadeo:** temporizador aleatorio de 2-6s, independiente de si hay comandos
  serial llegando. Reabre siempre a la posición fija "abierta", no a un objetivo
  variable, porque v5 no tiene emociones ni sincronía párpado-mirada todavía.

**v5 es autónoma exactamente igual que v4:** [`v5/face_tracker.py`](v5/face_tracker.py)
y [`v5/pico_serial.py`](v5/pico_serial.py) son copias de las de v4, con su propio
`.venv/` y tests. Si arreglas algo en esos dos ficheros estando en v5, ese arreglo
no se propaga a v3/v4 — replícalo a mano si aplica.

### El PCA9685 se abandonó a mitad de la depuración — no lo reintroduzcas sin releer esto

`v5/main.py` **no usa PCA9685 ni I2C**. Genera el PWM de cada servo directamente
desde `machine.PWM` en 8 pines de la Pico
(`LR=GP2 UD=GP3 TL=GP4 BL=GP5 TR=GP6 BR=GP7 PAN=GP8 TILT=GP9`). Esto no fue la
decisión de diseño de partida: v5 empezó con PCA9685 (igual que v3/v4 y
`ojosMecanicos`), y ese enfoque sigue existiendo, **archivado y marcado como "no
usar"**, en [`v5/main_pca9685.py`](v5/main_pca9685.py).

**Por qué se abandonó**, verificado en hardware real, no solo sospechado: con
PCA9685, v5 daba tres síntomas — temblor aleatorio en todos los servos al conectar
la alimentación, un temblor periódico (cada ~5s) que resultó estar disparado por
el propio parpadeo, y el eje PAN sin moverse en absoluto. Se intentaron varios
arreglos (gating del pin `/OE`, subir el espaciado entre servos del parpadeo de
10ms a 50ms) — el primero funcionó parcialmente, el segundo **empeoró** el
problema (de "cada 5s" a "continuo, sin pausas"). Al eliminar el PCA9685 por
completo, los tres síntomas desaparecieron a la vez, incluido PAN, que nunca se
había tocado en ese cambio — evidencia de que los tres compartían el mismo origen
(el chip o la comunicación I2C con él), no la fuente de alimentación ni un bug de
temporización del firmware. Cronología completa, con cada intento fallido, en
[`v5/README-v5.md`](v5/README-v5.md#historial-de-depuración-completo) — léela
antes de considerar volver a un controlador PWM externo en una versión futura.

**Cómo se verificó:**
- Sin hardware: sintaxis, [`v5/tests/test_main_math.py`](v5/tests/test_main_math.py)
  (conversión de grados a PWM directo, amortiguación del cuello, y un test cruzado
  que confirma que la fórmula de PWM directo da la misma posición física que la
  fórmula de pulso del PCA9685 archivado — diferencia < 5µs en todo el rango)
- Con la Pico real, por el usuario: "todos los motores se mueven y parpadea sin
  vibraciones" — confirmado también que PAN funciona, sin que se hubiera tocado
  nada específico de ese eje en el cambio de arquitectura
- **Un hallazgo de despliegue, no de código:** `File "<stdin>"` en un
  `SyntaxError` al cargar el firmware es la firma de que Thonny está pegando el
  código por el REPL (botón ▶ Run) en vez de guardarlo como `main.py` en el
  sistema de archivos de la Pico y reiniciarla. Guardarlo explícitamente
  (`Archivo → Guardar como → Raspberry Pi Pico`) + reinicio físico lo resuelve.
- **No verificado todavía:** sesión larga sin reinicios ni degradación

## v6 — Estado base + secuencia de expresiones

[`v6/estado_base.py`](v6/estado_base.py) es un programa **independiente de
`main.py`** que lleva los 8 servos a 90° (uno a uno, con el mismo espaciado de
0.1s contra picos de corriente que usa `main.py` al arrancar) y luego no hace
nada más — el PWM de la Pico mantiene la señal sola. Pensado para dejar el rig
en una posición segura antes de desconectar la alimentación, o para recuperar
un estado neutral tras un error.

`estado_base.py` usa la misma fórmula de conversión de grados a PWM y el mismo
mapeo de pines que `main.py` (`LR=GP2 UD=GP3 TL=GP4 BL=GP5 TR=GP6 BR=GP7 PAN=GP8
TILT=GP9`) — verificado con un test
([`v6/tests/test_estado_base.py`](v6/tests/test_estado_base.py)) que compara el
`duty_u16` de 90° calculado por ambos programas, para que "90°" sea la misma
posición física en los dos.

**[`v6/main.py`](v6/main.py) añade la secuencia de expresiones faciales**, lo
segundo nuevo de esta versión. Cicla en orden fijo por las 10 emociones de
`ojosMecanicos/main.py` (`OFFSETS_EMOCIONES`, copiadas literalmente y
reverificadas contra el original antes de usarlas), una cada 5 segundos — sin
depender de voz ni sentimiento todavía, es el primer paso. Detalles del
mecanismo:

- Los offsets de párpados se aplican sobre `PARPADOS_REPOSO` (una posición de
  reposo fija, no el 100% abierto — ver el ajuste de realismo más abajo) y se
  recortan con `LIMITES_PARPADOS` (min, max por canal, copiado de
  `servo_limits`). El offset de `TILT` se suma al que ya calcula
  `actualizar_objetivo_cuello()`; el de `PAN` no se aplica porque en las 10
  emociones originales siempre es 0.
- Los párpados entran al mismo sistema de suavizado EMA que `LR/UD/PAN/TILT`,
  para que el cambio de expresión sea gradual.
- `parpadear()` no se dispara con `DORMIDO` activo (mismo criterio que el
  original) y, al reabrir, vuelve a `objetivo_actual` (la posición de la
  expresión activa), no siempre a "abierto".

**Ajuste de realismo, tras probar Hitos 1-3 en hardware real:** el usuario
pidió varios cambios para que las expresiones se distingan mejor. El más
importante — `PARPADOS_REPOSO` — resuelve de raíz un hallazgo real detectado
antes de esa prueba: con `NEUTRAL` en el 100% abierto, **SORPRENDIDO clampaba
en los 4 canales** (su offset empuja hacia "más abierto todavía", sin margen
mecánico) y no se distinguía de `NEUTRAL`. En vez de añadir sincronía
párpado-mirada (fuera de alcance), se bajó el reposo a un 40% de cierre —
mínimo con margen cómodo en los 4 canales de SORPRENDIDO (TR es el canal más
exigente, ~34% mínimo teórico). Efecto colateral esperado: `DORMIDO` (offsets
sin cambiar) ahora clampa en los 4 canales y cierra los párpados por completo
(antes solo 2 canales) — coherente con la expresión, no un problema. `FELIZ` y
`SOSPECHA` se recalcularon en términos absolutos (el offset original de
`ojosMecanicos`, pensado para una base 100% abierta, casi no se notaba sobre el
nuevo reposo): FELIZ sube los párpados inferiores un 50% del camino restante
hacia cerrado; SOSPECHA cierra los 4 canales un 80%. Además, `DUDA` y
`PENSATIVO` ahora **ignoran el rastreo facial y fijan la mirada** mientras
duran: DUDA barre `LR` de un extremo a otro (40↔140, 2.5s por tramo, ida y
vuelta completa en los 5s de la expresión); PENSATIVO fija `LR=40, UD=40`
(arriba-izquierda; UD bajo es "arriba" en este montaje). `NERVIOSO` usa el
mismo mecanismo con saltos discretos al azar: cada 1s, `LR`/`UD` saltan a un
punto al azar en un rango moderado (65–115), como "mirando a cualquier lado
sin buscar contacto visual" (pedido explícito). El cuello acompaña los tres
gestos porque sigue leyendo el mismo `objetivo_actual[LR]/[UD]`. Al cambiar de
expresión, si la que termina era DUDA, PENSATIVO o NERVIOSO, la mirada se
reinicia al centro — corrige un bug real donde la siguiente expresión heredaba
la mirada desviada. Además, TRISTE fuerza `TILT` directamente a su mínimo
mecánico (cabeza gacha) en vez de sumar un offset relativo al TILT del
seguimiento del cuello — pedido explícito, para que se note siempre igual sin
depender de hacia dónde esté mirando el rastreo. Detalle completo en
[`v6/README-v6.md`](v6/README-v6.md), sección "Ajustes de realismo tras probar
en hardware real".

**El resto de v6 es la base funcional de v5, copiada sin cambios de lógica:**
`face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`. Si tocas alguno de
esos ficheros estando en v6, el arreglo no se propaga solo a v5 — replícalo a
mano si aplica también ahí. `main_pca9685.py` (la versión retirada con
PCA9685) **no** se copió a v6 a propósito: no es "base funcional", es código no
usado, y su historial ya vive en `v5/README-v5.md`.

**Cómo se verificó:** sintaxis de los 6 ficheros, y 49 tests (los heredados de
v5 + 4 para `estado_base.py` + los de la secuencia de expresiones y sus
ajustes de realismo) corriendo dentro de `v6/.venv` sin ninguna referencia a
`v5/`. **Completa y validada en hardware real por el usuario:** la base de v5,
`estado_base.py`, la secuencia de expresiones y los diez ajustes de realismo
(reposo al 40%, SORPRENDIDO/FELIZ/SOSPECHA/DORMIDO recalculados, barrido de
DUDA, mirada fija de PENSATIVO, cabeza gacha de TRISTE, saltos al azar de
NERVIOSO, y el recentrado de mirada al cambiar de expresión) — confirmado:
"todo ha funcionado bien", incluida la interacción entre el temporizador de
parpadeo, el de cambio de expresión, y los overrides de mirada, sin problema
observado. Versión cerrada.

## v7 — Seguimiento visual real + secuencia de expresiones

[`v7/main.py`](v7/main.py) es una copia de [`v6/main.py`](v6/main.py) **sin
ningún cambio de lógica** — solo referencias de documentación actualizadas
(título, mensajes de arranque, punteros a README-v7.md/PLAN-v7.md). El
objetivo de v7 no es cambiar el firmware, sino juntar y validar por primera
vez dos piezas que hasta ahora se habían probado por separado: el rastreo
facial real de una persona (`face_tracker.py`, en el Mac, enviando `LR,UD` por
serial) y la secuencia de expresiones activa (que hasta ahora solo se probó
sin cámara conectada, o sin la secuencia corriendo a la vez).

**El mecanismo ya existía en v6, sin proponérselo como objetivo explícito:**
en el bucle principal, `procesar_comando()` actualiza `objetivo_actual[LR]/
[UD]` cada vez que llega un comando serial; después,
`actualizar_objetivo_mirada_expresion()` solo sobreescribe esos valores para
`DUDA`, `PENSATIVO` y `NERVIOSO` — para las otras 7 emociones
(`NEUTRAL`/`FELIZ`/`ENOJADO`/`TRISTE`/`SORPRENDIDO`/`DORMIDO`/`SOSPECHA`) no
hace nada, así que la mirada real que llegó por serial queda intacta y el
offset de cada emoción se aplica encima de ella, no en su lugar. v7 promueve
esta distinción a objetivo central de la versión, documentándola con
claridad en [`v7/README-v7.md`](v7/README-v7.md) en vez de dejarla como un
detalle interno de implementación.

**Corregidas de paso, encontradas al copiar los ficheros** (stale desde hacía
varias versiones, no introducidas por v7): `v6/requirements.txt` seguía con un
comentario de cabecera que decía "v4" (arrastrado sin corregir desde v4→v5→v6);
el docstring de `face_tracker.py`/`pico_serial.py` decía "copia idéntica de
`../v4/...`" en vez de mencionar la copia inmediata real; y el docstring de
`tests/test_main_math.py` apuntaba a "README-v6.md, Historial de depuración"
para la historia del PCA9685, cuando esa sección en realidad solo existe en
`v5/README-v5.md` — nunca se copió a v6. Las tres corregidas en v7; no se
tocó v6 para no introducir cambios fuera de lo pedido en esa versión ya
cerrada.

**Cómo se verificó:** sintaxis de los 5 ficheros `.py`, y los mismos 49 tests
de v6 (sin cambios, porque la matemática no cambió) corriendo dentro de
`v7/.venv` sin ninguna referencia a `v6/`. **Completa y validada en hardware
real por el usuario:** con cámara y Pico funcionando a la vez y la secuencia
de expresiones activa — "funcionó perfecto". Versión cerrada.

## v8 — Voz + sentimiento controlando la expresión facial

Junta lo construido en v1/v2 (voz en tiempo real + análisis de sentimiento)
con lo construido en v6/v7 (firmware de la Pico + expresiones): la emoción
detectada en la conversación controla ahora la expresión facial. Pedido
explícito del usuario, con un alcance acotado a propósito: **todavía sin
rastreo facial** — eso queda para v9, después de validar que voz + sentimiento
+ expresión funcionan bien juntos.

**Del lado del Mac** ([`v8/realtime_voice.py`](v8/realtime_voice.py),
[`v8/sentiment_analyzer.py`](v8/sentiment_analyzer.py)): copias de v2, sin
cambios de lógica en la conversación de voz ni en el análisis de sentimiento.
Lo nuevo: con `--sentiment` y una Pico conectada (autodetectada, igual patrón
que `face_tracker.py` en versiones anteriores), cada emoción por encima de
`--confidence-threshold` se traduce con `EMOTION_TO_PICO` y se envía por
serial. Pedido explícito del usuario: **las 7 categorías de pysentimiento
mapean a alguna de las 10 expresiones del robot, ninguna se queda sin
enviar.** Las 5 de siempre (joy→FELIZ, sadness→TRISTE, anger→ENOJADO,
fear→NERVIOSO, surprise→SORPRENDIDO) más dos revisadas respecto a v3:
`disgust`→`SOSPECHA` (no `NEUTRAL` como en la tabla de v3 — se degrada a la
expresión más parecida facialmente, párpados entrecerrados y mirada de
rechazo, mismo criterio que fear→NERVIOSO) y `others`→`NEUTRAL` (corresponde
1 a 1). `DORMIDO`/`DUDA`/`PENSATIVO` se quedan sin usar: no hay categoría de
pysentimiento que les corresponda ni de lejos, y forzar una sería inventar
precisión que no existe — para que aparezcan haría falta otro mecanismo
(p. ej. function-calling del propio modelo de voz, como hacía `ojosMecanicos`
— ver `model.md`). Efecto colateral aceptado de que `others` ahora sí envíe
`NEUTRAL`: una frase neutra puede cortar antes de tiempo el pulso de una
expresión real en curso (antes no pasaba). Nueva opción `--no-pico` para
probar sentimiento sin tocar la Pico.

**Segundo cambio, pedido tras probar `realtime_voice.py`:** el usuario sintió
que la conversación por terminal (medio-dúplex, interrumpir con Enter) no daba
la conversación instantánea que quería, y pidió lo que v1 ya resuelve para
ese mismo problema — que la voz viva en el navegador. Nuevo
[`v8/webrtc_server.py`](v8/webrtc_server.py) + [`v8/static/index.html`](v8/static/index.html),
copiados de v1 sin cambios en la negociación SDP/WebRTC en sí, más un
endpoint nuevo, `POST /api/analyze-sentiment`: con WebRTC, el audio y la
transcripción van directo entre el navegador y OpenAI por el canal de datos
`oai-events`, así que `webrtc_server.py` nunca ve ni un byte de la
conversación — el navegador manda el texto de cada frase completa a ese
endpoint, que hace el mismo análisis y envío a la Pico que `realtime_voice.py`.
`EMOTION_TO_PICO` está duplicado a propósito en los dos ficheros (mismo
criterio de "copiar, no importar" que entre carpetas de versión, aplicado
aquí dentro de la misma carpeta); `tests/test_webrtc_server.py` comprueba que
no diverjan. `realtime_voice.py` se mantiene sin cambios de comportamiento,
como alternativa para probar sin navegador.

**Del lado de la Pico** ([`v8/main.py`](v8/main.py)): **este es el cambio de
fondo de la versión.** En v6/v7, la expresión cambiaba sola cada 5s, cicladas
en un orden fijo. En v8, un modelo dirigido por eventos la reemplaza: al
recibir `"LR,UD,EMOCION\n"` con un EMOCION válido (antes se aceptaba ese campo
pero se ignoraba, desde v3), la Pico adopta esa expresión y la mantiene
`INTERVALO_EXPRESION_MS` (5000ms, el mismo valor de antes, reusado como
duración del pulso); si no llega una nueva a tiempo, vuelve sola a NEUTRAL.
Una nueva función, `cambiar_emocion()`, centraliza el cambio de expresión
(antes vivía solo en el bloque del ciclo fijo) y la reutilizan tanto
`procesar_comando()` como la expiración del pulso — conserva sin cambios el
recentrado de mirada al salir de DUDA/PENSATIVO/NERVIOSO y el reinicio de sus
temporizadores al entrar, ya construidos en v6/v7.

**Por qué no hay `face_tracker.py` en v8:** ausencia deliberada, no un
descuido — LR/UD se mandan fijos a 90,90 junto con cada EMOCION, porque esta
versión no tiene cámara conectada. El rastreo real es v9.

**Cómo se verificó:** sintaxis de los 7 ficheros, y 65 tests (heredados de v2
y v7 sin cambios, más `test_main_math.py` reescrito para el mecanismo de
pulso y `test_webrtc_server.py` nuevo, que compara el `EMOTION_TO_PICO` de
los dos ficheros del Mac) corriendo dentro de `v8/.venv` sin ninguna
referencia a `v2/` ni `v7/`. Antes de la conversación real: `realtime_voice.py
--sentiment` con una clave de API inválida a propósito confirmó entorno, TLS
y conexión a la Pico; `webrtc_server.py --sentiment --no-browser` confirmó
que el endpoint nuevo clasifica y envía a la Pico bien, sin necesitar
siquiera una clave de API. **Completa y validada con una conversación real
por el usuario:** clave de API válida, hablando de verdad por el navegador,
con la Pico física — las 6 frases de prueba (una por emoción no neutral,
ver `v8/README-v8.md`) movieron la expresión correcta: "ha funcionado muy
bien y el robot también ha seguido todos los sentimientos". Versión cerrada.

## Cómo verificar cambios (todas las versiones)

Ninguna versión se puede validar completamente de forma automatizada: todas necesitan
un humano hablando (v1, v2) o además una cámara y posiblemente hardware serial (v3).
Lo que sí se puede verificar sin eso:

- **Arranque y esquema de sesión.** Lanza el script en segundo plano redirigiendo la
  salida, espera unos segundos, lee el log, mátalo:
  ```bash
  .venv/bin/python -u realtime_voice.py > /tmp/rt.log 2>&1 &
  sleep 10; cat /tmp/rt.log; pkill -f realtime_voice.py
  ```
  Un arranque sano llega a `🎙️ Listo.` sin más líneas. Los errores de esquema de
  sesión **no abortan el proceso** — solo imprimen `⚠️ Error de la API` — así que hay
  que leer el log siempre, no solo comprobar que el proceso sigue vivo.
- **Con una clave inválida**, el fallo esperado es
  `ConnectionClosedError: … invalid_api_key`. Eso confirma que el resto de la cadena
  (audio, `.env`, TLS) funciona y el único problema es la credencial.
- **Lógica sin la API** (v2 en adelante): tests con un doble de prueba inyectado
  (`analyzer._analyzer = FakeAnalyzer(...)`) para lo que no necesita el modelo real,
  y un grupo separado marcado que sí lo descarga, para verificar contra el
  comportamiento real y no solo contra una simulación.
- **Nunca asumas que un fix funciona por `py_compile`.** Los dos bugs de v2 (ver
  arriba) solo aparecieron ejecutando el script de verdad contra la API. Compilar
  limpio no prueba que el código corra bien.

## Estilo

Código y comentarios en español. Comentarios escasos y solo donde el porqué no sea
evidente — no describir qué hace el código si el nombre ya lo dice. Cuando se
documenten resultados de un modelo o medición (precisión, latencia, límites), usar
datos reales obtenidos ejecutando el código, no cifras plausibles inventadas. Si algo
se corrige por ser inexacto (como el modelo de sentimiento original), dejar constancia
de la corrección y por qué, no solo el estado final — ayuda a no repetir el error.
