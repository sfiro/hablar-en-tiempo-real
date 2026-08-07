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

## v2.0.0 🔄 — Código completo, validación pendiente

**Objetivo cambiado respecto al plan original:** en vez de Raspberry Pi 5, v2 pasó a
ser análisis de emociones en tiempo real. Raspberry Pi 5 se aparcó — la especificación
en [`docs/RASPBERRY-PI.md`](docs/RASPBERRY-PI.md) sigue siendo válida, pero no es el
objetivo actual de v2. Se retomará como una versión futura si hace falta.

**Corrección importante durante el desarrollo:** el primer modelo elegido
(`bert-base-multilingual-uncased-sentiment`) en realidad da estrellas de opinión de
producto (1-5), no una emoción. Se sustituyó por `pysentimiento`, verificado antes de
escribir la versión final: clasifica de verdad las 6 emociones de Ekman + neutral.

**Hito 1: Análisis básico (COMPLETADO Y VERIFICADO)**
- ✅ `sentiment_analyzer.py` con `pysentimiento` (RoBERTuito para español)
- ✅ Integración en `realtime_voice.py` sin bloquear el audio (`run_in_executor`)
- ✅ Visualización en consola: emoji + etiqueta + confianza
- ✅ `--stats`: resumen de emociones al terminar la conversación
- ✅ Dos bugs reales encontrados y corregidos en ejecución real (ver CLAUDE.md)

**Hito 2: Validación y refinamiento (COMPLETADO salvo un punto)**
- ✅ Tests de integración con el modelo real: las 6 emociones de Ekman, todos pasan
- ✅ Umbral de confianza documentado con datos reales (no supuestos)
- [ ] **Conversación real hablada** — la única tarea que falta en todo v2, y depende
  de que alguien hable de verdad con `--sentiment` (no se puede automatizar)

**Descarga:** aún sin tag propio; código en `v2/` sobre `main`.

**Uso:**
```bash
cd v2
python realtime_voice.py --sentiment --stats
```

---

## v3.0.0 📋 — Rastreo facial y servos (planificación)

**Objetivo:** Mostrar la posición x,y del rostro en consola junto al sentimiento, y
opcionalmente enviarla —junto con la emoción, traducida a su vocabulario— por serial a
una Raspberry Pi Pico que mueve servos.

**Hito 0: Investigación (COMPLETADO)**
- ✅ Investigado un proyecto hermano (`ojosMecanicos`) antes de escribir código
- ✅ Confirmado que no existe ahí una integración funcional voz+emoción+cámara+servos
- ✅ Identificado y documentado un bug de diseño real en su intento de puente (hilos
  arrancados, pero la emoción nunca conectada al movimiento — código muerto)
- ✅ Protocolo serial de la Pico confirmado y reutilizable (formato, baud, latido,
  reconexión)
- ✅ Tabla de mapeo emoción→vocabulario de la Pico definida

**Hito 1: Rastreo facial standalone (SIGUIENTE)**
- [ ] Adaptar el rastreador de rostro (OpenCV) a `v3/face_tracker.py`
- [ ] Módulo de serial hacia la Pico (`v3/pico_serial.py`), con reconexión y latido

**Hito 2: Integración con voz + sentimiento**
- [ ] Hilo de cámara + hilo de Pico arrancados desde `realtime_voice.py`
- [ ] x,y visible en consola junto al sentimiento
- [ ] Sentimiento cableado de verdad al comando serial, con test que lo confirme —
  la lección aprendida de `ojosMecanicos`

**Hito 3: Validación con hardware real** (cámara, y si está disponible, la Pico)

**Hito 4: Documentación**

Detalle completo: [`v3/PLAN-v3.md`](v3/PLAN-v3.md).

**Estimado:** sin fecha todavía, depende de completar la validación de v2 primero.

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

| Versión | Estado | Plataforma |
|---------|--------|-----------|
| v1.0.0  | ✅ Completa | macOS, Linux |
| v2.0.0  | 🔄 Código completo, falta validar con voz real | macOS |
| v3.0.0  | 📋 Planificación (Hito 0 completo, sin código) | macOS + Raspberry Pi Pico (opcional) |

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
