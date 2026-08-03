# Instalación — v2.0 Análisis de emociones

Guía rápida para instalar y ejecutar v2 en macOS.

## Requisitos previos

- Python 3.9+ (mismo que v1)
- Una clave de OpenAI con acceso a Realtime API
- Micrófono y altavoces (o auriculares)
- Espacio en disco: ~2GB (para `torch` + `transformers`, dependencias de `pysentimiento`)
- Conexión a internet estable para la instalación y para la primera descarga del modelo

## Instalación

### 1. Entorno virtual

```bash
cd v2
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

**Esto tarda.** `pysentimiento` trae `torch` y `transformers` como dependencias, que
suman varios cientos de MB de descarga. En una conexión normal, cuenta con varios
minutos. Es un paso que solo se paga una vez.

### 3. Configurar clave de OpenAI

```bash
cp .env.example .env
# Edita .env con tu clave real: OPENAI_API_KEY="sk-..."
```

## Uso

### Con análisis de emociones

```bash
python realtime_voice.py --sentiment
```

La **primera vez**, al hablar la primera frase, el script descarga el modelo de
emociones en español (~cientos de MB) en segundo plano. Esa descarga empieza al
arrancar, no al hablar, así que si esperas medio minuto antes de tu primera frase, ya
debería estar lista.

Ejemplo:

```
🎙️  Listo. Habla con naturalidad; haz una pausa y el modelo responderá.
    Emociones: ACTIVO (es) — el modelo se descarga la primera vez, puede tardar.
    (Ctrl+C para salir)

🗣️  Tú: Me siento increíble hoy, conseguí ese trabajo que quería
   😊 ALEGRÍA (0.91)

😊 Asistente: ¡Felicitaciones! Eso es genial...
   😐 NEUTRAL (0.58)
```

### Sin análisis de emociones (igual que v1)

```bash
python realtime_voice.py
```

### Con resumen al terminar

```bash
python realtime_voice.py --sentiment --stats
```

Al pulsar Ctrl+C:

```
📊 ESTADÍSTICAS DE CONVERSACIÓN
─────────────────────────────────
Tú:
  ALEGRÍA: 3 turno(s) (promedio: 0.85)
  NEUTRAL: 2 turno(s) (promedio: 0.60)

Asistente:
  NEUTRAL: 4 turno(s) (promedio: 0.65)
  ALEGRÍA: 1 turno(s) (promedio: 0.72)

Tono general (heurística, no del modelo): POSITIVO 😊
```

### Otro idioma

```bash
python realtime_voice.py --sentiment --language en
```

Idiomas soportados: `es` (español, por defecto), `en` (inglés), `it` (italiano),
`pt` (portugués). Cada uno usa un modelo distinto internamente; no hay opción para
mezclar idiomas en la misma sesión.

### Ajustar sensibilidad

```bash
# Menos falsos positivos, solo emociones claras
python realtime_voice.py --sentiment --confidence-threshold 0.7

# Ver todo, incluso clasificaciones dudosas (útil para depurar)
python realtime_voice.py --sentiment --confidence-threshold 0 --debug
```

## Opciones completas

```bash
python realtime_voice.py [opciones]

Opciones de v1 (sin cambios):
  --voice VOICE              Voz del asistente (marin, cedar, etc.)
  --no-half-duplex           Con auriculares, permite barge-in
  --noise-reduction MODE     far_field (por defecto) o near_field

Opciones de v2 (análisis de emociones):
  --sentiment                Activa la clasificación de emociones
  --language {es,en,it,pt}   Idioma del modelo (por defecto: es)
  --stats                    Resumen de emociones al terminar (Ctrl+C)
  --no-emoji                 Solo texto, sin emojis
  --confidence-threshold T   Solo muestra si confianza >= T (por defecto: 0.5)
```

## Troubleshooting

**La instalación tarda mucho o parece colgada**
→ Normal. `pip install -r requirements.txt` resuelve dependencias de `torch` y
`transformers`, que son pesadas. Déjalo correr varios minutos antes de asumir que falló.

**`ERROR: --sentiment necesita 'pysentimiento'`**
→ No completaste la instalación. Corre `pip install -r requirements.txt` de nuevo y
revisa que no haya errores.

**Las emociones no aparecen nunca**
→ Baja el umbral: `--confidence-threshold 0.3`. Si con eso tampoco aparece nada,
prueba `--debug` para ver si hay errores de análisis en la salida de error.

**Tarda varios segundos en mostrar la emoción de la primera frase**
→ Esperado: es la descarga/carga del modelo. Las frases siguientes son casi
instantáneas porque el modelo ya está en memoria.

**Uso de RAM alto**
→ El modelo ocupa varios cientos de MB en memoria mientras el script corre. Es
esperable con `transformers`; no hay forma de evitarlo sin cambiar de enfoque.

**`UserWarning: resource_tracker: There appear to be 1 leaked semaphore objects...`**
→ Aviso benigno de `multiprocessing` al cerrar el proceso, viene de una dependencia
interna de `torch`/`transformers` en macOS. Se ve al salir con Ctrl+C. No indica un
fallo de este proyecto; se puede ignorar.

---

## Diferencias con v1

| Aspecto | v1 | v2 |
|---------|----|----|
| Instalación | pip (rápida) | pip + torch/transformers (varios minutos) |
| Uso básico | igual | igual, agrega `--sentiment` |
| Consola | transcripción | transcripción + emoción por frase |
| Latencia de audio | sin cambios | sin cambios (análisis en hilo aparte) |
| RAM en reposo | ~200MB | ~200MB sin `--sentiment`, +varios cientos MB con él |

---

## Próximos pasos

- Leer [README-v2.md](README-v2.md) para el contexto completo y qué NO detecta
- Ver [PLAN-v2.md](PLAN-v2.md) para el estado de desarrollo
- Probar con una conversación real y reportar si las emociones detectadas tienen sentido

---

**¿Necesitas ayuda?** Ver [README-v2.md](README-v2.md).
