# Diagnóstico de un solo canal, sin nada de rastreo ni serial de por medio.
# Sirve para aislar si un eje que "no funciona" es un problema de firmware
# (main.py) o de hardware (cable, servo, tope mecánico).
#
# Cómo usarlo: cambia CANAL_A_PROBAR abajo y corre este fichero en Thonny (con la
# Pico conectada). Verás/oirás si el servo de ese canal se mueve de un extremo al
# otro, lentamente, grado a grado — igual que 01_prueba_uno_a_uno.py en ojosMecanicos.
#
# Prueba primero el canal que SÍ funciona (TILT=7) para confirmar que ves/oyes
# movimiento cuando el hardware está bien. Luego cambia a PAN=6 y compara.
#
# Nota heredada, no corregida en v13 (fuera de alcance de esta versión): este
# fichero sigue usando el controlador PCA9685 por I2C, igual que en v9/v12 y en
# todas las versiones anteriores desde que existe — a diferencia de main.py y
# estado_base.py, que generan PWM directo desde la Pico desde v5 (ver
# ../v5/README-v5.md, "por qué se abandonó el PCA9685"). Esta inconsistencia ya
# existía antes de v13; no se ha usado ni validado con el hardware actual (sin
# PCA9685 conectado), así que no se toca aquí sin confirmar primero con el
# usuario si vale la pena reescribirlo para el PWM directo.

import machine
import math
import time

CANAL_A_PROBAR = 6   # 0=LR, 1=UD, 2=TL, 3=BL, 4=TR, 5=BR, 6=PAN, 7=TILT
GRADO_MIN, GRADO_MAX = 40, 140
PASO = 2              # grados por paso
PAUSA_S = 0.03         # pausa entre pasos, para verlo "lento"


class ControladorPCA9685:
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
        except OSError as e:
            print("  ⚠️  Error I2C escribiendo el canal:", e)


i2c = machine.I2C(0, sda=machine.Pin(0), scl=machine.Pin(1), freq=400000)
pca = ControladorPCA9685(i2c)

print(f"Probando SOLO el canal {CANAL_A_PROBAR}. Ctrl+C para detener.")
print("Centrando en 90°...")
pca.mover_servo(CANAL_A_PROBAR, 90)
time.sleep(1)

try:
    while True:
        print(f"  -> barriendo de {GRADO_MIN}° a {GRADO_MAX}°")
        for g in range(GRADO_MIN, GRADO_MAX + 1, PASO):
            pca.mover_servo(CANAL_A_PROBAR, g)
            time.sleep(PAUSA_S)
        time.sleep(0.3)
        print(f"  <- barriendo de {GRADO_MAX}° a {GRADO_MIN}°")
        for g in range(GRADO_MAX, GRADO_MIN - 1, -PASO):
            pca.mover_servo(CANAL_A_PROBAR, g)
            time.sleep(PAUSA_S)
        time.sleep(0.3)

except KeyboardInterrupt:
    print("\nCentrando y saliendo...")
    pca.mover_servo(CANAL_A_PROBAR, 90)
