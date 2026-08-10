"""
Tests de webrtc_server.py: solo lo que es seguro probar sin abrir un servidor HTTP
real ni negociar WebRTC con OpenAI (eso solo se verifica a mano, ver README-v8.md).

`webrtc_server.py` define su propio `EMOTION_TO_PICO` (no lo importa de
`realtime_voice.py` — cada fichero es autónomo dentro de la misma carpeta de
versión, mismo criterio de "copiar, no importar" que entre carpetas de
versión). El riesgo real de tener el mismo diccionario duplicado dos veces es
que diverjan sin querer si se cambia uno y se olvida el otro — este test lo
detecta.

Ejecutar:
    python -m pytest tests/test_webrtc_server.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import realtime_voice
import webrtc_server


def test_el_mapeo_de_emociones_es_idéntico_al_de_realtime_voice():
    assert webrtc_server.EMOTION_TO_PICO == realtime_voice.EMOTION_TO_PICO


def test_el_mapeo_cubre_las_7_categorias_de_pysentimiento():
    from sentiment_analyzer import EMOTION_MAP
    assert set(webrtc_server.EMOTION_TO_PICO.keys()) == set(EMOTION_MAP.keys())
