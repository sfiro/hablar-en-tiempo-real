# v4 — Firmware MicroPython para la Raspberry Pi Pico, simplificado a propósito.
#
# Hace solo dos cosas:
#   1. Abre los párpados una vez al arrancar y los deja así (sin parpadeo, sin
#      sincronía con la mirada, sin emociones).
#   2. Recibe "LR,UD\n" por USB serial y mueve los ojos (canales LR/UD) hacia esa
#      posición, con suavizado EMA.
#
# Deliberadamente NO incluye (respecto al main.py "de producción" de ojosMecanicos):
# joystick, modo autónomo, emociones, parpadeo, sincronía párpado-cuello. Es el punto
# de partida antes de reintegrar la voz: primero confirmar que la Pico recibe x,y y
# mueve los ojos de forma fiable, sin la complejidad de las 8 emociones y los 3 modos
# encima. Ver ../v4/README-v4.md para el porqué y el plan de qué se añade después.
#
# Acepta también "LR,UD,EMOCION\n" (el formato de v3) ignorando el tercer campo: así
# el pico_serial.py de v4 (o el de v3) no necesita ningún cambio para hablar con esta versión.

import machine
import math
import select
import sys
import time


class ControladorPCA9685:
    """Igual que en el main.py de ojosMecanicos: control del PCA9685 por I2C."""

    def __init__(self, i2c, address=0x40, freq=50):
        self.i2c = i2c
        self.address = address
        self.i2c.writeto_mem(self.address, 0x00, b"\x10")
        prescale = int(math.floor(25000000.0 / 4096 / freq - 0.5))
        self.i2c.writeto_mem(self.address, 0xFE, bytes([prescale]))
        self.i2c.writeto_mem(self.address, 0x00, b"\x00")
        time.sleep(0.005)
        self.i2c.writeto_mem(self.address, 0x00, b"\xA1")

    def mover_servo(self, canal, grados):
        pulso = int(102 + (grados / 180.0) * (512 - 102))
        registro = 0x06 + 4 * canal
        try:
            self.i2c.writeto_mem(self.address, registro, bytes([0, 0, pulso & 0xFF, pulso >> 8]))
        except OSError:
            # Bus I2C ocupado o con ruido eléctrico de los motores: se ignora, el
            # siguiente ciclo del bucle vuelve a intentar la escritura.
            pass


# ==========================================
# CONFIGURACIÓN DE HARDWARE (igual que ojosMecanicos/main.py)
# ==========================================
i2c = machine.I2C(0, sda=machine.Pin(0), scl=machine.Pin(1), freq=400000)
pca = ControladorPCA9685(i2c)

CANAL_LR, CANAL_UD = 0, 1
CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR = 2, 3, 4, 5
CANAL_PAN, CANAL_TILT = 6, 7

# (cerrado, abierto) para los párpados — mismos valores que model.md/main.py.
PARPADOS_ABIERTOS = {
    CANAL_TL: 170,
    CANAL_BL: 10,
    CANAL_TR: 10,
    CANAL_BR: 160,
}

LR_MIN, LR_MAX = 40, 140
UD_MIN, UD_MAX = 40, 140
ALPHA = 0.1  # mismo suavizado que la versión completa

posicion_actual = {"LR": 90.0, "UD": 90.0}
objetivo_actual = {"LR": 90.0, "UD": 90.0}

# ==========================================
# INICIALIZACIÓN: ojos abiertos, mirada y cuello centrados, una sola vez.
# ==========================================
print("v4: iniciando (solo apertura de ojos + rastreo x,y)...")

for canal, grados in PARPADOS_ABIERTOS.items():
    pca.mover_servo(canal, grados)
    time.sleep(0.1)  # una pausa entre motor y motor, para no pedir toda la corriente de golpe

# El cuello no se controla en esta versión: se centra una vez al arrancar y se deja
# quieto, para que el rig no quede torcido de una sesión anterior.
pca.mover_servo(CANAL_PAN, 90)
time.sleep(0.1)
pca.mover_servo(CANAL_TILT, 90)
time.sleep(0.1)

pca.mover_servo(CANAL_LR, 90)
time.sleep(0.1)
pca.mover_servo(CANAL_UD, 90)
time.sleep(0.1)

print("Ojos abiertos y centrados. Esperando \"LR,UD\" por serial (40-140 cada uno).")

# ==========================================
# LECTURA DESDE USB SERIAL (sys.stdin, no UART físico — igual que ojosMecanicos)
# ==========================================
lector_serial = select.poll()
lector_serial.register(sys.stdin, select.POLLIN)


def procesar_comando(linea):
    """Formato esperado: "LR,UD" o "LR,UD,EMOCION" (el tercer campo se ignora aquí:
    ver la cabecera del fichero — esta versión no tiene sistema de emociones)."""
    try:
        partes = linea.strip().split(",")
        if len(partes) < 2:
            return False
        lr = max(LR_MIN, min(LR_MAX, int(partes[0])))
        ud = max(UD_MIN, min(UD_MAX, int(partes[1])))
        objetivo_actual["LR"] = float(lr)
        objetivo_actual["UD"] = float(ud)
        print("Serial: LR={}, UD={}".format(lr, ud))
        return True
    except (ValueError, IndexError):
        return False


# ==========================================
# BUCLE PRINCIPAL
# ==========================================
try:
    while True:
        if lector_serial.poll(0):
            try:
                linea = sys.stdin.readline()
                if linea:
                    procesar_comando(linea)
            except Exception:
                pass  # basura en el serial no debe tumbar el firmware

        for eje, canal in (("LR", CANAL_LR), ("UD", CANAL_UD)):
            objetivo = objetivo_actual[eje]
            actual = posicion_actual[eje]
            if abs(objetivo - actual) > 0.5:
                actual = (objetivo * ALPHA) + (actual * (1 - ALPHA))
                pca.mover_servo(canal, int(actual))
                posicion_actual[eje] = actual

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nDeteniendo... centrando los ojos.")
    pca.mover_servo(CANAL_LR, 90)
    pca.mover_servo(CANAL_UD, 90)
