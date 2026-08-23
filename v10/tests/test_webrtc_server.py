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


# --- Modo dormido por inactividad (_decidir_sueno), nuevo en v9 -------------
# Lógica pura (sin threading.Event ni time.sleep real), así que se puede
# probar directamente con valores de tiempo fijos, a diferencia del hilo de
# rastreo o la negociación WebRTC.

def test_no_duerme_antes_de_que_pase_el_timeout():
    dormir, despertando = webrtc_server._decidir_sueno(
        ahora=30.0, ultima_actividad=0.0, timeout=60.0, dormido_previo=False)
    assert dormir is False
    assert despertando is False


def test_duerme_justo_al_cumplirse_el_timeout():
    dormir, despertando = webrtc_server._decidir_sueno(
        ahora=60.0, ultima_actividad=0.0, timeout=60.0, dormido_previo=False)
    assert dormir is True
    assert despertando is False


def test_se_mantiene_dormido_mientras_siga_el_silencio():
    dormir, despertando = webrtc_server._decidir_sueno(
        ahora=200.0, ultima_actividad=0.0, timeout=60.0, dormido_previo=True)
    assert dormir is True
    assert despertando is False, "no debe repetir el gesto de despertar en cada vuelta"


def test_despierta_una_vez_cuando_vuelve_la_actividad():
    # ultima_actividad se actualizó justo ahora (una frase nueva llegó)
    dormir, despertando = webrtc_server._decidir_sueno(
        ahora=250.0, ultima_actividad=250.0, timeout=60.0, dormido_previo=True)
    assert dormir is False
    assert despertando is True


def test_no_marca_despertando_si_ya_estaba_despierto():
    dormir, despertando = webrtc_server._decidir_sueno(
        ahora=10.0, ultima_actividad=10.0, timeout=60.0, dormido_previo=False)
    assert dormir is False
    assert despertando is False
