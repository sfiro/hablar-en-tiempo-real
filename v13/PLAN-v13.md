# Plan de desarrollo — v13.0.0 Voz + rastreo real, sin sentimiento todavía

---

## Hito 1: Firmware, enlace serial y rastreo traídos de v12, sin cambios ✅ (completado)

- [x] `main.py` copiado de `../v12/main.py` (== `../v9/main.py`), sin ningún
      cambio de lógica
- [x] `pico_serial.py` copiado de `../v12/pico_serial.py`, sin cambios
      (incluye `_drenar_entrada()`, el fix del buffer USB)
- [x] `face_tracker.py` copiado de `../v12/face_tracker.py`, sin cambios
      (cámara CSI OV5647 vía `picamera2` como vía principal, webcam USB
      como respaldo; parámetros de detección calibrados en hardware real:
      1296×972, `scaleFactor=1.2, minNeighbors=4`, selección del rostro
      más grande, `alpha=0.5, zona_muerta=0`)
- [x] `estado_base.py`, `diagnostico_canal.py` copiados de `../v12/`, sin
      cambios
- [x] 24 tests (8 + 12 + 4) copiados y verificados en `v13/.venv` en este
      hito, sin ninguna referencia a v12 — ampliados a 33 en el Hito 4, con
      7 tests nuevos para `rastreo_expresiones.py`

## Hito 2: Voz por terminal + rastreo — `realtime_voice.py` ✅ (completado, primer hito pedido explícito)

**Objetivo, pedido explícito:** "primero con el servidor .py" — la
conversación de voz de v11 (`realtime_voice.py`, WebSocket, terminal),
ahora con `--tracking` para rastrear el rostro y controlar la Pico en
paralelo. Primera vez en todo el proyecto que `realtime_voice.py` rastrea
—hasta v9/v10, solo `webrtc_server.py` lo hacía—.

- [x] Base: copia literal de `../v11/realtime_voice.py` (parte de audio,
      sin ningún cambio de lógica)
- [x] `--tracking` (nuevo): abre la Pico (si `--no-pico` no está puesto) y
      la cámara (CSI primero, con respaldo a webcam USB — mismo patrón que
      `../v12/rastreo_expresiones.py`), y lanza `_hilo_rastreo()` en un
      hilo daemon antes de `asyncio.run(run(...))`
- [x] `_hilo_rastreo()`: copia del mecanismo de `../v12/rastreo_expresiones.py`
      (cadencia mínima de 200ms entre envíos, `FaceTracker(alpha=0.5,
      zona_muerta=0)`, envía en cada frame detectado dentro de la cadencia,
      no solo en "cambio significativo") — **nunca manda un campo EMOCION**,
      a propósito: sin sentimiento, la Pico se queda siempre en NEUTRAL
- [x] La cámara se abre en `main()` (antes de `asyncio.run`), no dentro del
      hilo de rastreo — mismo patrón defensivo que v9/v10/v12 (imprescindible
      en macOS, mantenido por consistencia en Linux)
- [x] Liberación de recursos en el `finally` de `main()`: detiene el hilo de
      rastreo, libera la cámara según su tipo (`picam2.stop()` /
      `cap.release()`), y para `PICO` — todo esto envuelve el
      `asyncio.run(run(...))` existente, sin tocar su lógica interna
- [x] Sin tests nuevos: no hay lógica pura nueva que valga la pena testear
      sin hardware (mismo criterio que v9 con su propio `_hilo_rastreo()`)

**Verificado sin hardware:** sintaxis, y arranque real con una clave de API
falsa, sin Pico, sin `picamera2` y sin permiso de cámara en este entorno:
la cadena de respaldo (CSI → USB → sin cámara) degrada limpiamente en cada
paso, sin excepciones no manejadas, y la conversación de voz sigue su curso
hasta el punto de necesitar una clave real ("Conectando a gpt-realtime …").

## Hito 3: Voz por navegador + rastreo — `webrtc_server.py` ✅ (completado, segundo hito pedido explícito)

**Objetivo, pedido explícito:** "despues con el web" — una vez el Hito 2
está completo, la misma integración de rastreo sobre `webrtc_server.py` de
v11 (WebRTC, navegador, cancelación de eco real).

- [x] Base: copia literal de `../v11/webrtc_server.py` (incluye el fix real
      de v11: `do_GET` parseaba mal la query string, ya corregido ahí)
- [x] `--tracking` (nuevo): mismo mecanismo que v9/v10 ya validaron para
      esta pieza (`_hilo_rastreo()`, cámara CSI con respaldo USB, Pico
      compartida), sin la parte de sentimiento que v9 sí tenía
      (`--sentiment`, `_handle_analyze_sentiment`) — v13 no la trae, a
      propósito
- [x] `rastreo_activo` (variable local en `main()`): distingue "se pidió
      `--tracking`" de "el rastreo quedó realmente activo" — corregido tras
      notar, en el propio arranque de prueba, que el mensaje de resumen
      decía "ACTIVO" incluso cuando la cámara había fallado en abrirse
- [x] `static/index.html` copiado de `../v11/`, sin ningún cambio: el
      navegador no necesita saber nada del rastreo, que vive enteramente
      del lado del servidor

**Verificado sin hardware:** sintaxis, y arranque real con `--no-browser` y
una clave de API falsa: sirve la página y llega a
"Abre http://127.0.0.1:8000/" con normalidad; sin cámara disponible, el
mensaje de resumen dice correctamente "pedido con --tracking, pero sin
cámara disponible" en vez de "ACTIVO".

## Hito 4: Validación en hardware real — bug de eco y arquitectura de dos procesos ✅ (completado)

**Lo que se descubrió al validar voz + rastreo a la vez en la Pi 5 real:**
combinar las dos piezas en un solo proceso (el diseño de los Hitos 2-3) SÍ
funciona, pero en la vía de navegador compite por CPU con el audio en
tiempo real lo bastante como para colar eco. Diario completo, con
mediciones: [`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md).

- [x] **Bug real, corregido: realimentación de audio.** Causa: durante la
      depuración se cargó el módulo de cancelación de eco de PipeWire
      (pensado para la vía de terminal con AEC de sistema) a la vez que se
      desactivaba la cancelación de eco del navegador — dos capas mal
      combinadas. Fix: ninguno de código (`static/index.html` ya traía
      `echoCancellation: true` correcto desde v11); el error fue de
      configuración del sistema. Regla documentada: una sola capa de AEC,
      nunca mezclar navegador + PipeWire.
- [x] **Hallazgo de arquitectura, confirmado con mediciones:** rastreo +
      voz por navegador en el mismo proceso — carga del sistema ~3.25,
      frente a ~2.1 con cada pieza en su propio proceso. Arquitectura
      recomendada para uso real por navegador: `rastreo_expresiones.py`
      (retomado de v12 sin cambios de lógica, nuevo en v13) como proceso
      aparte para cámara + Pico, y `webrtc_server.py` **sin** `--tracking`
      para la voz — cada proceso con su propio recurso.
- [x] `rastreo_expresiones.py` añadido a v13 (copia de v12, sin cambios de
      lógica) — la pieza que sí se valida corriendo *junto* a la voz, en
      su propio proceso. Cicla las 10 expresiones (no "siempre NEUTRAL"),
      pero sigue sin depender del contenido de la conversación — no es
      sentimiento, solo el mismo ciclo fijo de v12
- [x] `FPS_CAMARA` (nuevo, 5 en vez de los 15 de v12) en `face_tracker.py`:
      v13 comparte CPU con el audio en tiempo real, algo que v12 no tenía
      que considerar; 5fps deja margen sin perder fluidez perceptible
- [x] `--tracking` en `realtime_voice.py`/`webrtc_server.py` (rastreo
      integrado en el mismo proceso de voz) se mantiene sin cambios,
      documentado ahora como "útil para pruebas rápidas o la vía de
      terminal", no como la configuración recomendada para producción por
      navegador
- [x] 7 tests nuevos para `rastreo_expresiones.py` (idénticos a los de
      v12, migrados) — 33 tests en total
- [x] Notas de infraestructura documentadas: WiFi power-save cortando ICE
      a los ~35s (hay que desactivarlo a nivel de sistema), y que la vía
      de terminal con AEC de PipeWire y la vía web no deben correr a la vez

**Confirmado en hardware real, con la arquitectura de dos procesos:** voz
por navegador clara, sin eco ni autointerrupción, con el rastreo facial
siguiendo un rostro real y la Pico ciclando las 10 expresiones al mismo
tiempo, de forma sostenida.

---

## Definición de listo

v13.0.0 está lista cuando:

1. [x] Firmware, enlace serial y rastreo facial traídos sin cambios de
   lógica desde v12
2. [x] `realtime_voice.py` (Hito 2, pedido primero) con `--tracking`
   funcionando en paralelo a la conversación de voz
3. [x] `webrtc_server.py` (Hito 3, pedido después) con `--tracking`
   funcionando en paralelo a la conversación de voz
4. [x] La Pico nunca recibe un EMOCION cuando el rastreo va integrado en
   el proceso de voz: expresión siempre NEUTRAL, parpadeo normal, mirada
   real del rastreo sin que nada la fije
5. [x] 33 tests pasando, sin ninguna referencia a v11/v12
6. [x] **Validada con hardware real**: bug de realimentación de audio
   encontrado y corregido (configuración, no código); arquitectura de dos
   procesos confirmada como la recomendada para voz + rastreo por
   navegador sin degradar el audio. Ver Hito 4.
7. [ ] Análisis de sentimiento — explícitamente **fuera de alcance** de
   esta versión, para una v14 posterior.

---

**Última actualización:** Agosto 23, 2026
**Estado actual:** v13.0.0 **completa y validada en hardware real** (Hitos
1-4), con 33 tests pasando. El hallazgo más importante no fue de código,
sino de arquitectura: voz y rastreo en el mismo proceso funcionan, pero
para uso real por navegador la combinación validada es dos procesos
separados (`rastreo_expresiones.py` + `webrtc_server.py` sin `--tracking`),
por la competencia de CPU con el audio en tiempo real. Versión cerrada.
