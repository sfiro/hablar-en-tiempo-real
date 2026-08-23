#!/usr/bin/env python3
"""Diagnóstico rápido del rastreo facial con la cámara CSI OV5647.

Mide: tasa de detección (¿se pierde el rostro?), temblor del bbox (¿salta?),
y posición mapeada frame a frame — para ver si el problema de los ojos es
inestabilidad de detección o algo del mapeo/servos.

Herramienta de diagnóstico usada durante la depuración en hardware real del
23/08/2026 (ver MODIFICACIONES-LOCALES.md) — pensada para correr directamente
en la Raspberry Pi 5, con la ruta del proyecto fija en /home/pi/v12 (ajusta el
sys.path.insert() si tu clon vive en otra ruta).
"""
import sys
import time

sys.path.insert(0, "/home/pi/v12")

import cv2
from face_tracker import FaceTracker, abrir_camara_csi, leer_frame

print("🔍 Abriendo cámara CSI...")
camara = abrir_camara_csi(640, 480)
tracker = FaceTracker()
print("✅ Cámara lista. Rastreando 12 segundos...\n")

frames = 0
detectados = 0
perdidos_consecutivos = 0
racha_max_perdida = 0
ultimo_bbox = None
salto_max = 0
inicio = time.time()

while time.time() - inicio < 12:
    ret, frame = leer_frame(camara)
    if not ret:
        continue
    frames += 1
    frame = cv2.flip(frame, 1)
    res = tracker.procesar(frame)
    if res["detectado"]:
        detectados += 1
        perdidos_consecutivos = 0
        x, y, w, h = res["bbox"]
        if ultimo_bbox is not None:
            salto = abs((x + w // 2) - (ultimo_bbox[0] + ultimo_bbox[2] // 2)) + \
                    abs((y + h // 2) - (ultimo_bbox[1] + ultimo_bbox[3] // 2))
            salto_max = max(salto_max, salto)
        ultimo_bbox = (x, y, w, h)
    else:
        perdidos_consecutivos += 1
        racha_max_perdida = max(racha_max_perdida, perdidos_consecutivos)

print(f"Frames procesados:        {frames}")
print(f"Detecciones positivas:    {detectados}  ({100*detectados/max(frames,1):.0f}%)")
print(f"Racha máx de pérdidas:    {racha_max_perdida} frames seguidos sin rostro")
print(f"Salto máx del centro:     {salto_max} px entre frames consecutivos")
print(f"Mirada final:             lr={res['grado_x']}, ud={res['grado_y']}" if 'res' in dir() else "")

camara.stop()
