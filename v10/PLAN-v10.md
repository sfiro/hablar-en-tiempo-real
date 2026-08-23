# Plan de desarrollo — v10.0.0 Todo lo de v9, en la Raspberry Pi 5

---

## Hito 1: Base funcional traída completa ✅ (completado)

- [x] Copiados `main.py`, `estado_base.py`, `diagnostico_canal.py`,
      `sentiment_analyzer.py`, `static/index.html` desde `v9/`, sin cambios
      de lógica (solo referencias de documentación actualizadas donde
      mencionaban "v9"/"el Mac")
- [x] `pico_serial.py`: `encontrar_puerto_mac()` → `encontrar_puerto_pico()`,
      globs cambiados de `/dev/cu.usbmodem*`/`/dev/tty.usbmodem*` (macOS) a
      `/dev/ttyACM*` (Linux/Raspberry Pi OS)
- [x] `realtime_voice.py`: mismo cambio de `encontrar_puerto_pico()`, resto
      sin cambios de lógica
- [x] `v10/requirements.txt`: mismas dependencias que v9, con una nota
      explícita de por qué `picamera2` NO está ahí (se instala por `apt`)
- [x] Copiados los 79 tests de v9 → `v10/tests/`, con la ruta fake de
      `test_pico_serial.py` actualizada a `/dev/ttyACM_FAKE`
- [x] Verificado: 73 tests pasan, 6 se saltan (requieren `pysentimiento`,
      no instalado en esta máquina de desarrollo) dentro de `v10/.venv`, sin
      ninguna referencia a `v9/`

## Hito 2: Cámara CSI en vez de webcam del Mac ✅ (completo, sin validar en hardware)

**Objetivo:** que `face_tracker.py`/`webrtc_server.py` capturen frames de la
cámara CSI de la Raspberry Pi 5 (vía `picamera2`/`libcamera`) en vez de la
webcam del Mac (vía `cv2.VideoCapture`), sin tocar la lógica de
`FaceTracker.procesar()` — que no sabe ni le importa de dónde vino el frame.

- [x] `abrir_camara_csi()` y `leer_frame()` nuevas en `face_tracker.py`:
      envuelven `Picamera2`, configurada con `format="BGR888"` para que
      `capture_array()` entregue frames en el mismo orden de canal que
      `cv2.VideoCapture` entregaba antes — así `FaceTracker.procesar()` no
      tiene que distinguir el origen
- [x] Import de `picamera2` diferido dentro de `abrir_camara_csi()`, no a
      nivel de módulo — para que los tests (y cualquier uso de
      `FaceTracker`/`_mapear` sin cámara) no necesiten tenerlo instalado
- [x] `_run_standalone()` (script independiente de `face_tracker.py`)
      adaptado a la nueva cámara; quitado `--camera-index` (picamera2 no
      indexa cámaras USB por número igual que `cv2.VideoCapture` — una sola
      cámara CSI asumida, sin añadir una opción que no se pidió)
- [x] `webrtc_server.py`: `_hilo_rastreo()` recibe un `Picamera2` ya abierto
      y arrancado (mismo patrón que v9 con `cv2.VideoCapture`), usa
      `leer_frame()` en vez de `cap.read()`; `main()` llama a
      `abrir_camara_csi()` en vez de `cv2.VideoCapture(args.camera_index)`,
      con el mismo manejo de error (degrada a "sin rastreo" si falla, no
      tumba el servidor)
- [x] Documentado con honestidad que el patrón "abrir la cámara en el hilo
      principal" (heredado del bug real de AVFoundation en macOS, v9) se
      mantiene en esta versión por consistencia/precaución, **no** porque se
      haya confirmado un problema equivalente en Linux/picamera2 — eso solo
      se puede confirmar probando en la Pi 5 real

**Verificado sin hardware:** sintaxis, y que los tests de `FaceTracker`
siguen pasando sin `picamera2` instalado (import diferido funciona). Arranque
real de `webrtc_server.py --tracking` sin `picamera2` instalado: degrada
limpiamente, no crashea.

**No verificado, pendiente de la Pi 5 real:** que `picamera2` capture frames
de verdad, que `BGR888` entregue el orden de canal esperado, que no haya un
bug de threading equivalente al de macOS.

## Hito 3: Puerto serial de la Pico en Linux ✅ (completo, sin validar en hardware)

- [x] `encontrar_puerto_pico()` (antes `encontrar_puerto_mac()`) busca
      `/dev/ttyACM*` en vez de los nombres de macOS
- [x] Documentado el requisito de grupo `dialout` en Linux (no aplicable en
      macOS, donde nunca hizo falta) — sin él, `pyserial` falla con
      `PermissionError` y `PicoLink` se queda reintentando sin decir por qué
- [x] `_puerto_sigue_existiendo()` (chequeo de reconexión): sigue
      funcionando igual, solo cambia qué patrón de archivo comprueba

**No verificado, pendiente de la Pi 5 real:** que la Pico enumere
efectivamente como `/dev/ttyACM0` (comportamiento estándar de un dispositivo
USB CDC-ACM en Linux, pero no confirmado contra el hardware concreto de este
proyecto), y que el enlace serial completo (conectar, latido, reconexión)
funcione igual que en macOS.

## Hito 4: Voz por navegador con micro/parlante USB — decisión de arquitectura, sin cambios de código

**Objetivo:** decidir cómo captura audio la Pi 5, dado que no tiene el
micro/altavoz integrados del Mac ni (necesariamente) auriculares.

- [x] Decisión (con el usuario, antes de escribir código): mantener
      `webrtc_server.py` (navegador, con AEC real) como vía recomendada,
      igual que en v1-v9 — un micro y un parlante USB separados, sin
      auriculares, es exactamente el escenario para el que la cancelación de
      eco del navegador existe. La Pi 5 necesita pantalla y Chromium
      corriendo en modo kiosk (documentado en README-v10.md), no solo el
      micro/parlante
      - Descartada la alternativa de acceder al navegador desde otro
        dispositivo: eso pondría el micro/parlante reales en ese otro
        dispositivo, no en la Pi 5, contradiciendo el pedido
      - `realtime_voice.py` se mantiene sin cambios de lógica, como
        alternativa de prueba (igual que en v8/v9), no como la vía principal
- [x] `sounddevice`/PortAudio (usados por `realtime_voice.py`) y
      `getUserMedia` (usado por el navegador en `webrtc_server.py`) leen
      ambos el dispositivo de audio **por defecto del sistema** — ninguno de
      los dos necesita cambios de código para usar el micro/parlante USB, con
      tal de que estén fijados como predeterminados a nivel de sistema
      (PipeWire/`wpctl`, documentado en README-v10.md) antes de arrancar
- [x] Documentado en README-v10.md el setup de audio (paso 3) y de Chromium
      en modo kiosk, con `--autoplay-policy=no-user-gesture-required` para
      que el audio de la respuesta no quede bloqueado por falta de gesto del
      usuario en un arranque sin interacción manual

**Sin cambios de código en este hito** — es una decisión de arquitectura y
de despliegue, no de lógica: ni `webrtc_server.py` ni `realtime_voice.py`
necesitaron tocar nada relacionado con audio para funcionar en la Pi 5.

**No verificado, pendiente de la Pi 5 real:** que la cancelación de eco del
navegador funcione igual de bien con un parlante y un micrófono USB
físicamente separados (la configuración acústica de la Pi 5) que con el
micro/altavoz integrados y muy próximos del Mac (la configuración validada
en v9) — es la pieza de esta versión con más incertidumbre real, porque el
AEC del navegador no es algo que este proyecto controle ni pueda simular sin
el hardware delante.

---

## Definición de listo

v10.0.0 está lista cuando:

1. [x] Base de v9 (voz + sentimiento + rastreo + sueño) traída completa y
   verificada de forma autónoma
2. [x] Cámara CSI (`picamera2`) reemplaza a la webcam del Mac, sin tocar la
   lógica de `FaceTracker`
3. [x] Detección de puerto serial de la Pico adaptada a Linux
   (`/dev/ttyACM*`)
4. [x] Arquitectura de audio decidida y documentada (navegador con AEC real,
   micro/parlante USB fijados como predeterminados del sistema)
5. [ ] **Validada con hardware real de la Raspberry Pi 5** — cámara CSI,
   micrófono/parlante USB, y una Pico física, con una conversación hablada
   de verdad. Pendiente: es lo único que falta para que esta versión pase de
   "código completo" a "completa y validada", como todas las anteriores.

---

**Última actualización:** Agosto 14, 2026
**Estado actual:** v10.0.0 con código completo (Hitos 1-4) y 79 tests, todos
verificables sin hardware pasando (73 passed, 6 skipped por falta de
`pysentimiento` en la máquina de desarrollo). **Sin validar todavía en una
Raspberry Pi 5 real** — la primera vez que una versión de este proyecto llega
a este punto sin ninguna pieza del hardware nuevo (Pi 5, cámara CSI,
micro/parlante USB) probada de verdad. Versión abierta hasta esa validación.
