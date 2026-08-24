# Versión 13.0 — Voz en tiempo real + rastreo facial real, sin sentimiento todavía 🎙️👁️

**Objetivo:** juntar las dos piezas que hasta ahora se habían validado por
separado en la Raspberry Pi 5: la conversación de voz en tiempo real (v11)
y el rastreo facial real con control de la Pico (v12). **Todavía sin
análisis de sentimiento** — pedido explícito: la expresión de la Pico se
queda siempre en `NEUTRAL` (con parpadeo normal) cuando el rastreo corre
dentro del propio proceso de voz, y solo la mirada sigue al rostro
rastreado de verdad. Implementado en dos hitos, en el orden pedido: primero
la vía de terminal (`realtime_voice.py`), después la vía de navegador
(`webrtc_server.py`).

**Estado: ✅ validada en hardware real** — con un hallazgo real importante:
combinar voz y rastreo **en el mismo proceso** funciona, pero en la vía de
navegador compite por CPU con el audio en tiempo real lo bastante como para
colar eco. La arquitectura confirmada y recomendada para uso real por
navegador son **dos procesos separados** — ver "Validación en hardware
real" más abajo.

## Por qué existe esta versión

v11 aisló la voz sola (sin sentimiento, sin rastreo, sin Pico) para
validarla cuanto antes en la Pi 5, sin esperar a la cámara. v12 aisló la
otra mitad: la Pi 5 hablando con la Pico real y viendo con su propia cámara
(cicla las 10 expresiones cada 5s), también sin voz. Las dos piezas ya
estaban validadas por separado en hardware real — v13 las junta.

Es el mismo patrón que siguió v9 al juntar v8 (voz) con v7 (rastreo) — la
diferencia es que v13 no trae sentimiento todavía (eso sería una versión
posterior), así que el firmware nunca recibe un `EMOCION` cuando el rastreo
corre integrado en la conversación de voz: la Pico se queda en `NEUTRAL`
con su parpadeo periódico normal y la mirada siguiendo el rostro real.

## Qué trae y qué no

| Pieza | En v13 |
|---|---|
| Voz en tiempo real (terminal) | `realtime_voice.py`, retomado de v11 sin cambios de lógica en la parte de audio |
| Voz en tiempo real (navegador) | `webrtc_server.py` + `static/index.html`, retomados de v11 sin cambios |
| Rastreo facial real | `face_tracker.py`, retomado de v12 (cámara CSI OV5647 con respaldo USB, parámetros calibrados en hardware real; FPS de cámara reducido a 5 — ver más abajo) |
| Enlace serial con la Pico | `pico_serial.py`, retomado de v12 (incluye `_drenar_entrada()`, el fix del buffer USB) |
| Firmware de la Pico | `main.py`, retomado de v9/v12 sin ningún cambio |
| Ciclo de expresiones + rastreo, como proceso aparte | `rastreo_expresiones.py`, retomado de v12 — la pieza que sí se valida corriendo *junto* a la voz, en su propio proceso |
| Análisis de sentimiento | ❌ Fuera de alcance, a propósito |
| Modo dormido por inactividad | ❌ Fuera de alcance por ahora (depende de medir actividad de la conversación, que v13 no analiza todavía) |

## Por qué la expresión se queda siempre en NEUTRAL (cuando el rastreo va integrado)

El firmware (`main.py`, sin cambios desde v8) solo cambia de expresión
cuando recibe un `EMOCION` válido por serial junto con `LR,UD`. El hilo de
rastreo integrado en `realtime_voice.py`/`webrtc_server.py`
(`_hilo_rastreo()`, retomado de v12) nunca manda ese campo — solo
`PICO.enviar(lr, ud)`, sin emoción — así que `emocion_actual` se queda en
su valor inicial, `NEUTRAL`, durante toda la sesión. Efectos concretos,
todos ya construidos en el firmware desde versiones anteriores, sin tocar
nada aquí:
- El parpadeo periódico sigue activo con normalidad (solo se desactiva con
  `DORMIDO`, que aquí nunca se manda).
- Los párpados quedan en su posición de reposo (`PARPADOS_REPOSO`), sin
  ningún offset de expresión aplicado.
- Ninguna de las tres expresiones que fijan la mirada por su cuenta
  (`DUDA`/`PENSATIVO`/`NERVIOSO`) se activa nunca — la mirada real del
  rastreo tiene siempre la última palabra.

`rastreo_expresiones.py` (la pieza validada para correr *junto* a la voz,
en su propio proceso — ver más abajo) sí cicla las 10 expresiones, porque
es literalmente el mismo script de v12: eso no es "sentimiento" — sigue
siendo un ciclo fijo, ajeno al contenido de la conversación — solo que se
demostró como la forma de tener rastreo + expresiones *y* voz clara al
mismo tiempo.

## Validación en hardware real (23/08/2026)

**El bug real: realimentación de audio.** Con la voz por navegador, el
asistente se oía a sí mismo y se autointerrumpía. Causa: durante la propia
depuración se cargó el módulo de cancelación de eco de PipeWire (pensado
para la vía de terminal con AEC de sistema, `v11/pipewire-aec/`) *a la vez*
que se desactivaba la cancelación de eco del navegador en
`static/index.html` — dos capas mal combinadas, más el navegador
capturando el nodo virtual de PipeWire en vez del micrófono crudo. **Fix:
ninguno de código** — `static/index.html` ya traía `echoCancellation: true`
correcto desde v11; el error fue de configuración del sistema. **Regla para
siempre: una sola capa de cancelación de eco.** La vía web la hace el
navegador sobre el micrófono crudo; la vía de terminal con AEC de sistema
la hace PipeWire. No mezclarlas.

**El hallazgo de arquitectura: rastreo y voz por navegador compiten por
CPU en el mismo proceso.** `webrtc_server.py --tracking` funciona, pero la
carga del sistema pasó de ~2.1 (rastreo y voz en procesos separados) a
~3.25 (juntos en uno) — suficiente para que el audio en tiempo real se
degrade y el eco se cuele. **Arquitectura validada y recomendada para uso
real por navegador:**

```
Proceso 1: rastreo_expresiones.py   ← rastreo facial + ciclo de 10 expresiones
            (cámara CSI OV5647 + Pico, sin voz)
Proceso 2: webrtc_server.py SIN --tracking   ← solo voz por el navegador
            (micrófono/parlante + WebRTC, AEC del navegador)
```

```bash
# Terminal 1: el robot (rastreo + ciclo de expresiones)
cd v13 && .venv/bin/python rastreo_expresiones.py

# Terminal 2: la voz por navegador (SIN --tracking)
cd v13 && .venv/bin/python webrtc_server.py --no-browser
# y abre http://127.0.0.1:8000/?auto=1 en el navegador
```

`--tracking` en `webrtc_server.py`/`realtime_voice.py` (rastreo integrado
en el mismo proceso de voz) sigue existiendo y funciona — útil para
pruebas rápidas del rastreo, o para la vía de terminal (que no comparte el
mismo mecanismo de cancelación de eco, así que no se midió el mismo
problema ahí, aunque tampoco se ha confirmado que esté libre de él). Para
producción por navegador, la combinación de dos procesos es la confirmada
sin eco ni degradación de audio.

**Ajuste de cámara: FPS reducido a 5 (antes 15 en v12).** v13 comparte CPU
con el procesamiento de audio en tiempo real (algo que v12 no tenía que
considerar); 5 FPS deja margen de sobra sin perder fluidez perceptible en
el rastreo (la Pico ya suaviza el movimiento internamente). Aplicado como
la constante `FPS_CAMARA` en `face_tracker.py`.

**Notas de infraestructura de la Pi 5:**
- El power-save del WiFi puede cortar la conexión WebRTC a los ~35s (ICE
  `disconnected` → `failed`, por keepalives de STUN perdidos) — hace falta
  desactivarlo a nivel de sistema al arrancar.
- La vía de terminal con AEC de PipeWire (`v11/pipewire-aec/`, si se
  despliega) y la vía web no deben correr a la vez: comparten
  micrófono/parlante y producirían dos voces simultáneas.

Detalle completo, con mediciones: [`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md).

**Confirmado en hardware real, con la arquitectura de dos procesos:** voz
por navegador clara, sin eco ni autointerrupción, con el rastreo facial
siguiendo un rostro real y la Pico ciclando las 10 expresiones al mismo
tiempo, de forma sostenida.

## Arquitectura

**Recomendada (dos procesos, validada para uso real por navegador):**
```
Proceso 1                                        Proceso 2
Cámara CSI OV5647 (picamera2, 5fps)               Navegador (WebRTC, AEC real)
  ó webcam USB de respaldo                              │
      │  leer_frame() / cap.read()                      │  audio
      ▼                                                  ▼
FaceTracker.procesar()                          webrtc_server.py (sin --tracking)
      │  (hilo de fondo, cadencia 200ms)               negocia SDP con OpenAI
      ▼
_ciclar_expresiones() ── PICO.enviar(lr, ud, emocion) ──► Raspberry Pi Pico
   (rastreo_expresiones.py)                              (main.py, igual que v9/v12)
```

**Integrada (un proceso, disponible con `--tracking`, útil para pruebas
rápidas o la vía de terminal):**
```
Micrófono/parlante (terminal, sounddevice)     Cámara CSI OV5647 (picamera2)
      ó navegador (WebRTC, AEC real)              ó webcam USB de respaldo
      │                                                    │  leer_frame() / cap.read()
      ▼                                                    ▼
Conversación de voz (bucle asyncio /              FaceTracker.procesar()
servidor HTTP — hilo/loop principal)                    │  (hilo de fondo, cadencia 200ms)
      │                                                    ▼
      │                                          PICO.enviar(lr, ud)  [nunca con EMOCION]
      │                                                    │
      └───────────────── mismo proceso ──────────────────►│
                                                            ▼
                                          Raspberry Pi Pico (main.py, igual que v9/v12)
                                          emocion_actual siempre "NEUTRAL": parpadeo
                                          normal + mirada real del rastreo, sin fijar
```

## Instalación

```bash
cd v13
python3 -m venv --system-site-packages .venv   # --system-site-packages: para ver picamera2
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env && chmod 600 .env   # y pon tu OPENAI_API_KEY real
python -m pytest tests/ -v     # 33 tests
```

En la Raspberry Pi 5 real, además:
- `sudo apt install -y python3-picamera2 --no-install-recommends` (cámara CSI).
- El usuario debe pertenecer al grupo `dialout` para abrir `/dev/ttyACM0` sin
  sudo: `sudo usermod -aG dialout $USER` y volver a iniciar sesión.
- Fijar el micrófono/parlante USB como dispositivos por defecto del sistema
  (PipeWire/`wpctl`) antes de arrancar — igual que en v10/v11.
- Desactivar el power-save del WiFi (ver "Validación en hardware real").
- Si tu Pi 5 usa webcam USB en vez de CSI, confirma su índice con
  `v4l2-ctl --list-devices` y pásalo con `--camera-index`.

## Uso

**Recomendado para uso real por navegador (dos procesos):**
```bash
# Terminal 1
python rastreo_expresiones.py
# Terminal 2
python webrtc_server.py --no-browser
# y abre http://127.0.0.1:8000/?auto=1
```

**Hito A — terminal (`realtime_voice.py`), integrado en un proceso:**
```bash
python realtime_voice.py --barge-in                     # voz sola, sin rastreo (igual que v11)
python realtime_voice.py --barge-in --tracking          # voz + rastreo + Pico, mismo proceso
python realtime_voice.py --tracking --no-pico           # rastreo sin mover servos, para probar
```

**Hito B — navegador (`webrtc_server.py`), integrado en un proceso (prueba rápida):**
```bash
python webrtc_server.py                                  # voz sola, sin rastreo (igual que v11)
python webrtc_server.py --tracking                       # voz + rastreo + Pico, mismo proceso
```

## Cómo se verificó

Sin hardware real, en el entorno de desarrollo original: sintaxis, y 33
tests (8 de `FaceTracker`, 12 de `pico_serial.py`, 4 de `estado_base.py`,
7 de la lógica del ciclo en `rastreo_expresiones.py`), todos pasando en
`v13/.venv`. Arranque real de `realtime_voice.py --tracking`,
`webrtc_server.py --tracking` y `rastreo_expresiones.py` con una clave de
API falsa, sin Pico, sin `picamera2` y sin permiso de cámara: la cadena de
respaldo completa degrada limpia en los tres, sin ninguna excepción no
manejada. Con hardware real: ver "Validación en hardware real" arriba.

## Notas heredadas de v11/v12, sin cambios

- **`realtime_voice.py`** sigue sin cancelación de eco real — usa los
  paliativos de v1 (`MicGate`, `BargeInDetector`, half-duplex). `--barge-in`
  es necesario para poder interrumpir hablando por encima; sin él, solo
  corta con Enter (ver v11/README-v11.md).
- **`webrtc_server.py`** es la vía recomendada para eco real (cancelación
  del navegador) — `static/index.html` ya trae `iceServers` (STUN) y
  autoconexión (`?auto=1`), ambos validados en v11 en la Pi 5 real.
- **`diagnostico_canal.py`** sigue con el PCA9685 heredado, sin corregir a
  propósito (inconsistencia preexistente desde v5, ver v12/README-v12.md).

## Próximos pasos

- Confirmar la arquitectura de dos procesos en sesiones más largas (varios
  minutos u horas seguidas).
- Retomar el análisis de sentimiento sobre esta base (v14 o similar): el
  firmware ya está listo desde v8/v9 para recibir `EMOCION` por serial sin
  ningún cambio adicional — probablemente enchufado sobre
  `rastreo_expresiones.py` o una variante suya, dado que ese es el proceso
  validado para correr junto a la voz.
