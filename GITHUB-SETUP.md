# Publicar en GitHub — Instrucciones

Guía para crear el repositorio en GitHub y respaldar v1.0.0.

## Opción A: Por línea de comandos (CLI de GitHub)

### 1. Instalar gh

```bash
brew install gh
```

### 2. Autenticarse

```bash
gh auth login
# Elige: GitHub.com
# HTTPS preferred
# Y para "Authenticate Git with your GitHub credentials?" elige Y
```

### 3. Crear repositorio

```bash
cd "/Users/debbie/Desktop/programacion/Hablar en tiempo real"
gh repo create hablar-realtime --public --source=. --remote=origin --push
```

Esto crea el repositorio, le añade el remoto `origin`, y hace push de todas las ramas.

### 4. Crear release para v1.0.0

```bash
gh release create v1.0.0 --title "Version 1.0.0" --notes "
Conversación en tiempo real sin autointerrupción.

## Características
- Versión WebRTC con navegador (macOS, cancelación de eco real)
- Versión terminal con WebSocket (paliativos contra eco)
- Barge-in natural: interrumpir hablando
- Documentación completa

## Uso
\`\`\`bash
cd v1
python webrtc_server.py    # WebRTC (recomendado)
# o
python realtime_voice.py   # Terminal
\`\`\`

## Descargar solo v1
\`\`\`bash
git clone --branch v1.0.0 https://github.com/<tu-usuario>/hablar-realtime
\`\`\`

Ver README.md para documentación completa.
"
```

---

## Opción B: Por web (GitHub.com)

### 1. Ir a https://github.com/new

Rellena:
- **Repository name:** `hablar-realtime`
- **Description:** Conversación en tiempo real con OpenAI Realtime API
- **Public** (recomendado)
- **No** inicializar con README (ya tienes uno)

Crea el repositorio.

### 2. Conectar repositorio local

```bash
cd "/Users/debbie/Desktop/programacion/Hablar en tiempo real"
git remote add origin https://github.com/<tu-usuario>/hablar-realtime.git
git branch -M main
git push -u origin main
git push origin --tags   # Sube el tag v1.0.0
```

### 3. Crear release en GitHub

Ve a tu repositorio en GitHub:
- **Releases** (lado derecho)
- **Create a new release**
- **Choose a tag:** v1.0.0
- **Release title:** Version 1.0.0
- **Description:** (copiar de Opción A arriba)
- **Publish release**

---

## Verificar

Después de cualquier opción, verifica:

```bash
# Ver remoto
git remote -v

# Ver que el tag está en GitHub
gh api repos/<tu-usuario>/hablar-realtime/releases/tags/v1.0.0

# O navega a: https://github.com/<tu-usuario>/hablar-realtime/releases
```

---

## Descargar solo v1.0.0

Una vez subido, cualquiera puede clonar solo v1:

```bash
# Opción 1: solo la rama v1.0.0
git clone --branch v1.0.0 https://github.com/<tu-usuario>/hablar-realtime
cd hablar-realtime/v1

# Opción 2: descargar ZIP desde Releases
# https://github.com/<tu-usuario>/hablar-realtime/releases/tag/v1.0.0
# → Download ZIP
```

---

## Estructura visible en GitHub

Después de subir, GitHub mostrará:

```
hablar-realtime/
├── README.md           # Índice con versiones
├── VERSIONS.md         # Hoja de ruta
├── v1/                 # Versión 1 (completa)
│   ├── README-v1.md
│   ├── INSTALL.md
│   ├── webrtc_server.py
│   ├── realtime_voice.py
│   ├── requirements.txt
│   └── static/
├── v2/                 # Versión 2 (en desarrollo)
├── docs/
│   └── RASPBERRY-PI.md
└── .github/            # (opcional futuramente)
    └── workflows/      # CI/CD
```

---

## Próximos pasos

1. ✅ v1.0.0 respaldado en GitHub
2. 🚀 Empieza a trabajar en v2/ sin afectar v1
3. Cuando v2 esté lista: tag v2.0.0, release en GitHub
4. v1 sigue disponible: `git clone --branch v1.0.0`

---

**¿Necesitas ayuda?** Ve a [README.md](README.md) o [VERSIONS.md](VERSIONS.md).
