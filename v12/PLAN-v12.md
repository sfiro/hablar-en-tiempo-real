# Plan de desarrollo — v12.0.0 Pi 5 + Pico: ciclo de expresiones + rastreo real, sin voz

---

## Hito 1: Firmware y enlace serial traídos de v9/v10, sin cambios de lógica ✅ (completado)

- [x] `main.py` copiado de `../v9/main.py`, **sin ningún cambio de lógica**
      (solo cabecera de comentarios actualizada) — sigue aceptando
      `"LR,UD\n"` y `"LR,UD,EMOCION\n"` por USB serial, sin distinguir qué
      máquina se lo manda
- [x] `estado_base.py`, `diagnostico_canal.py` copiados de `../v9/`, sin
      cambios de lógica (`diagnostico_canal.py` sigue usando PCA9685 por I2C,
      una inconsistencia ya presente desde v5 con `main.py`/`estado_base.py`
      —que sí generan PWM directo—; no se toca en v12 por estar fuera de
      alcance, ver README-v12.md)
- [x] `pico_serial.py` copiado de `../v10/pico_serial.py` (ya adaptado a
      Linux: `encontrar_puerto_pico()`, `/dev/ttyACM*`, nota de grupo
      `dialout`), sin cambios — v12 es también un cliente Linux/Raspberry Pi 5
- [x] Tests de `pico_serial.py` y `estado_base.py` copiados y verificados:
      14 tests pasando en `v12/.venv` (10 + 4), sin ninguna referencia a v9/v10

## Hito 2: Cámara USB de la Pi 5 (no CSI) ✅ (completado)

**Objetivo:** rastrear el rostro con la cámara conectada a la Pi 5, que a
diferencia de v10 es una **webcam USB** (`/dev/video1`, driver V4L2 genérico),
no una cámara CSI. Esto simplifica mucho respecto a v10: no hace falta
`picamera2`/`libcamera` ni un venv con `--system-site-packages` — el mismo
`cv2.VideoCapture` que usaban v3-v9 en el Mac funciona igual aquí, solo
cambiando el índice de cámara por defecto.

- [x] `face_tracker.py` copiado de `../v9/face_tracker.py`: la clase
      `FaceTracker` (EMA, zona muerta, mapeo a grados) no cambió ni una
      línea
- [x] Único cambio real: `--camera-index` por defecto pasa de 0 (Mac) a 1
      (esta Pi 5 concreta, donde la webcam USB enumera como `/dev/video1`) —
      configurable si la cámara de otra Pi 5 enumerase distinto
- [x] Import de la Pico en el script standalone cambiado a
      `encontrar_puerto_pico()` (Linux), en vez de `encontrar_puerto_mac()`
- [x] 8 tests de `FaceTracker` verificados sin cámara real conectada a este
      entorno (cascada falsa inyectada, mismo patrón desde v3)

**Verificado sin hardware:** los 8 tests de `FaceTracker` pasan. Arranque
real de `face_tracker.py`/`rastreo_expresiones.py` en este Mac (sin permiso de
cámara concedido al proceso, situación distinta pero análoga a la Pi 5 sin
cámara conectada): degrada limpiamente con un mensaje claro, sin traceback.

**No verificado, pendiente de la Pi 5 real:** que `/dev/video1` sea
efectivamente el índice correcto para la webcam USB de esta Pi 5 en concreto
(depende de qué más enumere como dispositivo de vídeo V4L2 en esa máquina —
`v4l2-ctl --list-devices` lo confirma), y que la detección funcione igual de
bien que en el Mac con el hardware real.

## Hito 3: Ciclo de expresiones desde el cliente, no desde el firmware — `rastreo_expresiones.py` ✅ (completado)

**Objetivo, pedido explícito:** que el robot vaya cambiando de expresión cada
5 segundos, con la mirada real del rastreo facial, sin implementar todavía
conversación de voz.

**Decisión de diseño:** no se modifica `main.py` para que vuelva a ciclar
solo (como hacía en v6/v7) porque eso sería un paso atrás respecto al modelo
dirigido por eventos que ya tiene desde v8/v9 — un modelo que además es
justo el que hace falta para cuando se retome la voz. En su lugar, el ciclo
vive en un script nuevo del lado de la Pi 5
(`rastreo_expresiones.py`), que manda una `EMOCION` nueva por serial cada
`--interval` segundos (5 por defecto, igual a `INTERVALO_EXPRESION_MS` del
firmware) — desde fuera se ve el mismo ciclo fijo de v6/v7, pero el firmware
es exactamente el de v9, reutilizable sin cambios el día que se añada voz.

- [x] `CICLO_EMOCIONES`: mismo orden fijo que usaban v6/v7
      (`NEUTRAL → FELIZ → ENOJADO → TRISTE → SORPRENDIDO → DORMIDO → DUDA →
      SOSPECHA → PENSATIVO → NERVIOSO → NEUTRAL...`), verificado por test
      contra `EMOCIONES_VALIDAS` de `pico_serial.py` para que nunca diverjan
      en silencio (mismo patrón que `test_webrtc_server.py` en v8/v9)
- [x] `_hilo_rastreo()`: copiado del mecanismo de `../v9/webrtc_server.py`
      (cámara abierta en el hilo principal, pasada ya abierta al hilo de
      fondo — mismo criterio "por consistencia" que v10 documentó, sin
      confirmar que Linux lo necesite), actualiza `ULTIMA_MIRADA` bajo lock y
      manda `PICO.enviar(lr, ud)` sin emoción en cada cambio significativo
- [x] `_ciclar_expresiones()`: en el hilo principal, cada `--interval`
      segundos manda `PICO.enviar(lr, ud, emocion)` con la última mirada real
      conocida (no un `90,90` fijo — mismo razonamiento que `ULTIMA_MIRADA`
      en v9) y avanza al siguiente índice del ciclo
- [x] `_siguiente_indice()` aislado como función pura, testeable sin esperar
      segundos de verdad (mismo patrón que `_decidir_sueno()` en v9)
- [x] Sin servidor HTTP, sin `.env`, sin `OPENAI_API_KEY`: no hay voz ni
      sentimiento en esta versión, así que no hace falta nada de eso —
      requirements.txt más corto de todo el proyecto (`pyserial` +
      `opencv-python<5`)
- [x] Degradación limpia verificada: sin Pico conectada (avisa y sigue sin
      mover servos), sin cámara/permiso (avisa y sigue con mirada fija en
      90,90), y `--no-tracking`/`--no-pico` para aislar cada pieza a mano
- [x] 7 tests nuevos para la lógica del ciclo
      (`tests/test_rastreo_expresiones.py`)

**Verificado sin hardware:** 29 tests en total pasan en `v12/.venv`. Arranque
real de `rastreo_expresiones.py --no-tracking` (sin Pico, sin cámara)
confirma en los logs el ciclo avanzando cada `--interval` segundos con la
mirada fija en 90,90; con `--tracking` (sin permiso de cámara en este
entorno) degrada limpiamente y el ciclo sigue igual.

**No verificado, pendiente de la Raspberry Pi 5 + Pico reales:** que la Pico
reciba de verdad los 10 comandos por USB serial y cicle las expresiones cada
5 segundos sin caer a NEUTRAL entre medias; que el rastreo real mueva la
mirada de las 7 expresiones que la siguen (`NEUTRAL/FELIZ/ENOJADO/TRISTE/
SORPRENDIDO/DORMIDO/SOSPECHA`) mientras `DUDA/PENSATIVO/NERVIOSO` la
ignoran, exactamente como ya se validó en v7/v9 con un Mac.

---

## Definición de listo

v12.0.0 está lista cuando:

1. [x] Firmware (`main.py`) y enlace serial (`pico_serial.py`) traídos sin
   cambios de lógica desde v9/v10
2. [x] Rastreo facial real con la webcam USB de la Pi 5 (`cv2.VideoCapture`,
   sin necesitar `picamera2`)
3. [x] Ciclo de expresiones cada 5 segundos desde el cliente, con la mirada
   real del rastreo, sin tocar el firmware event-driven de v9
4. [x] 29 tests pasando, sin ninguna referencia a v9/v10/v11
5. [ ] **Validada con hardware real**: Raspberry Pi 5 conectada por USB a la
   Pico (con el firmware de esta carpeta), webcam USB en `/dev/video1` (o el
   índice que corresponda), y una sesión real viendo ciclar las 10
   expresiones con la mirada siguiendo un rostro de verdad. Pendiente: es lo
   único que falta para pasar de "código completo" a "completa y validada".
6. [ ] Conversación de voz — explícitamente **fuera de alcance** de esta
   versión, para una v13 posterior una vez validado lo anterior.

---

**Última actualización:** Agosto 23, 2026
**Estado actual:** v12.0.0 con código completo (Hitos 1-3) y 29 tests, todos
pasando sin hardware. **Sin validar todavía en la Raspberry Pi 5 real** — como
v10, escrita sin la Pi 5, la Pico ni la cámara delante. A diferencia de v10,
la cámara aquí es una webcam USB (más simple: sin `picamera2`), y esta
versión no toca voz en absoluto, lo que reduce bastante la superficie sin
probar. Versión abierta hasta esa validación.
