"""
Verificación de la matemática pura de main.py (firmware de la Pico): conversión de
grados a PWM (directo desde la Pico, sin PCA9685), amortiguación del cuello
(PAN/TILT siguiendo a LR/UD), y los valores de párpados abiertos/cerrados.

No se puede importar main.py directamente: usa `machine`, que no existe fuera de
MicroPython real. Por eso las fórmulas se duplican aquí, literalmente copiadas del
fichero, para poder testearlas con CPython normal. Si cambias una fórmula en
main.py, actualiza también la copia de aquí — son deliberadamente independientes,
no hay una sola fuente de verdad automática entre firmware y test (limitación
aceptada, no un descuido).

Esto verifica que la matemática es internamente consistente; NO verifica que los
servos reales se muevan como se espera — eso solo lo confirma la Pico física.

Nota histórica: hasta que se abandonó el PCA9685 (ver README-v6.md, "Historial de
depuración"), este test verificaba su fórmula de pulso (registros 102-512 a 50Hz).
Esa fórmula sigue en `main_pca9685.py` (archivado, no usado); aquí se testea la
fórmula real de `main.py`, en microsegundos/duty_u16 sobre PWM directo de la Pico.

Ejecutar:
    python -m pytest tests/test_main_math.py -v
"""

import pytest

# --- Copiado de main.py: conversión de grados a PWM directo (sin PCA9685) ----

PULSO_MIN_US, PULSO_MAX_US = 500, 2500
FREQ_SERVO = 50
PERIODO_US = 1_000_000 / FREQ_SERVO


def grados_a_duty_u16(grados):
    us = PULSO_MIN_US + (grados / 180.0) * (PULSO_MAX_US - PULSO_MIN_US)
    return int((us / PERIODO_US) * 65535)


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

def test_duty_en_los_extremos_y_el_centro():
    # 500-2500us sobre un periodo de 20ms (50Hz) = 2.5%-12.5% del duty_u16 (0-65535).
    assert grados_a_duty_u16(0) == pytest.approx(1638, abs=1)
    assert grados_a_duty_u16(90) == pytest.approx(4915, abs=1)
    assert grados_a_duty_u16(180) == pytest.approx(8191, abs=1)


def test_duty_directo_da_la_misma_posicion_fisica_que_el_pca9685_archivado():
    # main_pca9685.py (archivado) usaba 102-512 en registros de 12 bits a 50Hz,
    # equivalentes a ~498-2500us. Confirma que ambos enfoques apuntan al mismo
    # ángulo físico, no solo que cada fórmula es internamente consistente.
    def pulso_pca_en_us(grados):
        pulso = 102 + (grados / 180.0) * (512 - 102)
        return pulso * (20000 / 4096)

    def us_directo(grados):
        return PULSO_MIN_US + (grados / 180.0) * (PULSO_MAX_US - PULSO_MIN_US)

    for grados in (0, 40, 90, 140, 180):
        diferencia_us = abs(pulso_pca_en_us(grados) - us_directo(grados))
        assert diferencia_us < 5, f"a {grados}°, difieren {diferencia_us:.1f}us"


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
