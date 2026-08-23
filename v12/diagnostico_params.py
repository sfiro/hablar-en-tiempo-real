#!/usr/bin/env python3
"""Barrido de parámetros de detección con la cámara CSI OV5647 (v2: reutiliza
la cámara, sin cerrarla entre combinaciones — arregla 'Device or resource busy').

MIDE SOLO DETECCIÓN (sin servos): ponte frente a la cámara durante la prueba.

Herramienta de diagnóstico usada durante la depuración en hardware real del
23/08/2026 (ver MODIFICACIONES-LOCALES.md) — el barrido que encontró que
1296×972 + scaleFactor=1.2/minNeighbors=4 pasa de 0% a 100% de detección
frente a la config original (640×480, pensada para una webcam USB). Pensada
para correr directamente en la Raspberry Pi 5, con la ruta del proyecto fija
en /home/pi/v12 (ajusta el sys.path.insert() si tu clon vive en otra ruta).
"""
import sys
import time

sys.path.insert(0, "/home/pi/v12")

import cv2
from picamera2 import Picamera2

CASCADA = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

RESOLUCIONES = [(640, 480), (1296, 972)]
PARAMS = [
    {"sf": 1.3, "mn": 5},   # original (pensada para webcam USB)
    {"sf": 1.2, "mn": 4},
    {"sf": 1.1, "mn": 4},
    {"sf": 1.1, "mn": 3},
]
DURACION = 4.0

picam2 = Picamera2()
picam2.start()  # arranca con la config por defecto; reconfiguramos por resolución
time.sleep(1)

def probar(ancho, alto, sf, mn):
    cfg = picam2.create_preview_configuration(
        main={"size": (ancho, alto), "format": "BGR888"})
    picam2.stop()
    time.sleep(0.3)
    picam2.configure(cfg)
    picam2.start()
    time.sleep(0.5)
    total = hits = 0
    inicio = time.time()
    while time.time() - inicio < DURACION:
        try:
            frame = picam2.capture_array()
        except Exception:
            continue
        total += 1
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eq = cv2.equalizeHist(gris)
        pequeno = cv2.resize(eq, (0, 0), fx=0.5, fy=0.5)
        if len(CASCADA.detectMultiScale(pequeno, scaleFactor=sf, minNeighbors=mn)) > 0:
            hits += 1
    return total, hits

print("Mantente FRENTE A LA CÁMARA, sin moverte mucho...\n")
mejor = None
for ancho, alto in RESOLUCIONES:
    for p in PARAMS:
        total, hits = probar(ancho, alto, p["sf"], p["mn"])
        pct = 100 * hits / max(total, 1)
        tag = " ← ORIGINAL" if (ancho, alto, p["sf"], p["mn"]) == (640, 480, 1.3, 5) else ""
        print(f"{ancho}x{alto} sf={p['sf']} mn={p['mn']}: {hits}/{total} = {pct:.0f}%{tag}")
        if mejor is None or pct > mejor[0]:
            mejor = (pct, ancho, alto, p["sf"], p["mn"])

picam2.stop()
pct, ancho, alto, sf, mn = mejor
print(f"\n🏆 MEJOR: {ancho}x{alto} sf={sf} mn={mn} → {pct:.0f}% de frames con rostro")
print("(escríbelo: hay que actualizar FaceTracker/rastreo_expresiones con esto)")
