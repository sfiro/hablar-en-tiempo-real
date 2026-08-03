# Plan de desarrollo — v2.0.0 Análisis de sentimientos

---

## Hito 1: Análisis básico 🔄 (en progreso)

**Objetivo:** Motor de análisis funcional integrado con v1

### Tarea 1.1: Crear `sentiment_analyzer.py`

**Qué:** Módulo independiente que clasifica emociones

```python
from sentiment_analyzer import SentimentAnalyzer

analyzer = SentimentAnalyzer(model="bert-base-multilingual-uncased-sentiment")

result = analyzer.analyze("Me siento increíble hoy")
# Resultado: {
#   "emotion": "joy",
#   "label": "ALEGRÍA",
#   "confidence": 0.94,
#   "emoji": "😊"
# }
```

**Características:**
- [ ] Carga modelo `transformers` lazy (solo cuando se necesita)
- [ ] Soporta múltiples idiomas
- [ ] Retorna: emoción, etiqueta, confianza, emoji
- [ ] Caché de resultados para evitar recomputar

**Modelo seleccionado:** `bert-base-multilingual-uncased-sentiment`  
**Instalación:** agregado a `requirements.txt`

### Tarea 1.2: Integrar en realtime_voice.py

**Qué:** Procesar transcripción en tiempo real

```python
# En receiver(), cuando llega "response.output_audio_transcript.delta"
if args.sentiment:
    emotion = analyzer.analyze(transcript_delta)
    print_emotion(emotion)
```

**Cambios:**
- [ ] Importar `SentimentAnalyzer`
- [ ] Crear instancia si `--sentiment` está activo
- [ ] Analizar cada delta de transcripción (tuyo y del asistente)
- [ ] Mostrar emoción sin bloquear audio

**Criterio:** No debe añadir latencia > 100ms

### Tarea 1.3: Visualización en consola

**Qué:** Formato claro de salida

```
🗣️ Tú: Estoy muy feliz
   📊 ALEGRÍA (0.92)

😊 Asistente: ¡Qué bueno!
   📊 ALEGRÍA (0.88)
```

**Cambios:**
- [ ] Función `print_emotion(emotion_dict)`
- [ ] Mapeo emoji ↔ emoción en `config/emotions.yaml`
- [ ] Formato: `emoji ETIQUETA (confianza)`
- [ ] Colores opcionales (si terminal lo soporta)

---

## Hito 2: Refinamiento 📋 (próximo)

**Objetivo:** Precisión, filtrado y validación

### Tarea 2.1: Filtro de confianza

```bash
python realtime_voice.py --sentiment --confidence-threshold 0.7
# Solo muestra emociones con confianza >= 0.7
```

**Cambios:**
- [ ] Argumento `--confidence-threshold` (por defecto 0.5)
- [ ] Comparar `emotion.confidence >= threshold` antes de mostrar
- [ ] Opción `--show-all` para ver todo sin filtro

**Criterio:** Evitar falsos positivos sin perder información útil

### Tarea 2.2: Manejo de idiomas

**Qué:** Detectar idioma automáticamente

```python
# El modelo ya soporta 100+ idiomas
# Pero si quieres especificar:
python realtime_voice.py --sentiment --language es
```

**Cambios:**
- [ ] Detectar idioma de transcripción (langdetect o similar)
- [ ] Opción `--language` para forzar idioma
- [ ] Mostrar idioma detectado si `--debug`

### Tarea 2.3: Mapeo de emociones

**Qué:** `config/emotions.yaml`

```yaml
joy:
  label: ALEGRÍA
  emoji: 😊
  color: yellow
  synonyms: ["felicidad", "dicha", "contento"]

sadness:
  label: TRISTEZA
  emoji: 😢
  color: blue
  synonyms: ["pena", "depresión", "melancolía"]

# ... 8 emociones principales
```

**Cambios:**
- [ ] Crear archivo YAML con mapeo
- [ ] Cargar en startup
- [ ] Usar para traducción y visualización

### Tarea 2.4: Tests unitarios

**Qué:** `tests/test_sentiment.py`

```python
def test_joy_detection():
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze("I'm so happy!")
    assert result["emotion"] == "joy"
    assert result["confidence"] > 0.8

def test_sadness_detection():
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze("Estoy muy triste")
    assert result["emotion"] == "sadness"
    assert result["confidence"] > 0.7

# ... tests de:
# - Ambigüedad
# - Idiomas múltiples
# - Textos cortos vs largos
# - Confianza
```

**Criterios:**
- [ ] Cobertura >= 80%
- [ ] Tests pasan en macOS y Linux
- [ ] Performance: < 100ms por análisis

---

## Hito 3: Visualización avanzada 📋 (próximo)

**Objetivo:** Estadísticas y análisis más ricos

### Tarea 3.1: Estadísticas de conversación

```bash
python realtime_voice.py --sentiment --stats
```

**Salida al finalizar:**
```
📊 ESTADÍSTICAS
─────────────────────
Emociones tuyas:
  ALEGRÍA: 5 turnos (promedio 0.87)
  CONFIANZA: 2 turnos (promedio 0.79)
  
Emociones del asistente:
  EMPATÍA: 4 turnos (promedio 0.83)
  ALEGRÍA: 3 turnos (promedio 0.90)
  
Tono general: POSITIVO 😊
```

**Cambios:**
- [ ] Clase `ConversationStats` para acumular emociones
- [ ] Método `summarize()` que retorna resumen
- [ ] Mostrar al terminar o con `--export-stats`

### Tarea 3.2: Exportar a JSON

```bash
python realtime_voice.py --sentiment --export-stats stats.json
```

**Formato:**
```json
{
  "start_time": "2026-08-03T15:30:00",
  "end_time": "2026-08-03T15:45:30",
  "duration_seconds": 930,
  "user_emotions": [
    {"timestamp": 5.2, "text": "Hola", "emotion": "joy", "confidence": 0.91},
    {"timestamp": 12.5, "text": "Gracias", "emotion": "gratitude", "confidence": 0.85}
  ],
  "assistant_emotions": [...],
  "summary": { "overall_tone": "positive", ... }
}
```

### Tarea 3.3: Gráficos ASCII (opcional)

```bash
python realtime_voice.py --sentiment --chart
```

Salida:
```
Emociones en el tiempo:
Alegría     ████████░░ 80%
Tristeza    ░░░░░░░░░░  0%
Confianza   █████░░░░░ 50%
Esperanza   ██████░░░░ 60%
```

---

## Hito 4: Documentación 📋 (próximo)

### Tarea 4.1: INSTALL-v2.md

```markdown
# Instalación — v2.0 Análisis de sentimientos

## Requisitos
- Python 3.9+
- GPU opcional (detecta automáticamente si está disponible)

## Instalación rápida
```

### Tarea 4.2: Ejemplos de emociones

Documento: `EMOTIONS.md`

```markdown
# Emociones soportadas

## ALEGRÍA 😊
Ejemplos: "Estoy muy feliz", "Qué genial", "Me encanta"
Confianza típica: 0.85-0.95

## TRISTEZA 😢
Ejemplos: "Estoy triste", "No me siento bien", "Deprimido"
Confianza típica: 0.80-0.92

...
```

### Tarea 4.3: Troubleshooting

`TROUBLESHOOTING.md`

**P: Las emociones no se detectan**  
A: Prueba con `--debug` para ver confianza. Si < 0.5, sube `--confidence-threshold`.

**P: Muy lento, latencia de 2+ segundos**  
A: Usa GPU (`torch` con CUDA). O cambia a modelo más pequeño: `--sentiment-model distilbert`.

---

## Modelos disponibles

### Recomendado: `bert-base-multilingual-uncased-sentiment`
- **Idiomas:** 100+
- **Tamaño:** 600MB
- **Velocidad:** ~200ms por frase
- **Precisión:** ⭐⭐⭐⭐

### Ligero: `distilbert-base-uncased-finetuned-sst-2-english`
- **Idiomas:** Inglés principalmente
- **Tamaño:** 268MB
- **Velocidad:** ~50ms por frase
- **Precisión:** ⭐⭐⭐

### Modelos personalizados
```bash
python realtime_voice.py --sentiment --sentiment-model "ruc/bert-base-spanish-wwm-cased-finetuned-sentiment"
```

---

## Timeline

| Semana | Hito | Estado |
|--------|------|--------|
| 1 | Hito 1: Análisis básico | 🔄 En progreso |
| 2 | Hito 2: Refinamiento | 📋 Próximo |
| 3 | Hito 3: Visualización | 📋 Próximo |
| 4 | Hito 4: Documentación | 📋 Próximo |
| **Semana 5** | **v2.0.0 lanzada** | 🚀 Meta |

---

## Definición de listo

v2.0.0 está **lista para release** cuando:

1. ✅ Detecta emociones en tiempo real sin latencia > 200ms
2. ✅ Soporta 50+ idiomas (vía modelo multilingual)
3. ✅ Funciona igual que v1 si no usas `--sentiment`
4. ✅ Documentación con ejemplos de cada emoción
5. ✅ Tests unitarios con cobertura >= 80%
6. ✅ Validada en macOS con conversaciones reales

---

**Última actualización:** Agosto 3, 2026  
**Estado actual:** Iniciando Hito 1
