# v5 (variante) — Firmware MicroPython para la Raspberry Pi Pico, SIN el PCA9685.
#
# Misma funcionalidad que main.py (ojos abiertos + rastreo x,y + cuello + parpadeo
# periódico), pero generando el PWM de cada servo directamente desde los pines de
# la propia Pico (machine.PWM), sin pasar por el controlador PCA9685 ni por I2C.
#
# Por qué existe este fichero: al depurar un temblor aleatorio y luego uno periódico
# (ver README-v5.md), se agotaron las hipótesis de temporización y de firmware sin
# encontrar el bug. Este fichero es un experimento para aislar si el PCA9685/I2C es
# parte del problema (ruido en el bus, estado propio del chip al arrancar, etc.).
#
# Lo que este cambio SÍ puede descartar: cualquier problema específico del chip
# PCA9685 o de la comunicación I2C con él.
# Lo que este cambio NO puede arreglar: si la causa real es que la fuente de
# alimentación no aguanta el pico de corriente de varios servos moviéndose a la
# vez, mover el PWM a la Pico no cambia nada — los servos siguen tirando de la
# misma corriente, de la misma fuente. Esa hipótesis solo se descarta con hardware
# (una fuente con más margen, o un condensador de buffer en el riel de los servos).
#
# Mapeo de pines (cada par comparte "slice" de PWM en el RP2040, pero como los 8
# servos usan la misma frecuencia de 50Hz, comparten slice sin ningún conflicto):
#   LR=GP2  UD=GP3  TL=GP4  BL=GP5  TR=GP6  BR=GP7  PAN=GP8  TILT=GP9
#
# Aviso sin confirmar, paralelo al de /OE en la versión con PCA9685: los GPIOs de
# la Pico también empiezan en alta impedancia (flotando) hasta que el código los
# configura como PWM, así que en teoría el mismo temblor de arranque original
# podría reaparecer aquí, a menos que se añadan resistencias de pull-down externas
# en cada una de las 8 líneas de señal (no solo una, como bastaba con /OE). No se
# ha probado si hace falta.
#
# Acepta "LR,UD\n" o "LR,UD,EMOCION\n" igual que main.py — protocolo sin cambios.

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

LR_MIN, LR_MAX = 40, 140
UD_MIN, UD_MAX = 40, 140
PAN_MIN, PAN_MAX = 40, 140
TILT_MIN, TILT_MAX = 40, 140

FACTOR_PAN = 0.8
FACTOR_TILT = 0.6

ALPHA = 0.1

PARPADEO_ACTIVO = True
ESPACIADO_PARPADEO_S = 0.05

EJES = (CANAL_LR, CANAL_UD, CANAL_PAN, CANAL_TILT)

posicion_actual = {CANAL_LR: 90.0, CANAL_UD: 90.0, CANAL_PAN: 90.0, CANAL_TILT: 90.0}
objetivo_actual = {CANAL_LR: 90.0, CANAL_UD: 90.0, CANAL_PAN: 90.0, CANAL_TILT: 90.0}


def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


# ==========================================
# INICIALIZACIÓN: ojos abiertos, mirada y cuello centrados, una sola vez.
# ==========================================
print("v5 (PWM directo, sin PCA9685): iniciando...")

for canal, grados in PARPADOS_ABIERTOS.items():
    mover_servo(canal, grados)
    time.sleep(0.1)

for eje in EJES:
    mover_servo(eje, 90)
    time.sleep(0.1)

print("Ojos y cuello centrados, párpados abiertos. Esperando \"LR,UD\" por serial.")

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


def parpadear():
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        mover_servo(canal, PARPADOS_CERRADOS[canal])
        time.sleep(ESPACIADO_PARPADEO_S)
    time.sleep(0.15)
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        mover_servo(canal, PARPADOS_ABIERTOS[canal])
        time.sleep(ESPACIADO_PARPADEO_S)


# ==========================================
# BUCLE PRINCIPAL
# ==========================================
ultimo_parpadeo_en = time.ticks_ms()
proximo_parpadeo = time.ticks_add(ultimo_parpadeo_en, random.randint(2000, 6000))
vueltas_de_bucle = 0

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

        for eje in EJES:
            objetivo = objetivo_actual[eje]
            actual = posicion_actual[eje]
            if abs(objetivo - actual) > 0.5:
                actual = (objetivo * ALPHA) + (actual * (1 - ALPHA))
                mover_servo(eje, int(actual))
                posicion_actual[eje] = actual

        ahora = time.ticks_ms()
        if PARPADEO_ACTIVO and time.ticks_diff(ahora, proximo_parpadeo) > 0:
            transcurrido = time.ticks_diff(ahora, ultimo_parpadeo_en)
            print(f"[parpadeo] han pasado {transcurrido}ms, {vueltas_de_bucle} "
                  f"vueltas de bucle desde el anterior")
            parpadear()
            ultimo_parpadeo_en = ahora
            vueltas_de_bucle = 0
            proximo_parpadeo = time.ticks_add(ahora, random.randint(2000, 6000))
        else:
            vueltas_de_bucle += 1

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nDeteniendo... centrando ojos y cuello.")
    for eje in EJES:
        mover_servo(eje, 90)
