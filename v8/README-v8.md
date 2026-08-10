# Versión 8.0 — Voz + sentimiento controlando la expresión facial 🎙️👁️

**Objetivo:** juntar lo construido en v1/v2 (conversación de voz en tiempo real
+ análisis de sentimiento) con lo construido en v6/v7 (firmware de la Pico +
secuencia de expresiones): la emoción detectada en cada frase de la
conversación pasa a controlar la expresión facial del robot. **Sin rastreo
facial todavía** — eso es lo próximo (v9), a propósito: primero se valida que
voz + sentimiento + expresión funcionen bien juntos, sin la complejidad de la
cámara encima.

**Estado: completa y validada en hardware real.** Confirmado por el usuario
hablando de verdad con el asistente por el navegador, con la Pico física
conectada: "ha funcionado muy bien y el robot también ha seguido todos los
sentimientos" — las 7 categorías de sentimiento alcanzables (ver el mapeo más
abajo) movieron la expresión correcta.

## Dos formas de hablar: navegador (recomendado) o terminal

**`webrtc_server.py` — la forma recomendada, nueva en v8.** Sirve una página
en el navegador que habla con la Realtime API por WebRTC, igual que
`v1/webrtc_server.py`: cancelación de eco real del navegador, conversación
sin lag, y puedes interrumpir al asistente hablando por encima, sin los
paliativos que necesita la terminal (medio-dúplex, Enter para interrumpir).
Pedido explícito: la conversación de voz vive en el navegador; a Python solo
le debe llegar el texto ya transcrito, para el análisis de sentimiento y el
envío a la Pico.

**`realtime_voice.py` — se mantiene, para pruebas de terminal sin navegador.**
Es v2 sin cambios de lógica en la conversación de voz ni en el análisis de
sentimiento — sigue funcionando igual que antes de esta actualización, con
sus paliativos de medio-dúplex. Útil para probar sentimiento/Pico sin abrir
un navegador, o en un entorno sin pantalla.

## Arquitectura de la conversación en tiempo real

Cómo se debe implementar esta integración, de punta a punta (ruta
recomendada, con `webrtc_server.py`):

```
Navegador (getUserMedia, cancelación de eco real)
   │  WebRTC: audio + canal de datos "oai-events"
   ▼
OpenAI Realtime API (transcribe + responde)
   │  el navegador ve la transcripción por el canal de datos —
   │  webrtc_server.py NUNCA la ve, solo negoció la conexión (SDP)
   ▼
Navegador ── POST /api/analyze-sentiment ──▶ webrtc_server.py
                                                │  sentiment_analyzer.analyze(texto)
                                                │  (pysentimiento: 6 emociones
                                                │  de Ekman + neutral)
                                                │  EMOTION_TO_PICO[emoción],
                                                │  si supera el umbral de
                                                │  confianza (0.5 por defecto)
                                                ▼
                                            PicoLink.enviar(90, 90, EMOCION)
                                                │  USB serial "90,90,EMOCION\n"
                                                ▼
                                     Pico (main.py): cambiar_emocion()
                                                │  mantiene la expresión 5s;
                                                │  si no llega una nueva,
                                                │  vuelve sola a NEUTRAL
                                                ▼
                                              servos
```

**Por qué hace falta el endpoint `/api/analyze-sentiment` y no basta con lo
que ya recibía el servidor:** con WebRTC, el micrófono lo captura el
navegador (no Python) y la sesión completa —audio y eventos de la API,
incluida la transcripción— viaja directo entre el navegador y OpenAI por el
canal de datos `oai-events`. `webrtc_server.py` solo hizo una cosa al
arrancar la llamada: reenviar la oferta SDP a OpenAI firmada con la clave, y
devolver la respuesta — después de eso, no ve ni un byte de la conversación.
Por eso el navegador tiene que mandarle explícitamente el texto de cada frase
ya transcrita, y por eso el análisis de sentimiento y el envío a la Pico
viven en un endpoint HTTP nuevo, no en el flujo de negociación WebRTC.

**Por qué el firmware mantiene el estado con un pulso de 5s en vez de recibir
`NEUTRAL` explícito tras cada frase:** porque `disgust`/`others` sí mandan
`NEUTRAL` explícitamente (ver la tabla de mapeo), y una frase sin carga
emocional entre dos frases con la misma emoción fuerte no debería cortar el
gesto a la mitad — el pulso de 5 segundos absorbe ese ruido. Frases repetidas
con la misma emoción **extienden** el pulso en vez de reiniciarlo desde cero
de forma redundante, así que una conversación sostenidamente alegre no hace
parpadear la cara de vuelta a NEUTRAL entre una frase feliz y la siguiente.

**Confirmado hablando de verdad:** la latencia percibida es la suma de
transcripción (streaming, casi inmediata) + inferencia de sentimiento
(cientos de ms, corre en un hilo aparte vía `ThreadingHTTPServer` — no bloquea
la conversación) + el tiempo de suavizado EMA del firmware (gradual, no un
salto). En la práctica, la expresión cambia a los pocos segundos de terminada
la frase.

## Qué cambia respecto a v1/v2 y v6/v7

**Del lado del Mac, en ambos scripts:** con `--sentiment` activo y una Pico
conectada (autodetectada, igual que ya hacía `face_tracker.py` en v3-v7),
cada emoción detectada por encima de `--confidence-threshold` se traduce al
vocabulario de la Pico (`EMOTION_TO_PICO`) y se envía por serial.

- **`realtime_voice.py`:** analiza el texto directamente, porque ya lo tiene
  (la conversación entera pasa por este proceso vía WebSocket).
- **`webrtc_server.py`:** aquí Python **nunca ve la transcripción** — con
  WebRTC, el audio y los eventos de la API (incluida la transcripción) van
  directo entre el navegador y OpenAI por el canal de datos `oai-events`; este
  proceso solo negocia la conexión (intercambia SDP). Por eso hay una pieza
  nueva: `static/index.html` manda el texto de cada frase completa a
  `POST /api/analyze-sentiment` en cuanto la tiene, y ese endpoint (nuevo en
  este fichero) hace el análisis y el envío a la Pico exactamente igual que
  `realtime_voice.py`. El navegador muestra la emoción detectada junto a cada
  frase en la transcripción, para poder verificar que está funcionando.

**Del lado de la Pico (`main.py`): este es el cambio de fondo de la versión.**
En v6/v7, la expresión cambiaba sola cada 5 segundos, cicladas en un orden
fijo, sin depender de nada externo. En v8 eso se reemplaza por un modelo
dirigido por eventos: la expresión cambia cuando llega un comando
`"LR,UD,EMOCION\n"` con un EMOCION válido, se mantiene durante
`INTERVALO_EXPRESION_MS` (5000ms, el mismo valor de antes, ahora usado como
duración del "pulso" en vez de periodo del ciclo), y si no llega una emoción
nueva antes de que expire, vuelve sola a NEUTRAL — el estado base. Antes de
v8, ese tercer campo del protocolo se aceptaba pero se ignoraba (documentado
así desde v3); ahora es lo que decide la expresión. Esta parte es igual sin
importar cuál de los dos scripts del Mac esté mandando el comando.

## Mapeo de emoción → expresión de la Pico

Las 5 primeras corresponencias vienen razonadas desde v3, reutilizadas sin
cambios. **Pedido explícito en v8: las 7 categorías de pysentimiento mapean
ahora a alguna expresión del robot — ninguna se queda sin enviar:**

| pysentimiento (`result["emotion"]`) | Comando a la Pico | Nota |
|---|---|---|
| `joy` | `FELIZ` | directo |
| `sadness` | `TRISTE` | directo |
| `anger` | `ENOJADO` | directo |
| `fear` | `NERVIOSO` | no hay "MIEDO" en el vocabulario de la Pico |
| `surprise` | `SORPRENDIDO` | directo |
| `disgust` | `SOSPECHA` | no hay "ASCO"; se degrada a la más parecida facialmente (párpados entrecerrados, mirada de rechazo) |
| `others` (neutral) | `NEUTRAL` | corresponde 1 a 1 |

**`DORMIDO`, `DUDA` y `PENSATIVO` se quedan sin usar en esta versión.** No es
un olvido: pysentimiento solo detecta las 6 emociones de Ekman + neutral —
no hay ninguna categoría suya que corresponda, ni de lejos, a "duda" o
"sueño". Forzar una correspondencia inventada iría contra el mismo criterio
que ya se siguió con `fear`→`NERVIOSO` (degradar a lo más cercano cuando hay
algo parecido, no inventar precisión que no existe). Para que esas tres
aparezcan en una conversación real haría falta otro mecanismo — por ejemplo,
que el propio modelo de voz las elija por function-calling durante la
conversación, como hacía `ojosMecanicos` (ver `model.md`) — no forzarlas
sobre un clasificador de sentimiento que no las conoce.

**Efecto colateral aceptado de que `others` ahora sí envíe `NEUTRAL`:** antes
(cuando disgust/others no enviaban nada), la expresión activa siempre
terminaba su pulso de 5 segundos sin interrupción. Ahora, una frase neutra
puede cortarlo antes de tiempo. Es la consecuencia esperada de que las 7
categorías manden algo — si se prefiere el comportamiento anterior, es un
cambio de una línea en `EMOTION_TO_PICO`.

**Frases repetidas con la misma emoción extienden el pulso**, no lo
reinician desde cero de forma redundante: cada `pico.enviar(...)` con un
EMOCION nuevo (aunque sea la misma que la actual) refresca cuándo expira, así
que una conversación sostenidamente alegre no hace parpadear la cara de vuelta
a NEUTRAL entre una frase feliz y la siguiente.

## Cómo probarlo

Hacen falta dos procesos: el firmware en la Pico, y la conversación en el Mac.

**1. Firmware (Pico):** despliega `main.py` como en versiones anteriores —
Thonny, `Archivo → Guardar como → Raspberry Pi Pico`, nómbralo `main.py`, y
reinicia la placa físicamente (no uses el botón ▶ Run, ver la lección de v5).

**2. Conversación (Mac), recomendado — navegador:**
```bash
cd v8
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y pon tu OPENAI_API_KEY real
python webrtc_server.py --sentiment
```
Se abre solo el navegador en `http://localhost:8000/`; pulsa «Conectar». Por
defecto intenta conectar con la Pico automáticamente; usa `--no-pico` para
probar sin tocar la Pico, o sin `--sentiment` para la conversación de voz
sola (igual que `v1/webrtc_server.py`).

**Alternativa — terminal, sin navegador:**
```bash
python realtime_voice.py --sentiment
```
Mismas opciones (`--no-pico`, `--confidence-threshold`, etc.), pero con los
paliativos de medio-dúplex de v1/v2 en vez de cancelación de eco real.

**Qué observar:** al decir algo con carga emocional clara ("qué alegría",
"esto me da mucha rabia"), la expresión de la Pico debería cambiar a los
pocos segundos (latencia de la transcripción + la inferencia de
sentimiento), mantenerse 5 segundos, y volver sola a NEUTRAL si no sigue una
frase con emoción similar. En el navegador, además, debería aparecer la
emoción detectada junto a cada frase de la transcripción (p. ej. "😊 ALEGRÍA
(0.99) → FELIZ").

## Cómo se verificó

**Sin hardware ni conversación real:**
- Sintaxis de los 7 ficheros `.py` (`py_compile`)
- 65 tests: los heredados de v2 (`test_sentiment.py`, sin cambios — incluye
  los que descargan el modelo real de `pysentimiento`) y de v7
  (`test_estado_base.py`, `test_pico_serial.py`, sin cambios), `test_main_math.py`
  reescrito para el mecanismo de pulso (una emoción nueva lo activa, expira a
  los 5s y vuelve a NEUTRAL, una nueva antes de expirar lo reemplaza, la misma
  emoción repetida lo extiende, una no reconocida se ignora, entrar/salir de
  DUDA/PENSATIVO/NERVIOSO sigue reiniciando sus temporizadores y recentrando
  la mirada), y `test_webrtc_server.py` (nuevo): el `EMOTION_TO_PICO` de
  `webrtc_server.py` es idéntico al de `realtime_voice.py` y cubre las 7
  categorías de `pysentimiento` — con dos copias del mismo diccionario en dos
  ficheros autónomos, este test detecta si divergen sin querer

**Confirmado con pruebas reales, previas a la conversación completa:**
- `realtime_voice.py --sentiment` con una clave de API inválida a propósito
  (para no consumir cuota): con una Pico real conectada a este entorno, se
  detectó y conectó sola (`✅ Pico detectada en /dev/cu.usbmodem...`), y el
  fallo fue exactamente el esperado desde v1 (`ConnectionClosedError: …
  invalid_api_key`) — confirma entorno, TLS, websockets y conexión a la Pico
- `webrtc_server.py --sentiment --no-browser`, sin necesidad de clave de API
  ni de conectar de verdad con OpenAI (el endpoint nuevo es independiente de
  la negociación SDP): sirvió la página (`200`), y `POST
  /api/analyze-sentiment` con frases reales devolvió el análisis correcto y
  disparó el envío por serial a la Pico real conectada — `{"role": "user",
  "label": "ALEGRÍA", "confidence": 0.99, "pico": "FELIZ"}` para una frase
  alegre, `{"label": "ASCO", "pico": "SOSPECHA"}` para una de asco

**Confirmado por el usuario, conversación real de punta a punta con clave de
API válida y Pico física:** las 6 frases de prueba (una por cada emoción no
neutral: alegría, tristeza, rabia, miedo, sorpresa, asco — ver la lista
verificada más abajo) movieron la expresión correcta de la Pico. Frases
cortas sin carga emocional explícita fallan como ya estaba documentado desde
v2 (el modelo las confunde con otra categoría) — no es un bug de esta
integración, es la limitación real y conocida del clasificador.

**Frases de prueba verificadas** (las mismas de `test_sentiment.py`, ya
confirmadas contra el modelo real):

| Dila así | Detecta | Robot muestra |
|---|---|---|
| "Estoy feliz de verte, qué alegría" | ALEGRÍA | FELIZ |
| "Estoy muy triste, perdí a mi mascota" | TRISTEZA | TRISTE |
| "Odio que me traten así, es indignante" | RABIA | ENOJADO |
| "Tengo mucho miedo, esto me aterra" | MIEDO | NERVIOSO |
| "No puedo creerlo, esto es una sorpresa total" | SORPRESA | SORPRENDIDO |
| "Esto me da asco" | ASCO | SOSPECHA |

Para NEUTRAL no hace falta forzar una frase neutra a propósito (es la
categoría que peor clasifica el modelo, con falsos positivos documentados) —
basta con esperar 5 segundos sin decir nada con carga emocional después de
cualquier otra expresión.

**Sin verificar todavía:**
- Que el pulso de 5 segundos sea la duración ideal en una conversación larga
  y natural (se confirmó que funciona, no que sea el valor óptimo)
- Que enviar `pico.enviar(90, 90, ...)` repetidamente durante una conversación
  larga no sature el enlace serial ni el heartbeat de `PicoLink`

## Qué NO incluye esta versión (a propósito)

- **Rastreo facial real.** LR/UD van fijos a 90,90 — el Mac de esta versión no
  tiene cámara conectada. Es lo siguiente (v9), pedido explícitamente para
  después de validar voz + sentimiento + expresión.
- **Sincronía de párpados con la mirada**, joystick, modo autónomo — mismos
  pendientes ya documentados desde v6/v7.

## Ficheros de esta versión

- **`webrtc_server.py` + `static/index.html`** — nuevos en v8, copiados de
  `v1/webrtc_server.py` y `v1/static/index.html` y extendidos con
  `/api/analyze-sentiment` (servidor) y el envío del texto transcrito a ese
  endpoint + la insignia de emoción en la transcripción (navegador). La
  negociación WebRTC en sí no cambió respecto a v1.
- **`realtime_voice.py`, `sentiment_analyzer.py`** — copias de v2.
  `sentiment_analyzer.py` sin cambios; `realtime_voice.py` con el mismo
  `EMOTION_TO_PICO` y la misma lógica de envío a la Pico que
  `webrtc_server.py` (duplicados a propósito entre los dos ficheros, no
  importados — ver `test_webrtc_server.py`, que comprueba que no diverjan).
- **`pico_serial.py`, `estado_base.py`, `diagnostico_canal.py`** — copias de
  v7, sin cambios de lógica.
- **`main.py`** — copia de v7 con el cambio de fondo descrito arriba (ciclo
  fijo → pulso dirigido por EMOCION). El resto (párpados, cuello, parpadeo,
  DUDA/PENSATIVO/NERVIOSO) no cambió.

Mapeo de pines (igual que en versiones anteriores):

```
LR=GP2   UD=GP3   TL=GP4   BL=GP5   TR=GP6   BR=GP7   PAN=GP8   TILT=GP9
```

## Próximos pasos (fuera de esta versión)

1. Rastreo facial real (v9): retomar `face_tracker.py`, ahora combinado con
   el control de expresión por sentimiento de esta versión
2. Sincronía de párpados con la mirada, joystick, modo autónomo — pendientes
   heredados de versiones anteriores

## Referencias

- [`../v7/README-v7.md`](../v7/README-v7.md) — seguimiento visual real +
  secuencia de expresiones (base de la que parte el firmware de esta versión)
- [`../v6/README-v6.md`](../v6/README-v6.md) — detalle de cada expresión y
  sus offsets
- [`../v2/README-v2.md`](../v2/README-v2.md) — análisis de sentimiento, con
  las limitaciones reales del modelo documentadas con datos reales
- [`../v5/README-v5.md`](../v5/README-v5.md) — historial completo de por qué
  el firmware usa PWM directo en vez de PCA9685
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) —
  documentación de hardware; incluye una nota comparando esta arquitectura
  (clasificador de sentimiento aparte) con la de function-calling que describe
  ese documento para el mismo problema
- [PLAN-v8.md](PLAN-v8.md) — hitos
