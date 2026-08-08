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


# --- Copiado de main.py: offsets de expresión y su aplicación ---------------

LIMITES_PARPADOS = {"TL": (70, 170), "BL": (10, 90), "TR": (10, 70), "BR": (90, 160)}

OFFSETS_EMOCIONES = {
    "NEUTRAL":     {"TL": 0,    "TR": 0,   "BL": 0,   "BR": 0,   "TILT": 0},
    "FELIZ":       {"TL": 0,    "TR": 0,   "BL": 30,  "BR": -30, "TILT": 0},
    "ENOJADO":     {"TL": -40,  "TR": 40,  "BL": 0,   "BR": 0,   "TILT": 10},
    "TRISTE":      {"TL": -30,  "TR": 30,  "BL": 20,  "BR": -20, "TILT": -20},
    "SORPRENDIDO": {"TL": 20,   "TR": -20, "BL": -10, "BR": 10,  "TILT": -10},
    "DORMIDO":     {"TL": -100, "TR": 100, "BL": 80,  "BR": -80, "TILT": -30},
    "DUDA":        {"TL": -50,  "TR": 0,   "BL": 0,   "BR": 0,   "TILT": 10},
    "SOSPECHA":    {"TL": -40,  "TR": 40,  "BL": 40,  "BR": -40, "TILT": 0},
    "PENSATIVO":   {"TL": 0,    "TR": 0,   "BL": 10,  "BR": -10, "TILT": 15},
    "NERVIOSO":    {"TL": 0,    "TR": 0,   "BL": 0,   "BR": 0,   "TILT": -5},
}

SECUENCIA_EMOCIONES = ("NEUTRAL", "FELIZ", "ENOJADO", "TRISTE", "SORPRENDIDO",
                       "DORMIDO", "DUDA", "SOSPECHA", "PENSATIVO", "NERVIOSO")


def objetivo_parpados_para(emocion):
    """Misma lógica que actualizar_objetivo_expresion() en main.py, aislada de
    todo lo demás (sin tocar TILT ni depender de objetivo_actual del firmware)."""
    offsets = OFFSETS_EMOCIONES[emocion]
    return {
        canal: clamp(PARPADOS_ABIERTOS[canal] + offsets[canal], *LIMITES_PARPADOS[canal])
        for canal in ("TL", "BL", "TR", "BR")
    }


def test_todas_las_emociones_de_la_secuencia_tienen_offsets_definidos():
    for emocion in SECUENCIA_EMOCIONES:
        assert emocion in OFFSETS_EMOCIONES


def test_neutral_no_mueve_los_parpados_respecto_a_abierto():
    assert objetivo_parpados_para("NEUTRAL") == PARPADOS_ABIERTOS


def test_ninguna_emocion_saca_los_parpados_de_su_rango_mecanico():
    for emocion in OFFSETS_EMOCIONES:
        objetivo = objetivo_parpados_para(emocion)
        for canal, valor in objetivo.items():
            minimo, maximo = LIMITES_PARPADOS[canal]
            assert minimo <= valor <= maximo, f"{emocion}/{canal}: {valor} fuera de ({minimo},{maximo})"


def test_sorprendido_no_se_distingue_de_neutral_en_v6():
    # Hallazgo real, no un bug: SORPRENDIDO empuja los 4 párpados hacia "más
    # abiertos todavía", pero en v6 ya parten del máximo (no hay sincronía con la
    # mirada que los abra menos, a diferencia del original). Los 4 canales
    # clampan de vuelta al valor de PARPADOS_ABIERTOS — la expresión no se ve.
    # Documentado en README-v6.md, sección de limitaciones.
    assert objetivo_parpados_para("SORPRENDIDO") == PARPADOS_ABIERTOS


def test_dormido_si_se_distingue_cierra_parcialmente_los_parpados():
    # A diferencia de SORPRENDIDO, DORMIDO empuja hacia "más cerrado", que sí
    # tiene margen desde la base abierta — la expresión sí debería verse.
    objetivo = objetivo_parpados_para("DORMIDO")
    assert objetivo != PARPADOS_ABIERTOS
    # TL llega justo al límite de cerrado (70); BL casi al suyo (90).
    assert objetivo["TL"] == 70
    assert objetivo["BL"] == 90


def test_feliz_sube_el_parpado_inferior_izquierdo_y_baja_el_derecho():
    objetivo = objetivo_parpados_para("FELIZ")
    assert objetivo["BL"] > PARPADOS_ABIERTOS["BL"]
    assert objetivo["BR"] < PARPADOS_ABIERTOS["BR"]
