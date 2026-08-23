# Plan de desarrollo — v12.0.0 Pi 5 + Pico: ciclo de expresiones + rastreo real, sin voz

---

## Hito 1: Firmware y enlace serial traídos de v9/v10, sin cambios de lógica ✅ (completado)

- [x] `main.py` copiado de `../v9/main.py`, **sin ningún cambio de lógica**
      (solo cabecera de comentarios actualizada) — sigue aceptando
      `"LR,UD\n"` y `"LR,UD,EMOCION\n"` por USB serial, sin distinguir qué
      máquina se lo manda
- [x] `estado_base.py`, `diagnostico_canal.py` copiados de `../v9/`, sin
      cambios de lógica (`diagnostico_canal.py` sigue usando PCA9685 por I2C,
      una inconsistencia ya presente desde v5 con `main.py`/`estado_base.py`
      —que sí generan PWM directo—; no se toca en v12 por estar fuera de
      alcance, ver README-v12.md)
- [x] `pico_serial.py` copiado de `../v10/pico_serial.py` (ya adaptado a
      Linux: `encontrar_puerto_pico()`, `/dev/ttyACM*`, nota de grupo
      `dialout`), sin cambios — v12 es también un cliente Linux/Raspberry Pi 5
- [x] Tests de `pico_serial.py` y `estado_base.py` copiados y verificados:
      14 tests pasando en `v12/.venv` (10 + 4) en este hito, sin ninguna
      referencia a v9/v10 — ampliados a 12 + 4 en el Hito 4, con 2 tests
      nuevos para `_drenar_entrada()`

## Hito 2: Cámara de la Pi 5 — planificada como USB, corregida a CSI tras validar ✅ (completado)

**Objetivo:** rastrear el rostro con la cámara conectada a la Pi 5. La
planificación original asumía una **webcam USB** (`/dev/video1`, driver V4L2
genérico), a diferencia de v10 (cámara CSI) — con la idea de que no hiciera
falta `picamera2`/`libcamera` ni un venv con `--system-site-packages`.

**Corregido tras la validación en hardware real (23/08/2026):** la Pi 5 real
usa la cámara **CSI OV5647** (conector CAM/DISP 1), no una webcam USB. Ver
Hito 4 para el detalle completo — este hito se actualiza aquí solo para que
la crónica no quede contradictoria con lo que terminó siendo cierto.

- [x] `face_tracker.py` copiado de `../v9/face_tracker.py`: la clase
      `FaceTracker` (EMA, zona muerta, mapeo a grados) mantiene su estructura
      original, con los parámetros recalibrados en el Hito 4
- [x] `abrir_camara_csi()`/`leer_frame()` portadas de `../v10/face_tracker.py`
      (import diferido de `picamera2`), añadidas en el Hito 4 al confirmarse
      que el hardware real es CSI, no USB
- [x] `--camera-index` por defecto 1 se conserva como **respaldo**: si no hay
      cámara CSI disponible (o falta `picamera2`), `rastreo_expresiones.py`/
      `rastreo_solo.py` caen automáticamente a `cv2.VideoCapture` con este
      índice
- [x] Import de la Pico en el script standalone cambiado a
      `encontrar_puerto_pico()` (Linux), en vez de `encontrar_puerto_mac()`
- [x] Tests de `FaceTracker` verificados sin cámara real conectada (cascada
      falsa inyectada, mismo patrón desde v3), incluidos los dos tests nuevos
      del Hito 4 (selección del rostro más grande, filtro de 80px)

**Verificado sin hardware:** los tests de `FaceTracker` pasan, incluso sin
`picamera2` instalado (import diferido). Arranque real de
`rastreo_expresiones.py` en un Mac sin permiso de cámara ni `picamera2`
instalado: intenta CSI, falla limpiamente con el mensaje de instalación, cae
a USB, falla limpiamente también (sin permiso), y el ciclo de expresiones
sigue con la mirada fija en 90,90 — la cadena de respaldo completa degrada
sin excepciones no manejadas.

**Confirmado con la Pi 5 real:** ver Hito 4.

## Hito 3: Ciclo de expresiones desde el cliente, no desde el firmware — `rastreo_expresiones.py` ✅ (completado)

**Objetivo, pedido explícito:** que el robot vaya cambiando de expresión cada
5 segundos, con la mirada real del rastreo facial, sin implementar todavía
conversación de voz.

**Decisión de diseño:** no se modifica `main.py` para que vuelva a ciclar
solo (como hacía en v6/v7) porque eso sería un paso atrás respecto al modelo
dirigido por eventos que ya tiene desde v8/v9 — un modelo que además es
justo el que hace falta para cuando se retome la voz. En su lugar, el ciclo
vive en un script nuevo del lado de la Pi 5
(`rastreo_expresiones.py`), que manda una `EMOCION` nueva por serial cada
`--interval` segundos (5 por defecto, igual a `INTERVALO_EXPRESION_MS` del
firmware) — desde fuera se ve el mismo ciclo fijo de v6/v7, pero el firmware
es exactamente el de v9, reutilizable sin cambios el día que se añada voz.

- [x] `CICLO_EMOCIONES`: mismo orden fijo que usaban v6/v7
      (`NEUTRAL → FELIZ → ENOJADO → TRISTE → SORPRENDIDO → DORMIDO → DUDA →
      SOSPECHA → PENSATIVO → NERVIOSO → NEUTRAL...`), verificado por test
      contra `EMOCIONES_VALIDAS` de `pico_serial.py` para que nunca diverjan
      en silencio (mismo patrón que `test_webrtc_server.py` en v8/v9)
- [x] `_hilo_rastreo()`: copiado del mecanismo de `../v9/webrtc_server.py`
      (cámara abierta en el hilo principal, pasada ya abierta al hilo de
      fondo — mismo criterio "por consistencia" que v10 documentó, sin
      confirmar que Linux lo necesite), actualiza `ULTIMA_MIRADA` bajo lock y
      manda `PICO.enviar(lr, ud)` sin emoción en cada cambio significativo
- [x] `_ciclar_expresiones()`: en el hilo principal, cada `--interval`
      segundos manda `PICO.enviar(lr, ud, emocion)` con la última mirada real
      conocida (no un `90,90` fijo — mismo razonamiento que `ULTIMA_MIRADA`
      en v9) y avanza al siguiente índice del ciclo
- [x] `_siguiente_indice()` aislado como función pura, testeable sin esperar
      segundos de verdad (mismo patrón que `_decidir_sueno()` en v9)
- [x] Sin servidor HTTP, sin `.env`, sin `OPENAI_API_KEY`: no hay voz ni
      sentimiento en esta versión, así que no hace falta nada de eso —
      requirements.txt más corto de todo el proyecto (`pyserial` +
      `opencv-python<5`)
- [x] Degradación limpia verificada: sin Pico conectada (avisa y sigue sin
      mover servos), sin cámara/permiso (avisa y sigue con mirada fija en
      90,90), y `--no-tracking`/`--no-pico` para aislar cada pieza a mano
- [x] 7 tests nuevos para la lógica del ciclo
      (`tests/test_rastreo_expresiones.py`)

**Verificado sin hardware:** 29 tests en total pasaban en `v12/.venv` en este
hito. Arranque real de `rastreo_expresiones.py --no-tracking` (sin Pico, sin
cámara) confirma en los logs el ciclo avanzando cada `--interval` segundos
con la mirada fija en 90,90; con `--tracking` (sin permiso de cámara en este
entorno) degrada limpiamente y el ciclo sigue igual.

**Confirmado con la Pi 5 real:** ver Hito 4 — con los fixes de ese hito, la
Pico recibió de verdad los 10 comandos por USB serial y cicló las expresiones
sin caer a NEUTRAL entre medias, y el rastreo real movió la mirada de las 7
expresiones que la siguen mientras DUDA/PENSATIVO/NERVIOSO la ignoraron,
exactamente como ya se había validado en v7/v9 con un Mac.

## Hito 4: Validación en hardware real — tres bugs encontrados y corregidos ✅ (completado)

**Lo que se descubrió al conectar por fin la Pi 5, la Pico y la cámara
reales:** la cámara de esta Pi 5 es una **CSI OV5647** (conector CAM/DISP 1),
no la webcam USB que asumía la planificación original — y con ella, tres
bugs reales que no aparecían en ningún test sin hardware. Diario completo,
con mediciones y tablas: [`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md).

- [x] **Soporte de cámara CSI**, portado literalmente de v10:
      `abrir_camara_csi()`/`leer_frame()` en `face_tracker.py`;
      `rastreo_expresiones.py`/`rastreo_solo.py` (nuevo) intentan CSI primero
      y caen a `cv2.VideoCapture` (USB) solo si falla — `_hilo_rastreo()`
      pasó a recibir un *callable* `leer()` en vez de un objeto de cámara
      concreto, para servir a los dos casos sin ramificar el bucle
- [x] **Bug 1, corregido:** la cascada Haar casi no detectaba caras a
      640×480 (0.4% de los frames — la OV5647 hace un crop del sensor a esa
      resolución). Fix: `ANCHO=1296, ALTO=972` +
      `detectMultiScale(scaleFactor=1.2, minNeighbors=4)` → 100% de
      detección, medido con una persona real delante de la cámara
      (`diagnostico_params.py`, barrido completo en el diario)
- [x] **Bug 2, corregido:** un falso positivo fijo del fondo (~64×64px)
      secuestraba la mirada porque `procesar()` tomaba `rostros[0]` (el
      primero). Fix: elegir el rostro de **mayor área** entre todas las
      detecciones, descartando las menores de 80px de lado
- [x] **Bug 3, el definitivo, corregido:** el firmware imprime
      `Serial: LR=.., UD=..` por cada comando recibido, y este lado nunca
      leía esa salida — el buffer USB CDC de la Pico (256 bytes) se llenaba
      en segundos y su `print()` bloqueaba el firmware, dejando de procesar
      comandos (síntoma: "el rastreo empieza bien y muere a los ~10s", muy
      engañoso porque el log de la Pi seguía creciendo). Fix:
      `_drenar_entrada()` en `PicoLink` (`pico_serial.py`), que lee y
      descarta la salida de la Pico en cada ciclo del hilo de envío
- [x] **Ajustes de calibración, validados:** cadencia de envío a la Pico
      limitada a 200ms (a 20/s el buffer volvía a saturarse), y
      `FaceTracker(alpha=0.5, zona_muerta=0)` en el hilo de rastreo — la
      Pico ya suaviza internamente, el cliente solo necesita mandar un flujo
      continuo de objetivos
- [x] `rastreo_solo.py` (nuevo): rastreo facial puro sin ciclo de
      expresiones, creado para aislar el rastreo de DUDA/PENSATIVO/NERVIOSO
      (que mueven la mirada por su cuenta y confundían la depuración)
- [x] Herramientas de diagnóstico incorporadas al repo:
      `diagnostico_rastreo.py`, `diagnostico_params.py`,
      `capturar_deteccion.py` — usadas para medir y confirmar cada bug antes
      de aplicar el fix
- [x] 4 tests nuevos: 2 para la selección del rostro más grande y el filtro
      de 80px (`test_face_tracker.py`), 2 para `_drenar_entrada()`
      (`test_pico_serial.py`) — 33 tests en total, todos pasando sin hardware

**Confirmado en hardware real, con los cuatro fixes aplicados:** cámara CSI
abierta sin errores; Pico detectada en `/dev/ttyACM0`; ciclo de las 10
expresiones enviándose en orden; rastreo facial siguiendo un rostro real de
forma continua y sostenida en el tiempo, sin volverse lento tras los
primeros segundos — el punto que quedaba abierto en el Hito 3 queda cerrado.

---

## Definición de listo

v12.0.0 está lista cuando:

1. [x] Firmware (`main.py`) y enlace serial (`pico_serial.py`) traídos sin
   cambios de lógica desde v9/v10 (salvo `_drenar_entrada()`, añadido en el
   Hito 4 tras el bug real del buffer USB)
2. [x] Rastreo facial real con la cámara de la Pi 5 (CSI vía `picamera2`,
   con respaldo automático a webcam USB vía `cv2.VideoCapture`)
3. [x] Ciclo de expresiones cada 5 segundos desde el cliente, con la mirada
   real del rastreo, sin tocar el firmware event-driven de v9
4. [x] 33 tests pasando, sin ninguna referencia a v9/v10/v11
5. [x] **Validada con hardware real**: Raspberry Pi 5 conectada por USB a la
   Pico física, cámara CSI real, y una sesión real viendo ciclar las 10
   expresiones con la mirada siguiendo un rostro de verdad, de forma
   sostenida en el tiempo. Ver Hito 4.
6. [ ] Conversación de voz — explícitamente **fuera de alcance** de esta
   versión, para una v13 posterior.

---

**Última actualización:** Agosto 23, 2026
**Estado actual:** v12.0.0 **completa y validada en hardware real** (Hitos
1-4), con 33 tests pasando. La cámara real resultó ser CSI (OV5647), no la
webcam USB que asumía la planificación original — corregido con el mismo
patrón (`picamera2`, import diferido) que ya había documentado v10, con
respaldo automático a USB si no hay CSI disponible. Tres bugs reales
encontrados y corregidos en la validación (cascada mal calibrada para la
OV5647, falso positivo secuestrando la mirada, y el buffer USB de la Pico
desbordándose) — ninguno anticipado por los tests sin hardware, todos
confirmados y resueltos con la Pi 5 real delante. Versión cerrada.
