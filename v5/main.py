# v5 — Firmware MicroPython para la Raspberry Pi Pico.
#
# v4 hacía solo dos cosas (párpados abiertos + rastreo x,y de los ojos). v5 añade,
# mientras el rastreo de ojos sigue funcionando igual:
#   1. Rotación de cabeza (PAN, canal 6): imita el giro horizontal de los ojos,
#      amortiguado al 80% (mismo factor que ojosMecanicos/main.py).
#   2. Subir/bajar cabeza (TILT, canal 7): imita la inclinación vertical de los ojos,
#      amortiguado al 60%.
#   3. Parpadeo periódico (canales TL/BL/TR/BR): cada 2-6 segundos, sin depender de
#      si hay rastreo activo o no — parpadea igual mientras los ojos siguen la cara.
#
# Deliberadamente NO incluye todavía (respecto al main.py "de producción" de
# ojosMecanicos): joystick, modo autónomo, emociones y su sincronía con la mirada.
# Ver ../v5/README-v5.md para el porqué y qué falta.
#
# Acepta "LR,UD\n" o "LR,UD,EMOCION\n" (formato de v3/v4) ignorando el tercer campo:
# el Mac (pico_serial.py, copia propia de v5) no necesita ningún cambio.
#
# --- Arranque limpio con /OE (Output Enable) del PCA9685 ---------------------
# Al conectar la alimentación, todos los servos se movían solos y en direcciones
# aleatorias durante 1-2s, hasta que este firmware terminaba de arrancar y tomaba
# el control. Pasaba con cualquier firmware, incluso antes de ejecutar código: las
# salidas PWM del PCA9685 quedan en un estado indefinido en el instante entre
# "llega la alimentación" y "la Pico termina de arrancar y configura el chip", y
# los servos reaccionan a esa señal indefinida como si fuera un comando válido.
# La solución: cablear el pin /OE (activo en bajo) del PCA9685 a GP2, con una
# resistencia de pull-up externa hacia VCC en la propia placa PCA9685 (antes
# estaba puesto directo a GND, lo que dejaba las salidas siempre habilitadas).
# El pull-up garantiza que /OE esté en HIGH (deshabilitado) por defecto incluso
# antes de que la Pico arranque; el firmware lo confirma explícitamente al
# principio y solo lo baja (habilita) cuando todos los servos ya están en su
# posición inicial correcta — así nunca llega una señal indefinida a los motores.

import machine
import math
import random
import select
import sys
import time

# Deshabilita las salidas del PCA9685 ya mismo, lo primero que hace el firmware,
# antes incluso de tocar el I2C. El pull-up externo en la placa PCA9685 ya lo
# mantiene en HIGH desde antes de esto; esta línea lo hace explícito en el código
# y no depende de que el pull-up sea perfecto.
PIN_OE = machine.Pin(2, machine.Pin.OUT)
PIN_OE.value(1)  # 1 = deshabilitado (OE es activo en bajo)


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

# Habilitamos las salidas AQUÍ, justo tras configurar el chip y antes de mover
# ningún servo: en este punto los registros de posición de cada canal siguen en
# su estado de reposo de fábrica (sin señal), así que habilitar ahora no mueve
# nada todavía. Si se habilitara más tarde, después de programar ya todas las
# posiciones, los 8 servos saltarían TODOS A LA VEZ al habilitar — justo lo que
# el espaciado de 0.1s entre motores del bucle de abajo quiere evitar.
PIN_OE.value(0)

CANAL_LR, CANAL_UD = 0, 1
CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR = 2, 3, 4, 5
CANAL_PAN, CANAL_TILT = 6, 7

# (cerrado, abierto) para los párpados — mismos valores que model.md/main.py.
PARPADOS_ABIERTOS = {CANAL_TL: 170, CANAL_BL: 10, CANAL_TR: 10, CANAL_BR: 160}
PARPADOS_CERRADOS = {CANAL_TL: 70, CANAL_BL: 90, CANAL_TR: 70, CANAL_BR: 90}

LR_MIN, LR_MAX = 40, 140
UD_MIN, UD_MAX = 40, 140
PAN_MIN, PAN_MAX = 40, 140
TILT_MIN, TILT_MAX = 40, 140

# Cuánto del movimiento de los ojos se traslada al cuello (mismos factores que
# ojosMecanicos/main.py: la cabeza acompaña la mirada, no la iguala 1 a 1).
FACTOR_PAN = 0.8
FACTOR_TILT = 0.6

ALPHA = 0.1  # mismo suavizado que la versión completa, para los 4 ejes con EMA

# Interruptor de diagnóstico: si el temblor periódico persiste con esto en False,
# el parpadeo queda descartado como causa y hay que seguir buscando en otro lado.
PARPADEO_ACTIVO = True

EJES = ("LR", "UD", "PAN", "TILT")
CANAL_DE_EJE = {"LR": CANAL_LR, "UD": CANAL_UD, "PAN": CANAL_PAN, "TILT": CANAL_TILT}

posicion_actual = {"LR": 90.0, "UD": 90.0, "PAN": 90.0, "TILT": 90.0}
objetivo_actual = {"LR": 90.0, "UD": 90.0, "PAN": 90.0, "TILT": 90.0}


def clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


# ==========================================
# INICIALIZACIÓN: ojos abiertos, mirada y cuello centrados, una sola vez.
# ==========================================
print("v5: iniciando (rastreo de ojos + cuello + parpadeo periódico)...")

for canal, grados in PARPADOS_ABIERTOS.items():
    pca.mover_servo(canal, grados)
    time.sleep(0.1)  # pausa entre motor y motor, para no pedir toda la corriente de golpe

for eje in EJES:
    pca.mover_servo(CANAL_DE_EJE[eje], 90)
    time.sleep(0.1)

print("Ojos y cuello centrados, párpados abiertos. Esperando \"LR,UD\" por serial.")

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
        lr = clamp(int(partes[0]), LR_MIN, LR_MAX)
        ud = clamp(int(partes[1]), UD_MIN, UD_MAX)
        objetivo_actual["LR"] = float(lr)
        objetivo_actual["UD"] = float(ud)
        print("Serial: LR={}, UD={}".format(lr, ud))
        return True
    except (ValueError, IndexError):
        return False


def actualizar_objetivo_cuello():
    """El cuello sigue a los ojos, amortiguado — se recalcula en cada vuelta del
    bucle a partir del objetivo de LR/UD, igual que sincronizar_parpados_y_cuello()
    en ojosMecanicos/main.py (ahí sin la parte de párpados, que en v5 no depende
    de la mirada, solo del parpadeo periódico)."""
    objetivo_pan = 90 + (objetivo_actual["LR"] - 90) * FACTOR_PAN
    objetivo_tilt = 90 + (objetivo_actual["UD"] - 90) * FACTOR_TILT
    objetivo_actual["PAN"] = clamp(objetivo_pan, PAN_MIN, PAN_MAX)
    objetivo_actual["TILT"] = clamp(objetivo_tilt, TILT_MIN, TILT_MAX)


def parpadear():
    """Cierra los 4 párpados de forma escalonada (10ms de separación, para no pedir
    toda la corriente de golpe), espera, y los vuelve a abrir. Bloquea el bucle
    principal unos ~230ms mientras dura — igual que en ojosMecanicos/main.py."""
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        pca.mover_servo(canal, PARPADOS_CERRADOS[canal])
        time.sleep(0.01)
    time.sleep(0.15)
    for canal in (CANAL_TL, CANAL_BL, CANAL_TR, CANAL_BR):
        pca.mover_servo(canal, PARPADOS_ABIERTOS[canal])
        time.sleep(0.01)


# ==========================================
# BUCLE PRINCIPAL
# ==========================================
proximo_parpadeo = time.ticks_add(time.ticks_ms(), random.randint(2000, 6000))

try:
    while True:
        if lector_serial.poll(0):
            try:
                linea = sys.stdin.readline()
                if linea:
                    procesar_comando(linea)
            except Exception:
                pass  # basura en el serial no debe tumbar el firmware

        actualizar_objetivo_cuello()

        for eje in EJES:
            objetivo = objetivo_actual[eje]
            actual = posicion_actual[eje]
            if abs(objetivo - actual) > 0.5:
                actual = (objetivo * ALPHA) + (actual * (1 - ALPHA))
                pca.mover_servo(CANAL_DE_EJE[eje], int(actual))
                posicion_actual[eje] = actual

        ahora = time.ticks_ms()
        if PARPADEO_ACTIVO and time.ticks_diff(ahora, proximo_parpadeo) > 0:
            parpadear()
            proximo_parpadeo = time.ticks_add(ahora, random.randint(2000, 6000))

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nDeteniendo... centrando ojos y cuello.")
    for eje in EJES:
        pca.mover_servo(CANAL_DE_EJE[eje], 90)
