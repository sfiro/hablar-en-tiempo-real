# Hoja de ruta de versiones

Documento de planificación y seguimiento de releases.

---

## v1.0.0 ✅ — Completado (Agosto 2026)

**Objetivo:** Demostrar conversación en tiempo real sin autointerrupción en macOS.

**Completado:**
- ✅ Versión WebRTC con cancelación de eco del navegador
- ✅ Versión terminal con paliativos contra eco (half-duplex, MicGate, BargeInDetector)
- ✅ Cancelación de eco real probada y funcionando
- ✅ Barge-in natural: interrumpir al asistente hablando
- ✅ Documentación completa: README, CLAUDE.md, especificación Raspberry Pi
- ✅ Repositorio local con versionado git

**Descarga:**
- Rama: `main` (último tag: `v1.0.0`)
- ZIP: GitHub Releases → v1.0.0

**Uso:**
```bash
cd v1
python webrtc_server.py      # Recomendado
# o
python realtime_voice.py     # Terminal
```

---

## v2.0.0 🔄 — Código completo, validación pendiente

**Objetivo cambiado respecto al plan original:** en vez de Raspberry Pi 5, v2 pasó a
ser análisis de emociones en tiempo real. Raspberry Pi 5 se aparcó — la especificación
en [`docs/RASPBERRY-PI.md`](docs/RASPBERRY-PI.md) sigue siendo válida, pero no es el
objetivo actual de v2. Se retomará como una versión futura si hace falta.

**Corrección importante durante el desarrollo:** el primer modelo elegido
(`bert-base-multilingual-uncased-sentiment`) en realidad da estrellas de opinión de
producto (1-5), no una emoción. Se sustituyó por `pysentimiento`, verificado antes de
escribir la versión final: clasifica de verdad las 6 emociones de Ekman + neutral.

**Hito 1: Análisis básico (COMPLETADO Y VERIFICADO)**
- ✅ `sentiment_analyzer.py` con `pysentimiento` (RoBERTuito para español)
- ✅ Integración en `realtime_voice.py` sin bloquear el audio (`run_in_executor`)
- ✅ Visualización en consola: emoji + etiqueta + confianza
- ✅ `--stats`: resumen de emociones al terminar la conversación
- ✅ Dos bugs reales encontrados y corregidos en ejecución real (ver CLAUDE.md)

**Hito 2: Validación y refinamiento (COMPLETADO salvo un punto)**
- ✅ Tests de integración con el modelo real: las 6 emociones de Ekman, todos pasan
- ✅ Umbral de confianza documentado con datos reales (no supuestos)
- [ ] **Conversación real hablada** — la única tarea que falta en todo v2, y depende
  de que alguien hable de verdad con `--sentiment` (no se puede automatizar)

**Descarga:** aún sin tag propio; código en `v2/` sobre `main`.

**Uso:**
```bash
cd v2
python realtime_voice.py --sentiment --stats
```

---

## v3.0.0 📋 — Rastreo facial y servos (planificación)

**Objetivo:** Mostrar la posición x,y del rostro en consola junto al sentimiento, y
opcionalmente enviarla —junto con la emoción, traducida a su vocabulario— por serial a
una Raspberry Pi Pico que mueve servos.

**Hito 0: Investigación (COMPLETADO)**
- ✅ Investigado un proyecto hermano (`ojosMecanicos`) antes de escribir código
- ✅ Confirmado que no existe ahí una integración funcional voz+emoción+cámara+servos
- ✅ Identificado y documentado un bug de diseño real en su intento de puente (hilos
  arrancados, pero la emoción nunca conectada al movimiento — código muerto)
- ✅ Protocolo serial de la Pico confirmado y reutilizable (formato, baud, latido,
  reconexión)
- ✅ Tabla de mapeo emoción→vocabulario de la Pico definida

**Hito 1: Rastreo facial standalone (COMPLETADO en código, falta hardware real)**
- ✅ `v3/face_tracker.py`: clase `FaceTracker` headless + script standalone con
  ventana opcional (`--no-window`)
- ✅ `v3/pico_serial.py`: `PicoLink` con reconexión y latido
- ✅ 19 tests (`v3/tests/`), todos pasan, sin necesitar cámara ni Pico reales
- ✅ Dos bugs reales corregidos: `opencv-python` 5.0 eliminó `CascadeClassifier`
  (fijado `<5`); el chequeo de reconexión rompía con puertos de prueba inyectados
  (aislado para hardware real únicamente)
- [ ] Validar con cámara real — bloqueado por permisos de macOS en este entorno,
  necesita que el usuario lo pruebe en su propia Terminal
- [ ] Validar con la Pico física, si está disponible

**Hito 2: Integración con voz + sentimiento**
- [ ] Hilo de cámara + hilo de Pico arrancados desde `realtime_voice.py`
- [ ] x,y visible en consola junto al sentimiento
- [ ] Sentimiento cableado de verdad al comando serial, con test que lo confirme —
  la lección aprendida de `ojosMecanicos`

**Hito 3: Validación con hardware real** (cámara, y si está disponible, la Pico)

**Hito 4: Documentación**

Detalle completo: [`v3/PLAN-v3.md`](v3/PLAN-v3.md).

**Estimado:** sin fecha todavía, depende de completar la validación de v2 primero.

---

## v4.0.0 ✅ — Rastreo facial + servos, simplificado y autónomo (completa y validada)

**Objetivo:** antes de retomar v3, organizar el firmware de la Pico con lo mínimo
imprescindible: ojos abiertos + rastreo x,y, sin la complejidad de emociones,
joystick, modo autónomo y parpadeo del `main.py` completo de `ojosMecanicos`.

**Autónoma, no solo el firmware.** Tiene su propia copia de `face_tracker.py` y
`pico_serial.py` (idénticas a las de v3, no importadas desde ahí), con su propio
`.venv/` y `requirements.txt` — más ligero que el de v3, porque v4 no toca voz ni
sentimiento. Solo `v4/main.py` (el firmware) rompe el patrón de venv, porque corre
dentro de la Pico, no en el Mac. Se despliega con Thonny o `mpremote`, no con pip.

**Hito 1: `main.py` mínimo (COMPLETADO Y VALIDADO EN HARDWARE REAL)**
- ✅ `v4/main.py`: solo párpados abiertos al arrancar + rastreo x,y con suavizado EMA
- ✅ Protocolo compatible con v3 sin cambios (el `pico_serial.py` propio de v4
  funciona tal cual)
- ✅ Verificado sin hardware: sintaxis, fórmula de pulso PCA9685 (0°→102, 90°→307,
  180°→512), parseo de comandos con casos límite y basura
- ✅ **Validado en la Pico real por el usuario:** el rastreo funciona, los ojos
  siguen la cara "perfectamente"

**Hito 1.5: Autonomía completa (COMPLETADO)**
- ✅ `face_tracker.py` y `pico_serial.py` copiados a `v4/` (no importados desde v3)
- ✅ `v4/requirements.txt` propio, `v4/.venv` propio
- ✅ 19 tests duplicados en `v4/tests/`, corridos dentro de `v4/.venv` sin ninguna
  referencia a `v3/` — confirmado que pasan de forma completamente aislada

**Hito 2: Validación con hardware — COMPLETADO**

**Hito 3: Reintroducir complejidad por partes — en progreso, ver v5.0.0 abajo**

Detalle completo: [`v4/PLAN-v4.md`](v4/PLAN-v4.md).

---

## v5.0.0 ✅ — + Cuello y parpadeo (completa y validada en hardware real)

**Objetivo:** siguiendo el Hito 3 de v4, reintroducir parpadeo y movimiento de
cuello (sin emociones todavía) mientras el rastreo de ojos sigue funcionando igual.

**Autónoma, igual que v4:** copia propia de `face_tracker.py` y `pico_serial.py`
(sin cambios respecto a v4), `.venv` propio, 25 tests propios.

**Cambio de arquitectura no anticipado:** el firmware empezó usando el mismo
controlador PCA9685 (I2C) de `ojosMecanicos`, pero en hardware real dio tres
problemas — temblor de servos al encender, temblor periódico al parpadear, y el
eje PAN sin moverse — que, tras una depuración larga (arreglo de `/OE`, ajustes de
temporización, instrumentación de diagnóstico), resultaron tener el mismo origen:
el PCA9685 o la comunicación I2C con él. Se abandonó el PCA9685 por completo,
generando el PWM directamente desde los pines de la Pico, y los tres problemas
desaparecieron a la vez. Cronología completa, con cada intento y cada error, en
[`v5/README-v5.md`](v5/README-v5.md#historial-de-depuración-completo).

**Hito 1: Autonomía completa — COMPLETADO**
- ✅ Copiado todo lo del lado Mac desde `v4/`, sin cambios de lógica

**Hito 2: Cuello — PAN/TILT — COMPLETADO**
- ✅ El cuello sigue a los ojos, amortiguado (80% horizontal, 60% vertical — mismos
  factores que `ojosMecanicos/main.py`), con el mismo suavizado EMA que los ojos

**Hito 3: Parpadeo periódico — COMPLETADO**
- ✅ Cada 2-6 segundos, independiente de si hay rastreo activo

**Hito 4: Validación con hardware — COMPLETADO**
- ✅ Confirmado por el usuario: "todos los motores se mueven y parpadea sin
  vibraciones", incluyendo PAN, que nunca se había movido con el PCA9685
- [ ] Sesión larga sin problemas — no verificado, no bloqueante

Detalle completo: [`v5/PLAN-v5.md`](v5/PLAN-v5.md).

---

## v6.0.0 ✅ — Estado base + secuencia de expresiones (completa y validada en hardware real)

**Objetivo:** dos cosas. Un programa dedicado (`estado_base.py`) que lleve los 8
servos a 90° y los mantenga ahí — posición segura antes de desconectar la
alimentación, o para recuperar un estado neutral tras un error. Y en `main.py`,
el primer paso de expresiones faciales: cambian solas cada 5 segundos, en un
orden fijo, sin depender de voz ni sentimiento todavía.

**Trae toda la base funcional de v5, salvo `main.py`, sin cambios:**
`face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`. `main_pca9685.py`
(la versión retirada) no se copió — no es "base funcional".

**Hito 1: Base funcional de v5 traída completa — COMPLETADO**
- ✅ Copiado todo desde `v5/`, sin cambios de lógica

**Hito 2: `estado_base.py` — COMPLETADO, validado en hardware real**
- ✅ Centra los 8 servos con el mismo espaciado de 0.1s que usa `main.py` al
  arrancar (protección contra picos de corriente)
- ✅ Misma fórmula de PWM y mismo mapeo de pines que `main.py` — verificado con
  un test que compara ambos directamente
- ✅ Validado en la Pico real por el usuario

**Hito 3: Secuencia de expresiones faciales — COMPLETADO en código**
- ✅ Los 10 offsets de párpados/cuello de `ojosMecanicos/main.py`, copiados
  literalmente y verificados contra el original antes de usarlos
- ✅ Temporizador fijo de 5s, cicla en orden, envuelve al final
- ✅ Párpados incorporados al suavizado EMA; el parpadeo respeta la expresión
  activa (no parpadea en DORMIDO, reabre a la posición de la expresión actual)
- ✅ **Hallazgo real, confirmado con test:** SORPRENDIDO no se distinguía de
  NEUTRAL en v6 — su offset empujaba hacia un extremo en el que los párpados ya
  estaban (sin sincronía párpado-mirada, no había margen para que se note).
  **Resuelto en el Hito 4** bajando el reposo, en vez de añadir esa sincronía.
- ✅ Validado en la Pico real (rastreo + cuello + parpadeo) por el usuario

**Hito 4: Ajustes de realismo, tras probar en hardware — COMPLETADO Y VALIDADO EN HARDWARE REAL**
- ✅ `PARPADOS_REPOSO`: nueva posición de reposo al 40% de cierre (no el 100%
  abierto) — resuelve de raíz el hallazgo de SORPRENDIDO del Hito 3
- ✅ SORPRENDIDO ahora se aplica sin clamping en los 4 canales (confirmado con
  test); DORMIDO, como efecto colateral esperado, ahora cierra los 4 canales
  por completo
- ✅ FELIZ y SOSPECHA recalculados para notarse sobre el nuevo reposo (los
  offsets originales de `ojosMecanicos`, pensados para 100% abierto, casi no
  se notaban)
- ✅ TRISTE fuerza la cabeza (`TILT`) a su mínimo mecánico en vez de un offset
  relativo — pedido explícito, para que la cabeza gacha se note siempre igual
- ✅ DUDA, PENSATIVO y NERVIOSO ahora ignoran el rastreo facial y fijan o
  mueven la mirada por su cuenta mientras duran (barrido lateral 40↔140 en
  DUDA; mirada fija arriba-izquierda en PENSATIVO; saltos al azar cada 1s en
  NERVIOSO) — el cuello acompaña los tres gestos
- ✅ Corregido un bug real: al salir de DUDA/PENSATIVO/NERVIOSO, la mirada
  ahora vuelve al centro antes de la siguiente expresión, en vez de heredar
  la posición desviada
- ✅ **Validado en la Pico real por el usuario:** "todo ha funcionado bien" —
  incluida la interacción entre parpadeo, cambio de expresión y los overrides
  de mirada, sin problema observado

49 tests en total. Detalle completo: [`v6/PLAN-v6.md`](v6/PLAN-v6.md).

---

## v7.0.0 ✅ — Seguimiento visual real + secuencia de expresiones (completa y validada en hardware real)

**Objetivo:** sin cambios de lógica respecto a v6 — juntar, por primera vez,
el rastreo facial real de una persona (`face_tracker.py`, en el Mac,
enviando `LR,UD` por serial) con la secuencia de expresiones activa, y
documentar con claridad qué expresiones siguen el rostro y cuáles no.

**Hito 1: Base funcional de v6 traída completa — COMPLETADO**
- ✅ Copiado todo desde `v6/`, sin cambios de lógica
- ✅ Corregidas de paso tres referencias de documentación arrastradas sin
  corregir desde v4/v5/v6 (un comentario de `requirements.txt` que aún decía
  "v4", un docstring que decía "copia idéntica de `../v4/...`" en vez de
  `../v6/...`, y un puntero a "README-v6.md, Historial de depuración" que en
  realidad vive solo en `v5/README-v5.md`)

**Hito 2: Documentar y validar el seguimiento real junto a la secuencia — COMPLETADO Y VALIDADO EN HARDWARE REAL**
- ✅ Confirmado, leyendo el código, que `actualizar_objetivo_mirada_expresion()`
  ya distinguía correctamente las 7 emociones que siguen el rastreo real
  (NEUTRAL/FELIZ/ENOJADO/TRISTE/SORPRENDIDO/DORMIDO/SOSPECHA, que no tocan
  `LR`/`UD`) de las 3 que lo ignoran a propósito (DUDA/PENSATIVO/NERVIOSO)
- ✅ `README-v7.md`: nueva sección explícita sobre qué expresiones siguen el
  rostro y cuáles no, con el mecanismo exacto
- ✅ **Validado en hardware real por el usuario:** cámara + Pico funcionando a
  la vez, con la secuencia de expresiones activa — "funcionó perfecto"

49 tests en total (heredados de v6, sin cambios). Detalle completo:
[`v7/PLAN-v7.md`](v7/PLAN-v7.md).

---

## v8.0.0 ✅ — Voz + sentimiento controlando la expresión facial (completa y validada en conversación real)

**Objetivo:** juntar v1/v2 (voz en tiempo real + análisis de sentimiento) con
v6/v7 (firmware de la Pico + expresiones): la emoción detectada en cada frase
de la conversación controla la expresión facial. Acotado a propósito, pedido
explícito del usuario: **sin rastreo facial todavía** — eso es v9, después de
validar que voz + sentimiento + expresión funcionan bien juntos.

**Hito 1: Base funcional traída completa — COMPLETADO**
- ✅ Copiado `realtime_voice.py`/`sentiment_analyzer.py` desde `v2/`, y
  `pico_serial.py`/`estado_base.py`/`diagnostico_canal.py` desde `v7/`, sin
  cambios de lógica
- ✅ Deliberadamente sin copiar `face_tracker.py`: v8 no rastrea el rostro
  todavía

**Hito 2: `main.py` — de ciclo fijo a pulso dirigido por EMOCION — COMPLETADO en código**
- ✅ `cambiar_emocion()`: único punto donde cambia la expresión, usado tanto
  al recibir un EMOCION nuevo por serial como al expirar el pulso de 5s
  (mismo `INTERVALO_EXPRESION_MS` de v6/v7, reusado con otro propósito)
- ✅ Eliminado el ciclo fijo (`SECUENCIA_EMOCIONES`, `indice_emocion`) — ya
  no hace falta, la expresión la decide siempre el EMOCION recibido
- ✅ Sin cambios en el resto (párpados, cuello, parpadeo, DUDA/PENSATIVO/
  NERVIOSO): dependen de `emocion_actual` sin importar cómo se estableció

**Hito 3: Mac — la emoción detectada controla la Pico — COMPLETADO en código**
- ✅ `EMOTION_TO_PICO`: 5 correspondencias razonadas en v3 (joy→FELIZ,
  sadness→TRISTE, anger→ENOJADO, fear→NERVIOSO, surprise→SORPRENDIDO)
- ✅ **Pedido explícito del usuario, cambiado sobre la primera versión de esta
  tabla:** las 7 categorías de pysentimiento deben mapear a alguna expresión
  del robot, ninguna sin enviar. `disgust`→`SOSPECHA` (no `NEUTRAL` como en
  la tabla original de v3 — se degrada a la más parecida facialmente) y
  `others`→`NEUTRAL` (1 a 1). `DORMIDO`/`DUDA`/`PENSATIVO` quedan sin usar:
  ninguna categoría de pysentimiento les corresponde ni de lejos
- ✅ Conexión a la Pico autodetectada, con `--no-pico` para desactivarla
- ✅ **Confirmado con una conversación real por el usuario:** las 6 frases
  de prueba (una por emoción no neutral) movieron la expresión correcta

**Hito 4: `webrtc_server.py` — la conversación pasa al navegador — COMPLETADO Y VALIDADO EN CONVERSACIÓN REAL**
- ✅ El usuario reportó que la terminal (medio-dúplex, Enter para interrumpir)
  no daba la conversación instantánea deseada, y pidió lo que v1 ya resuelve
  para ese problema: la voz en el navegador por WebRTC
- ✅ Copiados `v1/webrtc_server.py` y `v1/static/index.html`, sin cambios en
  la negociación SDP/WebRTC; nuevo endpoint `POST /api/analyze-sentiment`
  para que el navegador mande el texto transcrito (que este proceso nunca ve
  con WebRTC) y así poder analizarlo y avisar a la Pico
- ✅ `EMOTION_TO_PICO` duplicado a propósito entre `webrtc_server.py` y
  `realtime_voice.py` (mismo criterio de "copiar, no importar"); nuevo test
  que comprueba que no diverjan
- ✅ Verificado primero a mano (Pico conectada, sin necesitar clave de API):
  el servidor sirvió la página y el endpoint clasificó y envió correctamente
  a la Pico frases de prueba reales
- ✅ **Validado por el usuario con una conversación real completa** (clave de
  API válida, hablando de verdad por el navegador, con la Pico física): "ha
  funcionado muy bien y el robot también ha seguido todos los sentimientos"

65 tests en total. Detalle completo: [`v8/PLAN-v8.md`](v8/PLAN-v8.md).

---

## v9.0.0 ✅ — Voz + sentimiento + rastreo facial real, todo junto (completa y validada en hardware real)

**Objetivo:** juntar, en un solo proceso, las tres piezas validadas por
separado hasta ahora: voz + sentimiento (v8) y rastreo facial real (v7).
Alcance acotado: solo `webrtc_server.py` recibe la cámara — `realtime_voice.py`
se queda igual que en v8.

**Hito 1: Base funcional traída completa — COMPLETADO**
- ✅ Copiado todo desde `v8/`, y retomado `face_tracker.py` desde `v7/`
  (v8 no lo tenía a propósito), sin cambios de lógica

**Hito 2: `webrtc_server.py` — rastreo facial real en un hilo de fondo — COMPLETADO Y VALIDADO EN HARDWARE REAL**
- ✅ `_hilo_rastreo()`: hilo de fondo que lee la cámara vía `FaceTracker` y
  llama a `PICO.enviar(lr, ud)` (sin EMOCION) cuando hay cambio significativo
- ✅ `ULTIMA_MIRADA`: reemplaza el `90,90` fijo que usaba v8 — el endpoint de
  sentimiento ahora manda la posición real junto con la emoción
- ✅ Conexión a la Pico compartida: se abre si `--sentiment` o `--tracking`
  están activos (antes solo dependía de `--sentiment`)
- ✅ `main.py` (el firmware): sin cambios — ya aceptaba mirada real desde v4
- ✅ **Bug real encontrado y corregido, no anticipado:** abrir la cámara
  dentro del propio hilo de rastreo falla en macOS
  (`"can not spin main run loop from other thread"` — AVFoundation necesita
  el hilo principal para negociar el permiso de cámara). Corregido: la
  cámara se abre en `main()` (hilo principal) y el objeto ya abierto se pasa
  al hilo de fondo
- ✅ **Validado por el usuario, con permiso de cámara concedido y una
  conversación real:** "funciona bien, hace el tracking perfecto, y puedo
  hablar en tiempo real" — rastreo real + sentimiento a la vez, sin
  conflictos entre los dos hilos

**Hito 3: Modo dormido por inactividad — COMPLETADO Y VALIDADO EN HARDWARE REAL**
- ✅ Pedido explícito tras validar los Hitos 1-2: tras `--sleep-timeout`
  segundos (60 por defecto) sin que el usuario hable, la Pico entra en
  `DORMIDO`; al volver la actividad, se despierta con `DUDA` y de ahí pasa
  sola a `NEUTRAL`
- ✅ `main.py` (el firmware): sin cambios, otra vez — el modo dormido reusa
  "la misma emoción repetida extiende el pulso" (ya probado desde v8) para
  mantener `DORMIDO` indefinidamente, y el pulso normal de 5s para volver de
  `DUDA` a `NEUTRAL` sin intervención adicional
- ✅ Solo cuenta como actividad lo que dice el usuario, no el asistente —
  decisión explícita
- ✅ `_decidir_sueno()`: lógica pura, aislada de threading, con 5 tests
  nuevos que la prueban directamente con valores de tiempo fijos
- ✅ **Validado con hardware real:** `--sleep-timeout 4` confirmó la
  secuencia completa (dormir tras el silencio, despertar con la primera
  actividad) por los logs y el envío serial real a la Pico física

79 tests en total. Detalle completo: [`v9/PLAN-v9.md`](v9/PLAN-v9.md).

---

## v10.0.0 🔄 — Todo lo de v9, en la Raspberry Pi 5 (código completo, validación en hardware pendiente)

**Objetivo:** llevar la pila completa de v9 (voz por navegador + sentimiento +
rastreo facial real + modo dormido) de un Mac a una **Raspberry Pi 5**, con
micrófono y parlante USB. La Pico se mantiene sin cambios como controlador de
servos — la Pi 5 sustituye al Mac como cliente, no a la Pico.

**Decisión de arquitectura, con el usuario:** este proyecto ya tenía una
especificación aparcada para Raspberry Pi 5 desde v1
([`docs/RASPBERRY-PI.md`](docs/RASPBERRY-PI.md)) que elegía un enfoque
headless (sin pantalla) con `realtime_voice.py` + cancelación de eco de
PipeWire a nivel de sistema — pensado para el mismo hardware (micro y
parlante USB independientes). Al planificar v10 se le presentó ese
contraste al usuario explícitamente, y se decidió **no** seguir esa spec
esta vez: v10 usa `webrtc_server.py` con Chromium corriendo en la propia Pi
5 (necesita pantalla), igual que la vía recomendada en el resto de
versiones, para no perder ninguna de las cuatro piezas de v9 de golpe. La
spec de PipeWire sigue siendo válida como referencia si en el futuro se
quiere una versión headless.

**Hito 1: Base funcional traída completa — COMPLETADO**
- ✅ Copiado todo desde `v9/`, sin cambios de lógica salvo lo descrito abajo
- ✅ 79 tests heredados, corridos dentro de `v10/.venv` (73 pasan, 6 se
  saltan por falta de `pysentimiento` en la máquina de desarrollo — sin
  cambios respecto al criterio de v2 en adelante)

**Hito 2: Cámara CSI en vez de la webcam del Mac — COMPLETADO EN CÓDIGO, sin hardware real**
- ✅ `face_tracker.py`: `FaceTracker` (la lógica pura) sin cambios;
  `abrir_camara_csi()`/`leer_frame()` nuevas, envuelven `picamera2` con el
  mismo contrato `(ret, frame)` que tenía `cv2.VideoCapture.read()`
- ✅ Import de `picamera2` diferido, para que los tests no lo necesiten
  instalado — confirmado corriendo los 79 tests sin `picamera2` en este Mac
- ✅ `webrtc_server.py`: mismo patrón defensivo de v9 (abrir la cámara en el
  hilo principal, no en el de rastreo), documentado con honestidad como
  "por consistencia", no como un bug confirmado en Linux (el bug real de
  v9 era específico de AVFoundation/macOS)

**Hito 3: Puerto serial de la Pico en Linux — COMPLETADO EN CÓDIGO, sin hardware real**
- ✅ `encontrar_puerto_mac()` → `encontrar_puerto_pico()`: busca
  `/dev/ttyACM*` en vez de los nombres de macOS
- ✅ Documentado el requisito de grupo `dialout`, específico de Linux

**Hito 4: Audio USB — decisión de arquitectura — COMPLETADO**
- ✅ Ver "Decisión de arquitectura" arriba
- ✅ Documentado en `README-v10.md` el setup de PipeWire/`wpctl` para fijar
  el micro/parlante USB como dispositivos por defecto del sistema (los usan
  tanto `getUserMedia` del navegador como `sounddevice` de
  `realtime_voice.py`, sin tocar código)

**Pendiente, el único punto que falta:**
- [ ] **Validar con hardware real de la Raspberry Pi 5** — cámara CSI,
  micro/parlante USB, Pico física, con una conversación hablada de verdad.
  Este código se escribió sin ninguna de esas piezas delante; es la primera
  versión de este proyecto que llega a este punto así.

79 tests en total (heredados de v9, sin tests nuevos — no hay lógica nueva
que probar sin hardware real). Detalle completo: [`v10/PLAN-v10.md`](v10/PLAN-v10.md).

---

## v11.0.0 ✅ — Solo conversación de voz, en la Raspberry Pi 5 (validada con conversación real, tres vías)

**Objetivo:** versión paralela a v10, no un reemplazo ni un paso previo
obligatorio. La cámara CSI que necesita v10 todavía no está disponible, así
que v11 aísla la única pieza que sí se puede validar ya: la conversación de
voz sola, sin sentimiento, sin rastreo facial, sin Pico — el alcance de v1,
en la Raspberry Pi 5 en vez del Mac.

**Hito 1: Copiar v1 sin cambios de lógica — COMPLETADO**
- ✅ `webrtc_server.py`, `realtime_voice.py`, `static/index.html` copiados
  de `v1/`, sin ningún cambio de lógica — v1 no tenía código específico de
  macOS (ni la cámara ni la Pico entran en esta versión), a diferencia de
  v10, que sí tuvo que adaptar ambas
- ✅ Único cambio real: un comentario sobre certificados TLS que mencionaba
  macOS, generalizado
- ✅ `requirements.txt` ligero (sin torch/opencv/pyserial), `.env.example`
  con el placeholder correcto
- ✅ Sin `tests/`, igual que v1: no hay lógica pura nueva que testear sin
  hardware real

**Hito 2: Documentar el setup de audio de la Pi 5 — COMPLETADO**
- ✅ Documentado Chromium en modo kiosk y `realtime_voice.py` como
  alternativa sin pantalla

**Hito 3: Validación en hardware real, vía terminal — COMPLETADO**
- ✅ **Bug real encontrado y corregido: sample rate.** `realtime_voice.py`
  fallaba con `paInvalidSampleRate` — la Realtime API pide 24kHz PCM, el
  micro/parlante USB de esta Pi 5 solo aceptan 44.1/48kHz de forma nativa,
  y PortAudio con ALSA no resamplea. Fijar el dispositivo por defecto de
  PipeWire (`wpctl set-default`, lo único documentado en el Hito 2) no
  bastaba, porque PortAudio abre ALSA directo sin pasar por PipeWire
- ✅ **Solución real, sin tocar código:** un `~/.asoundrc` con un
  `type plug` de ALSA por canal (resampling automático) — añadido
  [`v11/asoundrc.example`](v11/asoundrc.example) como plantilla
- ✅ **Aclarado un flag ya existente desde v1, pero subdocumentado:**
  `--barge-in` es necesario para interrumpir por voz en `realtime_voice.py`
  — sin él, solo Enter corta al asistente
- ✅ **Confirmado con una conversación real:** `realtime_voice.py
  --barge-in` conectó a la API, mantuvo una conversación completa en
  español por el micro/parlante USB, y permitió interrumpir al asistente
  hablando por encima

**Hito 4: Validación en hardware real, vía navegador — COMPLETADO**
- ✅ **Bug real encontrado: Chromium roto en esta Pi.** Chromium 149 no
  carga ninguna página (local ni externa) — pila de red rota, errores
  ANGLE/EGL con el display Xwayland. Causa raíz no investigada más allá
  del síntoma; documentado como confirmado en esta Pi, no como defecto
  general de Chromium en Pi 5. **Decisión de despliegue: usar Firefox**
- ✅ **Bug real encontrado y corregido: WebRTC sin STUN.**
  `static/index.html` creaba `RTCPeerConnection` sin `iceServers` → solo
  candidatos host (IP local), inalcanzables para OpenAI → ICE nunca
  conectaba pese a que la negociación SDP daba 200. Corregido añadiendo
  STUN (Google + Twilio) y esperando `iceGatheringState === 'complete'`
  antes de mandar el offer. `static/index.html` deja de ser copia de v1
  sin cambios — primera vez que hizo falta tocarlo en esta versión
- ✅ **Bug real menor, encontrado y corregido: query string en `do_GET`.**
  Necesario para la autoconexión en modo kiosko (`?auto=1`, sin clic
  humano) — `webrtc_server.py` no la soportaba, arreglado con
  `urllib.parse.urlparse`
- ✅ `start_browser.sh` / `stop_browser.sh`: scripts de operación de 1
  comando, con espera activa de `ICE: connected` antes de confirmar
- ✅ **Confirmado con una conversación real:** ICE conectado, audio
  bidireccional, conversación fluida e interrupción por voz — validado
  por el usuario (22/08/2026)

**Hito 5: Sistema de arranque automático — COMPLETADO EN CÓDIGO, ciclo de reinicio sin validar**
- ✅ `systemd/v11-webrtc.service`: unidad `systemd` para el servidor,
  `Restart=always`, no depende de sesión gráfica
- ✅ `autostart/v11-firefox-kiosk.desktop`: autostart de escritorio (XDG)
  para Firefox en kiosko
- ✅ `start_browser.sh` ampliado con autorreparación del perfil de
  Firefox; `stop_browser.sh` ampliado para reconocer si el servidor lo
  gestiona `systemd` (y pararlo de verdad con `systemctl stop`)
- [ ] **Pendiente:** validar el ciclo completo de apagar/encender la Pi y
  confirmar que queda conectada sola, sin tocar nada

**Hito 6: Tercera vía — AEC real de PipeWire (`v11/pipewire-aec/`) — COMPLETADO, validado en hardware real**
- ✅ `voice_chat.py`, escrito desde cero (no deriva de v1): usa
  `parec`/`paplay` contra los nodos virtuales de `module-echo-cancel` de
  PipeWire, con cancelación de eco real — el enfoque de la spec aparcada
  `docs/RASPBERRY-PI.md`
- ✅ **Hallazgo real:** cargar el módulo por `pipewire.conf.d` (la vía
  "oficial") crashea en esta build; funciona por `pactl` (`aec-load.sh`).
  Compensación de la deriva de reloj entre micro y parlante USB
  independientes con `webrtc.extended_filter`/`delay_agnostic`
- ✅ `voice-chat.service`: despliegue como servicio, `Restart=always`,
  validado en `/home/pi/voice-chat/` (carpeta distinta de `/home/pi/v11/`)
- ✅ **Bug encontrado y corregido:** `voice_rest.py` (script alternativo,
  Whisper→GPT→TTS, no Realtime API) llegó con la lectura de
  `OPENAI_API_KEY` corrompida por la exportación — reconstruida con el
  mismo patrón que `voice_chat.py`, a petición explícita del usuario
- ✅ **Confirmado con hardware real** por el usuario

**Cómo se hizo:** el usuario delegó la implementación en hardware real a
otro agente de código corriendo en la propia Pi 5, en tres rondas (terminal,
navegador, y esta tercera vía con AEC de PipeWire); cada ronda documentó su
proceso, y esa documentación se usó para corregir esta versión con los
hallazgos reales, sin suponer nada no confirmado ahí.

Sin tests nuevos (los bugs encontrados fueron de configuración de sistema o
de comportamiento del navegador/PipeWire, no de lógica pura). Detalle
completo: [`v11/PLAN-v11.md`](v11/PLAN-v11.md).

---

## Política de versiones

### Ramas y tags

- **`main`:** código de producción, último release estable
  - Tags: `v1.0.0`, `v2.0.0`, etc.
- **`develop`:** rama de integración (futura, si se expande)
- **Ramas de feature:** `feature/v2-pipewire`, `feature/wake-word`, etc.

### Descarga de versiones específicas

```bash
# Clonar solo v1
git clone --branch v1.0.0 <repo> hablar-v1

# Descargar ZIP (GitHub Releases)
# → hablar-realtime-v1.0.0.zip

# Actualizar a v2 cuando esté lista
git clone <repo>  # clona main con v2
cd main
cd v2             # entra en v2
```

### Compatibilidad

- **Cada versión es independiente:** su venv, requirements.txt, docs.
- **v1 seguirá siendo estable:** no se toca una vez que v2.0.0 se lance.
- **No hay dependencias cruzadas:** puedes usar v1 y dejar v2 en desarrollo.

### Soporte

- **v1:** En mantenimiento. Bugs críticos arreglados. Cambios menores si es necesario.
- **v2:** En desarrollo activo.
- **v3+:** Planeado, sujeto a cambios.

---

## Calendario

| Versión | Estado | Plataforma |
|---------|--------|-----------|
| v1.0.0  | ✅ Completa | macOS, Linux |
| v2.0.0  | 🔄 Código completo, falta validar con voz real | macOS |
| v3.0.0  | 🔄 Código completo (Hito 0 y 1), falta cámara/Pico reales | macOS + Raspberry Pi Pico (opcional) |
| v4.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) |
| v5.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) |
| v6.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) |
| v7.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) |
| v8.0.0  | ✅ Completa y validada en conversación real | Raspberry Pi Pico (MicroPython) + Mac |
| v9.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) + Mac + cámara |
| v10.0.0 | 🔄 Código completo, falta validar en hardware real | Raspberry Pi Pico (MicroPython) + **Raspberry Pi 5** + cámara CSI |
| v11.0.0 | ✅ Validada en hardware real (terminal, navegador y AEC PipeWire); falta el ciclo de autoarranque | **Raspberry Pi 5** (sin Pico ni cámara) |

---

## Cómo contribuir

Cada versión vive en su carpeta. Si quieres trabajar en v2 mientras otros usan v1:

1. Crea una rama: `git checkout -b feature/v2-xxx`
2. Trabaja en `v2/` sin tocar `v1/`
3. Cuando esté listo, merge a `main`
4. Tag: `git tag v2.0.0`
5. Actualiza este fichero

---

**Última actualización:** Agosto 22, 2026 (v11 validada en hardware real, tres vías)
