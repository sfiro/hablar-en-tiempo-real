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
- [x] 24 tests (8 + 12 + 4) copiados y verificados en `v13/.venv`, sin
      ninguna referencia a v12

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

---

## Definición de listo

v13.0.0 está lista cuando:

1. [x] Firmware, enlace serial y rastreo facial traídos sin cambios de
   lógica desde v12
2. [x] `realtime_voice.py` (Hito 2, pedido primero) con `--tracking`
   funcionando en paralelo a la conversación de voz
3. [x] `webrtc_server.py` (Hito 3, pedido después) con `--tracking`
   funcionando en paralelo a la conversación de voz
4. [x] La Pico nunca recibe un EMOCION: expresión siempre NEUTRAL, parpadeo
   normal, mirada real del rastreo sin que nada la fije
5. [x] 26 tests pasando, sin ninguna referencia a v11/v12
6. [ ] **Validada con hardware real**: Raspberry Pi 5 con Pico física,
   cámara (CSI u USB), micrófono/parlante, y una conversación hablada de
   verdad viendo el rastreo funcionar a la vez — primero por terminal
   (Hito 2), después por navegador (Hito 3). Pendiente: es lo único que
   falta para pasar de "código completo" a "completa y validada".
7. [ ] Análisis de sentimiento — explícitamente **fuera de alcance** de
   esta versión, para una v14 posterior.

---

**Última actualización:** Agosto 23, 2026
**Estado actual:** v13.0.0 con código completo (Hitos 1-3) y 26 tests, todos
pasando sin hardware. **Sin validar todavía en la Raspberry Pi 5 real** —
igual situación en la que quedaron v10 y v12 al escribirse. La pieza con más
incertidumbre real, que ningún test sin hardware puede confirmar, es si la
conversación de voz y el hilo de rastreo compiten por CPU de forma
perceptible en la Pi 5 real — v9 ya confirmó que voz + rastreo conviven bien
en un Mac, pero no se ha repetido esa confirmación aquí. Versión abierta
hasta esa validación.
