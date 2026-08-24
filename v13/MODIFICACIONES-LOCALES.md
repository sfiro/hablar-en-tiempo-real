# v13 — Validación en hardware real (23/08/2026)

**Por qué existe este fichero:** diario de lo que se encontró al validar v13
—voz en tiempo real + rastreo facial real— en la Raspberry Pi 5 real,
siguiendo el mismo patrón que `v11/README-IMPLEMENTACION.md` y
`v12/MODIFICACIONES-LOCALES.md`: documentar lo que pasó de verdad en
hardware, no una reescritura idealizada.

## 1. El bug real: realimentación de audio (el importante)

**Síntoma:** con la voz por navegador, el asistente se oía a sí mismo y se
autointerrumpía — pese a que el rastreo facial funcionaba perfectamente por
su lado.

**Causa raíz (un error de configuración durante la propia depuración, no un
bug del código de v13):**
1. Se cargó el módulo `module-echo-cancel` de PipeWire — que es el enfoque
   de la **vía de terminal con AEC de sistema** (`v11/pipewire-aec/`), no de
   la vía web.
2. Se desactivó la cancelación de eco del navegador
   (`echoCancellation: false`) en `static/index.html`, asumiendo que
   PipeWire se encargaría.
3. Resultado: dos capas de cancelación de eco mal combinadas, más el
   navegador capturando el nodo virtual `echo-cancel-source` de PipeWire en
   vez del micrófono crudo — el eco se colaba de todas formas.

**Cómo debe correr (y corría v11 cuando se validó, el 22/08):**
- `static/index.html` con **`echoCancellation: true`** (sin cambios desde
  v11) — el **navegador** cancela el eco, capturando el micrófono crudo.
- **Sin** cargar `module-echo-cancel` de PipeWire para la vía web — ese
  módulo es solo para la vía de terminal con AEC de sistema.

**Regla para siempre:** elegir UNA sola capa de cancelación de eco. La vía
web la hace el navegador sobre el micrófono crudo; la vía de terminal con
AEC de sistema la hace PipeWire (`v11/pipewire-aec/`). No mezclarlas.

`static/index.html` de v13 (copia idéntica de v11) ya tenía la configuración
correcta desde el principio — no hizo falta ningún cambio de código, solo
evitar la combinación incorrecta a nivel de sistema descrita arriba.

## 2. La arquitectura que funciona: dos procesos separados

**Hallazgo real:** correr el rastreo facial y la voz por navegador **en el
mismo proceso** (el diseño original de `webrtc_server.py --tracking`)
compite por CPU con el procesamiento de audio en tiempo real lo bastante
como para que el eco se cuele. Carga del sistema medida: **~3.25 con las dos
piezas compitiendo en un proceso, ~2.1 con cada una en el suyo**.

**Arquitectura validada y recomendada, dos procesos independientes, cada uno
con su propio recurso:**

```
Proceso 1: rastreo_expresiones.py   ← rastreo facial + ciclo de 10 expresiones
            (cámara CSI OV5647 + Pico, sin voz)
Proceso 2: webrtc_server.py SIN --tracking   ← solo voz por el navegador
            (micrófono/parlante + WebRTC, AEC del navegador)
```

- **`rastreo_expresiones.py`** (retomado de v12 sin cambios de lógica, salvo
  el FPS de la cámara — ver más abajo): los ojos siguen el rostro real y la
  Pico cicla las 10 expresiones cada 5s.
- **`webrtc_server.py` sin `--tracking`**: solo negocia la voz por WebRTC.
  Si además rastreara en el mismo proceso, competiría por CPU con el
  filtrado de audio en tiempo real.

**Cómo ejecutarlo (la receta validada):**
```bash
# Terminal 1: el robot (rastreo + ciclo de expresiones)
cd v13 && .venv/bin/python rastreo_expresiones.py

# Terminal 2: la voz por navegador (SIN --tracking)
cd v13 && .venv/bin/python webrtc_server.py --no-browser
# y abre http://127.0.0.1:8000/?auto=1 en el navegador
```

**Qué pasa con `--tracking` en `webrtc_server.py`/`realtime_voice.py`:**
siguen existiendo y funcionando — útiles para una prueba rápida del rastreo
solo, o para la vía de terminal (`realtime_voice.py`, sin cancelación de eco
real, así que no compite con el mismo mecanismo de AEC del navegador — no se
midió el mismo problema de CPU ahí, pero tampoco se ha confirmado que esté
libre de él). Para producción por navegador, la combinación de dos procesos
es la que se confirmó funcionando sin eco ni degradación de audio.

## 3. Ajuste de cámara: FPS reducido a 5 (antes 15 en v12)

**Por qué:** v12 no comparte CPU con nada más pesado que el propio rastreo,
así que 15 FPS en la cámara CSI iba bien. En v13, aunque el rastreo vive en
su propio proceso, sigue compitiendo por el mismo CPU físico que el proceso
de voz — bajar a 5 FPS deja más margen sin perder fluidez perceptible (la
Pico ya suaviza el movimiento internamente con su propio `ALPHA=0.1`).
Aplicado en `face_tracker.py` como la constante `FPS_CAMARA`.

## 4. Notas de infraestructura de la Pi 5, encontradas al validar

- **El WiFi power-save cortaba la conexión WebRTC a los ~35s** (ICE
  `disconnected` → `failed`, por pérdida de los keepalives de STUN). Se
  resolvió con una unidad `systemd` que desactiva el power-save del
  adaptador WiFi al arrancar (`wifi-power-save-off.service` o equivalente —
  no incluida en el repo, específica del hardware WiFi de cada Pi).
- El usuario debe pertenecer al grupo `dialout` (para la Pico) y tener
  `picamera2` instalado (venv con `--system-site-packages`) — mismos
  requisitos que v10/v12.
- La vía de terminal con AEC de PipeWire (`v11/pipewire-aec/`, si se
  despliega) y la vía web **no deben correr a la vez**: comparten
  micrófono/parlante y producirían dos voces simultáneas.

## 5. Otros ajustes, ya corregidos en v12 y heredados sin cambios en v13

- Cámara CSI OV5647 vía `abrir_camara_csi()`/`leer_frame()` (picamera2), con
  respaldo automático a webcam USB.
- Resolución de detección 1296×972 + `scaleFactor=1.2, minNeighbors=4` (a
  640×480 la cascada casi no detectaba caras: 0.4% → 100% con el fix).
- Selección del rostro de **mayor área** del frame + descarte de
  detecciones < 80px (un falso positivo fijo del fondo podía secuestrar la
  mirada).
- `FaceTracker(alpha=0.5, zona_muerta=0)` — el cliente apenas suaviza; la
  Pico suaviza internamente.
- `_drenar_entrada()` en `pico_serial.py` — lee y descarta la salida del
  firmware; sin esto, el buffer USB CDC de la Pico se desborda y el
  firmware se bloquea a los ~10s.
- Cadencia de envío a la Pico de 200ms (5/s) — a 20/s el buffer se
  saturaba.

## Confirmado en hardware real

Con la arquitectura de dos procesos (punto 2) y los ajustes de arriba: voz
por navegador clara, sin eco ni autointerrupción, con el rastreo facial
siguiendo un rostro real y la Pico ciclando las 10 expresiones al mismo
tiempo, de forma sostenida.
