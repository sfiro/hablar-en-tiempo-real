# Hablar en tiempo real 🎙️

Asistente de conversación por voz en tiempo real con la Realtime API de OpenAI.

**Estado:** Versión 1 completada y respaldada. Desarrollo de versión 2 en progreso.

## 📦 Versiones disponibles

Cada versión está en su propia carpeta con código, entorno y documentación independientes.

### [v1](v1/) — Versión 1.0 ✅ 
**Estado:** Completa y respaldada. Lanzamiento inicial.

Características:
- ✅ Conversación WebRTC en navegador (macOS)
- ✅ Versión terminal con paliativos contra eco
- ✅ Especificación para Raspberry Pi 5

**Instalar v1:**
```bash
cd v1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Edita con tu clave de OpenAI
python webrtc_server.py       # o python realtime_voice.py
```

Ver [`v1/README-v1.md`](v1/README-v1.md) para documentación completa.

### [v2](v2/) — Versión 2 🚀
**Estado:** En desarrollo.

Objetivos:
- Implementación completa en Raspberry Pi 5
- PipeWire con AEC por hardware
- Servicio systemd para arranque automático
- Mejoras de performance y estabilidad

**Próximamente:** Código y documentación en `v2/`.

## 📚 Documentación

- [v1/README-v1.md](v1/README-v1.md) — Guía completa de v1
- [v1/CLAUDE-v1.md](v1/CLAUDE-v1.md) — Detalles técnicos de v1
- [docs/RASPBERRY-PI.md](docs/RASPBERRY-PI.md) — Especificación técnica para Pi 5
- [VERSIONS.md](VERSIONS.md) — Hoja de ruta de versiones

## 🚀 Inicio rápido

**Quiero usar v1 ahora:**
```bash
cd v1
source .venv/bin/activate
python webrtc_server.py  # WebRTC con navegador (recomendado)
# o
python realtime_voice.py # Terminal con WebSocket
```

**Quiero descargar solo v1:**
```bash
git clone --branch v1.0.0 <repo-url> hablar-realtime-v1
# o descargar ZIP desde releases en GitHub
```

**Quiero esperar a v2 (Raspberry Pi):**
Mira [VERSIONS.md](VERSIONS.md) para el cronograma.

## 🔧 Requisitos

- Python 3.9+
- Clave de API de OpenAI con acceso a la Realtime API
- Micrófono y altavoces (o auriculares para v1 terminal)
- Git (opcional, para clonar)

## 📋 Comparativa de versiones

| Característica | v1 | v2 |
|---|---|---|
| Plataforma | macOS, Linux | **Raspberry Pi 5** |
| AEC | Navegador (WebRTC) | PipeWire del sistema |
| Tipo | WebRTC + Terminal | Terminal headless |
| Barge-in | ✅ natural | ✅ con AEC real |
| Autoarranque | Manual | systemd service |
| Estado | ✅ Completa | 🚀 En desarrollo |

## 🔗 GitHub

Repositorio: (ver instrucciones abajo para crear)

Descargar versión específica:
- v1.0.0: `git clone --branch v1.0.0`
- ZIP: GitHub → Releases → v1.0.0

## 📖 Estructura del proyecto

```
.
├── v1/                           # Versión 1.0 (completa)
│   ├── realtime_voice.py        # Cliente WebSocket
│   ├── webrtc_server.py         # Servidor SDP
│   ├── requirements.txt
│   ├── .env.example
│   ├── static/
│   ├── README-v1.md
│   └── CLAUDE-v1.md
├── v2/                           # Versión 2 (en desarrollo)
│   └── README-v2.md  (próximamente)
├── docs/
│   └── RASPBERRY-PI.md          # Especificación técnica
├── VERSIONS.md                   # Hoja de ruta
└── README.md                     # Este fichero
```

Cada versión es **independiente**: su propio venv, documentación y código. Puedes trabajar en v2 mientras v1 sigue siendo estable y respaldada.

## ❓ FAQ

**P: ¿Puedo usar v1 mientras trabajas en v2?**
R: Sí. v1 es estable y completa. v2 está en desarrollo paralelo.

**P: ¿Cómo bajo solo v1 sin todo el proyecto?**
R: `git clone --branch v1.0.0` (clona solo esa rama), o descarga el ZIP desde Releases en GitHub.

**P: ¿Qué cambios trae v2?**
R: Implementación en Raspberry Pi 5 con PipeWire AEC. Ver [VERSIONS.md](VERSIONS.md).

**P: ¿Se pierden cambios de v1 cuando paso a v2?**
R: No. Cada versión está en su carpeta. v1 no cambia.

---

**Última actualización:** Agosto 2026 — v1.0.0 lanzada
