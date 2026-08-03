#!/usr/bin/env python3
"""
Analizador de sentimientos en tiempo real.

Clasifica emociones de texto usando transformers (BERT multilingüe).
"""

from transformers import pipeline
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Mapeo de etiquetas del modelo a emociones humanas
EMOTION_MAP = {
    "positive": {"emotion": "joy", "label": "ALEGRÍA", "emoji": "😊", "color": "yellow"},
    "negative": {"emotion": "sadness", "label": "TRISTEZA", "emoji": "😢", "color": "blue"},
    "neutral": {"emotion": "neutral", "label": "NEUTRAL", "emoji": "😐", "color": "gray"},
}


class SentimentAnalyzer:
    """Análisis de sentimientos con caching y soporte multilingüe."""

    def __init__(self, model: str = "bert-base-multilingual-uncased-sentiment"):
        """
        Inicializa el analizador.

        Args:
            model: Nombre del modelo de Hugging Face. Por defecto, BERT multilingüe.
        """
        self.model_name = model
        self.pipeline = None
        self._cache = {}

        logger.info(f"SentimentAnalyzer inicializado con modelo: {model}")

    def _load_pipeline(self):
        """Carga el modelo lazy (solo cuando se necesita)."""
        if self.pipeline is None:
            logger.info(f"Descargando modelo {self.model_name}...")
            self.pipeline = pipeline("sentiment-analysis", model=self.model_name)
            logger.info("Modelo cargado.")

    def analyze(self, text: str) -> Dict:
        """
        Analiza el sentimiento de un texto.

        Args:
            text: Texto a analizar

        Returns:
            Dict con:
                - emotion: clave interna (joy, sadness, etc.)
                - label: etiqueta en español (ALEGRÍA, TRISTEZA, etc.)
                - confidence: confianza 0-1
                - emoji: emoji asociado
                - original_label: etiqueta original del modelo
        """
        if not text or len(text.strip()) == 0:
            return {
                "emotion": "neutral",
                "label": "NEUTRAL",
                "confidence": 0.0,
                "emoji": "😐",
                "original_label": "",
            }

        # Caché: evita reanalizar el mismo texto
        if text in self._cache:
            return self._cache[text]

        self._load_pipeline()

        try:
            result = self.pipeline(text[:512])[0]  # Limita a 512 caracteres
            label = result["label"].lower()
            confidence = result["score"]

            # Mapear a emociones humanas
            emotion_info = EMOTION_MAP.get(label, EMOTION_MAP["neutral"])

            output = {
                "emotion": emotion_info["emotion"],
                "label": emotion_info["label"],
                "confidence": confidence,
                "emoji": emotion_info["emoji"],
                "original_label": label,
            }

            self._cache[text] = output
            return output

        except Exception as e:
            logger.error(f"Error analizando sentimiento: {e}")
            return {
                "emotion": "neutral",
                "label": "ERROR",
                "confidence": 0.0,
                "emoji": "❌",
                "original_label": "error",
            }

    def clear_cache(self):
        """Limpia la caché de análisis."""
        self._cache.clear()


# Uso simple
if __name__ == "__main__":
    analyzer = SentimentAnalyzer()

    textos = [
        "Estoy muy feliz hoy",
        "Me siento triste",
        "Todo está bien",
        "I'm so happy!",
        "Je suis très heureux",
    ]

    for texto in textos:
        resultado = analyzer.analyze(texto)
        print(f"{resultado['emoji']} {resultado['label']} ({resultado['confidence']:.2f}) — {texto}")
