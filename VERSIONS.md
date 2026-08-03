# Hoja de ruta de versiones

Documento de planificación y seguimiento de releases.

---

## v1.0.0 ✅ — Completado (Agosto 2026)

**Objetivo:** Demostrar conversación en tiempo real sin autointerrupción en macOS.

**Completado:**
- ✅ Versión WebRTC con cancelación de eco del navegador
- ✅ Versión terminal con paliativos contra eco (half-duplex, MicGate, BargeInDetector)
- ✅ Cancelación de eco real probada y funcionando
- ✅ Barge-in natural: interrumpir al asistente hablando
- ✅ Documentación completa: README, CLAUDE.md, especificación Raspberry Pi
- ✅ Repositorio local con versionado git

**Descarga:**
- Rama: `main` (último tag: `v1.0.0`)
- ZIP: GitHub Releases → v1.0.0

**Uso:**
```bash
cd v1
python webrtc_server.py      # Recomendado
# o
python realtime_voice.py     # Terminal
```

---

## v2.0.0 🚀 — En desarrollo

**Objetivo:** Implementar en Raspberry Pi 5 con AEC por sistema operativo.

**Hito 1: Especificación (COMPLETADO)**
- ✅ Analizar arquitectura de audio en Pi OS Trixie
- ✅ Documentar configuración de PipeWire con `module-echo-cancel`
- ✅ Definir estructura de carpetas y pasos de instalación
- ✅ Documento: [`docs/RASPBERRY-PI.md`](docs/RASPBERRY-PI.md)

**Hito 2: Implementación (PRÓXIMO)**
- [ ] Configurar PipeWire en Pi 5 (pasos 4.1-4.3 de RASPBERRY-PI.md)
- [ ] Adaptar `realtime_voice.py` con parámetros `--input-device` / `--output-device`
- [ ] Probar AEC con grabación
- [ ] Desactivar paliativos de v1 (`--no-half-duplex`)
- [ ] Crear servicio systemd para arranque automático

**Hito 3: Validación**
- [ ] Pruebas de conversación: sin autointerrupción, barge-in funcional
- [ ] Pruebas de estabilidad: 1h de conversación
- [ ] Consumo de CPU/RAM en reposo
- [ ] Reconexión automática tras caída de red

**Hito 4: Documentación**
- [ ] README v2 con instrucciones paso a paso
- [ ] Guía de troubleshooting (PipeWire, clock drift, distorsión)
- [ ] Script de instalación automática

**Estimado:** Setembro 2026 (sujeto a revisión)

**Rama de desarrollo:** `main` (cambios en carpeta `v2/`)

---

## v3.0.0 📋 — Planeado

**Objetivo:** Mejoras de experiencia y características avanzadas.

**Candidatas:**
- **Wake word detection:** "Hey Claude", "Hablar" → arrancar conversación
- **Multi-sesión:** varios usuarios/conversaciones simultáneas
- **Integración HA:** Home Assistant, Node-RED
- **UI opcional:** dashboard web para configuración remota
- **AEC macOS:** PyObjC + `AVAudioEngine` (Voice Processing I/O)

**Estimado:** Q4 2026 / Q1 2027

---

## Política de versiones

### Ramas y tags

- **`main`:** código de producción, último release estable
  - Tags: `v1.0.0`, `v2.0.0`, etc.
- **`develop`:** rama de integración (futura, si se expande)
- **Ramas de feature:** `feature/v2-pipewire`, `feature/wake-word`, etc.

### Descarga de versiones específicas

```bash
# Clonar solo v1
git clone --branch v1.0.0 <repo> hablar-v1

# Descargar ZIP (GitHub Releases)
# → hablar-realtime-v1.0.0.zip

# Actualizar a v2 cuando esté lista
git clone <repo>  # clona main con v2
cd main
cd v2             # entra en v2
```

### Compatibilidad

- **Cada versión es independiente:** su venv, requirements.txt, docs.
- **v1 seguirá siendo estable:** no se toca una vez que v2.0.0 se lance.
- **No hay dependencias cruzadas:** puedes usar v1 y dejar v2 en desarrollo.

### Soporte

- **v1:** En mantenimiento. Bugs críticos arreglados. Cambios menores si es necesario.
- **v2:** En desarrollo activo.
- **v3+:** Planeado, sujeto a cambios.

---

## Calendario

| Versión | Estado | Fecha | Plataforma |
|---------|--------|-------|-----------|
| v1.0.0  | ✅ Completa | Ago 2026 | macOS, Linux |
| v2.0.0  | 🚀 En desarrollo | Sep 2026 | Raspberry Pi 5 |
| v3.0.0  | 📋 Planeado | Q4 2026 | TBD |

---

## Cómo contribuir

Cada versión vive en su carpeta. Si quieres trabajar en v2 mientras otros usan v1:

1. Crea una rama: `git checkout -b feature/v2-xxx`
2. Trabaja en `v2/` sin tocar `v1/`
3. Cuando esté listo, merge a `main`
4. Tag: `git tag v2.0.0`
5. Actualiza este fichero

---

**Última actualización:** Agosto 3, 2026
