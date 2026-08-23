# v10 — Utilidad: lleva los 8 servos a la posición base (90°) y los mantiene ahí.
#
# Independiente de main.py (que hace todo el rastreo + cuello + parpadeo). Pensada
# para dos casos:
#   1. Dejar el rig en una posición segura y conocida antes de desconectar la
#      alimentación (en vez de apagar con los servos en cualquier posición).
#   2. Recuperar un estado neutral tras un error o para calibrar/inspeccionar el
#      hardware, sin la lógica de rastreo/parpadeo de por medio.
#
# Mismo mapeo de pines y misma fórmula de pulso que main.py (PWM directo desde la
# Pico, sin PCA9685 — ver ../v5/README-v5.md para por qué):
#   LR=GP2  UD=GP3  TL=GP4  BL=GP5  TR=GP6  BR=GP7  PAN=GP8  TILT=GP9
#
# Uso: cópialo a la Pico (con Thonny o mpremote) y ejecútalo en vez de main.py, o
# renómbralo a main.py si quieres que sea lo que arranca por defecto.

import machine
import time

PULSO_MIN_US, PULSO_MAX_US = 500, 2500
FREQ_SERVO = 50
PERIODO_US = 1_000_000 / FREQ_SERVO  # 20000us a 50Hz


def grados_a_duty_u16(grados):
    us = PULSO_MIN_US + (grados / 180.0) * (PULSO_MAX_US - PULSO_MIN_US)
    return int((us / PERIODO_US) * 65535)


PIN_DE_CANAL = {
    "LR": 2, "UD": 3,
    "TL": 4, "BL": 5, "TR": 6, "BR": 7,
    "PAN": 8, "TILT": 9,
}

GRADOS_BASE = 90

print("Estado base: centrando los 8 servos a {}°...".format(GRADOS_BASE))

pwm_de_canal = {}
duty_base = grados_a_duty_u16(GRADOS_BASE)
for canal, pin in PIN_DE_CANAL.items():
    pwm = machine.PWM(machine.Pin(pin))
    pwm.freq(FREQ_SERVO)
    pwm.duty_u16(duty_base)
    pwm_de_canal[canal] = pwm
    print("  {} (GP{}) -> {}°".format(canal, pin, GRADOS_BASE))
    time.sleep(0.1)  # espaciado entre motores, igual que main.py: no pedir toda la corriente de golpe

print("Los 8 servos están en la posición base. Manteniendo posición (Ctrl+C para salir)...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nDetenido. Los servos mantienen su última posición (90°) mientras haya alimentación.")
