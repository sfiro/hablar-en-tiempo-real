# Plan de desarrollo — v9.0.0 Voz + sentimiento + rastreo facial real

---

## Hito 1: Base funcional traída completa ✅ (completado)

- [x] Copiado `main.py`, `pico_serial.py`, `estado_base.py`,
      `diagnostico_canal.py`, `realtime_voice.py`, `sentiment_analyzer.py`,
      `webrtc_server.py`, `static/index.html` desde `v8/`, sin cambios de
      lógica salvo lo descrito en el Hito 2
- [x] Retomado `face_tracker.py` desde `v7/` (v8 no lo tenía a propósito),
      sin cambios de lógica
- [x] `v9/requirements.txt`: unión de las dependencias de v8 (voz +
      sentimiento + pyserial) y de v7 (opencv-python)
- [x] Copiados los tests de v8 (65) y `test_face_tracker.py` de v7 → `v9/tests/`
- [x] Copiado `.env.example` (plantilla, sin la clave real)
- [x] Verificado: los 79 tests pasan dentro de `v9/.venv`, sin ninguna
      referencia a `v7/` ni `v8/`
- [x] Confirmado que `v8/` sigue intacto y sus propios tests siguen pasando
      tras la copia

## Hito 2: `webrtc_server.py` — rastreo facial real en un hilo de fondo ✅ (completo y validado en hardware real)

**Objetivo:** juntar, en el mismo proceso que ya maneja la conversación de
voz y el análisis de sentimiento, el rastreo facial real por cámara —
alcance acotado a propósito: solo `webrtc_server.py` (la forma recomendada),
no `realtime_voice.py`.

- [x] `_hilo_rastreo(cap, detener)`: hilo de fondo que lee frames de una
      `cv2.VideoCapture` ya abierta, los pasa por `FaceTracker.procesar()`
      (importado de `face_tracker.py`, sin cambios), y llama a
      `PICO.enviar(lr, ud)` (sin EMOCION) cuando hay un cambio significativo
- [x] `ULTIMA_MIRADA` + `_LOCK_MIRADA`: última posición real detectada,
      compartida con el endpoint de sentimiento — reemplaza el `90, 90` fijo
      que usaba v8 cuando no había cámara
- [x] Conexión a la Pico ya no depende solo de `--sentiment`: se conecta si
      `--sentiment` o `--tracking` están activos (ambos la necesitan, y solo
      puede haber un proceso con el puerto serial abierto a la vez)
- [x] Nuevas opciones `--tracking`, `--camera-index` — independientes de
      `--sentiment`: se puede rastrear sin sentimiento, tener sentimiento sin
      rastreo (como en v8), o ambos juntos
- [x] **Bug real encontrado y corregido, no anticipado:** el primer intento
      abría `cv2.VideoCapture` dentro del propio hilo de rastreo. En macOS
      eso falla con `"can not spin main run loop from other thread"` —
      AVFoundation necesita negociar el permiso de cámara desde el hilo
      principal. Corregido: `cv2.VideoCapture` se abre en `main()` (hilo
      principal) y solo el objeto ya abierto se pasa al hilo de fondo, que
      nunca vuelve a tocar la apertura ni el permiso
- [x] `main.py` (el firmware): **sin cambios**. Ya aceptaba LR/UD reales por
      serial desde v4, y el mecanismo de que 7 de las 10 expresiones sigan
      esa mirada mientras 3 la ignoran ya estaba construido desde v6/v7 —
      v9 solo empezó a mandarle datos reales en vez del valor fijo de v8

**Verificado con hardware real, con una Pico física conectada a este
entorno:** confirmado que el error de hilos desaparece con la corrección
(la cámara ya no falla por ese motivo). El error que queda —
`"OpenCV: not authorized to capture video"` — es el mismo bloqueo de
permiso ya documentado en v3: este entorno no puede conceder permisos de
cámara de forma interactiva. El resto de la cadena (Pico autodetectada y
conectada, `POST /api/analyze-sentiment` con frases reales, envío por
serial) se confirmó funcionando igual que en v8.

**Tests:** ninguno nuevo para el hilo de rastreo en sí — abrir una cámara
real y verificar detección no es matemática pura testeable sin hardware
(mismo criterio que v3-v8: la lógica de `FaceTracker` ya está cubierta por
`test_face_tracker.py`, heredado sin cambios). El hallazgo del hilo
principal se verificó ejecutando el servidor de verdad, no con un test.

**Validado por el usuario, con permiso de cámara concedido y una
conversación real:** "funciona bien, hace el tracking perfecto, y puedo
hablar en tiempo real" — el rastreo detecta el rostro y mueve los ojos/cuello
de la Pico en consecuencia, rastreo real + cambio de expresión por
sentimiento conviven bien a la vez sin conflictos entre los dos hilos, y la
conversación completa de punta a punta funciona con las tres piezas activas.

## Hito 3: Modo dormido por inactividad ✅ (completo y validado en hardware real)

**Objetivo, pedido explícito del usuario tras validar los Hitos 1-2:** si
pasa `--sleep-timeout` segundos (60 por defecto) sin que el usuario hable, la
Pico entra en `DORMIDO`; al volver la actividad, se despierta con `DUDA` y de
ahí pasa sola a `NEUTRAL`.

- [x] `_hilo_vigia_sueno()`: hilo nuevo que reenvía `DORMIDO` cada segundo
      mientras dure el silencio (reutiliza "la misma emoción repetida
      extiende el pulso", ya probado desde v8 — no hace falta que `main.py`
      sepa que existe un modo dormido distinto) y manda `DUDA` una sola vez
      al detectar la primera actividad tras el silencio (el propio pulso de
      5s de la Pico la devuelve sola a `NEUTRAL`, sin intervención adicional)
- [x] `_decidir_sueno(ahora, ultima_actividad, timeout, dormido_previo)`:
      lógica pura, sin `threading`/`time.sleep`, aislada para poder probarla
      directamente con valores de tiempo fijos
- [x] `ULTIMA_ACTIVIDAD` se actualiza en `_handle_analyze_sentiment()` para
      cualquier frase del usuario, con o sin `--sentiment` activo — el
      navegador manda la transcripción de todos modos, así que el conteo de
      inactividad no depende de que el análisis de sentimiento esté encendido
- [x] Decisión explícita: solo cuenta como actividad lo que dice el
      **usuario**, no el asistente — "si no se le habla al robot" se
      interpretó como actividad del usuario específicamente
- [x] Nueva opción `--sleep-timeout` (por defecto 60s); el hilo arranca
      siempre que haya una Pico conectada, sin necesitar un flag propio
- [x] `main.py` (el firmware): **sin cambios**, otra vez — el modo dormido
      es enteramente una construcción del lado del Mac sobre mecanismos ya
      existentes y probados en el firmware

**Tests nuevos** (`tests/test_webrtc_server.py`, 5 tests): no duerme antes de
tiempo, duerme justo al cumplirse el timeout, se mantiene dormida sin repetir
el gesto de despertar en cada vuelta, despierta una sola vez cuando vuelve la
actividad, y no marca "despertando" si ya estaba despierta.

**Validado con hardware real, con una Pico física conectada a este entorno:**
se lanzó el servidor con `--sleep-timeout 4` (para no esperar los 60s por
defecto) y se confirmó la secuencia completa por los logs y el envío serial
real — tras 4s sin actividad, mensaje de "se duerme" + envío repetido de
`DORMIDO`; al llegar una frase de prueba, mensaje de "despertando" + envío de
`DUDA` una sola vez.

---

## Definición de listo

v9.0.0 está lista cuando:

1. [x] Base de v8 (voz + sentimiento + Pico) y v7 (`face_tracker.py`) traída
   completa y verificada de forma autónoma
2. [x] `webrtc_server.py` rastrea por cámara en un hilo de fondo, comparte la
   conexión a la Pico con el endpoint de sentimiento, y manda la mirada real
   (no un valor fijo) junto con cada EMOCION
3. [x] Bug real de threading (apertura de cámara en el hilo equivocado)
   encontrado y corregido, confirmado con el servidor corriendo de verdad
4. [x] Validado con permiso de cámara concedido, rastreo real + sentimiento
   activos a la vez, y una conversación hablada de verdad — confirmado por
   el usuario
5. [x] Modo dormido por inactividad: `DORMIDO` tras `--sleep-timeout`
   segundos de silencio, `DUDA` al despertar, sin cambios en `main.py` —
   validado con hardware real

---

**Última actualización:** Agosto 10, 2026
**Estado actual:** v9.0.0 completa y validada en hardware real — Hitos 1-3,
con 79 tests, rastreo real + voz + sentimiento confirmados juntos por el
usuario ("funciona bien, hace el tracking perfecto, y puedo hablar en tiempo
real"), y el modo dormido por inactividad añadido y validado después. Versión
cerrada.
