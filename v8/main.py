# v8 — Firmware MicroPython para la Raspberry Pi Pico.
#
# Ojos abiertos + rastreo x,y + cuello (PAN/TILT amortiguado) + parpadeo periódico
# + expresión facial dirigida por el campo EMOCION del comando serial, generando
# el PWM de cada servo directamente desde los pines de la propia Pico
# (machine.PWM), SIN pasar por un controlador PCA9685 ni por I2C.
#
# Cambio de fondo respecto a v6/v7: hasta ahora, la expresión cambiaba sola cada
# 5 segundos, cicladas en un orden fijo, sin depender de nada externo. En v8 eso
# se reemplaza por un modelo dirigido por eventos: cada vez que llega
# "LR,UD,EMOCION\n" con un campo EMOCION válido, la Pico adopta esa expresión y
# la mantiene durante INTERVALO_EXPRESION_MS (5000ms, el mismo valor de antes,
# ahora usado como duración del "pulso" en vez de periodo del ciclo) — pasado ese
# tiempo sin una emoción nueva, vuelve sola a NEUTRAL, que es el estado base.
# Pensado para que el Mac (v8/realtime_voice.py) envíe la emoción detectada en
# cada frase de la conversación (ver sentiment_analyzer.py y el mapeo a las 10
# emociones de la Pico en README-v8.md) — la cara reacciona a la conversación,
# no a un temporizador ciego. Los offsets de párpados/cuello por emoción son los
# mismos de v6/v7 (OFFSETS_EMOCIONES, con FELIZ y SOSPECHA recalculados — ver el
# comentario junto a OFFSETS_EMOCIONES), aplicados sobre una posición de reposo
# fija de los párpados, no completamente abierta (v8 no sincroniza los párpados
# con la mirada todavía, a diferencia del original — ver PARPADOS_REPOSO).
#
# v8 todavía NO incluye rastreo facial real (eso es v9, a propósito — ver
# README-v8.md): LR/UD se aceptan por serial igual que siempre, pero el Mac de
# esta versión no tiene cámara conectada y manda un valor fijo (90,90) junto con
# cada EMOCION. DUDA, PENSATIVO y NERVIOSO siguen ignorando LR/UD y fijando o
# moviendo la mirada por su cuenta mientras están activas — así fueron
# construidas desde v6, sin cambios aquí.
#
# Por qué no hay PCA9685: en v5, la primera versión de este firmware sí lo usaba
# (sigue disponible en ../v5/main_pca9685.py, como referencia histórica — no se
# duplicó aquí porque está retirada, no es "base funcional") y daba tres problemas
# en hardware real: temblor aleatorio al encender, un temblor periódico disparado
# por el parpadeo (que empeoraba, no mejoraba, al ajustar su temporización), y el
# eje PAN sin moverse en absoluto. Al quitar el PCA9685 y generar el PWM directo
# desde la Pico, los tres problemas desaparecieron a la vez — confirmado en
# hardware real: "todos los motores se mueven y parpadea sin vibraciones". Esto
# señala al chip PCA9685 o a la comunicación I2C con él como la causa de fondo.
# Cronología completa en ../v5/README-v5.md, sección "Historial de depuración".
#
# Mapeo de pines (cada par comparte "slice" de PWM en el RP2040, pero como los 8
# servos usan la misma frecuencia de 50Hz, comparten slice sin ningún conflicto):
#   LR=GP2  UD=GP3  TL=GP4  BL=GP5  TR=GP6  BR=GP7  PAN=GP8  TILT=GP9
#
# Acepta "LR,UD\n" (sin cambiar de expresión) o "LR,UD,EMOCION\n". A diferencia
# de v3-v7, aquí el tercer campo ya NO se ignora: dispara el cambio de expresión
# descrito arriba. El Mac (pico_serial.py, copia propia de v8) no necesita
# ningún cambio — el protocolo es el mismo de siempre.

import machine
import random
import select
import sys
import time

# --- Conversión de grados a PWM ----------------------------------------------
# Mismo rango de pulso que el PCA9685 (102-512 en registros de 12 bits a 50Hz
# equivale a ~498-2500 microsegundos): mismos grados, misma posición física.
PULSO_MIN_US, PULSO_MAX_US = 500, 2500
FREQ_SERVO = 50
PERIODO_US = 1_000_000 / FREQ_SERVO  # 20000us a 50Hz


def grados_a_duty_u16(grados):
    us = PULSO_MIN_US + (grados / 180.0) * (PULSO_MAX_US - PULSO_MIN_US)
    return int((us / PERIODO_US) * 65535)


CANAL_LR, CANAL_UD = "LR", "UD"
CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR = "TL", "BL", "TR", "BR"
CANAL_PAN, CANAL_TILT = "PAN", "TILT"

PIN_DE_CANAL = {
    CANAL_LR: 2, CANAL_UD: 3,
    CANAL_TL: 4, CANAL_BL: 5, CANAL_TR: 6, CANAL_BR: 7,
    CANAL_PAN: 8, CANAL_TILT: 9,
}

pwm_de_canal = {}
for _canal, _pin in PIN_DE_CANAL.items():
    _pwm = machine.PWM(machine.Pin(_pin))
    _pwm.freq(FREQ_SERVO)
    pwm_de_canal[_canal] = _pwm


def mover_servo(canal, grados):
    pwm_de_canal[canal].duty_u16(grados_a_duty_u16(grados))


# (cerrado, abierto) para los párpados — mismos valores que model.md/main.py.
PARPADOS_ABIERTOS = {CANAL_TL: 170, CANAL_BL: 10, CANAL_TR: 10, CANAL_BR: 160}
PARPADOS_CERRADOS = {CANAL_TL: 70, CANAL_BL: 90, CANAL_TR: 70, CANAL_BR: 90}

# Posición real de reposo (usada por NEUTRAL y como base de todos los offsets de
# expresión): NO es el extremo 100% abierto, sino un 40% del camino hacia
# CERRADO. Pedido explícito tras probar en hardware real: con los párpados en
# reposo totalmente abiertos, SORPRENDIDO (que empuja hacia "más abierto
# todavía") no tenía margen mecánico para distinguirse de NEUTRAL — los 4
# canales clampaban de vuelta exactamente al mismo valor (ver
# ../v6/README-v6.md, sección "Ajustes de realismo", donde se resolvió esto
# por primera vez). 40% es el mínimo con margen cómodo en
# los 4 canales de SORPRENDIDO (el canal TR es el más exigente, con un mínimo
# de ~34%).
CIERRE_REPOSO = 0.40
PARPADOS_REPOSO = {
    canal: PARPADOS_ABIERTOS[canal] + CIERRE_REPOSO * (PARPADOS_CERRADOS[canal] - PARPADOS_ABIERTOS[canal])
    for canal in PARPADOS_ABIERTOS
}

# Límites mecánicos por canal, como (mínimo, máximo) — a diferencia de
# PARPADOS_ABIERTOS/CERRADOS, aquí el orden no importa el sentido "abierto" o
# "cerrado", solo sirve para no forzar un servo más allá de su rango físico al
# sumarle el offset de una emoción. Copiado de servo_limits en
# ojosMecanicos/main.py: "TL": (70,170), "BL": (90,10), "TR": (70,10), "BR": (90,160).
LIMITES_PARPADOS = {
    CANAL_TL: (70, 170),
    CANAL_BL: (10, 90),
    CANAL_TR: (10, 70),
    CANAL_BR: (90, 160),
}

LR_MIN, LR_MAX = 40, 140
UD_MIN, UD_MAX = 40, 140
PAN_MIN, PAN_MAX = 40, 140
TILT_MIN, TILT_MAX = 40, 140

FACTOR_PAN = 0.8
FACTOR_TILT = 0.6

ALPHA = 0.1

PARPADEO_ACTIVO = True    # False lo desactiva por completo, para pruebas
ESPACIADO_PARPADEO_S = 0.05  # separación entre cada servo de párpado al parpadear

# DUDA: en vez de seguir el rastreo facial, los ojos barren solos de un extremo
# a otro de LR — gesto de "pensando, mirando de lado a lado". Un tramo (de un
# extremo al otro) tarda esto; como INTERVALO_EXPRESION_MS son 5000ms, un tramo
# de 2500ms completa una ida y vuelta entera durante toda la expresión.
DUDA_TRAMO_MS = 2500

# PENSATIVO: en vez de seguir el rastreo facial, los ojos (y el cuello, que los
# sigue) se fijan mirando arriba a la izquierda. UD=40 es "arriba" en este
# montaje — mismo criterio que ojosMecanicos/main.py, donde "mirar hacia
# arriba" usa valores bajos de UD (random.randint(40, 60)).
PENSATIVO_LR, PENSATIVO_UD = 40, 40

# NERVIOSO: en vez de seguir el rastreo facial, los ojos saltan solos a un
# punto al azar cada segundo — gesto de "mirando a cualquier lado, evitando
# el contacto visual". Rango moderado (no los extremos mecánicos): saltos
# claramente notorios sin llegar a un movimiento exagerado.
NERVIOSO_SALTO_MS = 1000
NERVIOSO_LR_MIN, NERVIOSO_LR_MAX = 65, 115
NERVIOSO_UD_MIN, NERVIOSO_UD_MAX = 65, 115

# Offsets de párpados y cuello por emoción, copiados literalmente de
# OFFSETS_EMOCIONES en ojosMecanicos/main.py, salvo FELIZ y SOSPECHA (ver abajo).
# No se incluye el offset de PAN: en las 10 emociones originales siempre es 0,
# así que no hay nada que aplicar.
OFFSETS_EMOCIONES = {
    "NEUTRAL":     {"TL": 0,    "TR": 0,   "BL": 0,   "BR": 0,   "TILT": 0},
    # FELIZ recalculado para v6 (no es el de ojosMecanicos): con los párpados ya
    # al 40% de cierre en reposo, el offset original (+30/-30, pensado para una
    # base 100% abierta) apenas se notaba. Recalculado para que el párpado
    # inferior suba un 50% del camino restante hacia CERRADO desde el reposo
    # (BL: 42+24=66 de 90; BR: 132-21=111 de 90) — el superior se queda en la
    # posición neutral (offset 0, sin cambio).
    "FELIZ":       {"TL": 0,    "TR": 0,   "BL": 24,  "BR": -21, "TILT": 0},
    "ENOJADO":     {"TL": -40,  "TR": 40,  "BL": 0,   "BR": 0,   "TILT": 10},
    # El TILT de TRISTE (-20, el de ojosMecanicos) queda aquí sin usarse: la
    # cabeza gacha se fuerza al mínimo mecánico en actualizar_objetivo_expresion(),
    # no como offset relativo — ver esa función.
    "TRISTE":      {"TL": -30,  "TR": 30,  "BL": 20,  "BR": -20, "TILT": -20},
    "SORPRENDIDO": {"TL": 20,   "TR": -20, "BL": -10, "BR": 10,  "TILT": -10},
    "DORMIDO":     {"TL": -100, "TR": 100, "BL": 80,  "BR": -80, "TILT": -30},
    "DUDA":        {"TL": -50,  "TR": 0,   "BL": 0,   "BR": 0,   "TILT": 10},
    # SOSPECHA recalculado para v6, mismo motivo que FELIZ: los 4 canales
    # cierran un 80% del camino restante hacia CERRADO desde el reposo.
    "SOSPECHA":    {"TL": -48,  "TR": 29,  "BL": 38,  "BR": -34, "TILT": 0},
    "PENSATIVO":   {"TL": 0,    "TR": 0,   "BL": 10,  "BR": -10, "TILT": 15},
    "NERVIOSO":    {"TL": 0,    "TR": 0,   "BL": 0,   "BR": 0,   "TILT": -5},
}

# Duración del "pulso" de cada expresión recibida por serial: cuánto se mantiene
# antes de volver sola a NEUTRAL si no llega una emoción nueva. Mismo valor que
# el periodo del ciclo fijo en v6/v7 (5000ms), reutilizado con otro propósito.
INTERVALO_EXPRESION_MS = 5000

emocion_actual = "NEUTRAL"

# Los párpados entran al sistema de suavizado EMA igual que LR/UD/PAN/TILT, para
# que el cambio de expresión sea una transición suave, no un salto brusco.
EJES = (CANAL_LR, CANAL_UD, CANAL_PAN, CANAL_TILT, CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR)

posicion_actual = {CANAL_LR: 90.0, CANAL_UD: 90.0, CANAL_PAN: 90.0, CANAL_TILT: 90.0}
posicion_actual.update({canal: float(grados) for canal, grados in PARPADOS_REPOSO.items()})
objetivo_actual = dict(posicion_actual)


def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


# ==========================================
# INICIALIZACIÓN: ojos abiertos, mirada y cuello centrados, una sola vez.
# ==========================================
print("v8: iniciando (rastreo de ojos + cuello + parpadeo + expresión dirigida por EMOCION)...")

for canal, grados in PARPADOS_REPOSO.items():
    mover_servo(canal, grados)
    time.sleep(0.1)

for eje in (CANAL_LR, CANAL_UD, CANAL_PAN, CANAL_TILT):
    mover_servo(eje, 90)
    time.sleep(0.1)

print("Ojos y cuello centrados, párpados en reposo. Esperando \"LR,UD\" por serial.")
print("Expresión inicial:", emocion_actual)

# ==========================================
# LECTURA DESDE USB SERIAL
# ==========================================
lector_serial = select.poll()
lector_serial.register(sys.stdin, select.POLLIN)


def cambiar_emocion(nueva_emocion, ahora):
    """Cambia emocion_actual, con lo que hace falta al salir de una expresión
    que fijaba la mirada (DUDA/PENSATIVO/NERVIOSO) y al entrar a DUDA/NERVIOSO
    (reiniciar sus temporizadores). La usan tanto procesar_comando() (cuando
    llega un EMOCION nuevo por serial) como el bucle principal (cuando el pulso
    de INTERVALO_EXPRESION_MS expira y toca volver a NEUTRAL) — es el único
    punto donde se cambia de expresión, para no duplicar esta lógica dos veces."""
    global emocion_actual, inicio_duda, ultimo_salto_nervioso
    anterior = emocion_actual
    if anterior == nueva_emocion:
        return
    if anterior in ("DUDA", "PENSATIVO", "NERVIOSO"):
        objetivo_actual[CANAL_LR] = 90.0
        objetivo_actual[CANAL_UD] = 90.0
    emocion_actual = nueva_emocion
    if emocion_actual == "DUDA":
        inicio_duda = ahora
    elif emocion_actual == "NERVIOSO":
        # Resta el intervalo para que el primer salto sea inmediato, no que
        # espere 1s desde el cambio de expresión.
        ultimo_salto_nervioso = time.ticks_add(ahora, -NERVIOSO_SALTO_MS)
    print("Expresión:", emocion_actual)


def procesar_comando(linea):
    global vence_pulso_emocion
    try:
        partes = linea.strip().split(",")
        if len(partes) < 2:
            return False
        lr = clamp(int(partes[0]), LR_MIN, LR_MAX)
        ud = clamp(int(partes[1]), UD_MIN, UD_MAX)

        if len(partes) >= 3:
            emocion_recibida = partes[2].strip().upper()
            if emocion_recibida in OFFSETS_EMOCIONES:
                ahora = time.ticks_ms()
                # Antes de aplicar el LR/UD de este mismo comando: si toca
                # resetear la mirada al salir de DUDA/PENSATIVO/NERVIOSO, que
                # el valor real recibido a continuación tenga la última palabra.
                cambiar_emocion(emocion_recibida, ahora)
                vence_pulso_emocion = time.ticks_add(ahora, INTERVALO_EXPRESION_MS)

        objetivo_actual[CANAL_LR] = float(lr)
        objetivo_actual[CANAL_UD] = float(ud)
        print("Serial: LR={}, UD={}".format(lr, ud))
        return True
    except (ValueError, IndexError):
        return False


def actualizar_objetivo_cuello():
    objetivo_pan = 90 + (objetivo_actual[CANAL_LR] - 90) * FACTOR_PAN
    objetivo_tilt = 90 + (objetivo_actual[CANAL_UD] - 90) * FACTOR_TILT
    objetivo_actual[CANAL_PAN] = clamp(objetivo_pan, PAN_MIN, PAN_MAX)
    objetivo_actual[CANAL_TILT] = clamp(objetivo_tilt, TILT_MIN, TILT_MAX)


def actualizar_objetivo_expresion():
    """Aplica los offsets de la emoción actual sobre la posición de reposo fija
    de los párpados (v8 no sincroniza párpados con la mirada todavía) y, salvo
    en TRISTE (ver abajo), los suma al TILT ya calculado por
    actualizar_objetivo_cuello() en esta misma vuelta del bucle. Debe llamarse
    después de esa función, no antes."""
    offsets = OFFSETS_EMOCIONES[emocion_actual]
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        base = PARPADOS_REPOSO[canal]
        minimo, maximo = LIMITES_PARPADOS[canal]
        objetivo_actual[canal] = clamp(base + offsets[canal], minimo, maximo)
    if emocion_actual == "TRISTE":
        # Cabeza gacha hasta el tope mecánico (pedido explícito, "hasta el
        # mínimo inferior"), no un offset relativo sobre el TILT que sigue a
        # la mirada — así se nota siempre igual de marcada, sin importar hacia
        # dónde esté mirando el rastreo facial en ese momento.
        objetivo_actual[CANAL_TILT] = TILT_MIN
    else:
        objetivo_actual[CANAL_TILT] = clamp(
            objetivo_actual[CANAL_TILT] + offsets["TILT"], TILT_MIN, TILT_MAX
        )


def actualizar_objetivo_mirada_expresion():
    """Para las expresiones que fijan la mirada en vez de seguir el rastreo
    facial (DUDA, PENSATIVO, NERVIOSO), sobreescribe objetivo_actual[LR]/[UD]
    aquí, antes de que actualizar_objetivo_cuello() calcule PAN/TILT a partir
    de ellos — así el cuello también acompaña el gesto. Para el resto de
    expresiones no hace nada y el rastreo normal (procesar_comando) sigue
    mandando."""
    global ultimo_salto_nervioso
    if emocion_actual == "DUDA":
        transcurrido = time.ticks_diff(time.ticks_ms(), inicio_duda) % (DUDA_TRAMO_MS * 2)
        if transcurrido < DUDA_TRAMO_MS:
            progreso = transcurrido / DUDA_TRAMO_MS
            objetivo_actual[CANAL_LR] = LR_MIN + progreso * (LR_MAX - LR_MIN)
        else:
            progreso = (transcurrido - DUDA_TRAMO_MS) / DUDA_TRAMO_MS
            objetivo_actual[CANAL_LR] = LR_MAX - progreso * (LR_MAX - LR_MIN)
    elif emocion_actual == "PENSATIVO":
        objetivo_actual[CANAL_LR] = PENSATIVO_LR
        objetivo_actual[CANAL_UD] = PENSATIVO_UD
    elif emocion_actual == "NERVIOSO":
        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, ultimo_salto_nervioso) >= NERVIOSO_SALTO_MS:
            objetivo_actual[CANAL_LR] = float(random.randint(NERVIOSO_LR_MIN, NERVIOSO_LR_MAX))
            objetivo_actual[CANAL_UD] = float(random.randint(NERVIOSO_UD_MIN, NERVIOSO_UD_MAX))
            ultimo_salto_nervioso = ahora


def parpadear():
    """Cierra y reabre los párpados. Reabre a la posición de la expresión actual
    (objetivo_actual), no siempre a "abierto" — con FELIZ, por ejemplo, la
    posición de reposo de los párpados ya no es la neutral."""
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        mover_servo(canal, PARPADOS_CERRADOS[canal])
        time.sleep(ESPACIADO_PARPADEO_S)
    time.sleep(0.15)
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        objetivo = int(objetivo_actual[canal])
        mover_servo(canal, objetivo)
        posicion_actual[canal] = float(objetivo)  # evita un salto en el próximo suavizado
        time.sleep(ESPACIADO_PARPADEO_S)


# ==========================================
# BUCLE PRINCIPAL
# ==========================================
proximo_parpadeo = time.ticks_add(time.ticks_ms(), random.randint(2000, 6000))
vence_pulso_emocion = time.ticks_ms()  # sin efecto hasta que llegue el primer EMOCION
inicio_duda = time.ticks_ms()  # se reinicia cada vez que empieza una DUDA nueva
ultimo_salto_nervioso = time.ticks_ms()  # se reinicia cada vez que empieza un NERVIOSO nuevo

try:
    while True:
        if lector_serial.poll(0):
            try:
                linea = sys.stdin.readline()
                if linea:
                    procesar_comando(linea)
            except Exception:
                pass

        actualizar_objetivo_mirada_expresion()
        actualizar_objetivo_cuello()
        actualizar_objetivo_expresion()

        for eje in EJES:
            objetivo = objetivo_actual[eje]
            actual = posicion_actual[eje]
            if abs(objetivo - actual) > 0.5:
                actual = (objetivo * ALPHA) + (actual * (1 - ALPHA))
                mover_servo(eje, int(actual))
                posicion_actual[eje] = actual

        ahora = time.ticks_ms()

        # No parpadea con DORMIDO activo (los párpados ya están casi cerrados
        # por el offset) — mismo criterio que ojosMecanicos/main.py.
        if (PARPADEO_ACTIVO and emocion_actual != "DORMIDO"
                and time.ticks_diff(ahora, proximo_parpadeo) > 0):
            parpadear()
            proximo_parpadeo = time.ticks_add(ahora, random.randint(2000, 6000))

        # El pulso de la expresión actual expiró sin que llegara una emoción
        # nueva: vuelve sola a NEUTRAL, el estado base.
        if emocion_actual != "NEUTRAL" and time.ticks_diff(ahora, vence_pulso_emocion) > 0:
            cambiar_emocion("NEUTRAL", ahora)

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nDeteniendo... centrando ojos y cuello.")
    for eje in (CANAL_LR, CANAL_UD, CANAL_PAN, CANAL_TILT):
        mover_servo(eje, 90)
