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

**Hito 1: Rastreo facial standalone (COMPLETADO en código, falta hardware real)**
- ✅ `v3/face_tracker.py`: clase `FaceTracker` headless + script standalone con
  ventana opcional (`--no-window`)
- ✅ `v3/pico_serial.py`: `PicoLink` con reconexión y latido
- ✅ 19 tests (`v3/tests/`), todos pasan, sin necesitar cámara ni Pico reales
- ✅ Dos bugs reales corregidos: `opencv-python` 5.0 eliminó `CascadeClassifier`
  (fijado `<5`); el chequeo de reconexión rompía con puertos de prueba inyectados
  (aislado para hardware real únicamente)
- [ ] Validar con cámara real — bloqueado por permisos de macOS en este entorno,
  necesita que el usuario lo pruebe en su propia Terminal
- [ ] Validar con la Pico física, si está disponible

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

## v4.0.0 ✅ — Rastreo facial + servos, simplificado y autónomo (completa y validada)

**Objetivo:** antes de retomar v3, organizar el firmware de la Pico con lo mínimo
imprescindible: ojos abiertos + rastreo x,y, sin la complejidad de emociones,
joystick, modo autónomo y parpadeo del `main.py` completo de `ojosMecanicos`.

**Autónoma, no solo el firmware.** Tiene su propia copia de `face_tracker.py` y
`pico_serial.py` (idénticas a las de v3, no importadas desde ahí), con su propio
`.venv/` y `requirements.txt` — más ligero que el de v3, porque v4 no toca voz ni
sentimiento. Solo `v4/main.py` (el firmware) rompe el patrón de venv, porque corre
dentro de la Pico, no en el Mac. Se despliega con Thonny o `mpremote`, no con pip.

**Hito 1: `main.py` mínimo (COMPLETADO Y VALIDADO EN HARDWARE REAL)**
- ✅ `v4/main.py`: solo párpados abiertos al arrancar + rastreo x,y con suavizado EMA
- ✅ Protocolo compatible con v3 sin cambios (el `pico_serial.py` propio de v4
  funciona tal cual)
- ✅ Verificado sin hardware: sintaxis, fórmula de pulso PCA9685 (0°→102, 90°→307,
  180°→512), parseo de comandos con casos límite y basura
- ✅ **Validado en la Pico real por el usuario:** el rastreo funciona, los ojos
  siguen la cara "perfectamente"

**Hito 1.5: Autonomía completa (COMPLETADO)**
- ✅ `face_tracker.py` y `pico_serial.py` copiados a `v4/` (no importados desde v3)
- ✅ `v4/requirements.txt` propio, `v4/.venv` propio
- ✅ 19 tests duplicados en `v4/tests/`, corridos dentro de `v4/.venv` sin ninguna
  referencia a `v3/` — confirmado que pasan de forma completamente aislada

**Hito 2: Validación con hardware — COMPLETADO**

**Hito 3: Reintroducir complejidad por partes — en progreso, ver v5.0.0 abajo**

Detalle completo: [`v4/PLAN-v4.md`](v4/PLAN-v4.md).

---

## v5.0.0 ✅ — + Cuello y parpadeo (completa y validada en hardware real)

**Objetivo:** siguiendo el Hito 3 de v4, reintroducir parpadeo y movimiento de
cuello (sin emociones todavía) mientras el rastreo de ojos sigue funcionando igual.

**Autónoma, igual que v4:** copia propia de `face_tracker.py` y `pico_serial.py`
(sin cambios respecto a v4), `.venv` propio, 25 tests propios.

**Cambio de arquitectura no anticipado:** el firmware empezó usando el mismo
controlador PCA9685 (I2C) de `ojosMecanicos`, pero en hardware real dio tres
problemas — temblor de servos al encender, temblor periódico al parpadear, y el
eje PAN sin moverse — que, tras una depuración larga (arreglo de `/OE`, ajustes de
temporización, instrumentación de diagnóstico), resultaron tener el mismo origen:
el PCA9685 o la comunicación I2C con él. Se abandonó el PCA9685 por completo,
generando el PWM directamente desde los pines de la Pico, y los tres problemas
desaparecieron a la vez. Cronología completa, con cada intento y cada error, en
[`v5/README-v5.md`](v5/README-v5.md#historial-de-depuración-completo).

**Hito 1: Autonomía completa — COMPLETADO**
- ✅ Copiado todo lo del lado Mac desde `v4/`, sin cambios de lógica

**Hito 2: Cuello — PAN/TILT — COMPLETADO**
- ✅ El cuello sigue a los ojos, amortiguado (80% horizontal, 60% vertical — mismos
  factores que `ojosMecanicos/main.py`), con el mismo suavizado EMA que los ojos

**Hito 3: Parpadeo periódico — COMPLETADO**
- ✅ Cada 2-6 segundos, independiente de si hay rastreo activo

**Hito 4: Validación con hardware — COMPLETADO**
- ✅ Confirmado por el usuario: "todos los motores se mueven y parpadea sin
  vibraciones", incluyendo PAN, que nunca se había movido con el PCA9685
- [ ] Sesión larga sin problemas — no verificado, no bloqueante

Detalle completo: [`v5/PLAN-v5.md`](v5/PLAN-v5.md).

---

## v6.0.0 ✅ — Estado base + secuencia de expresiones (completa y validada en hardware real)

**Objetivo:** dos cosas. Un programa dedicado (`estado_base.py`) que lleve los 8
servos a 90° y los mantenga ahí — posición segura antes de desconectar la
alimentación, o para recuperar un estado neutral tras un error. Y en `main.py`,
el primer paso de expresiones faciales: cambian solas cada 5 segundos, en un
orden fijo, sin depender de voz ni sentimiento todavía.

**Trae toda la base funcional de v5, salvo `main.py`, sin cambios:**
`face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`. `main_pca9685.py`
(la versión retirada) no se copió — no es "base funcional".

**Hito 1: Base funcional de v5 traída completa — COMPLETADO**
- ✅ Copiado todo desde `v5/`, sin cambios de lógica

**Hito 2: `estado_base.py` — COMPLETADO, validado en hardware real**
- ✅ Centra los 8 servos con el mismo espaciado de 0.1s que usa `main.py` al
  arrancar (protección contra picos de corriente)
- ✅ Misma fórmula de PWM y mismo mapeo de pines que `main.py` — verificado con
  un test que compara ambos directamente
- ✅ Validado en la Pico real por el usuario

**Hito 3: Secuencia de expresiones faciales — COMPLETADO en código**
- ✅ Los 10 offsets de párpados/cuello de `ojosMecanicos/main.py`, copiados
  literalmente y verificados contra el original antes de usarlos
- ✅ Temporizador fijo de 5s, cicla en orden, envuelve al final
- ✅ Párpados incorporados al suavizado EMA; el parpadeo respeta la expresión
  activa (no parpadea en DORMIDO, reabre a la posición de la expresión actual)
- ✅ **Hallazgo real, confirmado con test:** SORPRENDIDO no se distinguía de
  NEUTRAL en v6 — su offset empujaba hacia un extremo en el que los párpados ya
  estaban (sin sincronía párpado-mirada, no había margen para que se note).
  **Resuelto en el Hito 4** bajando el reposo, en vez de añadir esa sincronía.
- ✅ Validado en la Pico real (rastreo + cuello + parpadeo) por el usuario

**Hito 4: Ajustes de realismo, tras probar en hardware — COMPLETADO Y VALIDADO EN HARDWARE REAL**
- ✅ `PARPADOS_REPOSO`: nueva posición de reposo al 40% de cierre (no el 100%
  abierto) — resuelve de raíz el hallazgo de SORPRENDIDO del Hito 3
- ✅ SORPRENDIDO ahora se aplica sin clamping en los 4 canales (confirmado con
  test); DORMIDO, como efecto colateral esperado, ahora cierra los 4 canales
  por completo
- ✅ FELIZ y SOSPECHA recalculados para notarse sobre el nuevo reposo (los
  offsets originales de `ojosMecanicos`, pensados para 100% abierto, casi no
  se notaban)
- ✅ TRISTE fuerza la cabeza (`TILT`) a su mínimo mecánico en vez de un offset
  relativo — pedido explícito, para que la cabeza gacha se note siempre igual
- ✅ DUDA, PENSATIVO y NERVIOSO ahora ignoran el rastreo facial y fijan o
  mueven la mirada por su cuenta mientras duran (barrido lateral 40↔140 en
  DUDA; mirada fija arriba-izquierda en PENSATIVO; saltos al azar cada 1s en
  NERVIOSO) — el cuello acompaña los tres gestos
- ✅ Corregido un bug real: al salir de DUDA/PENSATIVO/NERVIOSO, la mirada
  ahora vuelve al centro antes de la siguiente expresión, en vez de heredar
  la posición desviada
- ✅ **Validado en la Pico real por el usuario:** "todo ha funcionado bien" —
  incluida la interacción entre parpadeo, cambio de expresión y los overrides
  de mirada, sin problema observado

49 tests en total. Detalle completo: [`v6/PLAN-v6.md`](v6/PLAN-v6.md).

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
| v3.0.0  | 🔄 Código completo (Hito 0 y 1), falta cámara/Pico reales | macOS + Raspberry Pi Pico (opcional) |
| v4.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) |
| v5.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) |
| v6.0.0  | ✅ Completa y validada en hardware real | Raspberry Pi Pico (MicroPython) |

---

## Cómo contribuir

Cada versión vive en su carpeta. Si quieres trabajar en v2 mientras otros usan v1:

1. Crea una rama: `git checkout -b feature/v2-xxx`
2. Trabaja en `v2/` sin tocar `v1/`
3. Cuando esté listo, merge a `main`
4. Tag: `git tag v2.0.0`
5. Actualiza este fichero

---

**Última actualización:** Agosto 8, 2026
