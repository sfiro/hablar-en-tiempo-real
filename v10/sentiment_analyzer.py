#!/usr/bin/env python3
"""
Analizador de emociones en tiempo real, usando `pysentimiento`.

Clasifica las seis emociones de Ekman más una categoría neutral (`others`): alegría,
tristeza, rabia, miedo, sorpresa, asco. No hay atajo honesto para matices como
«esperanza» o «empatía»: los modelos públicos de emoción se entrenan sobre este
conjunto y es mejor ceñirse a él que fingir una precisión que no existe.

`pysentimiento` trae un modelo específico por idioma (RoBERTuito para español,
BERTweet para inglés, etc.), así que el idioma se fija al crear el analizador.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

LANGUAGES = ("es", "en", "it", "pt")

# Etiquetas reales que devuelve pysentimiento (task="emotion"): anger, disgust, fear,
# joy, sadness, surprise, others. Confirmado contra la documentación del modelo.
EMOTION_MAP = {
    "joy":      {"label": "ALEGRÍA",  "emoji": "😊"},
    "sadness":  {"label": "TRISTEZA", "emoji": "😢"},
    "anger":    {"label": "RABIA",    "emoji": "😠"},
    "fear":     {"label": "MIEDO",    "emoji": "😨"},
    "surprise": {"label": "SORPRESA", "emoji": "😲"},
    "disgust":  {"label": "ASCO",     "emoji": "🤢"},
    "others":   {"label": "NEUTRAL",  "emoji": "😐"},
}


class SentimentAnalyzer:
    """Clasificador de emociones con carga perezosa y caché de resultados."""

    def __init__(self, language: str = "es"):
        if language not in LANGUAGES:
            raise ValueError(f"Idioma no soportado: {language!r}. Usa uno de {LANGUAGES}.")
        self.language = language
        self._analyzer = None
        self._cache: Dict[str, Dict] = {}

    def _load(self):
        """Descarga y carga el modelo. Lento la primera vez (~cientos de MB)."""
        if self._analyzer is not None:
            return
        try:
            from pysentimiento import create_analyzer
        except ImportError as e:
            raise RuntimeError(
                "Falta 'pysentimiento'. Instala con: pip install -r requirements.txt"
            ) from e
        logger.info(f"Cargando modelo de emociones ({self.language})…")
        self._analyzer = create_analyzer(task="emotion", lang=self.language)
        logger.info("Modelo de emociones listo.")

    def analyze(self, text: str) -> Dict:
        """
        Clasifica la emoción dominante de un texto.

        Devuelve: {"emotion": clave interna, "label": etiqueta en español,
                   "confidence": 0-1, "emoji": str}
        """
        text = (text or "").strip()
        if not text:
            return {"emotion": "others", "label": "NEUTRAL", "confidence": 0.0, "emoji": "😐"}

        if text in self._cache:
            return self._cache[text]

        self._load()
        result = self._analyzer.predict(text[:512])
        emotion = result.output
        confidence = float(result.probas[emotion])
        info = EMOTION_MAP.get(emotion, EMOTION_MAP["others"])

        output = {
            "emotion": emotion,
            "label": info["label"],
            "confidence": confidence,
            "emoji": info["emoji"],
        }
        self._cache[text] = output
        return output

    def clear_cache(self):
        self._cache.clear()


if __name__ == "__main__":
    analyzer = SentimentAnalyzer(language="es")
    ejemplos = [
        "Estoy feliz de verte",
        "Me da mucha rabia esto",
        "Tengo miedo de lo que pueda pasar",
        "Qué sorpresa tan grande",
        "Esto me da asco",
        "Estoy muy triste hoy",
        "El cielo es azul",
    ]
    for texto in ejemplos:
        r = analyzer.analyze(texto)
        print(f"{r['emoji']} {r['label']} ({r['confidence']:.2f}) — {texto}")
