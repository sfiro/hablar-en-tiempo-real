# Versión 3.0 — Rastreo facial + servos 👁️

Extensión de v2 que añade rastreo facial por cámara: las coordenadas x,y del rostro se
muestran en consola junto al sentimiento, y opcionalmente se envían por serial a una
Raspberry Pi Pico que mueve un par de servos (sistema de "ojos mecánicos").

**Estado:** Hito 0 y Hito 1 completos (investigación + rastreador facial + enlace
serial, ambos con tests). Falta validar con cámara y hardware real — no se puede hacer
desde este entorno, necesita permiso de macOS concedido en una Terminal interactiva.
**Plataforma:** macOS (webcam integrada), igual que v1/v2.
**Base:** v2 completo (voz + sentimiento) + rastreo facial con OpenCV + serial opcional.

---

## Antes de escribir código: lo que ya existe

El usuario tiene un proyecto hermano, [`ojosMecanicos`](/Users/debbie/Desktop/programacion/ojosMecanicos/),
con un sistema de servos controlado por una Raspberry Pi Pico y varios intentos previos
de integrar cámara + voz + emociones. Investigamos ese proyecto a fondo antes de escribir
una sola línea de v3, para no rehacer lo que ya existe ni repetir errores ya cometidos ahí.

**Conclusión de la investigación:** no existe una integración funcional de voz +
emociones + rastreo facial + servos. Hay dos generaciones de arquitectura en
`ojosMecanicos` que nunca se terminaron de fusionar:

- **Generación A** (histórica, abandonada): cámara OpenCV + reconocimiento de voz
  (Google/Whisper/pyttsx3) en hilos separados comunicados por `queue.Queue`. El propio
  README de ese proyecto la da por reemplazada.
- **Generación B** (la que ellos documentan como "en producción"): WebRTC puro
  navegador↔OpenAI, sin cámara. El rastreo facial está en su TODO, no implementado.
- El único puente entre ambas (`08_voz_emociones_ojos_integrado.py`) tiene un bug de
  diseño real: lanza los hilos de cámara y de posición, pero la función que debía
  conectar el texto de la conversación con la emoción **nunca se llama**. Es código
  muerto — arrancan los hilos, pero la información real nunca fluye entre ellos.

**Qué SÍ reutilizamos de esa investigación** (probado, documentado, funciona):

1. **El protocolo serial hacia la Pico**, ya implementado y probado en su
   `server_realtime.py` y firmware `main.py`:
   ```
   Formato:   LR,UD,EMOCION\n     (o LR,UD\n sin emoción)
   Ejemplo:   120,60,FELIZ\n
   LR, UD:    enteros 40-140 (grados de servo)
   EMOCION:   opcional, mayúsculas, una de: NEUTRAL, FELIZ, ENOJADO, TRISTE,
              SORPRENDIDO, DORMIDO, DUDA, SOSPECHA, PENSATIVO, NERVIOSO
   Baud:      115200
   ```
2. **El truco del "latido"**: mientras haya control remoto activo, reenviar el último
   comando cada 1 segundo, o el firmware de la Pico vuelve a modo autónomo.
3. **Reconexión por comprobación de archivo**: en macOS, verificar si
   `/dev/cu.usbmodem...` sigue existiendo para detectar que la Pico se desconectó.
4. **La regla de threading que confirma nuestro propio diseño**: `cv2.imshow` +
   `waitKey` bloqueante debe vivir en su **propio hilo `daemon=True`**, nunca mezclado
   con `asyncio.run()`. Es exactamente el patrón que v1/v2 ya usan para el audio
   (PortAudio corre en sus propios hilos, separado del loop de asyncio).

**Qué NO reutilizamos:**

- Su análisis de sentimiento local (diccionario de palabras clave en español +
  `TextBlob`, que por defecto analiza en inglés y es casi inerte sobre texto en
  español). Nuestro `pysentimiento` de v2 ya es más sofisticado y ya está verificado
  con datos reales.
- Su código de cámara+voz+emociones tal cual (el bug del puente muerto). Vamos a cablear
  la conexión real entre sentimiento y comando serial, con un test que lo verifique.

---

## Qué añade v3

```bash
python realtime_voice.py --sentiment --face-tracking
```

Ejemplo de consola (mockup, aún no implementado):

```
🎙️  Listo. Habla con naturalidad; haz una pausa y el modelo responderá.
    Emociones: ACTIVO (es)
    Rastreo facial: ACTIVO (cámara 0) · Pico: conectada en /dev/cu.usbmodem1101
    (Ctrl+C para salir)

👁️  Rostro: x=320, y=210 (centro de cuadro)
🗣️  Tú: Estoy muy feliz hoy
   😊 ALEGRÍA (0.91)
👁️  Rostro: x=318, y=205
😊 Asistente: ¡Qué bueno escuchar eso!
   😊 ALEGRÍA (0.85)
```

Con la Pico conectada, cada actualización de emoción o de posición se traduce en un
comando serial `LR,UD,EMOCION\n` real.

---

## Arquitectura: tres contextos de ejecución concurrentes

Ninguno de los tres se mezcla con los otros directamente; se comunican por estado
compartido simple (protegido por el GIL, como hace `ojosMecanicos`) o por `Queue`.

1. **Loop de asyncio** (idéntico a v2): WebSocket con la Realtime API, sender/receiver,
   análisis de sentimiento vía `run_in_executor`. Sin cambios respecto a v2.
2. **Hilo de cámara** (`daemon=True`, nuevo en v3): bucle de OpenCV con
   `cap.read()` + detección de rostro + (opcionalmente) `cv2.imshow`. **Nunca** toca
   `asyncio`. Escribe la posición `(x, y)` actual en una variable compartida simple.
3. **Hilo de Pico** (`daemon=True`, nuevo en v3): cola de comandos serial +
   reconexión + latido cada 1s, siguiendo el patrón ya probado de `server_realtime.py`.
   Lee la posición del hilo de cámara y la emoción del loop de asyncio (vía la misma
   variable compartida que ya usa `analyze_and_print`), las combina, y escribe al
   puerto serial.

El hilo principal del proceso Python es el que llama a `asyncio.run()` (como en v1/v2);
los hilos de cámara y Pico se arrancan antes de entrar al loop y se detienen en el
`finally`, igual que ya se hace con `mic_stream` y `playback` en v1/v2.

## Mapeo de emoción a vocabulario de la Pico

El clasificador de v2 (`pysentimiento`) da 6 emociones de Ekman + neutral. El firmware
de la Pico espera un vocabulario de 10 palabras distinto. No hay una correspondencia
1 a 1 perfecta; esta es la que proponemos, y se declara explícitamente para no fingir
precisión que no existe:

| Emoción (pysentimiento) | Comando a la Pico | Nota |
|---|---|---|
| joy (ALEGRÍA) | FELIZ | directo |
| sadness (TRISTEZA) | TRISTE | directo |
| anger (RABIA) | ENOJADO | directo |
| fear (MIEDO) | NERVIOSO | no hay "MIEDO" en el vocabulario de la Pico; NERVIOSO es lo más cercano |
| surprise (SORPRESA) | SORPRENDIDO | directo |
| disgust (ASCO) | NEUTRAL | no hay equivalente en el vocabulario de la Pico; se degrada a neutral en vez de inventar uno |
| others (NEUTRAL) | NEUTRAL | directo |

`DORMIDO`, `DUDA`, `SOSPECHA`, `PENSATIVO` del vocabulario de la Pico quedan sin usar
desde esta vía — son alcanzables por otros modos de control de `ojosMecanicos`
(joystick, autónomo), no por el análisis de sentimiento de la conversación.

---

## Hardware

- Webcam (integrada de Mac o USB)
- **Opcional:** Raspberry Pi Pico con firmware de `ojosMecanicos` (`main.py`) y servos
  conectados vía I2C/PCA9685, cableada por USB
- Sin la Pico conectada, el script debe seguir funcionando igual que v2, mostrando
  solo las coordenadas en consola sin enviarlas a ningún lado (mismo patrón que
  `rastreoCara_Mac.py`, que ya maneja `pico is None` sin fallar)

## Preguntas abiertas, ya resueltas en el Hito 1

- **¿Ventana de vídeo o headless?** Resuelto: la clase `FaceTracker` es headless por
  diseño (nunca toca `cv2.imshow`); el script standalone `face_tracker.py` sí abre
  ventana por defecto (útil para calibrar), desactivable con `--no-window`. Cuando se
  integre con la voz (Hito 2), se usará la clase sin ventana.
- **¿Detector Haar Cascade o algo mejor?** Se mantiene Haar Cascade
  (`haarcascade_frontalface_default.xml`) para ser fiel al código de referencia.
  Con un efecto colateral real: `opencv-python` 5.0 movió `CascadeClassifier` a
  `opencv-contrib-python`; se fijó la versión a `<5` en `requirements.txt` en vez de
  migrar ya a la API DNN nueva (`cv2.FaceDetectorYN`), que sería la vía recomendada
  por OpenCV para un proyecto nuevo, pero no es fiel al original y es más trabajo del
  que pide este hito.
- **¿Qué pasa si no hay cámara disponible?** En el script standalone de este hito,
  sale con un mensaje claro (no hay nada que probar sin cámara). La degradación con
  gracia dentro de la app completa de voz —seguir conversando sin rastreo— es
  responsabilidad del Hito 2, no de este script de prueba aislado.

---

## Desarrollo

Seguimiento en [PLAN-v3.md](PLAN-v3.md). Hito 0 (esta investigación) completado.

## Referencias

- [ojosMecanicos](/Users/debbie/Desktop/programacion/ojosMecanicos/) — proyecto
  hermano, origen del protocolo serial y el firmware de la Pico
- [../v2/README-v2.md](../v2/README-v2.md) — base de v3 (voz + sentimiento)
- [../VERSIONS.md](../VERSIONS.md) — hoja de ruta general del proyecto
