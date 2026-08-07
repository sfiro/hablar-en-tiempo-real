# CLAUDE.md

Guía de todo el proyecto para trabajar en este repositorio. Cada versión (`v1/`, `v2/`,
`v3/`) tiene su propia documentación detallada; este fichero es el mapa general y
recoge los hechos que cruzan versiones. Empieza aquí, salta al `CLAUDE-vN.md` de la
versión concreta cuando necesites el detalle de implementación.

## Qué es el proyecto

Un asistente de voz en tiempo real contra la **Realtime API de OpenAI**, que crece por
versiones aditivas: cada una construye sobre la anterior sin romperla.

- **v1** — conversación de voz, dos transportes (WebRTC en navegador, WebSocket en
  terminal). Completa, respaldada con tag `v1.0.0`.
- **v2** — v1 + análisis de emociones de cada frase (`pysentimiento`), mostrado en
  consola. Código completo y probado contra el modelo real; falta validar con una
  conversación hablada de verdad.
- **v3** — v2 + rastreo facial por cámara y (opcional) control de servos vía una
  Raspberry Pi Pico. En planificación, sin código todavía.

Cada versión vive en su propia carpeta con su propio `.venv/`, `requirements.txt` y
`.env`. **No hay dependencias cruzadas de código** entre versiones: v2 es una copia de
v1 con el añadido de sentimiento, no un import de v1. Es deliberado — permite que v1
quede congelada y estable mientras v2/v3 evolucionan.

## Entorno, por versión

Cada carpeta tiene su propio venv. Usa siempre el Python de ese venv, nunca el del
sistema (los certificados TLS y las dependencias están solo ahí):

```bash
cd v1 && .venv/bin/python realtime_voice.py
cd v2 && .venv/bin/python realtime_voice.py --sentiment
```

`OPENAI_API_KEY` se carga con `python-dotenv` desde el `.env` de cada carpeta de
versión (no hay un `.env` compartido en la raíz). Está en `.gitignore`; nunca lo leas
en voz alta, lo copies fuera de su carpeta, ni lo incluyas en salidas o commits.

## v1 — Voz en tiempo real

Dos programas: [`v1/webrtc_server.py`](v1/webrtc_server.py) (recomendado, WebRTC,
cancelación de eco real del navegador) y [`v1/realtime_voice.py`](v1/realtime_voice.py)
(terminal, WebSocket, sin AEC real — usa paliativos: `MicGate`, `BargeInDetector`,
half-duplex).

**El hecho más importante de v1:** el navegador tiene AEC real
(`getUserMedia({echoCancellation: true})`) y Python con PortAudio no. Por eso la
versión WebRTC no se autointerrumpe con altavoces y la de terminal necesita
compuertas y umbrales para aproximarse a lo mismo. Antes de tocar esos paliativos en
`realtime_voice.py`, pregunta si no conviene simplemente usar `webrtc_server.py`.

Detalle completo, con todos los bugs encontrados y por qué cada pieza está como está:
[`v1/CLAUDE-v1.md`](v1/CLAUDE-v1.md).

## v2 — + Análisis de emociones

[`v2/realtime_voice.py`](v2/realtime_voice.py) es v1 (versión terminal) con
`--sentiment` añadido. [`v2/sentiment_analyzer.py`](v2/sentiment_analyzer.py) es el
clasificador, independiente y reutilizable.

**El hecho más importante de v2:** el modelo (`pysentimiento`, RoBERTuito para
español) clasifica las **6 emociones de Ekman + neutral** (`joy`, `sadness`, `anger`,
`fear`, `surprise`, `disgust`, `others`) — nada más. La primera versión de este
proyecto prometía 10 emociones (incluyendo "esperanza", "empatía") y un modelo
(`bert-base-multilingual-uncased-sentiment`) que en realidad da estrellas de opinión
de producto, no emoción. Se corrigió tras verificar contra la documentación real de
los modelos. **No repitas ese error**: cualquier emoción o modelo nuevo que se
proponga añadir aquí debe verificarse contra su documentación real antes de escribir
código o documentación sobre él.

**Arquitectura de no-bloqueo:** el análisis de una frase (cientos de ms de inferencia)
corre en `loop.run_in_executor(None, analyzer.analyze, texto)`, agendado con
`asyncio.create_task(analyze_and_print(...))` desde `receiver()`. Esto es intencional:
si se llamara a `analyzer.analyze()` directamente dentro de `receiver()`, bloquearía
la lectura de más eventos del websocket (incluidos los deltas de audio) mientras
corre la inferencia, causando cortes de audio perceptibles.

**Dos bugs reales encontrados verificando con ejecución real** (no solo `py_compile`):
1. `asyncio.create_task(loop.run_in_executor(...))` fallaba con `TypeError`:
   `run_in_executor` devuelve un `Future`, no una corrutina — no se envuelve en
   `create_task`, se usa directamente.
2. Imprimir el resultado de la emoción sin un `\n` inicial hacía que apareciera en
   medio del streaming de texto del otro lado (`print(delta, end="")` de la
   transcripción en curso). Se corrigió con el mismo patrón de `\n` inicial que ya
   usan los demás avisos asíncronos del script (`⏹️`, `⚠️`, `✂️`).

**Precisión real del modelo, verificada, no supuesta:** acierta claro en frases
elaboradas con carga emocional explícita ("no puedo creerlo, es una sorpresa total" →
SORPRESA 0.98) y falla más en exclamaciones cortas ("qué sorpresa tan grande" →
ALEGRÍA 0.80, incorrecto). También da falsos positivos ocasionales en frases neutras
("el cielo es azul" → ALEGRÍA 0.57, que supera el umbral por defecto de 0.5). Tabla
completa en [`v2/README-v2.md`](v2/README-v2.md), sección "Limitaciones conocidas".

Tests: [`v2/tests/test_sentiment.py`](v2/tests/test_sentiment.py). Dos grupos: lógica
interna (con un analizador falso inyectado, no necesitan el modelo real) e integración
con el modelo real (una frase por cada una de las 6 emociones, marcadas
`@requiere_modelo_real`, se saltan si falta `pysentimiento`).

Detalle de hitos y estado: [`v2/PLAN-v2.md`](v2/PLAN-v2.md).

## v3 — + Rastreo facial y servos (planificación)

Sin código todavía. Antes de escribir nada, se investigó a fondo un **proyecto
hermano y anterior del mismo usuario**,
[`ojosMecanicos`](/Users/debbie/Desktop/programacion/ojosMecanicos/) — un sistema de
servos (Raspberry Pi Pico) con varios intentos previos de integrar voz y cámara.
Léelo antes de tocar v3: [`v3/README-v3.md`](v3/README-v3.md), sección "Antes de
escribir código".

**Lo que se decidió reutilizar de esa investigación** (probado, no reinventar):
- **Protocolo serial hacia la Pico:** `"{LR},{UD},{EMOCION}\n"` (o sin emoción,
  `"{LR},{UD}\n"`), enteros 40-140 para los grados de servo, `EMOCION` opcional en
  mayúsculas de un enum de 10 valores (`NEUTRAL`, `FELIZ`, `ENOJADO`, `TRISTE`,
  `SORPRENDIDO`, `DORMIDO`, `DUDA`, `SOSPECHA`, `PENSATIVO`, `NERVIOSO`), baud 115200.
- **Latido:** con control remoto activo, reenviar el último comando cada 1s o el
  firmware de la Pico vuelve a modo autónomo.
- **Reconexión:** en macOS, comprobar si el path `/dev/cu.usbmodem...` sigue
  existiendo para detectar la desconexión de la Pico.
- **Regla de threading:** `cv2.imshow`/`waitKey` bloqueante vive en su propio hilo
  `daemon=True`, nunca mezclado con `asyncio.run()`. Coincide con el patrón que v1/v2
  ya usan para PortAudio (hilos propios, cruzando al loop con
  `call_soon_threadsafe`) — la misma disciplina aplica al hilo de cámara y al de Pico.

**Lo que NO se reutiliza:** el análisis de sentimiento de `ojosMecanicos` (palabras
clave en español + `TextBlob`, que analiza en inglés por defecto y es casi inerte
sobre español). El `pysentimiento` de v2 ya es más sofisticado y ya está verificado.

**El bug a no repetir:** el único intento de puente voz+emoción+cámara en
`ojosMecanicos` (`08_voz_emociones_ojos_integrado.py`) arranca los hilos de cámara y
de posición, pero la función que debía conectar la emoción detectada con el comando
serial **nunca se invoca** — código muerto, los hilos corren pero la información real
nunca fluye entre ellos. Cuando se implemente el Hito 2.3 de
[`v3/PLAN-v3.md`](v3/PLAN-v3.md) (cablear sentimiento → comando serial), hace falta un
test explícito que verifique que la emoción llega de verdad al comando encolado, no
solo que los hilos arrancan sin excepción.

**Mapeo de emoción (pysentimiento → vocabulario de la Pico)**, sin correspondencia
1 a 1 perfecta — declarado así a propósito, no se inventa precisión que no existe:

| pysentimiento | Comando Pico | Nota |
|---|---|---|
| joy | FELIZ | directo |
| sadness | TRISTE | directo |
| anger | ENOJADO | directo |
| fear | NERVIOSO | no hay "MIEDO" en el vocabulario de la Pico |
| surprise | SORPRENDIDO | directo |
| disgust | NEUTRAL | no hay equivalente; se degrada en vez de inventar uno |
| others | NEUTRAL | directo |

## Cómo verificar cambios (todas las versiones)

Ninguna versión se puede validar completamente de forma automatizada: todas necesitan
un humano hablando (v1, v2) o además una cámara y posiblemente hardware serial (v3).
Lo que sí se puede verificar sin eso:

- **Arranque y esquema de sesión.** Lanza el script en segundo plano redirigiendo la
  salida, espera unos segundos, lee el log, mátalo:
  ```bash
  .venv/bin/python -u realtime_voice.py > /tmp/rt.log 2>&1 &
  sleep 10; cat /tmp/rt.log; pkill -f realtime_voice.py
  ```
  Un arranque sano llega a `🎙️ Listo.` sin más líneas. Los errores de esquema de
  sesión **no abortan el proceso** — solo imprimen `⚠️ Error de la API` — así que hay
  que leer el log siempre, no solo comprobar que el proceso sigue vivo.
- **Con una clave inválida**, el fallo esperado es
  `ConnectionClosedError: … invalid_api_key`. Eso confirma que el resto de la cadena
  (audio, `.env`, TLS) funciona y el único problema es la credencial.
- **Lógica sin la API** (v2 en adelante): tests con un doble de prueba inyectado
  (`analyzer._analyzer = FakeAnalyzer(...)`) para lo que no necesita el modelo real,
  y un grupo separado marcado que sí lo descarga, para verificar contra el
  comportamiento real y no solo contra una simulación.
- **Nunca asumas que un fix funciona por `py_compile`.** Los dos bugs de v2 (ver
  arriba) solo aparecieron ejecutando el script de verdad contra la API. Compilar
  limpio no prueba que el código corra bien.

## Estilo

Código y comentarios en español. Comentarios escasos y solo donde el porqué no sea
evidente — no describir qué hace el código si el nombre ya lo dice. Cuando se
documenten resultados de un modelo o medición (precisión, latencia, límites), usar
datos reales obtenidos ejecutando el código, no cifras plausibles inventadas. Si algo
se corrige por ser inexacto (como el modelo de sentimiento original), dejar constancia
de la corrección y por qué, no solo el estado final — ayuda a no repetir el error.
