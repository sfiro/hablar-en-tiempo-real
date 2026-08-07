# Plan de desarrollo — v3.0.0 Rastreo facial + servos

---

## Hito 0: Investigación ✅ (completado)

**Objetivo:** No rehacer lo que ya existe, no repetir errores ya cometidos.

Se investigó a fondo el proyecto hermano `ojosMecanicos` antes de escribir código.
Hallazgos completos en [README-v3.md](README-v3.md), sección "Antes de escribir
código". Resumen:

- [x] Confirmado que no existe una integración funcional voz+emoción+cámara+servos
- [x] Identificado un bug de diseño real en su intento de puente (hilos lanzados,
      pero la conexión emoción↔texto nunca se invoca — código muerto)
- [x] Protocolo serial de la Pico documentado y confirmado: `LR,UD,EMOCION\n`,
      enteros 40-140, emoción opcional de un enum de 10 valores, baud 115200
- [x] Patrón de threading confirmado como reutilizable: cv2 bloqueante en hilo
      `daemon=True` separado, nunca mezclado con `asyncio.run()`
- [x] Confirmado que su análisis de sentimiento (palabras clave + TextBlob) es menos
      sofisticado que nuestro `pysentimiento` de v2 — no hay nada que "mejorar
      copiando de ahí" en esa parte

---

## Hito 1: Rastreo facial standalone ✅ (código completo y con tests; falta cámara real)

**Objetivo:** Adaptar `rastreoCara_Mac.py` a v3, funcionando solo (sin voz todavía),
para validar la cámara y el detector antes de integrar nada más.

### Tarea 1.1: Copiar y adaptar el rastreador — DONE (código)

- [x] `v3/face_tracker.py`: lógica extraída a una clase `FaceTracker.procesar(frame)`,
      headless por diseño — no toca `cv2.imshow` en absoluto, solo `cv2.resize`,
      `cv2.cvtColor` y el clasificador. Devuelve un dict con `grado_x`, `grado_y`,
      `bbox`, `detectado`, `cambio_significativo`
- [x] Pregunta abierta resuelta: **flag `--no-window`**, ventana ON por defecto en el
      script standalone (útil para calibrar); la clase headless es la que se
      reutilizará en el Hito 2, la ventana vive solo en el bucle de prueba
- [x] Cámara no disponible: `cap.isOpened()` se comprueba explícitamente, mensaje
      claro con la ruta de permisos de macOS, `sys.exit(1)` sin traceback — **no**
      degrada en silencio en este script standalone (si no hay cámara, no hay nada
      que probar); la degradación con gracia dentro de la app completa de voz es
      responsabilidad del Hito 2, no de este script de prueba
- [x] **Corrección real encontrada adaptando el código:** el original usaba
      `cv2.COLOR_RGB2GRAY` sobre un frame que en realidad viene en BGR de
      `cv2.VideoCapture`. Cambiado a `COLOR_BGR2GRAY`. Efecto visual mínimo (los
      pesos de canal son parecidos) pero es la conversión correcta.
- [x] **Bug real de dependencias encontrado instalando, no en el código:**
      `opencv-python` 5.0 (recién publicado) eliminó `cv2.CascadeClassifier` del
      paquete base — se movió a `opencv-contrib-python`. Fijado
      `opencv-python>=4.9,<5` en `requirements.txt` para no reescribir la detección
      a la API DNN nueva justo en el primer hito.
- [x] Tests de la lógica pura (`tests/test_face_tracker.py`, 9 tests): mapeo,
      suavizado EMA, zona muerta, con una cascada falsa inyectada — un detector Haar
      no se puede probar de forma fiable contra una imagen sintética, así que se
      separa "la matemática de seguimiento" (testeable) de "si detecta un rostro de
      verdad" (solo verificable con cámara real)

**Verificado sin cámara real:** construcción de `FaceTracker`, toda la lógica de
mapeo/suavizado/zona muerta con cascada inyectada, y el manejo de "cámara no
disponible" — confirmado en ejecución real: en este entorno, macOS niega el permiso
de cámara a un proceso no interactivo (`OpenCV: not authorized to capture video`), y
el script respondió exactamente como estaba diseñado: mensaje claro, sin traceback,
salida limpia. Exactamente el mismo tipo de limitación que ya se dio con el permiso
de micrófono en v1 — se resuelve concediendo el permiso en una Terminal real, no
desde aquí.

**Pendiente, necesita a alguien con cámara real:**
- [ ] Confirmar que el detector reconoce un rostro real y lo sigue con suavizado
      razonable (la lógica ya está probada; falta la pieza que no se puede simular)
- [ ] Con la ventana de depuración (`--no-window` desactivado), confirmar visualmente
      que el rectángulo/punto siguen al rostro

### Tarea 1.2: Módulo de serial hacia la Pico — DONE

- [x] `v3/pico_serial.py`: `PicoLink`, con cola de comandos, hilo `daemon=True`,
      reconexión (comprobando si el path `/dev/cu.usbmodem...` sigue existiendo — solo
      con el driver real, ver nota de test más abajo), latido cada 1s
- [x] `enviar(lr, ud, emocion=None)`: construye `"{lr},{ud},{emocion}\n"` o
      `"{lr},{ud}\n"`, valida grados (se recortan a 40-140) y emoción (debe ser una de
      las 10 del vocabulario de la Pico, o lanza `ValueError`)
- [x] Sin Pico conectada: `enviar()` no falla ni bloquea, igual que `pico is None` en
      el original
- [x] Tests con un `serial_factory` inyectado (`tests/test_pico_serial.py`, 10 tests):
      formato de comando, cola, **latido verificado con reenvíos reales contados**,
      reconexión tras fallo de escritura
- [x] **Bug real encontrado escribiendo el propio test:** la comprobación de "¿sigue
      existiendo el puerto?" usaba `glob.glob()` sobre el path tal cual — con un
      puerto de prueba inyectado (que no existe en el filesystem real), el hilo
      creía que la Pico se había desconectado justo después de conectar. Se corrigió
      para que ese chequeo solo aplique con el driver real de pyserial, no con un
      `serial_factory` inyectado.

**Criterio cumplido** para todo lo que no requiere hardware. Con la Pico conectada
de verdad (pendiente, como el punto anterior): mover el rostro delante de la cámara
debería mover los servos.

---

## Hito 2: Integración con voz + sentimiento 📋

**Objetivo:** Todo junto: conversación, sentimiento y rastreo facial en el mismo
proceso, mostrado en la misma consola.

### Tarea 2.1: Arrancar los hilos de cámara y Pico desde `realtime_voice.py`

- [ ] Nuevo flag `--face-tracking` (paralelo a `--sentiment`, independiente)
- [ ] Arrancar el hilo de cámara y el hilo de Pico antes de `websockets.connect`,
      pararlos en el `finally`, igual que ya se hace con `mic_stream`/`playback`
- [ ] Estado compartido simple para la posición actual (mismo patrón que
      `posicion_x`/`posicion_y` de `ojosMecanicos`, protegido por el GIL — no hace
      falta un lock para un solo entero leído/escrito, como ya asumía ese código)

### Tarea 2.2: Mostrar x,y en consola junto al sentimiento

- [ ] Imprimir la posición cuando cambie de forma perceptible (mismo criterio de
      "zona muerta" que ya usa el rastreador, para no inundar la consola)
- [ ] Formato consistente con el resto de la consola (ver mockup en README-v3.md)

### Tarea 2.3: Cablear el sentimiento al comando serial — el bug a NO repetir

**Esta es la tarea que en `ojosMecanicos` quedó a medias** (los hilos arrancan, pero
la emoción nunca llega al hilo de posición). Aquí sí se conecta de verdad:

- [ ] Cuando `analyze_and_print` calcula una emoción con confianza suficiente,
      traducirla con la tabla de mapeo de README-v3.md y actualizar el estado
      compartido que lee el hilo de Pico
- [ ] **Test explícito** que verifique que una emoción detectada llega de verdad al
      comando serial encolado — no solo que los hilos arrancan sin excepción. Este
      test es directamente la lección aprendida de `ojosMecanicos`.

**Criterio de esta tarea, literal:** si el test de "los hilos arrancan" pasara pero
el de "la emoción llega al comando serial" no, sería exactamente el bug que ya se
cometió una vez en el proyecto hermano. No cerrar este hito sin el segundo test.

---

## Hito 3: Validación con hardware real 📋

**Objetivo:** Confirmar en la vida real lo que los tests no pueden probar.

- [ ] Conversación real con `--sentiment --face-tracking`, cámara detectando el
      rostro, Pico moviendo los servos según la conversación
- [ ] Confirmar que el rastreo no compite por CPU de forma perceptible con el audio
      (la detección de rostro corre en cada frame; si es demasiado costosa, medir y
      considerar bajar resolución o frecuencia de detección)
- [ ] Confirmar que desconectar la Pico a mitad de conversación no rompe nada
      (mismo criterio de robustez que "cámara no disponible")

**No se puede automatizar:** necesita cámara real, alguien delante, y opcionalmente
la Pico con servos físicos conectada.

---

## Hito 4: Documentación 📋

- [ ] INSTALL-v3.md con pasos de instalación (opencv-python, pyserial nuevos)
- [ ] Actualizar CLAUDE.md raíz con la arquitectura de tres hilos
- [ ] Troubleshooting: permisos de cámara en macOS, puerto serial no encontrado,
      rendimiento de detección facial

---

## Definición de listo

v3.0.0 está lista cuando:

1. [ ] Rastreo facial standalone funciona (Hito 1.1)
2. [ ] Serial hacia la Pico funciona con reconexión y latido (Hito 1.2)
3. [ ] Todo integrado en el mismo proceso que v2, mostrado en la misma consola (Hito 2)
4. [ ] El sentimiento llega de verdad al comando serial, con test que lo confirme —
   no repetir el bug de código muerto de `ojosMecanicos` (Hito 2.3)
5. [ ] Validado con cámara y, si está disponible, con la Pico real (Hito 3)
6. [ ] Degrada con gracia sin cámara y sin Pico (funciona como v2 en ambos casos)

---

**Última actualización:** Agosto 7, 2026
**Estado actual:** Hito 0 y Hito 1 completos en código y tests (19 tests pasan).
Falta la validación con cámara real (necesita permiso de macOS concedido en una
Terminal interactiva) y, si está disponible, con la Pico física — ninguna de las dos
se puede hacer desde este entorno. Siguiente paso: Hito 2 (integración con voz +
sentimiento), o primero validar Hito 1 con hardware real si se prefiere en ese orden.
