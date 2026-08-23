# Versión 9.0 — Voz + sentimiento + rastreo facial real, todo junto 🎙️👁️📷

**Objetivo:** juntar, en un solo proceso, las tres piezas que hasta ahora se
habían validado por separado: la conversación de voz en el navegador con
sentimiento controlando la expresión (v8), y el rastreo facial real por
cámara (v7). El robot debería, a la vez, seguir tu rostro con la mirada y
mostrar la emoción detectada en la conversación.

**Estado: completa y validada en hardware real.** Confirmado por el usuario,
con permiso de cámara concedido, hablando de verdad por el navegador con la
Pico física: "funciona bien, hace el tracking perfecto, y puedo hablar en
tiempo real". Las tres piezas —voz, sentimiento y rastreo real— funcionando
juntas, tal como se planteó como objetivo de esta versión.

## Alcance: solo `webrtc_server.py` recibe la cámara

v8 tiene dos formas de hablar. Solo una de las dos se extendió en v9:

- **`webrtc_server.py` (navegador, recomendada)** — ahora también rastrea el
  rostro por cámara en un hilo de fondo, y manda su posición real a la Pico.
- **`realtime_voice.py` (terminal, alternativa)** — sin cambios respecto a
  v8. Sigue mandando un `LR,UD` fijo (90,90) junto con cada `EMOCION`; no
  tiene cámara. Decisión explícita de alcance, no una limitación técnica.

## Arquitectura

```
                    ┌─── Hilo de fondo: rastreo facial ───┐
                    │  cv2.VideoCapture (abierta en el     │
                    │  hilo principal — ver el hallazgo    │
                    │  real más abajo)                     │
                    │  → FaceTracker.procesar(frame)        │
                    │  → PICO.enviar(lr, ud)  [sin EMOCION] │
                    │  → actualiza ULTIMA_MIRADA            │
                    └───────────────┬───────────────────────┘
                                    │ (comparten PICO y ULTIMA_MIRADA)
Navegador (WebRTC)                 │
   │  audio + "oai-events"         │
   ▼                               │
OpenAI Realtime API                │
   │  el navegador ve la           │
   │  transcripción                │
   ▼                               │
POST /api/analyze-sentiment ──▶ webrtc_server.py (hilo principal)
                                    │  sentiment_analyzer.analyze(texto)
                                    │  EMOTION_TO_PICO[emoción]
                                    │  lee ULTIMA_MIRADA (no manda 90,90)
                                    ▼
                          PICO.enviar(lr_real, ud_real, EMOCION)
                                    │  USB serial "lr,ud,EMOCION\n"
                                    ▼
                          Pico (main.py, sin cambios desde v8):
                          - 7 expresiones dejan LR/UD tal cual llegan
                            (la mirada real sigue el rostro)
                          - DUDA/PENSATIVO/NERVIOSO la ignoran y fijan
                            o mueven la mirada por su cuenta, como siempre
                          - el pulso de 5s y la vuelta a NEUTRAL, sin cambios
```

**Por qué comparten una sola conexión a la Pico:** solo un proceso puede
tener el puerto serial abierto a la vez. El hilo de rastreo y el endpoint de
sentimiento son parte del mismo proceso Python y usan el mismo `PICO`
(`PicoLink`), cada uno llamando a `.enviar()` cuando le toca — `PicoLink` ya
serializa los envíos con una cola interna, así que no hay condición de
carrera al escribir por el puerto.

**Por qué el endpoint de sentimiento manda la mirada real, no 90,90:** antes
(v8, sin cámara), daba igual qué mandar como LR/UD porque no había ninguna
posición "real" — 90,90 (centro) era tan válido como cualquier otra. Ahora
que sí hay una posición real, mandar 90,90 haría que la cara saltara al
centro cada vez que cambia la expresión, deshaciendo el rastreo. `ULTIMA_MIRADA`
guarda la última posición que detectó el hilo de rastreo, protegida por un
lock simple, y el endpoint la usa en su lugar.

**Sin cambios en `main.py` (el firmware):** ya aceptaba LR/UD reales por
serial desde v4, sin distinguir si venían de un valor fijo o de un rastreo
real — el mecanismo que hace que 7 de las 10 expresiones sigan la mirada
real y las otras 3 la ignoren ya estaba construido desde v6/v7. v9 simplemente
empieza a mandarle datos reales en vez del valor fijo que usaba v8.

## Hallazgo real: la cámara debe abrirse en el hilo principal, no en el de rastreo

**No anticipado, encontrado al probarlo:** el primer intento abría
`cv2.VideoCapture` dentro del propio hilo de fondo del rastreo. En macOS eso
falla con:

```
OpenCV: can not spin main run loop from other thread, set
OPENCV_AVFOUNDATION_SKIP_AUTH=1 to disable authorization request and
perform it in your application.
```

AVFoundation (el framework de cámara de macOS que usa OpenCV por debajo)
necesita negociar el permiso de cámara desde el *run loop* del hilo
principal — no puede hacerlo desde un hilo secundario. La solución no es la
variable de entorno que sugiere el mensaje (`OPENCV_AVFOUNDATION_SKIP_AUTH=1`
desactiva la petición de permiso, no la resuelve), sino cambiar **dónde** se
abre la cámara: `cv2.VideoCapture(...)` se construye ahora en `main()` (hilo
principal), y solo el objeto ya abierto se pasa al hilo de fondo, que
únicamente hace `cap.read()` en bucle — nunca vuelve a tocar la apertura ni
el permiso.

Con ese cambio, el error de hilos desapareció (confirmado ejecutando el
servidor de verdad). Lo que queda, y es la misma limitación ya documentada
en v3, es que este entorno no puede conceder el permiso de cámara de forma
interactiva — necesita que el usuario lo pruebe en su propia Terminal:

```
OpenCV: not authorized to capture video (status 0), requesting...
```

## Modo dormido por inactividad

**Pedido explícito, añadido sobre la versión inicial de v9:** si pasa
`--sleep-timeout` segundos (60 por defecto) sin que el usuario diga nada, la
Pico entra en `DORMIDO`; en cuanto vuelve a hablar, se despierta con `DUDA` y
de ahí pasa sola a `NEUTRAL`.

**Cómo se implementó, sin tocar el firmware:** `main.py` no cambió. El
mecanismo reutiliza dos cosas que ya existían y ya estaban probadas desde v8:

1. **"La misma emoción repetida extiende el pulso, no lo reinicia desde
   cero"** (`test_recibir_la_misma_emocion_repetida_extiende_el_pulso`, v8).
   Un hilo nuevo, `_hilo_vigia_sueno()`, reenvía `DORMIDO` cada segundo
   mientras dure el silencio — cada reenvío extiende el pulso de 5s del
   firmware antes de que expire, así que la Pico se queda dormida
   indefinidamente, no solo 5 segundos, sin que el firmware sepa que está
   pasando algo distinto de recibir la misma emoción varias veces.
2. **El pulso de 5s ya vuelve solo a NEUTRAL.** Al detectar la primera
   actividad tras el silencio, el hilo manda `DUDA` **una sola vez** — el
   propio mecanismo de pulso de la Pico la mantiene 5s y la devuelve sola a
   `NEUTRAL`, exactamente como pasa con cualquier otra emoción. No hace falta
   que este proceso mande nada más para completar el "duda → neutro".

**Qué cuenta como actividad:** cualquier frase del **usuario** ya transcrita
que llegue al endpoint `/api/analyze-sentiment` — funciona con o sin
`--sentiment` activo, porque el navegador manda esa frase de todos modos (ver
`static/index.html`); el conteo de inactividad no depende de que el
clasificador de sentimiento esté encendido. Deliberadamente **no** cuenta lo
que dice el asistente: "si no se le habla al robot" se interpretó como
actividad del usuario específicamente, no de la conversación en general.

**Lógica aislada y probada sin hardware ni tiempo real:** la decisión de
dormir/despertar vive en `_decidir_sueno(ahora, ultima_actividad, timeout,
dormido_previo)`, una función pura sin `threading`/`time.sleep` de por medio
— `tests/test_webrtc_server.py` la prueba directamente con valores de tiempo
fijos (5 tests nuevos): no duerme antes de tiempo, duerme justo al cumplirse
el timeout, se mantiene dormida sin repetir el gesto de despertar en cada
vuelta, despierta una sola vez cuando vuelve la actividad, y no marca
"despertando" si ya estaba despierta.

**Confirmado con hardware real, con una Pico física conectada a este
entorno:** se lanzó el servidor con `--sleep-timeout 4` (para no esperar los
60s por defecto) y se confirmó la secuencia completa por los logs y el envío
serial real: tras 4s sin actividad, `"😴 Sin actividad por 4s: la Pico se
duerme."` y el envío repetido de `DORMIDO`; al llegar una frase de prueba,
`"👀 Actividad detectada tras el silencio: despertando (DUDA)."` y el envío
de `DUDA` una sola vez.

## Cómo probarlo

**1. Firmware (Pico):** sin cambios desde v8 — despliega `main.py` con
Thonny, `Archivo → Guardar como → Raspberry Pi Pico`, reinicia físicamente.

**2. Servidor (Mac):**
```bash
cd v9
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y pon tu OPENAI_API_KEY real
python webrtc_server.py --sentiment --tracking
```
La primera vez que corras esto con `--tracking`, macOS debería pedir permiso
de cámara para la Terminal (o para el binario de Python del `.venv`, según
cómo lo lances) — acéptalo. Usa `--tracking` solo, `--sentiment` solo, o
ambos juntos (el caso pensado para esta versión). `--camera-index` para
elegir cámara si tienes varias; `--no-pico` para probar sin tocar la Pico.

**Qué observar:** los ojos y el cuello deberían seguir tu rostro en tiempo
real durante `NEUTRAL/FELIZ/ENOJADO/TRISTE/SORPRENDIDO/DORMIDO/SOSPECHA`
(igual que en v7), y decir algo con carga emocional clara debería cambiar la
expresión sin que la mirada saltara al centro — el gesto de la emoción se
aplica sobre la posición real, no sobre un valor fijo. `DUDA/PENSATIVO/
NERVIOSO` siguen ignorando el rastreo y moviendo la mirada por su cuenta,
como siempre.

## Cómo se verificó

**Sin hardware ni cámara real:**
- Sintaxis de los 8 ficheros `.py` (`py_compile`)
- 79 tests: los 65 heredados de v8 sin cambios, más `test_face_tracker.py`
  (heredado de v7 sin cambios — matemática de `FaceTracker`: EMA, zona
  muerta, mapeo a grados, con una cascada falsa inyectada para no depender de
  detección real)

**Confirmado con hardware real, con una Pico física conectada a este
entorno (previo a que el usuario probara con permiso de cámara):**
- `webrtc_server.py --sentiment --tracking --no-browser`: la Pico se
  autodetectó y conectó, el servidor sirvió la página, y
  `POST /api/analyze-sentiment` con frases reales devolvió el análisis
  correcto y disparó el envío por serial — igual que en v8
- El hallazgo del hilo de cámara (arriba): confirmado que el error de hilos
  desaparece al abrir la cámara en el hilo principal; en ese momento el
  error restante (permiso de cámara no concedido en este entorno) era el
  mismo tipo de bloqueo ya documentado en v3, no un bug de esta versión

**Validado por el usuario, con permiso de cámara concedido y una
conversación real:** "funciona bien, hace el tracking perfecto, y puedo
hablar en tiempo real" — confirmado que el rastreo facial real mueve los
ojos y el cuello de la Pico siguiendo el rostro, que la conversación de voz
por el navegador funciona sin problema, y que las dos piezas conviven bien
a la vez (rastreo real + cambio de expresión por sentimiento, sin conflictos
entre los dos hilos).

## Ficheros de esta versión

- **`webrtc_server.py`** — copia de v8, con el hilo de rastreo nuevo
  (`_hilo_rastreo()`), las opciones `--tracking`/`--camera-index`, la
  conexión a la Pico ahora compartida entre sentimiento y rastreo (antes
  solo la usaba `--sentiment`), y `ULTIMA_MIRADA` para que el endpoint de
  sentimiento mande la posición real en vez de un valor fijo.
- **`face_tracker.py`** — retomado de v7, sin cambios de lógica. Ya no es
  solo un script standalone: `webrtc_server.py` importa `FaceTracker`
  directamente.
- **`static/index.html`, `realtime_voice.py`, `sentiment_analyzer.py`,
  `pico_serial.py`, `estado_base.py`, `diagnostico_canal.py`** — copias de
  v8, sin cambios de lógica.
- **`main.py`** — copia de v8, sin cambios de lógica. Ya aceptaba LR/UD
  reales; v9 simplemente empezó a mandárselos.

Mapeo de pines (igual que en versiones anteriores):

```
LR=GP2   UD=GP3   TL=GP4   BL=GP5   TR=GP6   BR=GP7   PAN=GP8   TILT=GP9
```

## Próximos pasos (fuera de esta versión)

1. Sincronía de párpados con la mirada, joystick, modo autónomo — pendientes
   heredados de versiones anteriores
2. Considerar si `realtime_voice.py` también necesita rastreo, si se termina
   usando como algo más que una alternativa de prueba

## Referencias

- [`../v8/README-v8.md`](../v8/README-v8.md) — arquitectura de voz +
  sentimiento + Pico (base de la que parte esta versión)
- [`../v7/README-v7.md`](../v7/README-v7.md) — seguimiento visual real +
  secuencia de expresiones (origen de `face_tracker.py` y del mecanismo de
  "7 expresiones siguen el rostro, 3 lo ignoran")
- [`../v3/README-v3.md`](../v3/README-v3.md) — primera vez que se documentó
  el bloqueo de permiso de cámara en este entorno sandboxed
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md)
- [PLAN-v9.md](PLAN-v9.md) — hitos
