# Hablar en tiempo real 🎙️

Asistente de **conversación por voz en tiempo real** con la Realtime API de OpenAI.

## 📊 Estado actual — Primer avance ✅

- **Versión WebRTC (navegador)**: ✅ **funcionando y verificada** en macOS.
  - Conversación fluida con altavoces sin autointerrupción.
  - Barge-in natural: interrumpir al asistente hablando por encima.
  - Arranca con: `python webrtc_server.py`
  
- **Versión de terminal**: ✅ funciona en macOS con auriculares.
  - Paliativos contra eco implementados (half-duplex, compuerta, detector de nivel).
  - Arranca con: `python realtime_voice.py`

- **Raspberry Pi 5 en desarrollo**: 📋 especificación completa en [RASPBERRY-PI.md](RASPBERRY-PI.md).
  - Arquitectura: terminal headless + AEC de PipeWire.
  - Configuración de audio y servicio de systemd documentados.
  - Hardware recomendado: manos libres USB con AEC por hardware.

---

## Cómo usar ahora

Hay **dos versiones**, y la diferencia entre ellas es quién captura el micrófono:

| | [`webrtc_server.py`](webrtc_server.py) — navegador | [`realtime_voice.py`](realtime_voice.py) — terminal |
|---|---|---|
| Transporte | WebRTC | WebSocket |
| Cancelación de eco | ✅ real, la del navegador | ❌ ninguna |
| Funciona con altavoces | ✅ | ⚠️ solo con paliativos |
| Interrumpirle hablando | ✅ natural | ⚠️ aproximado |
| Dónde ocurre | pestaña del navegador | terminal |

**Empieza por la versión WebRTC.** Es la que usa el modo de voz de ChatGPT y la única que
resuelve el eco de verdad:

```bash
python webrtc_server.py
```

La versión de terminal se mantiene porque no necesita navegador y sirve para integrarla en
otros programas, pero sin auriculares el modelo tiende a interrumpirse con su propia voz.

## Requisitos

- Python 3.9+
- Una clave de API de OpenAI con acceso a la Realtime API
- Micrófono y altavoces

En macOS, `sounddevice` (solo lo usa la versión de terminal) necesita PortAudio; normalmente
se instala solo con `pip`. Si falla: `brew install portaudio`.

## Instalación

```bash
cd "Hablar en tiempo real"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuración

Ambas versiones leen la clave del fichero `.env` de la raíz del proyecto:

```bash
cp .env.example .env
```

Edita `.env` y pon tu clave real:

```
OPENAI_API_KEY="sk-..."
```

`.env` está en `.gitignore`: **nunca lo subas a un repositorio**. Si prefieres no usar
fichero, también funciona exportando la variable en tu shell (tiene prioridad sobre `.env`):

```bash
export OPENAI_API_KEY="sk-..."
```

---

## Versión WebRTC (recomendada)

**Estado: funcionando.** Conversación fluida con altavoces, sin autointerrupción y
pudiendo intervenir en cualquier momento mientras el asistente habla.

```bash
python webrtc_server.py
python webrtc_server.py --voice cedar --port 8080
```

Abre `http://localhost:8000/`, pulsa **Conectar**, acepta el permiso de micrófono y habla.

Opciones: `--model` (por defecto `gpt-realtime-2.1`), `--voice`, `--instructions`,
`--port`, `--no-browser`, `--verbose`.

### Condiciones de uso

Necesita un navegador, pero **la página se sirve desde tu propio disco, en `localhost`**.
No hay nada publicado ni accesible desde fuera; internet solo hace falta para llegar a la
API de OpenAI.

- **Un solo comando**: `python webrtc_server.py` abre la pestaña él mismo.
- **Cualquier navegador moderno**: Safari, Chrome, Firefox o Edge.
- **Permiso de micrófono**, que el navegador pide una vez y recuerda para `localhost`.
- **No hace falta HTTPS ni certificados**: `localhost` cuenta como contexto seguro, así que
  `getUserMedia` funciona sin más.
- **La terminal, abierta** mientras conversas (con el matiz de abajo).

### El servidor no está en la ruta del audio

Solo interviene en el apretón de manos inicial: recibe la oferta SDP del navegador, la
firma con tu clave y devuelve la respuesta. A partir de ahí **el audio va directo entre el
navegador y OpenAI**.

En la práctica, una vez conectado podrías cerrar la terminal y la conversación seguiría; lo
necesitas de nuevo solo para volver a conectar. No es una forma recomendable de trabajar,
pero explica por qué el proceso local es tan ligero y por qué no añade latencia.

### Si te molesta el navegador

De menos a más trabajo:

1. **Modo aplicación de Chrome**, que abre una ventana limpia sin barra de direcciones ni
   pestañas. Parece una app y no requiere tocar el código:

   ```bash
   python webrtc_server.py --no-browser &
   open -a "Google Chrome" --args --app=http://localhost:8000
   ```

2. **Envolverlo en Tauri o Electron** para tener una app con su icono. Por dentro sigue
   siendo el mismo motor de navegador, que es justo lo que aporta el AEC.
3. **Volver a la terminal con AEC nativo de macOS**: sustituir `sounddevice` por
   `AVAudioEngine` vía PyObjC con Voice Processing I/O, que es el AEC del sistema. Es un
   rato de trabajo, solo funciona en macOS y **no está validado**.

### Por qué esta versión no sufre eco

El navegador captura el micro con `echoCancellation: true`, que activa **cancelación de eco
acústico real**: un filtro adaptativo que conoce la señal que sale por el altavoz y la resta
de la que entra por el micro. El modelo deja de oírse a sí mismo, así que el micro puede
estar abierto todo el tiempo y puedes cortarle hablando, con altavoces y sin trucos.

Eso es exactamente lo que hace el modo de voz de ChatGPT, y es imposible de replicar desde
Python con PortAudio, que entrega el micro en crudo y sin referencia de la salida.

### Tu clave no sale del equipo

El servidor solo escucha en `127.0.0.1` y hace de intermediario: el navegador le manda su
oferta SDP, él la reenvía a `https://api.openai.com/v1/realtime/calls` firmada con tu
`OPENAI_API_KEY`, y devuelve la respuesta SDP. La clave nunca llega al navegador.

---

## Versión de terminal

Hablas por el micrófono, el modelo detecta cuándo terminas tu turno (server VAD) y te
responde con voz por los altavoces. **Usa auriculares**: sin cancelación de eco, el altavoz
alimenta al micro y hace falta recurrir a los paliativos que se describen más abajo.

### Uso

Ejecútalo **desde tu Terminal** (macOS necesita concederle permiso de micrófono):

```bash
source .venv/bin/activate
python realtime_voice.py
```

O sin activar el entorno:

```bash
.venv/bin/python realtime_voice.py
```

Opciones:

```bash
python realtime_voice.py --voice cedar
python realtime_voice.py --model gpt-realtime --voice marin \
  --instructions "Eres un tutor de inglés. Corrige mis errores con amabilidad."
```

- `--model`   Modelo de voz (por defecto `gpt-realtime`).
- `--voice`   Voz: `marin`, `cedar`, `alloy`, `echo`, `shimmer`, … (por defecto `marin`).
- `--instructions`  Personalidad / instrucciones de sistema.
- `--half-duplex` / `--no-half-duplex`  Evita que el modelo se interrumpa con su propia voz
  (activado por defecto). Ver abajo.
- `--vad-threshold`  Sensibilidad del detector de voz, 0-1 (por defecto `0.75`).
- `--noise-reduction`  `far_field` (por defecto, altavoces/micro de portátil),
  `near_field` (auriculares con micro) u `off`.
- `--vad`  `server_vad` (por defecto) o `semantic_vad`.
- `--barge-in`  Permite cortarle hablando por encima (ver abajo).
- `--barge-in-factor`  Cuánto debe superar tu voz al eco para cortarle (por defecto `3.0`).
- `--push-to-talk`  Enter para hablar, Enter para enviar. Sin detección de turnos.
- `--echo-tail-ms`  Margen tras callar antes de reabrir el micro (por defecto `600`).
- `--debug`  Imprime los eventos de la API para diagnosticar cortes.

Sal con **Ctrl+C**.

### Eco: por qué el modelo se interrumpe solo

Si usas altavoces, su propia voz vuelve a entrar por el micro, el detector de voz del
servidor cree que has empezado a hablar y **corta la respuesta a media frase**.

Esta es la limitación de fondo de la versión de terminal, y no tiene solución completa:
PortAudio entrega el micro en crudo, sin referencia de lo que sale por el altavoz, así que
todo lo de abajo son paliativos que estiman el eco desde fuera. Si te molesta, usa la
[versión WebRTC](#versión-webrtc-recomendada), que sí tiene cancelación de eco real.

El script aplica cuatro medidas, todas activas por defecto:

1. **Reducción de ruido en la entrada** (`noise_reduction: far_field`). La API la trae
   **desactivada por defecto**; filtra el audio *antes* del VAD, y el modo `far_field` es
   justo el de micro de portátil o manos libres. Con auriculares usa `near_field`.
2. **Umbral de VAD a 0.75** en lugar de 0.5, para que el eco no cuente como voz.
3. **`interrupt_response: false`**, que impide al servidor cortar una respuesta en curso
   aunque crea haber detectado voz.
4. **Modo half-duplex**: mientras suena la voz del asistente, el micro se descarta en
   local (más un margen de 300 ms para el rebote de la sala), así su voz nunca llega a
   la API.

#### Si aun así se sigue cortando

El modo **pulsar-para-hablar** elimina el problema de raíz: desactiva la detección de
turnos del servidor, así que el eco no puede abrir un turno ni aunque se cuele.

```bash
python realtime_voice.py --push-to-talk
```

Enter para empezar a hablar, Enter otra vez para enviar.

Alternativas intermedias, de menos a más drásticas:

```bash
python realtime_voice.py --vad semantic_vad   # fin de turno decidido por un modelo
python realtime_voice.py --vad-threshold 0.9  # VAD casi sordo al eco
python realtime_voice.py --echo-tail-ms 1000  # más margen si la sala retumba
```

Y para ver *qué* está cortando la frase:

```bash
python realtime_voice.py --debug
```

Cada respuesta truncada imprime `✂️ Respuesta <estado>` con el motivo que da la API.

```bash
python realtime_voice.py                    # half-duplex (por defecto)
python realtime_voice.py --no-half-duplex   # barge-in, requiere auriculares
```

### Cómo interrumpirle

Con el micro cerrado mientras habla, el eco no puede cortarle… pero tú tampoco. Hay tres
maneras de recuperar la interrupción, de más a menos fiable:

**1. Enter** (siempre disponible, no falla nunca). Pulsa Enter mientras el asistente habla
y se calla al instante. No depende del audio, así que no tiene falsos positivos.

**2. Hablando por encima** (`--barge-in`):

```bash
python realtime_voice.py --barge-in
```

Mientras el micro está cerrado, lo que entra por él *es* el eco del altavoz, así que el
script lo aprovecha para medir su nivel. Solo cuenta como voz tuya lo que supere ese nivel
con holgura (×3 por defecto) durante 300 ms seguidos. Se adapta solo al volumen del
altavoz y a la sala, pero no es infalible: si te corta solo, sube el margen.

```bash
python realtime_voice.py --barge-in --barge-in-factor 5
```

**3. Con auriculares** (`--no-half-duplex`), que es lo más natural de todo: sin eco no hay
nada que filtrar y la interrupción por voz funciona con el VAD del servidor.

```bash
python realtime_voice.py --no-half-duplex --noise-reduction near_field
```

| | `--half-duplex` (por defecto) | `--half-duplex --barge-in` | `--no-half-duplex` |
|---|---|---|---|
| Sirve con altavoces | ✅ | ✅ | ❌ se autointerrumpe |
| Cortarle con Enter | ✅ | ✅ | ✅ |
| Cortarle hablando | ❌ | ✅ aproximado | ✅ |

Si aun así el ruido ambiente le hace saltar turnos falsos, sube el umbral:

```bash
python realtime_voice.py --vad-threshold 0.7
```

### Cómo funciona por dentro

1. El micro se captura en PCM16 mono a 24 kHz y se envía como eventos
   `input_audio_buffer.append` (base64) por WebSocket.
2. El servidor detecta el fin de tu turno (`server_vad`) y genera la respuesta.
3. Los deltas de audio (`response.output_audio.delta`) se reproducen en streaming.
4. Si empiezas a hablar mientras el modelo responde, se vacía el búfer de reproducción
   (evento `input_audio_buffer.speech_started`) para permitir la interrupción.

## Problemas frecuentes

**`ERROR: falta OPENAI_API_KEY`**
No has creado el `.env` o sigue con el valor de ejemplo. Pon tu clave real.

**`invalid_api_key`**
La conexión funciona pero la clave no es válida o no tiene acceso a la Realtime API.
Revisa la clave en <https://platform.openai.com/api-keys>.

**`SSL: CERTIFICATE_VERIFY_FAILED`**
El Python de python.org en macOS no trae certificados raíz. El script ya lo resuelve
usando el bundle de `certifi` (incluido en `requirements.txt`), así que asegúrate de
ejecutarlo con el intérprete del venv (`.venv/bin/python`) y no con otro Python.

**El modelo se interrumpe solo** *(versión de terminal)*
Eco del altavoz hacia el micro. El modo half-duplex (por defecto) lo mitiga, pero la
solución de verdad es usar la [versión WebRTC](#versión-webrtc-recomendada). Ver «Eco».

**No se oye nada / no capta el micro** *(versión de terminal)*
Comprueba los dispositivos que ve PortAudio:

```bash
.venv/bin/python -c "import sounddevice as sd; print(sd.query_devices())"
```

Y revisa que Terminal tenga permiso de micrófono en
*Ajustes del Sistema → Privacidad y seguridad → Micrófono*.

**`Sin acceso al micrófono: Permission denied`** *(versión WebRTC)*
Denegaste el permiso en el navegador. En Safari se restablece en *Ajustes → Webs →
Micrófono*; en Chrome, pulsando el icono junto a la barra de direcciones.

**El puerto 8000 está ocupado** *(versión WebRTC)*
Otro proceso lo está usando: `python webrtc_server.py --port 8080`.

**`invalid_offer` al conectar** *(versión WebRTC)*
El SDP que llegó a OpenAI no era válido. Si sale desde la página, mira la consola del
navegador; ese error aparece también al probar el endpoint a mano con un SDP falso, y en
ese caso confirma que el resto de la configuración sí se aceptó.

---

## 🗺️ Hoja de ruta

### Primer avance ✅ (completado)
- ✅ Versión WebRTC funcional en macOS, sin autointerrupción.
- ✅ Versión de terminal con paliativos contra eco.
- ✅ Documentación completa de ambas arquitecturas.
- ✅ Especificación para Raspberry Pi 5 lista para implementar.

### Próximos pasos 📋
1. **Implementación en Raspberry Pi 5**
   - Instalar y configurar PipeWire con `module-echo-cancel`.
   - Adaptar `realtime_voice.py` para dispositivos USB (con parámetros `--input-device` / `--output-device`).
   - Crear servicio de systemd para arranque automático.
   - Verificar AEC con grabación de prueba (paso 4.3 de [RASPBERRY-PI.md](RASPBERRY-PI.md)).

2. **Hardware de audio**
   - Evaluar manos libres USB con AEC por hardware como opción preferida.
   - Si se usan dos dispositivos USB separados, activar compensación de deriva en PipeWire.

3. **Modo aplicación (opcional)**
   - Script de arranque que levante el servidor WebRTC y abra Chrome en modo `--app`.
   - Útil si se monta una pantalla pequeña (e-ink, OLED) en la Pi.

4. **Mejoras futuras** (fuera del alcance actual)
   - Wake word detection para arrancar por voz.
   - Gestión de múltiples sesiones.
   - Integración con Home Assistant o Node-RED.
   - AEC nativo de macOS vía PyObjC + `AVAudioEngine` (validar que funciona).

### Referencias
- [RASPBERRY-PI.md](RASPBERRY-PI.md) — especificación técnica completa.
- [CLAUDE.md](CLAUDE.md) — detalles de arquitectura y esquemas de sesión.
- [webrtc_server.py](webrtc_server.py) — servidor intermediario SDP.
- [realtime_voice.py](realtime_voice.py) — cliente WebSocket terminal.
