# Versión 2.0 — Análisis de sentimientos en tiempo real 🎭

Extensión de v1 que analiza las emociones de la conversación en tiempo real y las muestra en la consola.

**Estado:** En desarrollo  
**Objetivo:** Detectar y mostrar sentimientos mientras conversas  
**Plataforma:** macOS (igual que v1)  
**Base:** v1 + modelo de clasificación de emociones

---

## ¿Qué es v2?

Mientras hablas con el asistente, la consola muestra las emociones detectadas:

```
🗣️ Tú: Estoy muy triste, perdí mi trabajo hoy
   → Sentimiento: TRISTEZA (0.92)

😊 Asistente: Lamento escuchar eso. Quiero ayudarte...
   → Sentimiento: EMPATÍA (0.85)

🗣️ Tú: Pero creo que es una oportunidad para empezar algo nuevo
   → Sentimiento: ESPERANZA (0.78)

😊 Asistente: Exacto, a veces los cambios traen...
   → Sentimiento: OPTIMISMO (0.82)
```

**Emociones detectadas:**
- Alegría 😊
- Tristeza 😢
- Rabia 😠
- Miedo 😨
- Sorpresa 😲
- Asco 🤢
- Confianza 💪
- Empatía ❤️
- Esperanza 🌟
- Optimismo ✨

---

## Cómo funciona

1. **Captura de texto:** cada frase que se transcribe (tuya y del asistente)
2. **Análisis:** modelo local `transformers` clasifica la emoción
3. **Visualización:** se muestra en consola con emoji y confianza (0-1)
4. **Estadísticas:** opcional, resumen de emociones al final

---

## Arquitectura

```
v2/
├── README-v2.md                    ← Este fichero
├── INSTALL-v2.md                   ← Instalación rápida
├── PLAN-v2.md                      ← Hitos y estado
│
├── realtime_voice.py               ← Script principal (adaptado de v1)
├── sentiment_analyzer.py           ← Motor de análisis de sentimientos
├── requirements.txt                ← (v1 + transformers + torch)
│
├── config/
│   └── emotions.yaml               ← Mapeo de emociones a emojis
│
├── tests/
│   └── test_sentiment.py           ← Tests del analizador
│
└── examples/
    └── demo_sentiment.txt          ← Ejemplo de salida
```

---

## Instalación rápida

Ver [INSTALL-v2.md](INSTALL-v2.md) para detalles completos.

```bash
cd v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # Pon tu clave de OpenAI
python realtime_voice.py --sentiment   # Con análisis de sentimientos
```

---

## Ejemplos de uso

### Básico

```bash
python realtime_voice.py --sentiment
```

Salida:
```
🎙️  Listo. Habla con naturalidad; haz una pausa y el modelo responderá.
    Análisis de sentimientos: ACTIVO
    (Ctrl+C para salir)

🗣️  Tú: Me siento increíble hoy, todo sale bien
   📊 ALEGRÍA (0.94) | confianza: muy alta

😊 Asistente: ¡Qué genial escuchar eso! Cuando todo fluye...
   📊 ALEGRÍA (0.91) | confianza: muy alta
```

### Con estadísticas

```bash
python realtime_voice.py --sentiment --stats
```

Al final de la conversación:
```
📊 ESTADÍSTICAS DE CONVERSACIÓN
─────────────────────────────────
Tú:
  Alegría: 3 (promedio: 0.87)
  Esperanza: 2 (promedio: 0.75)
  Confianza: 1 (promedio: 0.88)

Asistente:
  Empatía: 2 (promedio: 0.83)
  Alegría: 2 (promedio: 0.89)
  Optimismo: 1 (promedio: 0.80)

Tono general: POSITIVO 😊
```

### Sin sentimientos (como v1)

```bash
python realtime_voice.py              # Sin --sentiment, igual que v1
```

---

## Opciones de línea de comandos

```bash
python realtime_voice.py [opciones]

Opciones de v1:
  --voice VOICE              Voz del asistente (marin, cedar, etc.)
  --no-half-duplex           Con auriculares, permite barge-in
  --noise-reduction MODE     far_field (por defecto) o near_field

Opciones nuevas (v2):
  --sentiment                Activa análisis de sentimientos
  --sentiment-model MODEL    Modelo a usar (ver PLAN-v2.md)
  --stats                    Muestra estadísticas al final
  --no-emoji                 Sin emojis en salida (solo texto)
  --confidence-threshold T   Mostrar solo emociones > T (0-1, por defecto 0.5)
```

---

## Desarrollo

Seguimiento en [PLAN-v2.md](PLAN-v2.md).

### Hitos

**Hito 1: Análisis básico** 🔄 (en progreso)
- [ ] Crear módulo `sentiment_analyzer.py`
- [ ] Integrar modelo `transformers`
- [ ] Mostrar emociones en consola

**Hito 2: Refinamiento** 📋 (próximo)
- [ ] Filtrar emociones por confianza
- [ ] Mapeo emoji ↔ emoción
- [ ] Tests unitarios

**Hito 3: Visualización** 📋 (próximo)
- [ ] Estadísticas resumidas
- [ ] Gráficos ASCII opcionales
- [ ] Exportar a JSON

**Hito 4: Documentación** 📋 (próximo)
- [ ] INSTALL-v2.md completo
- [ ] FAQ de modelos y performance
- [ ] Ejemplos de uso

---

## Criterios de aceptación

Cuando esté completa, v2 debe:

1. ✅ Detectar emociones de texto en español, inglés y otros idiomas
2. ✅ Mostrar emociones en real-time sin latencia perceptible
3. ✅ Funcionar igual que v1 si no usas `--sentiment`
4. ✅ Confianza >= 0.5 para mostrar (evitar falsos positivos)
5. ✅ Documentación con ejemplos de cada emoción

---

## Modelo de IA

Opciones evaluadas:

| Modelo | Idioma | Velocidad | Tamaño | Precisión |
|--------|--------|-----------|--------|-----------|
| `bert-base-multilingual-uncased-sentiment` | 100+ idiomas | ⚡⚡ | 600MB | ⭐⭐⭐ |
| `xlm-roberta-base-finetuned-urdu-sentiment` | Urdu + otros | ⚡ | 600MB | ⭐⭐⭐⭐ |
| `distilbert-base-uncased-finetuned-sst-2-english` | Inglés | ⚡⚡⚡ | 268MB | ⭐⭐⭐ |
| `bert-base-spanish-wwm-cased` + fine-tuning | Español | ⚡ | 420MB | ⭐⭐⭐⭐ |

**Elegido:** `bert-base-multilingual-uncased-sentiment` (default), intercambiable.

Ver [PLAN-v2.md](PLAN-v2.md) para detalles técnicos.

---

## Referencias

- [PLAN-v2.md](PLAN-v2.md) — Desglose técnico de hitos
- [VERSIONS.md](../VERSIONS.md) — Hoja de ruta general
- [Hugging Face Transformers](https://huggingface.co/docs/transformers/) — Documentación de modelos
- [Emotion Detection Models](https://huggingface.co/models?filter=sentiment-analysis) — Repositorio de modelos

---

**¿Necesitas ayuda?** Abre [PLAN-v2.md](PLAN-v2.md) para ver tareas específicas.
