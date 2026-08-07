# Hablar en tiempo real 🎙️

Asistente de conversación por voz en tiempo real con la Realtime API de OpenAI, con
análisis de emociones y (en desarrollo) control de un rastreador facial mecánico.

**Estado:** v1 completa y respaldada · v2 completa en código, falta validar con voz
real · v3 con rastreador facial + enlace serial completos en código, falta validar
con cámara y hardware real.

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

## 📚 Documentación

- [CLAUDE.md](CLAUDE.md) — contexto técnico completo del proyecto (para trabajar en el código)
- [VERSIONS.md](VERSIONS.md) — hoja de ruta e historial de versiones
- [v1/README-v1.md](v1/README-v1.md) · [v1/CLAUDE-v1.md](v1/CLAUDE-v1.md)
- [v2/README-v2.md](v2/README-v2.md) · [v2/PLAN-v2.md](v2/PLAN-v2.md) · [v2/INSTALL-v2.md](v2/INSTALL-v2.md)
- [v3/README-v3.md](v3/README-v3.md) · [v3/PLAN-v3.md](v3/PLAN-v3.md)
- [docs/RASPBERRY-PI.md](docs/RASPBERRY-PI.md) — especificación para Pi 5, aparcada

## 🔧 Requisitos

- Python 3.9+
- Clave de API de OpenAI con acceso a la Realtime API
- Micrófono y altavoces (v1/v2) — cámara adicional para v3
- v2 instala `pysentimiento` (torch + transformers): ~2GB, varios minutos la primera vez

## 📋 Comparativa de versiones

| | v1 | v2 | v3 |
|---|---|---|---|
| Voz en tiempo real | ✅ | ✅ (hereda de v1) | ✅ (hereda de v2) |
| Cancelación de eco | Navegador (WebRTC) | igual que v1 | igual que v1 |
| Análisis de emociones | — | ✅ `pysentimiento`, en consola | ✅ (hereda de v2) |
| Rastreo facial | — | — | 🔄 código listo, falta cámara real |
| Control de servos (Pico) | — | — | 🔄 código listo, falta hardware real |
| Estado | ✅ Completa | Código completo, validación pendiente | Código completo, validación pendiente |

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
├── v3/                     # + Rastreo facial y servos
│   ├── face_tracker.py     # FaceTracker (headless) + script standalone con ventana
│   ├── pico_serial.py      # PicoLink: cola, reconexión, latido
│   ├── tests/
│   ├── README-v3.md
│   └── PLAN-v3.md
├── docs/
│   └── RASPBERRY-PI.md     # Especificación técnica, aparcada
├── CLAUDE.md               # Contexto técnico completo del proyecto
├── VERSIONS.md             # Hoja de ruta
└── README.md               # Este fichero
```

Cada versión es independiente: su propio venv, requirements y documentación. v1 no
cambia mientras se trabaja en v2 o v3.

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
