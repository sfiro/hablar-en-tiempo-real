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

Nota histórica: hasta que se abandonó el PCA9685 (ver ../v5/README-v5.md, sección
"Historial de depuración completo"), este test verificaba su fórmula de pulso
(registros 102-512 a 50Hz).
Esa fórmula sigue en `main_pca9685.py` (archivado, no usado); aquí se testea la
fórmula real de `main.py`, en microsegundos/duty_u16 sobre PWM directo de la Pico.

Ejecutar:
    python -m pytest tests/test_main_math.py -v
"""

import random

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


# --- Copiado de main.py: reposo real de los párpados (no 100% abierto) ------
# Pedido explícito tras probar en hardware real: con los párpados en reposo
# totalmente abiertos, SORPRENDIDO no tenía margen para distinguirse de
# NEUTRAL. 40% de cierre da margen cómodo en los 4 canales (TR es el más
# exigente, con un mínimo de ~34%).

CIERRE_REPOSO = 0.40
PARPADOS_REPOSO = {
    canal: PARPADOS_ABIERTOS[canal] + CIERRE_REPOSO * (PARPADOS_CERRADOS[canal] - PARPADOS_ABIERTOS[canal])
    for canal in PARPADOS_ABIERTOS
}

# --- Copiado de main.py: offsets de expresión y su aplicación ---------------

LIMITES_PARPADOS = {"TL": (70, 170), "BL": (10, 90), "TR": (10, 70), "BR": (90, 160)}

# FELIZ y SOSPECHA recalculados para v6 (no son los de ojosMecanicos): con el
# reposo ya al 40% de cierre, los offsets originales (pensados para una base
# 100% abierta) apenas se notaban. FELIZ ahora sube el párpado inferior un 50%
# del camino restante hacia CERRADO desde el reposo; SOSPECHA cierra los 4
# canales un 80% del camino restante hacia CERRADO. El resto son los 10 de
# ojosMecanicos/main.py, sin cambios.
OFFSETS_EMOCIONES = {
    "NEUTRAL":     {"TL": 0,    "TR": 0,   "BL": 0,   "BR": 0,   "TILT": 0},
    "FELIZ":       {"TL": 0,    "TR": 0,   "BL": 24,  "BR": -21, "TILT": 0},
    "ENOJADO":     {"TL": -40,  "TR": 40,  "BL": 0,   "BR": 0,   "TILT": 10},
    "TRISTE":      {"TL": -30,  "TR": 30,  "BL": 20,  "BR": -20, "TILT": -20},
    "SORPRENDIDO": {"TL": 20,   "TR": -20, "BL": -10, "BR": 10,  "TILT": -10},
    "DORMIDO":     {"TL": -100, "TR": 100, "BL": 80,  "BR": -80, "TILT": -30},
    "DUDA":        {"TL": -50,  "TR": 0,   "BL": 0,   "BR": 0,   "TILT": 10},
    "SOSPECHA":    {"TL": -48,  "TR": 29,  "BL": 38,  "BR": -34, "TILT": 0},
    "PENSATIVO":   {"TL": 0,    "TR": 0,   "BL": 10,  "BR": -10, "TILT": 15},
    "NERVIOSO":    {"TL": 0,    "TR": 0,   "BL": 0,   "BR": 0,   "TILT": -5},
}

def objetivo_parpados_para(emocion):
    """Misma lógica que actualizar_objetivo_expresion() en main.py, aislada de
    todo lo demás (sin tocar TILT ni depender de objetivo_actual del firmware)."""
    offsets = OFFSETS_EMOCIONES[emocion]
    return {
        canal: clamp(PARPADOS_REPOSO[canal] + offsets[canal], *LIMITES_PARPADOS[canal])
        for canal in ("TL", "BL", "TR", "BR")
    }


def test_todas_las_emociones_conocidas_tienen_offsets_definidos():
    # v8 ya no cicla una secuencia fija — cualquiera de las 10 puede llegar por
    # el campo EMOCION del serial, así que las 10 deben tener offset definido.
    for emocion in ("NEUTRAL", "FELIZ", "ENOJADO", "TRISTE", "SORPRENDIDO",
                    "DORMIDO", "DUDA", "SOSPECHA", "PENSATIVO", "NERVIOSO"):
        assert emocion in OFFSETS_EMOCIONES


def test_reposo_esta_mas_cerrado_que_el_extremo_totalmente_abierto():
    # El hallazgo original (SORPRENDIDO indistinguible de NEUTRAL) dependía de
    # que el reposo fuera el 100% abierto. Confirma que ya no lo es.
    assert PARPADOS_REPOSO != PARPADOS_ABIERTOS
    assert PARPADOS_REPOSO == {"TL": 130, "BL": 42, "TR": 34, "BR": 132}


def test_neutral_no_mueve_los_parpados_respecto_al_reposo():
    assert objetivo_parpados_para("NEUTRAL") == PARPADOS_REPOSO


def test_ninguna_emocion_saca_los_parpados_de_su_rango_mecanico():
    for emocion in OFFSETS_EMOCIONES:
        objetivo = objetivo_parpados_para(emocion)
        for canal, valor in objetivo.items():
            minimo, maximo = LIMITES_PARPADOS[canal]
            assert minimo <= valor <= maximo, f"{emocion}/{canal}: {valor} fuera de ({minimo},{maximo})"


def test_sorprendido_ahora_si_se_distingue_de_neutral_en_v6():
    # Antes (reposo 100% abierto) los 4 canales clampaban de vuelta al mismo
    # valor que NEUTRAL — no se veía. Con el reposo al 40% de cierre, los 4
    # canales tienen margen y el offset se aplica sin clamping.
    objetivo = objetivo_parpados_para("SORPRENDIDO")
    assert objetivo != PARPADOS_REPOSO
    offsets = OFFSETS_EMOCIONES["SORPRENDIDO"]
    for canal in ("TL", "BL", "TR", "BR"):
        assert objetivo[canal] == PARPADOS_REPOSO[canal] + offsets[canal], (
            f"{canal}: se esperaba el offset sin clamping"
        )


def test_dormido_cierra_los_4_canales_por_completo():
    # Con el reposo más cerrado, el offset de DORMIDO ahora clampa en los 4
    # canales (antes solo en 2) — los párpados llegan a CERRADO por completo,
    # coherente con la expresión de "dormido".
    assert objetivo_parpados_para("DORMIDO") == PARPADOS_CERRADOS


def test_feliz_sube_el_parpado_inferior_izquierdo_y_baja_el_derecho():
    objetivo = objetivo_parpados_para("FELIZ")
    assert objetivo["BL"] > PARPADOS_REPOSO["BL"]
    assert objetivo["BR"] < PARPADOS_REPOSO["BR"]
    # Superiores sin cambio: la expresión "se queda en posición neutral abierta".
    assert objetivo["TL"] == PARPADOS_REPOSO["TL"]
    assert objetivo["TR"] == PARPADOS_REPOSO["TR"]


def test_sospecha_cierra_los_4_canales_bastante_mas_que_neutral():
    objetivo = objetivo_parpados_para("SOSPECHA")
    neutral = objetivo_parpados_para("NEUTRAL")
    for canal in ("TL", "BL", "TR", "BR"):
        distancia_a_cerrado_reposo = abs(PARPADOS_CERRADOS[canal] - PARPADOS_REPOSO[canal])
        distancia_a_cerrado_sospecha = abs(PARPADOS_CERRADOS[canal] - objetivo[canal])
        # SOSPECHA debe estar bastante más cerca de CERRADO que NEUTRAL.
        assert distancia_a_cerrado_sospecha < distancia_a_cerrado_reposo * 0.3
        assert objetivo[canal] != neutral[canal]


# --- Copiado de main.py: barrido de ojos en DUDA -----------------------------

LR_MIN, LR_MAX = 40, 140
DUDA_TRAMO_MS = 2500


def lr_objetivo_duda(transcurrido_ms):
    """Misma lógica que actualizar_objetivo_mirada_expresion() en main.py para
    DUDA, aislada como función pura de "tiempo transcurrido desde que empezó
    DUDA" en vez de leer relojes reales."""
    transcurrido = transcurrido_ms % (DUDA_TRAMO_MS * 2)
    if transcurrido < DUDA_TRAMO_MS:
        progreso = transcurrido / DUDA_TRAMO_MS
        return LR_MIN + progreso * (LR_MAX - LR_MIN)
    else:
        progreso = (transcurrido - DUDA_TRAMO_MS) / DUDA_TRAMO_MS
        return LR_MAX - progreso * (LR_MAX - LR_MIN)


def test_duda_barre_de_un_extremo_al_otro_y_vuelve_en_5_segundos():
    assert lr_objetivo_duda(0) == pytest.approx(LR_MIN)
    assert lr_objetivo_duda(1250) == pytest.approx(90)
    assert lr_objetivo_duda(2500) == pytest.approx(LR_MAX)
    assert lr_objetivo_duda(3750) == pytest.approx(90)
    assert lr_objetivo_duda(5000) == pytest.approx(LR_MIN)  # vuelve al inicio


def test_duda_nunca_sale_del_rango_de_lr():
    for t in range(0, 5000, 100):
        assert LR_MIN <= lr_objetivo_duda(t) <= LR_MAX


# --- Copiado de main.py: mirada fija en PENSATIVO ----------------------------

PENSATIVO_LR, PENSATIVO_UD = 40, 40


def test_pensativo_fija_la_mirada_arriba_a_la_izquierda():
    # LR=40 es el extremo izquierdo; UD=40 es "arriba" en este montaje (mismo
    # criterio que "Mirar hacia arriba" en ojosMecanicos/main.py, que usa
    # valores bajos de UD).
    assert PENSATIVO_LR == LR_MIN
    assert PENSATIVO_UD == 40


# --- Copiado de main.py: recentrado de la mirada al salir de DUDA/PENSATIVO --

def objetivo_mirada_al_cambiar_de_expresion(expresion_anterior, lr_previo, ud_previo):
    """Misma lógica que el bloque de cambio de expresión en main.py: si la
    expresión que termina fijaba la mirada a un lado (DUDA, PENSATIVO,
    NERVIOSO), vuelve al centro antes de empezar la siguiente; si no, no toca
    nada."""
    if expresion_anterior in ("DUDA", "PENSATIVO", "NERVIOSO"):
        return 90.0, 90.0
    return lr_previo, ud_previo


def test_la_mirada_vuelve_al_centro_al_salir_de_duda():
    assert objetivo_mirada_al_cambiar_de_expresion("DUDA", 140, 90) == (90.0, 90.0)


def test_la_mirada_vuelve_al_centro_al_salir_de_pensativo():
    assert objetivo_mirada_al_cambiar_de_expresion("PENSATIVO", 40, 40) == (90.0, 90.0)


def test_la_mirada_no_se_toca_al_salir_de_expresiones_sin_override():
    # El resto de expresiones no fijan la mirada, así que el rastreo facial
    # (lo que sea que haya en LR/UD en ese momento) no debe alterarse.
    assert objetivo_mirada_al_cambiar_de_expresion("FELIZ", 120, 75) == (120, 75)


# --- Copiado de main.py: TRISTE fuerza la cabeza al mínimo mecánico ----------

TILT_MIN_MEC, TILT_MAX_MEC = 40, 140


def tilt_objetivo_para(emocion, tilt_de_cuello):
    """Misma lógica que la rama TRISTE de actualizar_objetivo_expresion(): para
    TRISTE, ignora el TILT que calculó el seguimiento del cuello y fuerza el
    mínimo; para el resto, suma el offset normal y recorta."""
    offset_tilt = OFFSETS_EMOCIONES[emocion]["TILT"]
    if emocion == "TRISTE":
        return TILT_MIN_MEC
    return clamp(tilt_de_cuello + offset_tilt, TILT_MIN_MEC, TILT_MAX_MEC)


def test_triste_fuerza_la_cabeza_al_minimo_sin_importar_el_seguimiento():
    for tilt_de_cuello in (40, 90, 140):
        assert tilt_objetivo_para("TRISTE", tilt_de_cuello) == TILT_MIN_MEC


def test_otras_emociones_siguen_usando_el_offset_relativo_de_tilt():
    # NEUTRAL no mueve el TILT del cuello (offset 0).
    assert tilt_objetivo_para("NEUTRAL", 90) == 90


# --- Copiado de main.py: saltos de mirada al azar en NERVIOSO ---------------

NERVIOSO_SALTO_MS = 1000
NERVIOSO_LR_MIN, NERVIOSO_LR_MAX = 65, 115
NERVIOSO_UD_MIN, NERVIOSO_UD_MAX = 65, 115


def hay_que_saltar_nervioso(transcurrido_desde_ultimo_salto_ms):
    """Misma condición que la rama NERVIOSO de
    actualizar_objetivo_mirada_expresion(): ¿ya pasó el intervalo de salto?"""
    return transcurrido_desde_ultimo_salto_ms >= NERVIOSO_SALTO_MS


def test_nervioso_no_salta_antes_de_tiempo():
    assert hay_que_saltar_nervioso(999) is False


def test_nervioso_salta_al_cumplirse_el_intervalo():
    assert hay_que_saltar_nervioso(1000) is True
    assert hay_que_saltar_nervioso(1500) is True


def test_nervioso_salta_dentro_de_un_rango_moderado_no_los_extremos_mecanicos():
    for _ in range(50):
        lr = random.randint(NERVIOSO_LR_MIN, NERVIOSO_LR_MAX)
        ud = random.randint(NERVIOSO_UD_MIN, NERVIOSO_UD_MAX)
        assert LR_MIN < lr < LR_MAX
        assert NERVIOSO_LR_MIN <= lr <= NERVIOSO_LR_MAX
        assert NERVIOSO_UD_MIN <= ud <= NERVIOSO_UD_MAX


def test_la_mirada_tambien_vuelve_al_centro_al_salir_de_nervioso():
    assert objetivo_mirada_al_cambiar_de_expresion("NERVIOSO", 70, 110) == (90.0, 90.0)


# --- Copiado de main.py: cambio de expresión dirigido por EMOCION (v8) ------
# Novedad de v8: ya no hay una secuencia fija que cicla sola. La expresión
# cambia cuando llega un EMOCION válido por serial, se mantiene durante
# INTERVALO_EXPRESION_MS, y si no llega uno nuevo antes de que expire, vuelve
# sola a NEUTRAL. cambiar_emocion() es el único punto que hace el cambio (lo
# usan tanto procesar_comando() como la expiración del pulso en el bucle
# principal), así que aquí se reproduce como una sola función/estado, igual
# que en el firmware.

INTERVALO_EXPRESION_MS = 5000


class EstadoExpresion:
    """Reproduce la parte de main.py que decide cuándo cambia emocion_actual:
    cambiar_emocion() y el resto de estado que esa función toca (mirada, y los
    temporizadores de inicio de DUDA/NERVIOSO). Aislado de PWM/servos reales."""

    def __init__(self):
        self.emocion_actual = "NEUTRAL"
        self.lr = 90.0
        self.ud = 90.0
        self.inicio_duda = 0
        self.ultimo_salto_nervioso = 0
        self.vence_pulso = 0

    def cambiar_emocion(self, nueva_emocion, ahora):
        anterior = self.emocion_actual
        if anterior == nueva_emocion:
            return
        if anterior in ("DUDA", "PENSATIVO", "NERVIOSO"):
            self.lr = 90.0
            self.ud = 90.0
        self.emocion_actual = nueva_emocion
        if nueva_emocion == "DUDA":
            self.inicio_duda = ahora
        elif nueva_emocion == "NERVIOSO":
            self.ultimo_salto_nervioso = ahora - NERVIOSO_SALTO_MS

    def recibir_emocion(self, nombre, ahora):
        """Misma lógica que procesar_comando() al recibir un tercer campo."""
        if nombre not in OFFSETS_EMOCIONES:
            return
        self.cambiar_emocion(nombre, ahora)
        self.vence_pulso = ahora + INTERVALO_EXPRESION_MS

    def tick(self, ahora):
        """Misma lógica que el bucle principal: revisa si el pulso expiró."""
        if self.emocion_actual != "NEUTRAL" and ahora >= self.vence_pulso:
            self.cambiar_emocion("NEUTRAL", ahora)


def test_una_emocion_nueva_activa_el_pulso():
    estado = EstadoExpresion()
    estado.recibir_emocion("FELIZ", 0)
    assert estado.emocion_actual == "FELIZ"
    assert estado.vence_pulso == INTERVALO_EXPRESION_MS


def test_el_pulso_expira_a_los_5_segundos_y_vuelve_a_neutral():
    estado = EstadoExpresion()
    estado.recibir_emocion("FELIZ", 0)
    estado.tick(4999)
    assert estado.emocion_actual == "FELIZ", "no debe volver antes de que expire"
    estado.tick(5000)
    assert estado.emocion_actual == "NEUTRAL"


def test_una_emocion_nueva_antes_de_expirar_reemplaza_el_pulso_en_curso():
    estado = EstadoExpresion()
    estado.recibir_emocion("FELIZ", 0)
    estado.recibir_emocion("ENOJADO", 2000)  # antes de que FELIZ expire (5000)
    estado.tick(4999)
    assert estado.emocion_actual == "ENOJADO", "ENOJADO todavía no debería expirar"
    estado.tick(7000)  # 2000 + 5000
    assert estado.emocion_actual == "NEUTRAL"


def test_recibir_la_misma_emocion_repetida_extiende_el_pulso():
    # Frases consecutivas con la misma emoción no deben hacer parpadear la
    # expresión de vuelta a NEUTRAL entre una y otra.
    estado = EstadoExpresion()
    estado.recibir_emocion("TRISTE", 0)
    estado.recibir_emocion("TRISTE", 4000)  # refresca el pulso antes de expirar
    estado.tick(8999)  # 4000 + 5000 - 1, no debería haber expirado aún
    assert estado.emocion_actual == "TRISTE"
    estado.tick(9000)
    assert estado.emocion_actual == "NEUTRAL"


def test_emocion_no_reconocida_se_ignora_por_completo():
    estado = EstadoExpresion()
    estado.recibir_emocion("ALEGRIA_INVENTADA", 0)
    assert estado.emocion_actual == "NEUTRAL"
    assert estado.vence_pulso == 0, "no debería haber activado ningún pulso"


def test_recibir_duda_reinicia_su_temporizador_de_barrido():
    estado = EstadoExpresion()
    estado.recibir_emocion("DUDA", 1000)
    assert estado.inicio_duda == 1000


def test_recibir_nervioso_deja_listo_el_primer_salto_inmediato():
    estado = EstadoExpresion()
    estado.recibir_emocion("NERVIOSO", 1000)
    assert estado.ultimo_salto_nervioso == 1000 - NERVIOSO_SALTO_MS


def test_salir_de_duda_por_una_emocion_nueva_recentra_la_mirada():
    estado = EstadoExpresion()
    estado.recibir_emocion("DUDA", 0)
    estado.lr, estado.ud = 140, 40  # como si el barrido la hubiera dejado a un lado
    estado.recibir_emocion("SORPRENDIDO", 1000)
    assert (estado.lr, estado.ud) == (90.0, 90.0)


def test_salir_de_nervioso_al_expirar_el_pulso_tambien_recentra_la_mirada():
    estado = EstadoExpresion()
    estado.recibir_emocion("NERVIOSO", 0)
    estado.lr, estado.ud = 65, 115  # como si un salto al azar la hubiera dejado ahí
    estado.tick(5000)  # el pulso expira, vuelve a NEUTRAL
    assert estado.emocion_actual == "NEUTRAL"
    assert (estado.lr, estado.ud) == (90.0, 90.0)
