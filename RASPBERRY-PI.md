# Especificación: portar «Hablar en tiempo real» a una Raspberry Pi 5

Documento para pasarle a un agente de código. Contiene el objetivo, las decisiones ya
tomadas, los pasos con su criterio de verificación, y los errores a evitar.

---

## 1. Objetivo

Un asistente de voz **headless** (sin pantalla ni navegador) en una Raspberry Pi 5, que
converse en tiempo real contra la Realtime API de OpenAI, arranque solo al encender, y
**no se interrumpa con su propia voz** al usar altavoces.

Punto de partida: el fichero `realtime_voice.py` de este repositorio, que ya funciona en
macOS y es portable a Linux sin cambios de código.

## 2. Hardware y la restricción que lo condiciona todo

- Raspberry Pi 5. **No tiene jack de 3,5 mm**: el audio sale por USB, HDMI o un DAC I2S.
- Micrófono USB y altavoces USB **como dos dispositivos independientes**.

**La restricción:** dos dispositivos USB distintos tienen relojes independientes. Derivan
entre sí, y para el cancelador de eco acústico (AEC) el eco parece desplazarse, así que el
filtro adaptativo no converge bien. El AEC necesita idealmente que captura y reproducción
compartan dominio de reloj.

Orden de preferencia de hardware:

1. **Un altavoz-manos libres USB con AEC por hardware** (tipo Jabra Speak, Anker PowerConf,
   eMeet). Se presenta como **un solo** dispositivo USB con entrada y salida, y cancela el
   eco en su propio DSP. Es la opción que elimina el problema de raíz y hace innecesario
   todo el AEC por software. **Recomendada.**
2. **Una sola interfaz de audio USB** que haga entrada y salida, más AEC de PipeWire. Un
   único reloj, así que el AEC converge.
3. **Micro USB + altavoces USB por separado** (lo que hay ahora) con AEC de PipeWire y
   compensación de deriva activada. Funciona, pero peor: espera cancelación parcial y
   prevé el plan B del punto 6.

## 3. Arquitectura elegida

Terminal + WebSocket (`realtime_voice.py`), **no** la versión WebRTC con navegador.

Motivo: en Linux el AEC se obtiene en la capa de audio del sistema (PipeWire
`module-echo-cancel` con `aec_method=webrtc`, el mismo motor que usa el navegador), así que
no hace falta Chromium. Eso ahorra CPU, RAM y pantalla, que es justo lo que se quiere en un
aparato headless.

## 4. Pasos

### 4.1 Sistema base

- Raspberry Pi OS (Trixie) **64 bits**. Vale la versión Lite.
- **Aviso:** en Raspberry Pi OS Lite, PipeWire **no viene instalado**. Hay que instalarlo a
  mano (`pipewire`, `pipewire-pulse`, `wireplumber`, `pipewire-audio`). En la versión con
  escritorio ya es el sistema de audio por defecto, en sustitución de PulseAudio.
- Dependencias del proyecto: `sudo apt install libportaudio2` para que funcione
  `sounddevice`, más el `requirements.txt` en un venv.

*Verificación:* `pactl info` responde y muestra PipeWire como servidor.

### 4.2 Identificar los dispositivos

```bash
pactl list short sources    # entradas (micro)
pactl list short sinks      # salidas (altavoces)
.venv/bin/python -c "import sounddevice as sd; print(sd.query_devices())"
```

Anotar los nombres exactos; hacen falta en el paso siguiente.

*Verificación:* grabar y reproducir suelto, antes de meter nada de AEC:

```bash
arecord -d 5 -f cd /tmp/prueba.wav && aplay /tmp/prueba.wav
```

### 4.3 Activar la cancelación de eco

Crear `~/.config/pipewire/pipewire.conf.d/99-echo-cancel.conf` cargando
`libpipewire-module-echo-cancel` con:

- `library.name = aec/libspa-aec-webrtc`
- el `source.name` y `sink.name` reales del paso anterior
- **compensación de deriva activada**, imprescindible por lo del apartado 2
- que exponga una fuente virtual nueva (p. ej. `echo-cancel-source`)

Reiniciar el servicio de usuario y comprobar que aparece la fuente virtual.

*Verificación:* `pactl list short sources` muestra la fuente virtual. Poner música por el
altavoz, grabar de la fuente virtual y confirmar que la música **no** aparece en la
grabación. Este es el criterio de éxito real del paso; no lo des por bueno sin hacerlo.

**Riesgo conocido:** algunas versiones de PipeWire han dado distorsión y crujidos con
`module-echo-cancel`. Si el audio capturado suena roto, prueba otra versión del paquete
antes de dar por perdido el enfoque.

### 4.4 Apuntar el script a la fuente virtual

`realtime_voice.py` usa el dispositivo por defecto de PortAudio. Hay dos vías:

- Poner la fuente virtual como predeterminada del sistema (`pactl set-default-source`), o
- Añadir al script argumentos `--input-device` / `--output-device` que se pasen a
  `sd.RawInputStream(device=…)` y `sd.RawOutputStream(device=…)`. **Preferible**: hace
  explícito qué dispositivo se usa y evita depender de la configuración global.

### 4.5 Desactivar los paliativos

Este paso es el que justifica todo lo anterior, y es fácil pasarlo por alto.

`realtime_voice.py` trae por defecto un modo half-duplex que **cierra el micro mientras
habla el asistente**, más umbrales altos y reducción de ruido `far_field`. Todo eso existe
únicamente porque en macOS no había AEC. Con AEC real sobra, y encima **impide el barge-in**,
que es lo que se quiere recuperar.

Con el AEC funcionando, ejecutar así:

```bash
.venv/bin/python realtime_voice.py --no-half-duplex --noise-reduction near_field
```

*Verificación:* interrumpir al asistente hablando por encima mientras responde. Debe
callarse y escuchar. Y al revés: dejarle hablar solo, sin decir nada, y comprobar que
**termina sus frases** sin cortarse.

### 4.6 Servicio de systemd

Servicio de usuario (no de sistema: necesita la sesión de PipeWire del usuario) que arranque
el script al inicio y lo reinicie si cae. Con `Restart=always` y un `RestartSec` de unos
segundos para no entrar en bucle rápido si falla la red.

La clave va en el `.env` del proyecto, o mejor en `EnvironmentFile=` con permisos `600`.
**Nunca en el fichero .service**, que suele ser legible por todos.

*Verificación:* `systemctl --user status`, reiniciar la Pi y confirmar que arranca solo.

## 5. Criterios de aceptación

1. Arranca al encender la Pi, sin intervención.
2. Con altavoces a volumen normal, el asistente **completa sus frases** sin autointerrumpirse.
3. Se le puede **interrumpir hablando por encima**, y reacciona en menos de un segundo.
4. Sobrevive a un corte de red: se reconecta o el servicio lo reinicia.
5. Uso de CPU en reposo razonable para dejarlo permanentemente encendido.

## 6. Plan B si el AEC no basta

Si con dos dispositivos USB separados la cancelación se queda corta —síntoma: se
autointerrumpe, o el aviso `⚠️ Eco detectado`— hay escalones intermedios antes de rendirse:

1. Bajar el volumen del altavoz y **separarlo físicamente** del micro. Ningún AEC recupera
   un micro saturado.
2. Volver al half-duplex (quitar `--no-half-duplex`): pierdes barge-in pero no se corta.
3. `--push-to-talk`, que elimina el problema por completo pero exige teclado; en un aparato
   headless tendría más sentido cablearlo a un **botón físico GPIO**.
4. Cambiar el hardware por la opción 1 del apartado 2, que es la solución de verdad.

## 7. Errores a evitar

- **No muevas la comprobación de la compuerta del micro al `sender`.** Va en
  `mic_callback`, en el instante de captura. Si se decide al enviar, los bloques grabados
  mientras hablaba el asistente ya están en la cola y salen igual, con el eco dentro. Es un
  bug que ya se cometió y costó encontrar.
- **No sustituyas la verificación TLS por `CERT_NONE`.** En Linux ni siquiera hace falta el
  `certifi` que lleva el script (el sistema ya trae las CA), pero es inofensivo dejarlo.
- **No des por buena la configuración de sesión porque el proceso no falle.** Los errores de
  esquema no abortan: solo imprimen `⚠️ Error de la API` y el script sigue vivo aunque el
  modelo nunca vaya a responder. Hay que leer el log siempre.
- **No expongas el servidor a la red local** si además montas la versión WebRTC. Escucha en
  `127.0.0.1` a propósito: abrirlo dejaría a cualquiera del wifi gastando tu clave.
- **No confíes en `sd.query_devices()` para el orden de los índices.** Con USB puede cambiar
  entre arranques; referencia los dispositivos por nombre.

## 8. Contexto útil del proyecto

Léete el `CLAUDE.md` del repositorio antes de tocar `realtime_voice.py`: documenta el
esquema GA de la sesión (con `audio` anidado, que los ejemplos antiguos tienen plano y no
funcionan), el formato PCM16 mono a 24 kHz, y las reglas de los hilos de PortAudio.
