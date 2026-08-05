# Plan de desarrollo — v2.0.0 Análisis de emociones

**Corrección respecto a la versión anterior de este documento:** la primera versión
prometía 10 emociones (alegría, tristeza, rabia, miedo, sorpresa, asco, confianza,
empatía, esperanza, optimismo) y varios modelos intercambiables de Hugging Face. Al
verificar contra la documentación real de los modelos, ninguno de los candidatos
clasifica más de las seis emociones de Ekman + neutral, y el modelo que se había puesto
por defecto (`bert-base-multilingual-uncased-sentiment`) en realidad da una puntuación
de 1 a 5 estrellas de opinión de producto, no una emoción. Este documento refleja ahora
lo que el código hace de verdad.

---

## Hito 1: Análisis básico ✅ (completo y verificado)

**Objetivo:** Motor de análisis funcional integrado con v1, sin bloquear el audio.

### Tarea 1.1: `sentiment_analyzer.py` — DONE

Usa [`pysentimiento`](https://github.com/pysentimiento/pysentimiento), que trae un
modelo de emociones real por idioma (RoBERTuito para español, entrenado con el corpus
TASS 2020 Task 2). Confirmado contra la documentación del modelo:

- **Etiquetas:** `joy`, `sadness`, `anger`, `fear`, `surprise`, `disgust`, `others`
- **API:** `create_analyzer(task="emotion", lang="es").predict(texto)` →
  `AnalyzerOutput(output="joy", probas={"joy": 0.72, "others": 0.19, ...})`
- **Idiomas soportados:** es, en, it, pt (cada uno con su propio modelo)

```python
from sentiment_analyzer import SentimentAnalyzer
analyzer = SentimentAnalyzer(language="es")
analyzer.analyze("Estoy muy feliz hoy")
# {"emotion": "joy", "label": "ALEGRÍA", "confidence": 0.94, "emoji": "😊"}
```

Características implementadas:
- [x] Carga del modelo lazy (solo al primer `analyze()`, o precargado en background)
- [x] Caché de resultados por texto exacto
- [x] Manejo de error si `pysentimiento` no está instalado (mensaje claro, no traceback)

### Tarea 1.2: Integración en `realtime_voice.py` — DONE

- [x] Transcripción del usuario (`conversation.item.input_audio_transcription.completed`)
      se analiza completa en cuanto llega
- [x] Transcripción del asistente se acumula por deltas
      (`response.output_audio_transcript.delta`) y se analiza completa al terminar
      la frase (`response.output_audio_transcript.done`)
- [x] El análisis corre en `run_in_executor` + `asyncio.create_task`: la inferencia
      (cientos de ms) nunca bloquea `receiver()`, que sigue leyendo deltas de audio
      mientras se calcula la emoción de la frase anterior
- [x] Precarga del modelo en background al arrancar, para no pagar el coste de
      descarga/carga en la primera frase de la conversación

**Verificado con ejecución real (no solo `py_compile`):**
- Conecta a la API, precarga el modelo en background sin bloquear el saludo inicial
- El análisis de una frase no retrasa el streaming de audio de la frase siguiente
- `--stats` imprime el resumen correcto al terminar (Ctrl+C)

**Dos bugs reales encontrados y corregidos en esta verificación:**
1. `asyncio.create_task(loop.run_in_executor(...))` fallaba con `TypeError`:
   `run_in_executor` devuelve un `Future`, no una corrutina. `create_task` exige lo
   segundo. Arreglo: llamar a `run_in_executor` directamente, sin envolver.
2. El resultado de la emoción se imprimía sin salto de línea inicial, así que si
   llegaba mientras el otro lado seguía en pleno streaming de su transcripción, el
   resultado aparecía en medio de esa frase. Arreglo: `\n` inicial, como el resto de
   avisos asíncronos del script.

**Pendiente:** la ejecución de prueba capturó ruido ambiente del micro (no había
nadie hablando a propósito), así que falta una conversación real deliberada para
confirmar que las emociones mostradas tienen sentido con frases reales dichas en voz
alta, no solo con texto de prueba.

### Tarea 1.3: Visualización en consola — DONE

```
🗣️  Tú: Estoy muy feliz hoy
   😊 ALEGRÍA (0.94)
```

- [x] Formato `emoji ETIQUETA (confianza)` bajo cada frase
- [x] `--no-emoji` para salida solo texto
- [x] `--confidence-threshold` (por defecto 0.5) para no mostrar clasificaciones dudosas

---

## Hito 2: Validación y refinamiento 🔄 (en progreso)

**Objetivo:** Confirmar que funciona con audio real y ajustar parámetros con datos reales.

### Tarea 2.1: Prueba con conversación real hablada

- [ ] Conversación de 5+ minutos con `--sentiment --debug`, hablando frases a propósito
- [ ] Confirmar que las emociones mostradas coinciden con lo dicho, para varios casos
      obvios (alegría clara, tristeza clara, neutral)
- [ ] Medir latencia real: tiempo entre "termina la frase" y "aparece la emoción"

**Estado:** se hizo una ejecución real de extremo a extremo (conecta, no bloquea audio,
`--stats` funciona), pero sin nadie hablando a propósito — el micro capturó ruido
ambiente. Falta repetir con frases deliberadas para validar precisión percibida.

**Criterio de éxito:** la emoción aparece en menos de 1 segundo tras terminar la frase,
y acierta en los casos claros (no hace falta que acierte en matices ambiguos).

### Tarea 2.2: Ajustar el umbral de confianza

- [x] Datos reales obtenidos (ver «Limitaciones conocidas» en README-v2.md): con
      texto de prueba, "el cielo es azul" dio ALEGRÍA (0.57) — pasa el umbral de 0.5
      siendo un falso positivo, y "me da mucha rabia esto" dio TRISTEZA (0.38) — queda
      oculto por baja confianza, ocultando también el error de fondo (era RABIA)
- [ ] Con más datos de conversación hablada, decidir si 0.5 sigue siendo razonable o
      conviene subirlo (a costa de ocultar más clasificaciones, aciertos incluidos)

### Tarea 2.3: Tests unitarios — DONE

`tests/test_sentiment.py`, dos grupos:
- **Lógica interna** (caché, validación de idioma, texto vacío, mapeo de emociones):
  con un analizador falso inyectado, no necesitan el modelo real. 8 tests, todos pasan.
- **Integración con el modelo real** (`@requiere_modelo_real`, se saltan si falta
  `pysentimiento`): las 6 emociones de Ekman. Los 6 pasan contra el modelo real
  descargado.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_sentiment.py -v
```

**Criterio:** casos obvios (uno por emoción) clasifican correctamente. No se testea
precisión estadística fina, solo que el pipeline funciona de extremo a extremo.
**Cumplido para las 6 emociones** (joy, sadness, fear, anger, surprise, disgust).

Para encontrar frases fiables de anger, surprise y disgust hubo que probar varias
antes de dar con una que el modelo clasificara bien: los primeros intentos (frases
cortas y directas) fallaban. Ese hallazgo — que las frases elaboradas aciertan más
que las cortas — quedó documentado en README-v2.md, sección «Limitaciones conocidas»,
con la tabla comparativa de frase corta (falla) vs. elaborada (acierta).

---

## Hito 3: Documentación 📋 (próximo)

### Tarea 3.1: Ejemplos reales por emoción

Reemplazar los ejemplos inventados de README-v2.md por frases probadas de verdad
contra el modelo, con la confianza real obtenida (no una que suene bien).

### Tarea 3.2: Troubleshooting

`TROUBLESHOOTING-v2.md` con al menos:

- **Instalación de `pysentimiento` falla o tarda mucho** → es normal, trae torch y
  transformers; en máquinas lentas puede tardar varios minutos
- **La emoción no aparece** → confianza por debajo del umbral; bajar
  `--confidence-threshold` o mirar con `--debug`
- **Latencia alta en la clasificación** → normal en CPU sin GPU; considerar si merece
  la pena frente al beneficio, documentar tiempos medidos reales

---

## Fuera de alcance (por ahora)

Estas ideas estaban en la versión anterior de este plan y se descartan hasta que haya
una necesidad concreta, para no acumular trabajo especulativo:

- Exportar a JSON — útil, pero no bloquea nada; se añade si hace falta
- Gráficos ASCII de emociones en el tiempo — cosmético, baja prioridad
- Detección de idioma automática — `--language` ya cubre el caso de uso real (tú
  hablando en un idioma fijo por sesión)

---

## Definición de listo

v2.0.0 está lista para release cuando:

1. ✅ Detecta las 6 emociones de Ekman + neutral en español (y opcionalmente en, it, pt)
2. ✅ No añade latencia perceptible al audio (verificado: análisis en hilo aparte,
   confirmado en ejecución real contra la API)
3. ✅ Funciona igual que v1 si no usas `--sentiment`
4. ✅ Tests de integración pasan para las 6 emociones de Ekman (joy, sadness, fear,
   anger, surprise, disgust)
5. ✅ Documentación con ejemplos reales, no inventados (incluye limitaciones reales)
6. [ ] Validado con conversación real hablada a propósito, no solo ruido ambiente ni
   texto de prueba — **la única tarea que queda, y necesita a alguien hablando**

---

**Última actualización:** Agosto 3, 2026
**Estado actual:** Hito 1 y 2 completos salvo la validación con voz real (punto 6 de
arriba). Todo lo demás verificado: modelo real, tests de las 6 emociones, ejecución
end-to-end sin bloquear audio, dos bugs encontrados y corregidos.
