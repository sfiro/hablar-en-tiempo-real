# Versión 13.0 — Voz en tiempo real + rastreo facial real, sin sentimiento todavía 🎙️👁️

**Objetivo:** juntar, en el mismo proceso, las dos piezas que hasta ahora se
habían validado por separado en la Raspberry Pi 5: la conversación de voz en
tiempo real (v11) y el rastreo facial real con control de la Pico (v12).
**Todavía sin análisis de sentimiento** — pedido explícito: la expresión de
la Pico se queda siempre en `NEUTRAL` (con parpadeo normal), y solo la
mirada sigue al rostro rastreado de verdad. Implementado en dos hitos, en el
orden pedido: primero la vía de terminal (`realtime_voice.py`), después la
vía de navegador (`webrtc_server.py`).

**Estado: código completo, sin validar todavía en hardware real.** Igual
situación que tuvieron v10 y v12 al escribirse: sin una Raspberry Pi 5,
Pico, micrófono/parlante ni cámara delante en este entorno.

## Por qué existe esta versión

v11 aisló la voz sola (sin sentimiento, sin rastreo, sin Pico) para
validarla cuanto antes en la Pi 5, sin esperar a la cámara. v12 aisló la
otra mitad: la Pi 5 hablando con la Pico real y viendo con su propia cámara
(cicla las 10 expresiones cada 5s), también sin voz. Las dos piezas ya
están validadas por separado en hardware real — v13 las junta: la misma
conversación de voz de v11, con el mismo rastreo facial real de v12
corriendo en un hilo de fondo, todo en el mismo proceso.

Es el mismo patrón que siguió v9 al juntar v8 (voz) con v7 (rastreo) — la
diferencia es que v13 no trae sentimiento todavía (eso sería una versión
posterior), así que el firmware nunca recibe un `EMOCION`: la Pico se queda
en `NEUTRAL` durante toda la conversación, con su parpadeo periódico normal
y la mirada siguiendo el rostro real.

## Qué trae y qué no

| Pieza | En v13 |
|---|---|
| Voz en tiempo real (terminal) | `realtime_voice.py`, retomado de v11 sin cambios de lógica en la parte de audio |
| Voz en tiempo real (navegador) | `webrtc_server.py` + `static/index.html`, retomados de v11 sin cambios |
| Rastreo facial real | `face_tracker.py`, retomado de v12 (cámara CSI OV5647 con respaldo USB, parámetros calibrados en hardware real) |
| Enlace serial con la Pico | `pico_serial.py`, retomado de v12 (incluye `_drenar_entrada()`, el fix del buffer USB) |
| Firmware de la Pico | `main.py`, retomado de v9/v12 sin ningún cambio |
| Análisis de sentimiento | ❌ Fuera de alcance, a propósito — la Pico nunca recibe un EMOCION |
| Modo dormido por inactividad | ❌ Fuera de alcance por ahora (depende de medir actividad de la conversación, que v13 no analiza todavía) |

## Por qué la expresión se queda siempre en NEUTRAL

El firmware (`main.py`, sin cambios desde v8) solo cambia de expresión
cuando recibe un `EMOCION` válido por serial junto con `LR,UD`. El hilo de
rastreo de v13 (retomado de `_hilo_rastreo()` en v12) nunca manda ese campo
— solo `PICO.enviar(lr, ud)`, sin emoción — así que `emocion_actual` se
queda en su valor inicial, `NEUTRAL`, durante toda la sesión. Efectos
concretos, todos ya construidos en el firmware desde versiones anteriores,
sin tocar nada aquí:
- El parpadeo periódico sigue activo con normalidad (solo se desactiva con
  `DORMIDO`, que aquí nunca se manda).
- Los párpados quedan en su posición de reposo (`PARPADOS_REPOSO`), sin
  ningún offset de expresión aplicado.
- Ninguna de las tres expresiones que fijan la mirada por su cuenta
  (`DUDA`/`PENSATIVO`/`NERVIOSO`) se activa nunca — la mirada real del
  rastreo tiene siempre la última palabra.

## Arquitectura

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
python -m pytest tests/ -v     # 26 tests, sin hardware
```

En la Raspberry Pi 5 real, además:
- `sudo apt install -y python3-picamera2 --no-install-recommends` (cámara CSI).
- El usuario debe pertenecer al grupo `dialout` para abrir `/dev/ttyACM0` sin
  sudo: `sudo usermod -aG dialout $USER` y volver a iniciar sesión.
- Fijar el micrófono/parlante USB como dispositivos por defecto del sistema
  (PipeWire/`wpctl`) antes de arrancar — igual que en v10/v11.
- Si tu Pi 5 usa webcam USB en vez de CSI, confirma su índice con
  `v4l2-ctl --list-devices` y pásalo con `--camera-index`.

## Uso

**Hito A — terminal (`realtime_voice.py`), primero:**
```bash
python realtime_voice.py --barge-in                     # voz sola, sin rastreo (igual que v11)
python realtime_voice.py --barge-in --tracking          # voz + rastreo + Pico
python realtime_voice.py --tracking --no-pico           # rastreo sin mover servos, para probar
```

**Hito B — navegador (`webrtc_server.py`), después de validar el Hito A:**
```bash
python webrtc_server.py                                  # voz sola, sin rastreo (igual que v11)
python webrtc_server.py --tracking                       # voz + rastreo + Pico
```

## Cómo se verificó

Sin hardware real (Raspberry Pi 5, Pico, micrófono/parlante, cámara) en este
entorno de desarrollo:
- Sintaxis de los 4 ficheros `.py` del lado cliente.
- **26 tests** (8 de `FaceTracker`, 12 de `pico_serial.py`, 4 de
  `estado_base.py`, heredados sin cambios de v12 — no hay lógica pura nueva
  que testear en `realtime_voice.py`/`webrtc_server.py`, igual criterio que
  v9 con `_hilo_rastreo()`), todos pasando en `v13/.venv`.
- Arranque real de `realtime_voice.py --tracking` y `webrtc_server.py
  --tracking` (clave de API falsa, sin Pico, sin `picamera2`, sin permiso de
  cámara en este entorno): la cadena de respaldo completa degrada limpia —
  intenta CSI, falla con el mensaje de instalación, cae a webcam USB, falla
  también (sin permiso), y la conversación de voz sigue su curso sin
  rastreo, sin ninguna excepción no manejada. `webrtc_server.py` sirve la
  página y llega a "Abre http://127.0.0.1:8000/" con normalidad;
  `realtime_voice.py` llega a "Conectando a gpt-realtime …" (el primer punto
  donde haría falta una clave real).

**No verificado, pendiente de la Raspberry Pi 5 real** (mismo punto en el
que quedaron v10/v12 al escribirse):
- Que la conversación de voz y el rastreo funcionen bien **a la vez**, sin
  que uno afecte la latencia o estabilidad del otro (el hilo de rastreo
  compite por CPU con el audio en tiempo real, algo que v9 sí llegó a
  confirmar sin problema con Mac + sentimiento, pero no se ha repetido aquí
  con voz + Pi 5).
- Que el parpadeo normal y la mirada real se vean bien mientras se habla,
  sin ningún salto raro.
- Índice correcto de la webcam USB de respaldo, si la Pi 5 de destino no
  tiene cámara CSI.

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

- Validar en la Raspberry Pi 5 real: Hito A primero (`realtime_voice.py
  --tracking`), Hito B después (`webrtc_server.py --tracking`).
- Retomar el análisis de sentimiento sobre esta base (v14 o similar): el
  firmware ya está listo desde v8/v9 para recibir `EMOCION` por serial sin
  ningún cambio adicional.
