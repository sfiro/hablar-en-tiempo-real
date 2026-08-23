#!/usr/bin/env python3
"""Captura un frame de la cámara CSI, dibuja el bbox de lo que la cascada Haar
detecta como 'rostro', y lo guarda como imagen para inspeccionar QUÉ está
detectando (falso positivo vs cara real).

Herramienta de diagnóstico usada durante la depuración en hardware real del
23/08/2026 (ver MODIFICACIONES-LOCALES.md) — pensada para correr directamente
en la Raspberry Pi 5, con la ruta del proyecto fija en /home/pi/v12 (ajusta el
sys.path.insert() si tu clon vive en otra ruta). No forma parte del pipeline
normal (rastreo_expresiones.py/rastreo_solo.py); solo para depurar detección.
"""
import sys
import time

sys.path.insert(0, "/home/pi/v12")

import cv2
from face_tracker import ANCHO, ALTO, abrir_camara_csi, leer_frame

print("🔍 Abriendo cámara CSI...")
camara = abrir_camara_csi(ANCHO, ALTO)
cascada = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

print("✅ Capturando 3 frames con 1s de separación (muévete si estás delante)...")
for i in range(3):
    time.sleep(1.0)
    ret, frame = leer_frame(camara)
    if not ret:
        print(f"  frame {i}: error leyendo")
        continue
    frame = cv2.flip(frame, 1)  # mismo espejo que el rastreo
    pequeno = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
    gris = cv2.cvtColor(pequeno, cv2.COLOR_BGR2GRAY)
    rostros = cascada.detectMultiScale(gris, scaleFactor=1.2, minNeighbors=4)
    print(f"  frame {i}: {len(rostros)} rostro(s) detectado(s)")
    for (x, y, w, h) in rostros:
        x, y, w, h = int(x * 2), int(y * 2), int(w * 2), int(h * 2)  # deshacer escala 0.5
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
        cv2.putText(frame, "DETECTADO", (x, max(20, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        print(f"    bbox: x={x}, y={y}, w={w}, h={h}")
    ruta = f"/tmp/v12_frame_{i}.jpg"
    cv2.imwrite(ruta, frame)
    print(f"  guardado en {ruta}")

camara.stop()
print("\n✅ Listo — revisa /tmp/v12_frame_*.jpg para ver QUÉ detecta la cámara")
