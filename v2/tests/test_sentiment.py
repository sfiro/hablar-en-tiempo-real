"""
Tests de sentiment_analyzer.py.

Se dividen en dos grupos:
  - Lógica interna (caché, validación, texto vacío): no necesitan el modelo real,
    se inyecta un analizador falso. Corren rápido y sin dependencias pesadas.
  - Integración con el modelo real (test_real_model_*): sí descargan/cargan
    pysentimiento. Lentos la primera vez. Se saltan si pysentimiento no está
    instalado, para no romper CI en máquinas sin torch.

Ejecutar:
    python -m pytest tests/test_sentiment.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentiment_analyzer import SentimentAnalyzer, EMOTION_MAP, LANGUAGES


class FakeOutput:
    """Imita el AnalyzerOutput que devuelve pysentimiento."""

    def __init__(self, output, probas):
        self.output = output
        self.probas = probas


class FakeAnalyzer:
    """Analizador falso: registra cuántas veces se le llama, para probar la caché."""

    def __init__(self, output="joy", confidence=0.9):
        self.calls = 0
        self._output = output
        self._confidence = confidence

    def predict(self, text):
        self.calls += 1
        return FakeOutput(self._output, {self._output: self._confidence, "others": 1 - self._confidence})


# --- Lógica interna, sin modelo real ----------------------------------------

def test_texto_vacio_no_toca_el_modelo():
    analyzer = SentimentAnalyzer(language="es")
    result = analyzer.analyze("")
    assert result == {"emotion": "others", "label": "NEUTRAL", "confidence": 0.0, "emoji": "😐"}
    assert analyzer._analyzer is None  # nunca se llegó a cargar


def test_solo_espacios_es_neutral():
    analyzer = SentimentAnalyzer(language="es")
    result = analyzer.analyze("   ")
    assert result["label"] == "NEUTRAL"


def test_idioma_invalido_falla_rapido():
    with pytest.raises(ValueError):
        SentimentAnalyzer(language="xx")


def test_todos_los_idiomas_soportados_se_aceptan():
    for lang in LANGUAGES:
        SentimentAnalyzer(language=lang)  # no debe lanzar


def test_cache_evita_reanalizar_el_mismo_texto():
    analyzer = SentimentAnalyzer(language="es")
    fake = FakeAnalyzer(output="joy", confidence=0.9)
    analyzer._analyzer = fake  # nos saltamos _load

    r1 = analyzer.analyze("Estoy feliz")
    r2 = analyzer.analyze("Estoy feliz")

    assert r1 == r2
    assert fake.calls == 1, "debería reusar el resultado en caché, no volver a inferir"


def test_mapeo_de_emocion_a_etiqueta_y_emoji():
    analyzer = SentimentAnalyzer(language="es")
    analyzer._analyzer = FakeAnalyzer(output="sadness", confidence=0.75)

    result = analyzer.analyze("Estoy triste")

    assert result["emotion"] == "sadness"
    assert result["label"] == "TRISTEZA"
    assert result["emoji"] == "😢"
    assert result["confidence"] == pytest.approx(0.75)


def test_etiqueta_desconocida_cae_en_neutral():
    """Si pysentimiento devolviera una etiqueta no mapeada, no debe explotar."""
    analyzer = SentimentAnalyzer(language="es")
    analyzer._analyzer = FakeAnalyzer(output="etiqueta_inventada", confidence=0.5)

    result = analyzer.analyze("texto cualquiera")

    assert result["label"] == "NEUTRAL"


def test_emotion_map_tiene_las_siete_categorias_de_ekman_mas_neutral():
    esperadas = {"joy", "sadness", "anger", "fear", "surprise", "disgust", "others"}
    assert set(EMOTION_MAP.keys()) == esperadas
    for info in EMOTION_MAP.values():
        assert "label" in info and "emoji" in info


# --- Integración con el modelo real (lentos, se saltan si falta pysentimiento) ---

pysentimiento_disponible = True
try:
    import pysentimiento  # noqa: F401
except ImportError:
    pysentimiento_disponible = False

requiere_modelo_real = pytest.mark.skipif(
    not pysentimiento_disponible,
    reason="pysentimiento no está instalado (pip install -r requirements.txt)",
)


@requiere_modelo_real
def test_real_model_detecta_alegria_obvia():
    analyzer = SentimentAnalyzer(language="es")
    result = analyzer.analyze("Estoy feliz de verte, qué alegría")
    assert result["emotion"] == "joy"


@requiere_modelo_real
def test_real_model_detecta_tristeza_obvia():
    analyzer = SentimentAnalyzer(language="es")
    result = analyzer.analyze("Estoy muy triste, perdí a mi mascota")
    assert result["emotion"] == "sadness"


@requiere_modelo_real
def test_real_model_detecta_miedo_obvio():
    analyzer = SentimentAnalyzer(language="es")
    result = analyzer.analyze("Tengo mucho miedo, esto me aterra")
    assert result["emotion"] == "fear"
