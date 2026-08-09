# Hablar en tiempo real 🎙️

Asistente de conversación por voz en tiempo real con la Realtime API de OpenAI, con
análisis de emociones y (en desarrollo) control de un rastreador facial mecánico.

**Estado:** v1 completa y respaldada · v2 completa en código, falta validar con voz
real · v3 con rastreador facial + enlace serial completos en código, falta validar
con cámara y hardware real · v4 completa y validada en hardware real (los ojos
siguen el rostro correctamente) · v5 completa y validada en hardware real (+
cuello y parpadeo, sin vibraciones, tras abandonar el PCA9685 por PWM directo) ·
v6 completa y validada en hardware real (utilidad de estado base + secuencia
de expresiones cada 5s, con ajustes de realismo tras la primera prueba —
reposo de párpados, SORPRENDIDO/FELIZ/SOSPECHA/DORMIDO recalculados, cabeza
gacha en TRISTE, mirada fija/errática en DUDA/PENSATIVO/NERVIOSO) · v7
completa y validada en hardware real (misma base de v6, junta el rastreo
facial real con la secuencia de expresiones activa).

## 📦 Versiones disponibles

Cada versión está en su propia carpeta con código, entorno y documentación
independientes. Cada una construye sobre la anterior.

### [v1](v1/) — Voz en tiempo real ✅
**Estado:** Completa y respaldada (tag `v1.0.0`).

- Conversación WebRTC en navegador (macOS), con cancelación de eco real del navegador
- Versión terminal por WebSocket, con paliativos contra eco (half-duplex, detector de
  nivel) para cuando no hay navegador
- Especificación para Raspberry Pi 5 (aparcada, ver [VERSIONS.md](VERSIONS.md))

```bash
cd v1 && source .venv/bin/activate
python webrtc_server.py       # recomendado: WebRTC con navegador
# o
python realtime_voice.py      # terminal, WebSocket
```

Ver [`v1/README-v1.md`](v1/README-v1.md).

### [v2](v2/) — + Análisis de emociones ✅ (código), 🔄 (validación con voz)
**Estado:** Implementado y con tests contra el modelo real; falta que alguien hable de
verdad con `--sentiment` para confirmar que las emociones mostradas tienen sentido.

- Clasifica cada frase (tuya y del asistente) en una de las 6 emociones de Ekman +
  neutral, usando [`pysentimiento`](https://github.com/pysentimiento/pysentimiento)
  (RoBERTuito para español)
- El análisis corre en un hilo aparte: nunca bloquea el audio
- `--stats` da un resumen de emociones al terminar la conversación
- Documentadas con datos reales, no inventados: el modelo acierta claro en frases
  elaboradas y falla más en exclamaciones cortas (ver limitaciones en
  [`v2/README-v2.md`](v2/README-v2.md))

```bash
cd v2 && source .venv/bin/activate
python realtime_voice.py --sentiment --stats
```

Ver [`v2/README-v2.md`](v2/README-v2.md) y [`v2/PLAN-v2.md`](v2/PLAN-v2.md).

### [v3](v3/) — + Rastreo facial y servos 🔄 (código completo, validación pendiente)
**Estado:** Rastreador facial (`FaceTracker`) y enlace serial (`PicoLink`) completos,
con 19 tests pasando. Falta la validación con cámara y hardware real, que no se pudo
hacer en un entorno sandboxed (macOS bloquea el acceso a cámara sin permiso concedido
interactivamente).

Se investigó a fondo un proyecto hermano (`ojosMecanicos`) antes de empezar, para
reusar lo que ya funciona ahí (protocolo serial hacia una Raspberry Pi Pico, patrón de
threading) y no repetir un bug de diseño real que se encontró (una integración de
voz+emoción+cámara que arrancaba los hilos pero nunca conectaba la emoción con el
movimiento).

- Objetivo: mostrar las coordenadas x,y del rostro en consola junto al sentimiento, y
  opcionalmente enviarlas (junto con la emoción, traducida a su vocabulario) por
  serial a una Pico que mueve servos
- Dos bugs reales encontrados en este hito: `opencv-python` 5.0 eliminó
  `CascadeClassifier` del paquete base (fijado a `<5`), y el chequeo de reconexión
  del enlace serial rompía con puertos de prueba inyectados (aislado para que solo
  aplique con hardware real)

```bash
cd v3 && source .venv/bin/activate
python face_tracker.py            # prueba solo la cámara, con ventana de depuración
python -m pytest tests/ -v        # 19 tests, sin necesitar cámara ni Pico
```

Ver [`v3/README-v3.md`](v3/README-v3.md) y [`v3/PLAN-v3.md`](v3/PLAN-v3.md).

### [v4](v4/) — Rastreo facial + servos, simplificado y autónomo ✅ (validado en hardware real)
**Estado:** Completa. Firmware `main.py` simplificado (párpados abiertos al
arrancar, sin parpadeo, + rastreo x,y por serial) **más su propia copia del lado
Mac** (`face_tracker.py`, `pico_serial.py`, con `.venv` propio). **Confirmado en
hardware real: el rastreo funciona y los ojos siguen el rostro correctamente.**

Antes de retomar la integración de voz de v3, se decidió apartar la complejidad del
`main.py` completo de `ojosMecanicos` (emociones, joystick, modo autónomo, parpadeo)
para confirmar primero que el rastreo x,y funciona bien con una base simple.

**Totalmente autónoma: no depende de ningún fichero de v1/v2/v3.** `face_tracker.py`
y `pico_serial.py` son copias de las de v3, no imports — puedes borrar `v3/` entero y
`v4/` sigue funcionando igual. Solo `v4/main.py` (el firmware) es distinto: no tiene
`.venv` porque corre en la Pico, no en el Mac.

```bash
cd v4 && source .venv/bin/activate
python face_tracker.py            # rastreo completo: cámara → x,y → servos
python -m pytest tests/ -v        # 19 tests, autónomos, sin tocar v3
```

Ver [`v4/README-v4.md`](v4/README-v4.md) para cómo desplegar el firmware
(Thonny/`mpremote`) y [`v4/PLAN-v4.md`](v4/PLAN-v4.md) para los hitos.

### [v5](v5/) — + Cuello y parpadeo, mientras rastrea ✅ (validado en hardware real)
**Estado:** Completa. Rotación de cabeza (PAN, amortiguada al 80%) + subir/bajar
cabeza (TILT, amortiguada al 60%) + parpadeo periódico cada 2-6s, todo mientras el
rastreo de ojos sigue funcionando igual que en v4. Sin emociones, joystick ni modo
autónomo todavía. **Confirmado por el usuario: "todos los motores se mueven y
parpadea sin vibraciones".**

**Cambio de arquitectura a mitad de la depuración:** el firmware empezó con el
mismo controlador PCA9685 (I2C) que usa `ojosMecanicos`, pero en hardware real dio
tres problemas (temblor al encender, temblor periódico al parpadear, y el eje PAN
sin moverse) que resultaron tener el mismo origen. Se abandonó el PCA9685 por
completo, generando el PWM de cada servo directamente desde los pines de la Pico
— y los tres problemas desaparecieron a la vez. La cronología completa, con cada
intento y cada error, está documentada en
[`v5/README-v5.md`](v5/README-v5.md#historial-de-depuración-completo).

**Totalmente autónoma, igual que v4:** copia propia de `face_tracker.py` y
`pico_serial.py` (sin cambios respecto a v4), `.venv` propio, 25 tests propios.

```bash
cd v5 && source .venv/bin/activate
python face_tracker.py            # rastreo de ojos, sin cambios respecto a v4
python -m pytest tests/ -v        # 25 tests
```

Ver [`v5/README-v5.md`](v5/README-v5.md) y [`v5/PLAN-v5.md`](v5/PLAN-v5.md).

### [v6](v6/) — Estado base + secuencia de expresiones ✅ (completa y validada en hardware real)
**Estado:** Dos cosas nuevas. `estado_base.py`: lleva los 8 servos a 90° (uno a
uno, con espaciado contra picos de corriente) y los mantiene ahí — posición
segura antes de desconectar la alimentación, o para recuperar un estado neutral
tras un error. Y en `main.py`: **secuencia de expresiones faciales**, cambiando
cada 5 segundos en un orden fijo (NEUTRAL → FELIZ → ENOJADO → ... → NERVIOSO →
NEUTRAL), sin depender de voz ni sentimiento todavía — primer paso, no la
versión final. **Confirmado por el usuario en la Pico real: "todo ha
funcionado bien".**

Tras la primera prueba, se ajustaron varias expresiones para verse más
realistas, y esos ajustes también se validaron en hardware: los párpados en
reposo ya no parten 100% abiertos sino a un 40% de cierre (esto resolvió de
raíz un hallazgo real anterior — SORPRENDIDO no se distinguía de NEUTRAL
porque su offset no tenía margen mecánico para abrir más), FELIZ y SOSPECHA se
recalcularon para notarse sobre el nuevo reposo, TRISTE fuerza la cabeza a su
mínimo mecánico (cabeza gacha), y DUDA/PENSATIVO/NERVIOSO ahora fijan o mueven
la mirada por su cuenta (barrido lateral, mirada arriba-izquierda, y saltos al
azar respectivamente) en vez de seguir el rastreo facial mientras duran.

**Trae toda la base funcional de v5**, sin cambios salvo `main.py`:
`face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`. `main.py` y
`estado_base.py` son programas independientes — desplegar uno no reemplaza al
otro.

```bash
cd v6 && source .venv/bin/activate
python -m pytest tests/ -v        # 49 tests
```

Ver [`v6/README-v6.md`](v6/README-v6.md) y [`v6/PLAN-v6.md`](v6/PLAN-v6.md).

### [v7](v7/) — Seguimiento visual real + secuencia de expresiones ✅ (completa y validada en hardware real)
**Estado:** Sin cambios de lógica respecto a v6 — el objetivo es juntar, por
primera vez, el rastreo facial real (`face_tracker.py`, en el Mac, enviando
`LR,UD` por serial) con la secuencia de expresiones activa. De las 10
emociones, 7 (`NEUTRAL/FELIZ/ENOJADO/TRISTE/SORPRENDIDO/DORMIDO/SOSPECHA`) no
tocan `LR`/`UD`, así que la mirada sigue al rostro real con el offset de cada
emoción aplicado encima; las otras 3 (`DUDA/PENSATIVO/NERVIOSO`) ignoran el
rastreo a propósito y fijan o mueven la mirada por su cuenta, tal como ya
estaban construidas en v6. **Confirmado por el usuario con cámara y Pico
funcionando a la vez: "funcionó perfecto".**

**Totalmente autónoma, igual que v6:** copia propia de `main.py`,
`face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`, `estado_base.py`
(sin cambios de lógica respecto a v6), `.venv` propio, mismos 49 tests.

```bash
cd v7 && source .venv/bin/activate
python -m pytest tests/ -v        # 49 tests
python face_tracker.py            # rastreo real + envío a la Pico, si hay una
```

Ver [`v7/README-v7.md`](v7/README-v7.md) y [`v7/PLAN-v7.md`](v7/PLAN-v7.md).

## 📚 Documentación

- [CLAUDE.md](CLAUDE.md) — contexto técnico completo del proyecto (para trabajar en el código)
- [VERSIONS.md](VERSIONS.md) — hoja de ruta e historial de versiones
- [v1/README-v1.md](v1/README-v1.md) · [v1/CLAUDE-v1.md](v1/CLAUDE-v1.md)
- [v2/README-v2.md](v2/README-v2.md) · [v2/PLAN-v2.md](v2/PLAN-v2.md) · [v2/INSTALL-v2.md](v2/INSTALL-v2.md)
- [v3/README-v3.md](v3/README-v3.md) · [v3/PLAN-v3.md](v3/PLAN-v3.md)
- [v4/README-v4.md](v4/README-v4.md) · [v4/PLAN-v4.md](v4/PLAN-v4.md)
- [v5/README-v5.md](v5/README-v5.md) · [v5/PLAN-v5.md](v5/PLAN-v5.md) — incluye la cronología completa de depuración
- [v6/README-v6.md](v6/README-v6.md) · [v6/PLAN-v6.md](v6/PLAN-v6.md)
- [v7/README-v7.md](v7/README-v7.md) · [v7/PLAN-v7.md](v7/PLAN-v7.md)
- [docs/RASPBERRY-PI.md](docs/RASPBERRY-PI.md) — especificación para Pi 5, aparcada

## 🔧 Requisitos

- Python 3.9+
- Clave de API de OpenAI con acceso a la Realtime API
- Micrófono y altavoces (v1/v2) — cámara adicional para v3/v4/v5/v6/v7
- v2 y v3 instalan `pysentimiento` (torch + transformers): ~2GB, varios minutos la
  primera vez. **v4, v5, v6 y v7 no** — son mucho más ligeros (solo `opencv-python` +
  `pyserial`), porque no tocan voz ni sentimiento
- `main.py`/`estado_base.py` de v4/v5/v6/v7 son firmware MicroPython: necesitan la
  Raspberry Pi Pico física; el resto (rastreo facial) es Python normal de Mac

## 📋 Comparativa de versiones

| | v1 | v2 | v3 | v4 | v5 | v6 | v7 |
|---|---|---|---|---|---|---|---|
| Dónde corre | Mac | Mac | Mac | Mac + **la Pico** | Mac + **la Pico** | Mac + **la Pico** | Mac + **la Pico** |
| Voz en tiempo real | ✅ | ✅ (hereda de v1) | ✅ (hereda de v2) | — (a propósito) | — (a propósito) | — (a propósito) | — (a propósito) |
| Cancelación de eco | Navegador (WebRTC) | igual que v1 | igual que v1 | n/a | n/a | n/a | n/a |
| Análisis de emociones | — | ✅ `pysentimiento`, en consola | ✅ (hereda de v2) | — | — | — | — |
| Rastreo facial (ojos) | — | — | 🔄 falta cámara real | ✅ validado en real | ✅ (hereda de v4) | ✅ (hereda de v5) | ✅ (hereda de v6) |
| Cuello (PAN/TILT) | — | — | — | — | ✅ validado en real | ✅ (hereda de v5) | ✅ (hereda de v6) |
| Parpadeo | — | — | — | — | ✅ validado en real | ✅ (hereda de v5) | ✅ (hereda de v6) |
| Utilidad de estado base | — | — | — | — | — | ✅ validada en real | ✅ (hereda de v6) |
| Expresiones faciales | — | — | — | — | — | ✅ secuencia + ajustes de realismo, validados en real | ✅ (hereda de v6) |
| Rastreo real + expresiones a la vez | — | — | — | — | — | — | ✅ validado en real |
| Estado | ✅ Completa | Validación pendiente | Validación pendiente | ✅ Completa y validada | ✅ Completa y validada | ✅ Completa y validada | ✅ Completa y validada |

**Nota sobre independencia:** cada carpeta de versión tiene sus propias copias de
cualquier código que reutilice de otra (nunca lo importa con una ruta cruzada). Por
eso `face_tracker.py` y `pico_serial.py` existen, idénticos, en `v3/`, `v4/`, `v5/`,
`v6/` y `v7/`. Puedes borrar cualquier carpeta de versión anterior y las demás
siguen funcionando.

## 📖 Estructura del proyecto

```
.
├── v1/                     # Voz en tiempo real (completa)
│   ├── realtime_voice.py   # Cliente WebSocket
│   ├── webrtc_server.py    # Servidor SDP (recomendado)
│   ├── static/
│   ├── README-v1.md
│   └── CLAUDE-v1.md
├── v2/                     # + Análisis de emociones
│   ├── realtime_voice.py   # v1 + --sentiment
│   ├── sentiment_analyzer.py
│   ├── tests/
│   ├── README-v2.md
│   ├── PLAN-v2.md
│   └── INSTALL-v2.md
├── v3/                     # + Rastreo facial y servos (código de Mac)
│   ├── face_tracker.py     # FaceTracker (headless) + script standalone con ventana
│   ├── pico_serial.py      # PicoLink: cola, reconexión, latido
│   ├── tests/
│   ├── README-v3.md
│   └── PLAN-v3.md
├── v4/                     # Rastreo facial + servos, simplificado y autónomo
│   ├── main.py             # Firmware Pico (MicroPython): ojos abiertos + rastreo x,y
│   ├── face_tracker.py     # Copia autónoma de v3 (Mac, con .venv propio)
│   ├── pico_serial.py      # Copia autónoma de v3 (Mac, con .venv propio)
│   ├── tests/
│   ├── README-v4.md
│   └── PLAN-v4.md
├── v5/                     # + Cuello (PAN/TILT) y parpadeo periódico
│   ├── main.py             # Firmware Pico: PWM directo (sin PCA9685), cuello + parpadeo
│   ├── main_pca9685.py     # Archivado: versión con PCA9685, no usar (ver README-v5.md)
│   ├── face_tracker.py     # Copia autónoma de v4, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v4, sin cambios
│   ├── diagnostico_canal.py # Herramienta: mueve un solo canal, aislado
│   ├── tests/              # 25 tests
│   ├── README-v5.md        # Incluye la cronología completa de depuración
│   └── PLAN-v5.md
├── v6/                     # Estado base + secuencia de expresiones
│   ├── estado_base.py      # Nuevo: centra los 8 servos y los mantiene
│   ├── main.py             # v5 + secuencia de expresiones cada 5s (nuevo)
│   ├── face_tracker.py     # Copia autónoma de v5, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v5, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v5, sin cambios
│   ├── tests/              # 49 tests
│   ├── README-v6.md
│   └── PLAN-v6.md
├── v7/                     # Seguimiento visual real + secuencia de expresiones
│   ├── main.py             # Copia idéntica de v6, sin cambios de lógica
│   ├── face_tracker.py     # Copia autónoma de v6, sin cambios
│   ├── pico_serial.py      # Copia autónoma de v6, sin cambios
│   ├── estado_base.py      # Copia autónoma de v6, sin cambios
│   ├── diagnostico_canal.py # Copia autónoma de v6, sin cambios
│   ├── tests/              # 49 tests (heredados de v6, sin cambios)
│   ├── README-v7.md
│   └── PLAN-v7.md
├── docs/
│   └── RASPBERRY-PI.md     # Especificación técnica, aparcada
├── CLAUDE.md               # Contexto técnico completo del proyecto
├── VERSIONS.md             # Hoja de ruta
└── README.md               # Este fichero
```

Cada versión es independiente: su propio venv, requirements y documentación, y sus
propias copias de cualquier código reutilizado de otra versión (nunca imports entre
carpetas). v1 no cambia mientras se trabaja en v2, v3, v4, v5, v6 o v7, y puedes
borrar cualquier versión anterior sin romper las demás.

## ❓ FAQ

**¿Puedo usar v1 o v2 mientras se trabaja en v3?**
Sí. Cada versión vive en su carpeta con su propio entorno; trabajar en v3 no toca v1 ni v2.

**¿Cómo bajo solo una versión?**
`git clone --branch v1.0.0 <repo>` para v1. v2 y v3 aún no tienen tag propio (ver
[VERSIONS.md](VERSIONS.md)).

**¿Por qué v2 dice "código completo, validación pendiente"?**
El análisis de emociones está probado contra el modelo real con tests automatizados,
pero falta que alguien mantenga una conversación de voz real con `--sentiment` para
confirmar que lo mostrado en consola tiene sentido con una conversación hablada, no
solo con texto de prueba.

**¿Qué es `ojosMecanicos`?**
Un proyecto hermano y anterior del mismo usuario: un sistema de servos (una Raspberry
Pi Pico moviendo "ojos" mecánicos) con su propio historial de intentos de integrar
voz y cámara. v3 reutiliza su protocolo serial y su patrón de threading, ya probados
ahí, en vez de reinventarlos. Ver [`v3/README-v3.md`](v3/README-v3.md).

---

**Última actualización:** Agosto 4, 2026
