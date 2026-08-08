# v6 — Firmware MicroPython para la Raspberry Pi Pico.
#
# Ojos abiertos + rastreo x,y + cuello (PAN/TILT amortiguado) + parpadeo periódico
# + secuencia de expresiones faciales, generando el PWM de cada servo directamente
# desde los pines de la propia Pico (machine.PWM), SIN pasar por un controlador
# PCA9685 ni por I2C.
#
# Expresiones: por ahora cambian solas cada 5 segundos, cicladas en orden fijo —
# todavía no dependen de voz ni de sentimiento (eso es trabajo futuro). Los
# offsets de párpados/cuello por emoción son los mismos 10 de
# ojosMecanicos/main.py (OFFSETS_EMOCIONES), copiados literalmente, aplicados
# sobre la posición "abierta" fija de los párpados (v6 no sincroniza los párpados
# con la mirada todavía, a diferencia del original).
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
# Acepta "LR,UD\n" o "LR,UD,EMOCION\n" (formato de v3/v4) ignorando el tercer
# campo: el Mac (pico_serial.py, copia propia de v6) no necesita ningún cambio.

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

# Offsets de párpados y cuello por emoción, copiados literalmente de
# OFFSETS_EMOCIONES en ojosMecanicos/main.py. No se incluye el offset de PAN: en
# las 10 emociones originales siempre es 0, así que no hay nada que aplicar.
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

# Orden fijo de la secuencia y cuánto dura cada expresión. Por ahora es un ciclo
# mecánico, sin depender de voz ni de sentimiento — eso es trabajo futuro.
SECUENCIA_EMOCIONES = ("NEUTRAL", "FELIZ", "ENOJADO", "TRISTE", "SORPRENDIDO",
                       "DORMIDO", "DUDA", "SOSPECHA", "PENSATIVO", "NERVIOSO")
INTERVALO_EXPRESION_MS = 5000

indice_emocion = 0
emocion_actual = SECUENCIA_EMOCIONES[indice_emocion]

# Los párpados entran al sistema de suavizado EMA igual que LR/UD/PAN/TILT, para
# que el cambio de expresión sea una transición suave, no un salto brusco.
EJES = (CANAL_LR, CANAL_UD, CANAL_PAN, CANAL_TILT, CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR)

posicion_actual = {CANAL_LR: 90.0, CANAL_UD: 90.0, CANAL_PAN: 90.0, CANAL_TILT: 90.0}
posicion_actual.update({canal: float(grados) for canal, grados in PARPADOS_ABIERTOS.items()})
objetivo_actual = dict(posicion_actual)


def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


# ==========================================
# INICIALIZACIÓN: ojos abiertos, mirada y cuello centrados, una sola vez.
# ==========================================
print("v6: iniciando (rastreo de ojos + cuello + parpadeo + expresiones)...")

for canal, grados in PARPADOS_ABIERTOS.items():
    mover_servo(canal, grados)
    time.sleep(0.1)

for eje in (CANAL_LR, CANAL_UD, CANAL_PAN, CANAL_TILT):
    mover_servo(eje, 90)
    time.sleep(0.1)

print("Ojos y cuello centrados, párpados abiertos. Esperando \"LR,UD\" por serial.")
print("Expresión inicial:", emocion_actual)

# ==========================================
# LECTURA DESDE USB SERIAL
# ==========================================
lector_serial = select.poll()
lector_serial.register(sys.stdin, select.POLLIN)


def procesar_comando(linea):
    try:
        partes = linea.strip().split(",")
        if len(partes) < 2:
            return False
        lr = clamp(int(partes[0]), LR_MIN, LR_MAX)
        ud = clamp(int(partes[1]), UD_MIN, UD_MAX)
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
    """Aplica los offsets de la emoción actual sobre la base "abierta" fija de
    los párpados (v6 no sincroniza párpados con la mirada todavía) y los suma al
    TILT ya calculado por actualizar_objetivo_cuello() en esta misma vuelta del
    bucle. Debe llamarse después de esa función, no antes."""
    offsets = OFFSETS_EMOCIONES[emocion_actual]
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        base = PARPADOS_ABIERTOS[canal]
        minimo, maximo = LIMITES_PARPADOS[canal]
        objetivo_actual[canal] = clamp(base + offsets[canal], minimo, maximo)
    objetivo_actual[CANAL_TILT] = clamp(
        objetivo_actual[CANAL_TILT] + offsets["TILT"], TILT_MIN, TILT_MAX
    )


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
proxima_expresion = time.ticks_add(time.ticks_ms(), INTERVALO_EXPRESION_MS)

try:
    while True:
        if lector_serial.poll(0):
            try:
                linea = sys.stdin.readline()
                if linea:
                    procesar_comando(linea)
            except Exception:
                pass

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

        if time.ticks_diff(ahora, proxima_expresion) > 0:
            indice_emocion = (indice_emocion + 1) % len(SECUENCIA_EMOCIONES)
            emocion_actual = SECUENCIA_EMOCIONES[indice_emocion]
            print("Expresión:", emocion_actual)
            proxima_expresion = time.ticks_add(ahora, INTERVALO_EXPRESION_MS)

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nDeteniendo... centrando ojos y cuello.")
    for eje in (CANAL_LR, CANAL_UD, CANAL_PAN, CANAL_TILT):
        mover_servo(eje, 90)
