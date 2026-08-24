"""
Tests de rastreo_expresiones.py: solo la lógica pura del ciclo de expresiones
(_siguiente_indice) y que CICLO_EMOCIONES sea consistente con el vocabulario
real de la Pico (EMOCIONES_VALIDAS de pico_serial.py) — mismo patrón que
test_webrtc_server.py en v8/v9, que comparaba EMOTION_TO_PICO entre dos
ficheros para que no divergieran en silencio.

No se prueban los hilos de cámara/serial reales aquí (necesitan hardware o
mocks pesados de cv2/pyserial); esos se validan a mano con el propio script,
igual que face_tracker.py y pico_serial.py.

Ejecutar:
    python -m pytest tests/test_rastreo_expresiones.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rastreo_expresiones import CICLO_EMOCIONES, INTERVALO_POR_DEFECTO_S, _siguiente_indice
from pico_serial import EMOCIONES_VALIDAS


def test_ciclo_incluye_las_diez_emociones_sin_repetir():
    assert len(CICLO_EMOCIONES) == 10
    assert len(set(CICLO_EMOCIONES)) == 10


def test_ciclo_no_tiene_ninguna_emocion_fuera_del_vocabulario_de_la_pico():
    # Si alguien añade una emoción al ciclo que la Pico no reconoce, PicoLink la
    # rechazaría con ValueError en cuanto se intentara enviar — mejor detectarlo
    # aquí, sin hardware.
    assert set(CICLO_EMOCIONES) == EMOCIONES_VALIDAS


def test_ciclo_empieza_en_neutral():
    # No es un requisito funcional (el firmware ya arranca en NEUTRAL de todos
    # modos), pero mantiene el mismo orden documentado desde v6/v7.
    assert CICLO_EMOCIONES[0] == "NEUTRAL"


def test_siguiente_indice_avanza_de_uno_en_uno():
    assert _siguiente_indice(0) == 1
    assert _siguiente_indice(5) == 6


def test_siguiente_indice_da_la_vuelta_al_final():
    ultimo = len(CICLO_EMOCIONES) - 1
    assert _siguiente_indice(ultimo) == 0


def test_una_vuelta_completa_pasa_por_las_diez_sin_repetir():
    indice = 0
    vistas = []
    for _ in range(len(CICLO_EMOCIONES)):
        vistas.append(CICLO_EMOCIONES[indice])
        indice = _siguiente_indice(indice)
    assert vistas == list(CICLO_EMOCIONES)
    assert indice == 0  # vuelve exactamente al punto de partida


def test_intervalo_por_defecto_coincide_con_el_pulso_del_firmware():
    # INTERVALO_EXPRESION_MS en main.py es 5000ms: si el intervalo del ciclo
    # fuera mayor, habría un hueco donde la Pico cae a NEUTRAL entre una
    # expresión y la siguiente, antes de que llegue la próxima del ciclo.
    assert INTERVALO_POR_DEFECTO_S == 5.0
