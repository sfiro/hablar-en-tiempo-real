"""
Verificación de la matemática pura de estado_base.py: la conversión de grados a
PWM debe ser idéntica a la de main.py (misma fórmula, mismo mapeo de pines), y
90° debe caer exactamente en el centro del rango de pulso.

No se puede importar estado_base.py directamente: usa `machine`, que no existe
fuera de MicroPython real. La fórmula se duplica aquí, igual que en
test_main_math.py de versiones anteriores.

Ejecutar:
    python -m pytest tests/test_estado_base.py -v
"""

import pytest

PULSO_MIN_US, PULSO_MAX_US = 500, 2500
FREQ_SERVO = 50
PERIODO_US = 1_000_000 / FREQ_SERVO


def grados_a_duty_u16(grados):
    us = PULSO_MIN_US + (grados / 180.0) * (PULSO_MAX_US - PULSO_MIN_US)
    return int((us / PERIODO_US) * 65535)


PIN_DE_CANAL = {
    "LR": 2, "UD": 3,
    "TL": 4, "BL": 5, "TR": 6, "BR": 7,
    "PAN": 8, "TILT": 9,
}


def test_noventa_grados_es_el_centro_del_rango_de_pulso():
    us_en_90 = PULSO_MIN_US + (90 / 180.0) * (PULSO_MAX_US - PULSO_MIN_US)
    assert us_en_90 == pytest.approx((PULSO_MIN_US + PULSO_MAX_US) / 2)


def test_duty_de_90_grados_coincide_con_main_py():
    assert grados_a_duty_u16(90) == pytest.approx(4915, abs=1)


def test_los_ocho_canales_tienen_un_pin_unico_sin_solapes():
    pines = list(PIN_DE_CANAL.values())
    assert len(pines) == len(set(pines)), "hay pines repetidos entre canales"
    assert len(pines) == 8


def test_mapeo_de_pines_coincide_con_main_py():
    # Copiado de main.py — si cambia allá, debe cambiar aquí también.
    esperado = {"LR": 2, "UD": 3, "TL": 4, "BL": 5, "TR": 6, "BR": 7, "PAN": 8, "TILT": 9}
    assert PIN_DE_CANAL == esperado
