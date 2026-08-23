# v12 — Diario de validación e implementación en hardware real (23/08/2026)

**Por qué existe este fichero:** la spec original de v12 asumía una **webcam
USB** (`/dev/video1`, `cv2.VideoCapture`), pero la Raspberry Pi 5 real usa la
**cámara CSI OV5647** (conector CAM/DISP 1). El propio `README-v12.md`
anticipaba este caso: *"Si en algún momento se cambia a una cámara CSI, el
patrón a seguir es el que ya documentó v10"*. Este fichero documenta, en
orden cronológico, los hallazgos y fixes reales encontrados al validar v12 en
esa Pi 5 — todos ya incorporados a `face_tracker.py`, `pico_serial.py` y
`rastreo_expresiones.py` en el repo. Sigue el mismo patrón que
`v11/README-IMPLEMENTACION.md`: un diario de lo que pasó de verdad en
hardware, no una reescritura idealizada.

---

## 1. Soporte de cámara CSI (portado de v10)

`main.py` (firmware), `pico_serial.py` y `estado_base.py` quedaron igual que
en el repo — solo se tocaron `face_tracker.py` y `rastreo_expresiones.py`.

**`face_tracker.py`** — añadidas dos funciones, portadas literalmente de
`v10/face_tracker.py`:

```python
def abrir_camara_csi(ancho: int = ANCHO, alto: int = ALTO):
    """Abre la cámara CSI vía picamera2 (import diferido, format BGR888)."""
    from picamera2 import Picamera2
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (ancho, alto), "format": "BGR888"}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
    return picam2


def leer_frame(picam2):
    """Mismo contrato que cv2.VideoCapture.read() -> (ret, frame)."""
    try:
        frame = picam2.capture_array()
    except Exception as e:
        print(f"⚠️  No se pudo leer el frame de la cámara CSI: {e}")
        return False, None
    return True, frame
```

**Por qué:** la OV5647 no habla el API de `cv2.VideoCapture` (bus CSI, no V4L2
genérico). `format="BGR888"` mantiene el mismo orden de canales que OpenCV, así
el pipeline (`cv2.flip`, `FaceTracker.procesar`) no cambia. Import diferido →
los tests siguen funcionando sin `picamera2` instalado.

**`rastreo_expresiones.py`** — dos cambios:

1. `_hilo_rastreo(cap, detener)` → `_hilo_rastreo(leer, detener)`: en vez de
   recibir un `cv2.VideoCapture` ya abierto y llamar `cap.read()`, recibe un
   **callable `leer`** (sin argumentos) que devuelve `(ret, frame)` — así el
   mismo hilo sirve para webcam USB (`cap.read`) y para CSI
   (`lambda: leer_frame(picam2)`), sin ramificar dentro del bucle.
2. `main()` — apertura de cámara: intenta `abrir_camara_csi()` primero; si
   falla por `ImportError` (falta `picamera2`) avisa cómo instalarlo, si falla
   por otra excepción avisa de revisar la conexión/`rpicam-hello`; si no hay
   CSI disponible, cae al `cv2.VideoCapture(args.camera_index)` original
   (webcam USB) como respaldo. La cámara se libera en el `finally` de `main()`
   según su tipo (`picam2.stop()` o `cap.release()`), no dentro del hilo.

---

## 2. Bug 1 — la cascada casi no detectaba caras a 640×480

**Síntoma:** las expresiones cambiaban bien, pero el seguimiento de los ojos
era muy lento o casi no se movía.

**Medición con `diagnostico_rastreo.py`:** la cámara iba bien (428 frames en
12s ≈ 35 FPS), pero la cascada Haar solo detectaba el rostro en **2 de 428
frames (0.4%)** — por eso los ojos casi nunca recibían posición nueva.

**Causa raíz:** la OV5647 en 640×480 (config original de v12, pensada para
webcam USB) hace un crop del sensor y la cascada Haar no encuentra el rostro
en esa configuración.

**Barrido de parámetros (`diagnostico_params.py`, con una persona real frente
a la cámara):**

| Resolución | sf/mn | Detección |
|---|---|---|
| 640×480 | 1.3/5 (original) | 0% |
| 640×480 | 1.2/4 | 0% |
| 640×480 | 1.1/4 | 2% |
| 640×480 | 1.1/3 | 45% |
| 1296×972 | 1.3/5 | 84% |
| **1296×972** | **1.2/4** | **100%** |

**Fix aplicado en `face_tracker.py`:** `ANCHO=1296`, `ALTO=972`, y
`detectMultiScale(scaleFactor=1.2, minNeighbors=4)` (antes 1.3/5). Los tests
existentes siguen pasando porque no dependen de la resolución ni de los
parámetros reales de la cascada (cascada falsa inyectada); se añadieron
además dos tests nuevos para la lógica del punto 3.

## 3. Bug 2 — un falso positivo fijo secuestraba la mirada

**Síntoma:** los ojos se quedaban clavados en un punto aunque hubiera
movimiento real delante de la cámara (valor fijo en el log, ~67,99).

**Causa raíz:** la cascada detectaba un objeto pequeño y fijo del fondo
(~64×64px, siempre en la misma posición) y `FaceTracker.procesar()` tomaba
`rostros[0]` (el primero de la lista) en vez de la cara real.

**Fix aplicado en `face_tracker.py`:** elegir el **rostro de mayor área**
entre todas las detecciones, y descartar detecciones menores de 80px de lado
(un falso positivo típico a esta distancia es más pequeño que una cara real).

## 4. Bug 3 (el definitivo) — el buffer USB CDC de la Pico se desbordaba

**Síntoma:** el rastreo "empieza bien y a los ~10s muere" — los ojos se
vuelven lentos, hacen pequeños saltos y se quedan parados. Engañó durante
buena parte de la depuración porque el log del proceso en la Pi seguía
creciendo (seguía enviando) mientras la Pico ya no respondía — parecía un
problema del rastreo, no del enlace serial.

**Causa raíz:** el firmware `main.py` de la Pico **imprime
`Serial: LR=.., UD=..` por cada comando** que recibe (su `print()` de debug).
La Pi solo **escribía** al puerto serial; nadie leía esa salida. El buffer USB
CDC de la Pico (256 bytes) se llenaba en pocos segundos de envíos continuos, y
el `print()` de MicroPython **bloquea el firmware** cuando el buffer de salida
está lleno — la Pico dejaba de procesar comandos nuevos.

**Prueba que lo confirmó:** el log del proceso se congeló (dejó de crecer) y
`cat /dev/ttyACM0` mostró comandos viejos acumulados sin leer (valores del
arranque).

**Fix en `pico_serial.py` (`PicoLink`):** nuevo método `_drenar_entrada()` que
lee `in_waiting` bytes de la Pico y los descarta (con los fakes de test que no
tienen `in_waiting`, captura la `AttributeError`). Se llama en `_run()` al
inicio de cada ciclo y justo después de cada `_escribir()`, así el buffer de
la Pico nunca llega a llenarse.

**Regla para siempre (lección aprendida):** cualquier firmware que imprima
por serial debe tener su salida **leída** (y descartada, si no hace falta)
por el cliente. Si un dispositivo USB CDC "se muere a los pocos segundos de
empezar a recibir datos", lo primero a comprobar es si su buffer de salida se
está llenando con algo que nadie lee.

## 5. Ajustes de cadencia y suavizado

Con los tres bugs anteriores corregidos, quedaron dos ajustes de calibración,
también validados en hardware real:

- **Cadencia de envío a la Pico: 200ms (5 envíos/s).** A 50ms (20/s) el
  buffer USB de la Pico volvía a saturarse — la Pico necesita tiempo entre
  comandos para procesarlos y responder con su `print()` de debug.
- **`FaceTracker(alpha=0.5, zona_muerta=0)`** en el hilo de rastreo (antes
  `alpha=0.2, zona_muerta=2`, los valores por defecto originales de v9): el
  firmware ya suaviza el movimiento internamente con su propio `ALPHA=0.1` en
  `main.py`, así que lo que necesita del cliente es un **flujo continuo** de
  objetivos — enviar en cada frame detectado (dentro de la cadencia), no solo
  cuando hay "cambio significativo" según el filtro del cliente, que solo
  añadía congelamiento al converger sin aportar suavidad real.
- **Nuevo script `rastreo_solo.py`:** rastreo facial puro, sin ciclo de
  expresiones — creado para aislar el rastreo de las expresiones
  DUDA/PENSATIVO/NERVIOSO (que mueven la mirada por su cuenta y podían
  confundirse con un bug del rastreo durante la depuración).

## 6. Resumen de los fixes reales de esta sesión de validación

| # | Problema | Fix | Archivo |
|---|---|---|---|
| 1 | Cascada no detectaba caras a 640×480 (0.4%) | Resolución 1296×972 + sf=1.2/mn=4 | `face_tracker.py` |
| 2 | Falso positivo fijo secuestraba `rostros[0]` | Elegir el rostro más grande + descartar <80px | `face_tracker.py` |
| 3 | Buffer USB de la Pico se desbordaba (prints sin leer) → firmware bloqueado | `_drenar_entrada()` en `PicoLink` | `pico_serial.py` |
| 4 | Sin los tres fixes anteriores, cadencia/suavizado por defecto no bastaban | Cadencia 200ms + `alpha=0.5, zona_muerta=0` | `rastreo_expresiones.py` / `rastreo_solo.py` |

**Validado en hardware real, con los cuatro fixes aplicados:** cámara CSI
OV5647 abierta por `picamera2` sin errores; Pico detectada en `/dev/ttyACM0`;
ciclo de las 10 expresiones enviándose en orden
(NEUTRAL→FELIZ→ENOJADO→TRISTE→SORPRENDIDO→DORMIDO→DUDA→SOSPECHA→PENSATIVO→NERVIOSO);
rastreo facial siguiendo un rostro real de forma continua y sostenida en el
tiempo, sin volverse lento tras los primeros segundos. 33 tests (los 29
originales más 4 nuevos: 2 para la selección del rostro más grande y el
filtro de 80px, 2 para `_drenar_entrada()`), todos pasando sin hardware.
