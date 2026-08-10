# Plan de desarrollo — v8.0.0 Voz + sentimiento controlando la expresión facial

---

## Hito 1: Base funcional traída completa ✅ (completado)

- [x] Copiado `v2/realtime_voice.py` y `v2/sentiment_analyzer.py` → `v8/`, sin
      cambios de lógica en la conversación de voz ni en el análisis de
      sentimiento
- [x] Copiado `v7/main.py`, `v7/pico_serial.py`, `v7/estado_base.py`,
      `v7/diagnostico_canal.py` → `v8/`
- [x] `v8/requirements.txt`: unión de las dependencias de v2 (voz +
      pysentimiento) y de v7 (pyserial) — nada nuevo, solo la unión
- [x] Copiado `v2/tests/test_sentiment.py` y `v7/tests/test_estado_base.py` /
      `test_pico_serial.py` → `v8/tests/`, sin cambios
- [x] Copiado `v2/.env.example` (plantilla, sin la clave real — nunca se
      copia un `.env` real entre carpetas de versión)
- [x] Deliberadamente **no** se copió `face_tracker.py` ni su test: v8 no
      rastrea el rostro todavía (pedido explícito, ver Hito 3)
- [x] Verificado: los 65 tests pasan dentro de `v8/.venv`, sin ninguna
      referencia a `v2/` ni `v7/`
- [x] Confirmado que `v7/` sigue intacto y sus propios tests siguen pasando
      tras la copia

## Hito 2: `main.py` — de ciclo fijo a pulso dirigido por EMOCION ✅ (completo y validado en conversación real)

**Objetivo:** el firmware dejaba de ciclar sola por las 10 expresiones cada
5s (v6/v7) y en su lugar adopta la expresión que llegue por el campo EMOCION
del comando serial, manteniéndola 5s (el mismo `INTERVALO_EXPRESION_MS` de
antes, reusado con otro propósito) y volviendo sola a NEUTRAL si no llega una
nueva a tiempo.

- [x] `cambiar_emocion(nueva_emocion, ahora)`: único punto donde cambia
      `emocion_actual` — lo usan tanto `procesar_comando()` (EMOCION nuevo
      por serial) como el bucle principal (expiración del pulso). Reutiliza,
      sin cambios, la lógica ya existente de recentrar la mirada al salir de
      DUDA/PENSATIVO/NERVIOSO y de reiniciar los temporizadores de DUDA y
      NERVIOSO al entrar a ellas — antes vivía repetida en dos sitios
      (bloque de cambio de expresión + `KeyboardInterrupt` no, ese no la
      tenía), ahora en una sola función
- [x] `procesar_comando()`: aplica el cambio de emoción **antes** de fijar
      `objetivo_actual[LR]/[UD]` con los valores del mismo comando — así, si
      el cambio de emoción resetea la mirada al centro (por salir de
      DUDA/PENSATIVO/NERVIOSO), el valor real recibido en ese mismo comando
      tiene la última palabra, no el reset transitorio
- [x] Eliminados `SECUENCIA_EMOCIONES`, `indice_emocion` y el bloque de ciclo
      fijo — ya no hace falta ciclar nada, la fuente de la expresión es
      siempre el EMOCION recibido (o su ausencia, que decae a NEUTRAL)
- [x] Sin cambios en `actualizar_objetivo_expresion()`,
      `actualizar_objetivo_mirada_expresion()`, `parpadear()`: dependen de
      `emocion_actual` sin importar cómo se estableció, así que el mecanismo
      de pulso es transparente para ellas

**Tests reescritos** (`tests/test_main_math.py`): se quitó
`test_todas_las_emociones_de_la_secuencia_tienen_offsets_definidos` (ya no
hay secuencia) y se añadió `EstadoExpresion`, una réplica de prueba de
`cambiar_emocion()` + el chequeo de expiración del pulso, con 9 tests nuevos:
una emoción nueva activa el pulso, expira a los 5s y vuelve a NEUTRAL, una
emoción nueva antes de expirar reemplaza el pulso en curso, la misma emoción
repetida lo extiende (no lo hace parpadear a NEUTRAL entre frases similares),
una emoción no reconocida se ignora, DUDA/NERVIOSO reinician sus
temporizadores al recibirse, y salir de DUDA o NERVIOSO (por una emoción
nueva o por expiración del pulso) recentra la mirada. El resto de tests de
`test_main_math.py` (párpados, cuello, TRISTE, barrido de DUDA, saltos de
NERVIOSO) se heredaron de v7 sin cambios, porque esa matemática no cambió.

## Hito 3: Mac — la emoción detectada controla la Pico ✅ (completo y validado en conversación real)

**Objetivo:** con `--sentiment` activo, cada emoción detectada en la
conversación (por encima de `--confidence-threshold`, igual que ya se exige
para mostrarla en consola) se traduce al vocabulario de la Pico y se envía
por serial.

- [x] `EMOTION_TO_PICO`: mapeo `pysentimiento` → Pico, con las 5
      correspondencias ya documentadas y razonadas en v3 (joy→FELIZ,
      sadness→TRISTE, anger→ENOJADO, fear→NERVIOSO, surprise→SORPRENDIDO)
- [x] **Cambiado a pedido explícito del usuario:** las 7 categorías de
      pysentimiento deben mapear a alguna expresión del robot, ninguna sin
      enviar. `disgust`→`SOSPECHA` (no hay "ASCO"; se degrada a la más
      parecida facialmente, mismo criterio que fear→NERVIOSO) y
      `others`→`NEUTRAL` (corresponde 1 a 1). `DORMIDO`/`DUDA`/`PENSATIVO`
      se quedan sin usar: no hay categoría de pysentimiento que les
      corresponda ni de lejos — forzar una sería inventar precisión que no
      existe, no degradarla a la más cercana
- [x] Efecto colateral documentado y aceptado: al enviar `NEUTRAL` para
      `others`, una frase neutra puede cortar antes de tiempo el pulso de
      una expresión real en curso (antes no pasaba, porque disgust/others
      no enviaban nada) — consecuencia esperada de que las 7 categorías
      manden algo, no un bug
- [x] Conexión a la Pico autodetectada (`encontrar_puerto_mac()`), igual
      patrón que `face_tracker.py` en versiones anteriores — sin Pico,
      sigue funcionando la conversación normalmente
- [x] Nueva opción `--no-pico`: desactiva el envío aunque haya una Pico
      conectada, para probar sentimiento sin tocar el hardware
- [x] `pico.stop()` en el `finally` del bucle principal, junto al resto de
      la limpieza de recursos

**Verificado con una prueba real, aunque parcial:** se lanzó
`realtime_voice.py --sentiment` con una clave de API inválida a propósito.
Con una Pico real conectada a este entorno, `encontrar_puerto_mac()` la
detectó y `PicoLink` se conectó sola. El fallo fue el esperado y ya
documentado desde v1 (`ConnectionClosedError: … invalid_api_key`) — confirma
que toda la cadena hasta el punto de fallo (entorno, TLS, websockets,
detección y conexión de la Pico) funciona.

**Validado con una conversación real por el usuario:** las 6 frases de
prueba (una por emoción no neutral, ver README-v8.md) dispararon el cambio
de expresión correcto en la Pico — "ha funcionado muy bien y el robot
también ha seguido todos los sentimientos". El mapeo completo y la duración
del pulso (5s) se sienten bien ajustados en la práctica.

## Hito 4: `webrtc_server.py` — la conversación pasa al navegador ✅ (completo y validado en conversación real)

**Objetivo:** el usuario reportó que la versión de terminal (medio-dúplex,
interrumpir con Enter) no daba la conversación instantánea que se quería, y
pidió explícitamente lo ya resuelto en v1 para este mismo problema: que la
voz viva en el navegador (WebRTC, cancelación de eco real, interrupción
natural hablando encima), y que a la terminal/Python solo le llegue el texto
transcrito, para el análisis de sentimiento y el envío a la Pico.

- [x] Copiados `v1/webrtc_server.py` y `v1/static/index.html` → `v8/`, sin
      cambios en la negociación SDP/WebRTC en sí
- [x] Nuevo endpoint `POST /api/analyze-sentiment` en `webrtc_server.py`:
      recibe `{"role", "text"}`, corre `sentiment_analyzer.analyze()`, y si
      supera `--confidence-threshold` envía la expresión mapeada a la Pico —
      misma lógica que `realtime_voice.py`, duplicada a propósito (mismo
      criterio de "copiar, no importar" entre ficheros autónomos)
- [x] **Por qué hace falta un endpoint nuevo, no basta con lo que ya
      recibía el servidor:** con WebRTC, el audio y los eventos de la API
      (incluida la transcripción) van directo entre el navegador y OpenAI —
      `webrtc_server.py` solo negocia la conexión (intercambia SDP) y nunca
      ve ni un byte de la conversación. Sin este endpoint, Python no tendría
      ninguna forma de saber qué se dijo.
- [x] `static/index.html`: al completarse la transcripción de cada frase
      (`response.output_audio_transcript.done` para el asistente,
      `conversation.item.input_audio_transcription.completed` para el
      usuario) se manda el texto a `/api/analyze-sentiment`, y la respuesta
      se muestra como una insignia junto a la frase en la transcripción
      (emoji + etiqueta + confianza + comando enviado a la Pico, si hubo uno)
- [x] `--sentiment`, `--language`, `--confidence-threshold`, `--no-pico`:
      mismos flags y mismo comportamiento que en `realtime_voice.py`
- [x] `realtime_voice.py` se mantiene sin cambios de comportamiento —
      sigue siendo una alternativa válida para probar sin navegador

**Tests nuevos** (`tests/test_webrtc_server.py`, 2 tests): el
`EMOTION_TO_PICO` de `webrtc_server.py` es idéntico al de `realtime_voice.py`
(evita que las dos copias diverjan sin querer) y cubre las 7 categorías de
`pysentimiento`.

**Verificado en dos pasos.** Primero a mano, sin necesitar clave de API
(`webrtc_server.py --sentiment --no-browser` sirvió la página y
`POST /api/analyze-sentiment` con frases reales disparó el envío por serial
correcto). Después, **con una conversación real completa por el usuario**:
clave de API válida, hablando de verdad por el navegador, con la Pico
física — confirmado que las 7 categorías alcanzables mueven la expresión
correspondiente y que la latencia percibida es aceptable.

---

## Definición de listo

v8.0.0 está lista cuando:

1. [x] Base de v2 (voz + sentimiento) y v7 (firmware + serial) traída
   completa y verificada de forma autónoma
2. [x] `main.py` cambiado de ciclo fijo a pulso dirigido por EMOCION,
   verificado sin hardware con tests
3. [x] `realtime_voice.py` envía la emoción detectada a la Pico, con el
   mapeo completo (7 categorías) documentado y razonado
4. [x] `webrtc_server.py`: la conversación de voz se mueve al navegador
   (WebRTC, cancelación de eco real), con el análisis de sentimiento y el
   envío a la Pico funcionando igual vía un endpoint nuevo — verificado a
   mano con una Pico real
5. [x] Validado con una conversación real (clave de API válida + hablar de
   verdad + Pico física): las 6 frases de prueba (una por emoción no neutral)
   movieron la expresión correcta de la Pico — confirmado por el usuario:
   "ha funcionado muy bien y el robot también ha seguido todos los
   sentimientos"

---

**Última actualización:** Agosto 10, 2026
**Estado actual:** v8.0.0 completa y validada en hardware real — Hitos 1-4,
con 65 tests, y conversación real de punta a punta (WebRTC + sentimiento +
Pico) confirmada por el usuario. Versión cerrada.
