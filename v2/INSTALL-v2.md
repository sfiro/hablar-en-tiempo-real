# Instalación — v2.0 Análisis de sentimientos

Guía rápida para instalar y ejecutar v2 en macOS.

## Requisitos previos

- Python 3.9+ (mismo que v1)
- Una clave de OpenAI con acceso a Realtime API
- Micrófono y altavoces (o auriculares)
- Espacio en disco: ~1.5GB (para modelos de transformers)
- RAM: 4GB+ (8GB recomendado)

## Instalación

### 1. Preparar v2

```bash
cd "/Users/debbie/Desktop/programacion/Hablar en tiempo real"
# v2 está en git como rama/carpeta
cd v2
```

### 2. Crear entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

**Qué se instala:**
- `websockets`, `sounddevice`, `numpy` (igual que v1)
- `transformers` (modelos de IA)
- `torch` (motor de inferencia)
- `certifi` (TLS)

**Primera vez:** Descarga de modelos (~600MB), tarda 2-3 minutos.

### 4. Configurar clave de OpenAI

```bash
cp .env.example .env
# Edita .env con tu clave real
```

## Uso

### Básico — Con análisis de sentimientos

```bash
python realtime_voice.py --sentiment
```

Ejemplo de salida:

```
🎙️  Listo. Habla con naturalidad; haz una pausa y el modelo responderá.
    Análisis de sentimientos: ACTIVO
    (Ctrl+C para salir)

🗣️  Tú: Me siento increíble hoy, conseguí ese trabajo que quería
   📊 ALEGRÍA (0.94)

😊 Asistente: ¡Felicitaciones! Eso es genial. Cuéntame más sobre cómo te sientes...
   📊 ALEGRÍA (0.91)

🗣️  Tú: Estoy nervioso pero muy emocionado
   📊 ESPERANZA (0.87)
```

### Sin análisis de sentimientos (igual que v1)

```bash
python realtime_voice.py
```

### Con estadísticas

```bash
python realtime_voice.py --sentiment --stats
```

Al finalizar:

```
📊 ESTADÍSTICAS DE CONVERSACIÓN
─────────────────────────────────
Tú:
  ALEGRÍA: 3 turnos (promedio: 0.87)
  ESPERANZA: 2 turnos (promedio: 0.82)

Asistente:
  ALEGRÍA: 2 turnos (promedio: 0.91)
  EMPATÍA: 2 turnos (promedio: 0.85)

Tono general: POSITIVO 😊
```

### Opciones completas

```bash
python realtime_voice.py [opciones]

Opciones de v1:
  --voice VOICE              Voz del asistente (marin, cedar, etc.)
  --no-half-duplex           Con auriculares, permite barge-in
  --noise-reduction MODE     far_field (por defecto) o near_field

Opciones de v2 (análisis de sentimientos):
  --sentiment                Activa análisis de sentimientos
  --sentiment-model MODEL    Modelo a usar (por defecto: bert-base-multilingual)
  --stats                    Muestra estadísticas al final
  --no-emoji                 Sin emojis, solo texto
  --confidence-threshold T   Mostrar solo emociones > T (0-1, por defecto 0.5)
  --language LANG            Especificar idioma (es, en, fr, etc.)
```

## Ejemplos

### Conversación con estadísticas

```bash
python realtime_voice.py --sentiment --stats --voice cedar
```

### Solo textos, sin emojis

```bash
python realtime_voice.py --sentiment --no-emoji
```

### Filtrar emociones débiles

```bash
python realtime_voice.py --sentiment --confidence-threshold 0.75
```

### Cambiar modelo

```bash
python realtime_voice.py --sentiment --sentiment-model distilbert-base-uncased-finetuned-sst-2-english
```

## Modelos disponibles

### Multilingual (recomendado)

```bash
python realtime_voice.py --sentiment
# o explícitamente:
python realtime_voice.py --sentiment --sentiment-model bert-base-multilingual-uncased-sentiment
```

- **Idiomas:** 100+
- **Tamaño:** 600MB
- **Velocidad:** ~200ms por frase

### Ligero (para máquinas lentas)

```bash
python realtime_voice.py --sentiment --sentiment-model distilbert-base-uncased-finetuned-sst-2-english
```

- **Idioma:** Inglés
- **Tamaño:** 268MB
- **Velocidad:** ~50ms por frase

## Troubleshooting

**`ModuleNotFoundError: No module named 'transformers'`**
→ Asegúrate de haber corrido `pip install -r requirements.txt`

**Muy lento, latencia de 2+ segundos**
→ Usa modelo ligero: `--sentiment-model distilbert-...`  
→ O habilita GPU si tienes (detecta automáticamente)

**Las emociones no aparecen**
→ Baja `--confidence-threshold`: `--confidence-threshold 0.3`  
→ Prueba con `--debug` para ver confianza real

**Uso de RAM muy alto**
→ Reinicia el script cada hora  
→ Usa modelo más pequeño

**¿Qué emociones detecta?**
→ Ver [EMOTIONS.md](EMOTIONS.md) (aún en desarrollo)

---

## Diferencias con v1

| Aspecto | v1 | v2 |
|---------|----|----|
| Instalación | pip + sounddevice | pip + transformers + torch |
| Uso básico | igual | igual, pero agrega `--sentiment` |
| Renderizado | transcripción | transcripción + emociones |
| Performance | muy rápido | +200ms por análisis |
| CPU | bajo | medio durante análisis |
| RAM | 200MB | 1GB+ (modelos precargados) |

---

## Próximos pasos

- Leer [README-v2.md](README-v2.md) para contexto
- Ver [PLAN-v2.md](PLAN-v2.md) para desarrollo
- Probar ejemplos arriba
- Reportar bugs o sugerencias

---

**¿Necesitas ayuda?** Ver [README-v2.md](README-v2.md) FAQ.
