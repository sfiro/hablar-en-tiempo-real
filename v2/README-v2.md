# Versión 2.0 — Análisis de emociones en tiempo real 🎭

Extensión de v1 que clasifica la emoción de cada frase de la conversación (tuya y del
asistente) y la muestra en consola mientras habláis.

**Estado:** En desarrollo (Hito 1 en curso)
**Plataforma:** macOS (igual que v1, mismos requisitos de audio)
**Base:** v1 + [`pysentimiento`](https://github.com/pysentimiento/pysentimiento)

---

## Qué detecta y qué no

`pysentimiento` clasifica texto en las **seis emociones de Ekman más una categoría
neutral**: alegría, tristeza, rabia, miedo, sorpresa, asco, y "otros" (neutral).

**No** detecta matices como esperanza, empatía, optimismo o confianza. Esa fue la
promesa inicial de este documento y no era honesta: no hay un modelo público fiable
que clasifique esas categorías con precisión razonable. Ceñirse a las siete que el
modelo sí entrena de verdad es mejor que fingir una granularidad que no existe.

| Emoción | Etiqueta | Emoji |
|---|---|---|
| joy | ALEGRÍA | 😊 |
| sadness | TRISTEZA | 😢 |
| anger | RABIA | 😠 |
| fear | MIEDO | 😨 |
| surprise | SORPRESA | 😲 |
| disgust | ASCO | 🤢 |
| others | NEUTRAL | 😐 |

---

## Ejemplo de uso

```bash
python realtime_voice.py --sentiment
```

Salida real, verificada corriendo `sentiment_analyzer.py` con el modelo cargado
(no son ejemplos inventados):

```
😊 ALEGRÍA (0.99) — Estoy feliz de verte
😢 TRISTEZA (0.38) — Me da mucha rabia esto
😨 MIEDO (0.97) — Tengo miedo de lo que pueda pasar
😊 ALEGRÍA (0.80) — Qué sorpresa tan grande
🤢 ASCO (0.71) — Esto me da asco
😢 TRISTEZA (0.99) — Estoy muy triste hoy
😊 ALEGRÍA (0.57) — El cielo es azul
```

Nota los aciertos claros (alegría, miedo, tristeza, asco con confianza alta) y también
los fallos reales: "me da mucha rabia esto" lo clasificó como TRISTEZA con solo 0.38 de
confianza (ese caso quedaría oculto con el umbral por defecto de 0.5), y "el cielo es
azul" —una frase neutra— le dio ALEGRÍA con 0.57, que sí pasaría el filtro por defecto.
No es un modelo perfecto; ver "Limitaciones conocidas" más abajo.

Con `--stats`, al terminar (Ctrl+C):

```
📊 ESTADÍSTICAS DE CONVERSACIÓN
─────────────────────────────────
Tú:
  TRISTEZA: 1 turno(s) (promedio: 0.89)
  ALEGRÍA: 1 turno(s) (promedio: 0.72)

Asistente:
  NEUTRAL: 1 turno(s) (promedio: 0.61)

Tono general (heurística, no del modelo): MIXTO 😐
```

El "tono general" es una cuenta simple de emociones positivas vs. negativas que
añadimos nosotros para dar un resumen legible — **no** es una salida del modelo.

---

## Limitaciones conocidas

Verificado con el modelo real, no supuesto:

- **Las frases cortas y directas fallan más que las elaboradas.** Es el patrón más
  claro que encontramos probando las seis emociones:

  | Frase corta (falla) | Clasificó como | Frase elaborada (acierta) | Clasificó como |
  |---|---|---|---|
  | "Me da mucha rabia esto" | TRISTEZA (0.38) | "Odio que me traten así, es indignante" | RABIA (0.91) |
  | "Estoy furioso contigo" | MIEDO (0.35) | "Qué rabia me da, no lo soporto" | RABIA (0.82) |
  | "Qué sorpresa tan grande" | ALEGRÍA (0.80) | "No puedo creerlo, es una sorpresa total" | SORPRESA (0.98) |

  Con el umbral por defecto (0.5), varias de esas fallas quedan ocultas por baja
  confianza — el síntoma visible es "no dijo nada" más que "se equivocó" — pero el
  fallo de fondo está ahí, y a veces sí supera el umbral (ver siguiente punto).
- **Falsos positivos en frases neutras.** "El cielo es azul" (neutral, obviamente) dio
  ALEGRÍA con 0.57, que sí supera el umbral por defecto y se mostraría como si fuera
  una clasificación real.
- **Entrenado con tuits, no con conversación hablada.** El modelo (`RoBERTuito`) se
  entrenó sobre texto de Twitter/X. La transcripción de una conversación de voz es
  distinta en registro y estructura; es razonable esperar más ruido que el reportado
  en los benchmarks originales del modelo.

En resumen: sirve bien para frases con carga emocional explícita y algo elaborada
("no puedo creerlo, qué sorpresa" en vez de solo "qué sorpresa"), y falla más de lo
ideal en exclamaciones cortas. Subir `--confidence-threshold` reduce el ruido pero no
lo elimina, y en algún caso ni siquiera ayuda (el falso positivo del cielo azul pasa
el umbral por defecto).

---

## Cómo funciona por dentro

1. Cada frase transcrita (tuya o del asistente) se manda a `SentimentAnalyzer.analyze()`
2. `pysentimiento` clasifica con un modelo RoBERTuito (español) o equivalente por idioma
3. El análisis corre en un hilo aparte (`run_in_executor`), así que **nunca bloquea el
   audio**: la inferencia tarda cientos de ms, y hacerla en el bucle de eventos
   principal cortaría la reproducción o el envío de audio mientras se calcula
4. El resultado se imprime bajo la frase correspondiente, con emoji + etiqueta + confianza

El modelo se precarga en segundo plano al arrancar (no bloquea el saludo inicial), pero
la primera vez que lo usas, la descarga (~cientos de MB) tarda uno o dos minutos.

---

## Instalación rápida

Ver [INSTALL-v2.md](INSTALL-v2.md) para detalles completos.

```bash
cd v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # incluye pysentimiento (torch + transformers)
cp .env.example .env                 # Pon tu clave de OpenAI
python realtime_voice.py --sentiment
```

**Aviso de espacio y tiempo:** `pysentimiento` instala `torch` y `transformers` como
dependencias. Son ~1-2GB de descarga y la instalación puede tardar varios minutos.

---

## Opciones de línea de comandos

```bash
python realtime_voice.py [opciones]

Opciones de v1 (sin cambios):
  --voice VOICE              Voz del asistente (marin, cedar, etc.)
  --no-half-duplex           Con auriculares, permite barge-in
  --noise-reduction MODE     far_field (por defecto) o near_field

Opciones nuevas (v2):
  --sentiment                Activa la clasificación de emociones
  --language {es,en,it,pt}   Idioma del modelo (por defecto: es)
  --stats                    Resumen de emociones al terminar (Ctrl+C)
  --no-emoji                 Solo texto, sin emojis
  --confidence-threshold T   Solo muestra si confianza >= T (por defecto: 0.5)
```

No hay `--sentiment-model`: a diferencia de un clasificador genérico de
positivo/negativo, `pysentimiento` liga un modelo concreto a cada idioma
(`--language` ya selecciona el correcto). Prometer que se puede cambiar por cualquier
modelo de Hugging Face habría sido, otra vez, una promesa que el código no cumple.

---

## Desarrollo

Seguimiento en [PLAN-v2.md](PLAN-v2.md).

### Hito 1: Análisis básico ✅ (completo y verificado)
- [x] `sentiment_analyzer.py` con `pysentimiento` (emoción real, no solo positivo/negativo)
- [x] Integración en `realtime_voice.py` sin bloquear el audio
- [x] Visualización en consola con emoji + etiqueta + confianza
- [x] Tests de integración con el modelo real (`tests/test_sentiment.py`, 3 casos obvios)
- [x] Verificado en ejecución real contra la API: conecta, precarga el modelo en
      background, analiza sin bloquear el streaming de audio, y el resumen de
      `--stats` se imprime correctamente al terminar
- [x] Dos bugs encontrados y corregidos en esta verificación (ver «Bugs encontrados»)
- [ ] Falta una conversación real hablando deliberadamente (la ejecución de prueba
      capturó ruido ambiente del micro, no frases dichas a propósito)

### Bugs encontrados y corregidos en esta ronda

1. **`asyncio.create_task()` sobre un `Future`.** La precarga del modelo se envolvía
   con `create_task(loop.run_in_executor(...))`, pero `run_in_executor` ya devuelve un
   `Future`, no una corrutina — `create_task` exige lo segundo y fallaba con
   `TypeError` en cuanto arrancaba. Se detectó al ejecutar el script real, no con
   `py_compile`. Arreglo: `loop.run_in_executor(...)` sin envolver.
2. **Salida sin salto de línea inicial.** El resultado de la emoción se imprimía sin
   `\n` delante, así que si llegaba mientras el otro lado seguía en pleno streaming de
   su transcripción (`print(delta, end="")`), el resultado aparecía **en medio** de esa
   frase. Se vio literalmente en una ejecución real. Arreglo: `\n` inicial, igual que
   el resto de avisos asíncronos del script.

### Hito 2: Validación y refinamiento 🔄 (en progreso)
- [x] Tests unitarios de lógica (caché, validación de idioma, mapeo de emociones)
- [x] Medida real de latencia: la carga inicial del modelo tarda unos segundos
      (visible en el log como barra de progreso), el análisis por frase después es
      rápido y no se notó impacto en el audio
- [ ] Conversación real hablando (pendiente, ver arriba)
- [ ] Revisar si 0.5 de umbral es razonable con más datos reales (ver limitaciones)

### Hito 3: Documentación 📋 (próximo)
- [x] Ejemplos reales de cada emoción (ver arriba, no inventados)
- [ ] Troubleshooting específico de pysentimiento/torch

---

## Referencias

- [PLAN-v2.md](PLAN-v2.md) — Desglose técnico de hitos
- [VERSIONS.md](../VERSIONS.md) — Hoja de ruta general
- [pysentimiento (GitHub)](https://github.com/pysentimiento/pysentimiento) — Biblioteca usada
- [robertuito-emotion-analysis (Hugging Face)](https://huggingface.co/pysentimiento/robertuito-emotion-analysis) — Modelo por defecto (español)

---

**¿Necesitas ayuda?** Abre [PLAN-v2.md](PLAN-v2.md) para ver tareas específicas.
