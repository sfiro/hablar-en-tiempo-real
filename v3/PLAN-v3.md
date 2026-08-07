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

## Hito 1: Rastreo facial standalone 📋 (siguiente)

**Objetivo:** Adaptar `rastreoCara_Mac.py` a v3, funcionando solo (sin voz todavía),
para validar la cámara y el detector antes de integrar nada más.

### Tarea 1.1: Copiar y adaptar el rastreador

- [ ] Copiar `rastreoCara_Mac.py` a `v3/face_tracker.py`
- [ ] Extraer la lógica de detección + suavizado EMA + zona muerta a una función/clase
      reutilizable (`FaceTracker`), separada del bucle de `cv2.imshow` — para poder
      usarla luego desde un hilo sin ventana si se decide ir headless
- [ ] Decidir la pregunta abierta de README-v3.md: ¿ventana de depuración opcional
      con un flag `--show-window`, o siempre headless?
- [ ] Manejar cámara no disponible sin traceback (aviso claro + seguir sin rastreo)

**Criterio:** `python face_tracker.py` corre solo, muestra x,y en consola (y opcionalmente
una ventana), funciona con o sin Pico conectada — igual que el original.

### Tarea 1.2: Módulo de serial hacia la Pico

- [ ] `v3/pico_serial.py`: adaptar el patrón de `server_realtime.py` de
      `ojosMecanicos` — cola de comandos, hilo `daemon=True`, reconexión comprobando
      si el path `/dev/cu.usbmodem...` sigue existiendo, latido cada 1s mientras haya
      control activo
- [ ] Función `enviar(lr, ud, emocion=None)` que construye `"{lr},{ud},{emocion}\n"`
      o `"{lr},{ud}\n"` si no hay emoción, y la encola
- [ ] Sin Pico conectada: debe seguir funcionando, solo sin escribir a ningún puerto
      (igual que `pico is None` en el código original)

**Criterio:** con la Pico conectada, mover el rostro delante de la cámara mueve los
servos. Sin Pico, no falla nada, solo no hay movimiento físico.

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

**Última actualización:** Agosto 4, 2026
**Estado actual:** Hito 0 completo. Sin código de v3 todavía — siguiente paso es
Hito 1 (rastreo facial standalone).
