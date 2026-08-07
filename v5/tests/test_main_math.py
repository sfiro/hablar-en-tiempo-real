"""
Verificación de la matemática pura de main.py (firmware de la Pico): fórmula de
pulso PCA9685, amortiguación del cuello (PAN/TILT siguiendo a LR/UD), y los valores
de párpados abiertos/cerrados.

No se puede importar main.py directamente: usa `machine`, que no existe fuera de
MicroPython real. Por eso las fórmulas se duplican aquí, literalmente copiadas del
fichero, para poder testearlas con CPython normal. Si cambias una fórmula en
main.py, actualiza también la copia de aquí — son deliberadamente independientes,
no hay una sola fuente de verdad automática entre firmware y test (limitación
aceptada, no un descuido).

Esto verifica que la matemática es internamente consistente; NO verifica que el
PCA9685 real se mueva como se espera — eso solo lo confirma la Pico física.

Ejecutar:
    python -m pytest tests/test_main_math.py -v
"""

import pytest

# --- Copiado de main.py: fórmula de pulso PCA9685 ---------------------------

def pulso_para(grados):
    return int(102 + (grados / 180.0) * (512 - 102))


# --- Copiado de main.py: amortiguación del cuello ----------------------------

FACTOR_PAN = 0.8
FACTOR_TILT = 0.6
PAN_MIN, PAN_MAX = 40, 140
TILT_MIN, TILT_MAX = 40, 140


def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def objetivo_cuello(lr, ud):
    pan = clamp(90 + (lr - 90) * FACTOR_PAN, PAN_MIN, PAN_MAX)
    tilt = clamp(90 + (ud - 90) * FACTOR_TILT, TILT_MIN, TILT_MAX)
    return pan, tilt


# --- Copiado de main.py: posiciones de párpados ------------------------------

PARPADOS_ABIERTOS = {"TL": 170, "BL": 10, "TR": 10, "BR": 160}
PARPADOS_CERRADOS = {"TL": 70, "BL": 90, "TR": 70, "BR": 90}


# --- Tests --------------------------------------------------------------

def test_pulso_en_los_extremos_y_el_centro():
    assert pulso_para(0) == 102
    assert pulso_para(90) == 307
    assert pulso_para(180) == 512


def test_cuello_centrado_cuando_los_ojos_estan_centrados():
    pan, tilt = objetivo_cuello(90, 90)
    assert pan == 90 and tilt == 90


def test_cuello_amortigua_el_movimiento_de_los_ojos():
    # Con factor 0.8/0.6, el cuello se mueve MENOS que los ojos, nunca más.
    pan, tilt = objetivo_cuello(140, 40)  # ojos en un extremo
    assert 90 < pan < 140          # se mueve hacia la derecha, pero no tanto como los ojos
    assert 40 < tilt < 90          # se mueve hacia abajo, pero no tanto como los ojos
    assert (pan - 90) < (140 - 90)   # el desplazamiento del cuello es menor que el de los ojos
    assert (90 - tilt) < (90 - 40)


def test_cuello_nunca_sale_de_su_rango_incluso_en_los_extremos_de_los_ojos():
    for lr in (40, 140):
        for ud in (40, 140):
            pan, tilt = objetivo_cuello(lr, ud)
            assert PAN_MIN <= pan <= PAN_MAX
            assert TILT_MIN <= tilt <= TILT_MAX


def test_parpados_abiertos_y_cerrados_son_valores_distintos_por_canal():
    for canal in PARPADOS_ABIERTOS:
        assert PARPADOS_ABIERTOS[canal] != PARPADOS_CERRADOS[canal], (
            f"canal {canal}: abierto y cerrado no deberían coincidir"
        )
