"""
Tests de face_tracker.py: la lógica pura de FaceTracker (mapeo, EMA, zona muerta),
inyectando una cascada falsa en vez de depender de que el detector real reconozca
un rostro en una imagen sintética (los Haar cascades necesitan rasgos faciales
reales; no tiene sentido intentar fabricar una imagen que los produzca de forma
fiable). Un test aparte, marcado, sí usa el detector real sobre un frame en negro
para confirmar al menos que "no hay rostro" se maneja sin explotar.

Sin cambios de lógica respecto a v9/v10: `FaceTracker` no cambió, solo cambió el
índice de cámara por defecto que usa el script standalone (no probado aquí, es
argparse, no lógica de FaceTracker).

Ejecutar:
    python -m pytest tests/test_face_tracker.py -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from face_tracker import FaceTracker, _mapear, ANCHO, ALTO, ESCALA_DETECCION


class FakeCascada:
    """Cascada falsa: devuelve las bboxes que se le den, en el espacio REDUCIDO
    (el que resulta tras el resize por ESCALA_DETECCION), como haría la real."""

    def __init__(self, rostros):
        self._rostros = rostros

    def detectMultiScale(self, gris, scaleFactor, minNeighbors):
        return self._rostros


def _frame_vacio(ancho=ANCHO, alto=ALTO):
    return np.zeros((alto, ancho, 3), dtype=np.uint8)


def _bbox_para_centro(px, py, tamano=40, escala=ESCALA_DETECCION):
    """bbox en espacio reducido cuyo centro, al reescalar, cae en (px, py) del
    frame completo."""
    x_full = px - tamano // 2
    y_full = py - tamano // 2
    lado = max(1, int(tamano * escala))
    return (int(x_full * escala), int(y_full * escala), lado, lado)


# --- _mapear, sin FaceTracker -----------------------------------------------

def test_mapear_centro_da_90_grados():
    assert _mapear(320, 0, 640, 40, 140) == 90


def test_mapear_extremos():
    assert _mapear(0, 0, 640, 40, 140) == 40
    assert _mapear(640, 0, 640, 40, 140) == 140


# --- FaceTracker con cascada inyectada --------------------------------------

def test_sin_rostro_no_falla_y_no_reporta_cambio():
    t = FaceTracker()
    t._cascada = FakeCascada([])
    r = t.procesar(_frame_vacio())
    assert r["detectado"] is False
    assert r["cambio_significativo"] is False
    assert r["bbox"] is None
    # Sin detección, debe devolver la posición inicial (centrado, 90/90).
    assert r["grado_x"] == 90 and r["grado_y"] == 90


def test_rostro_centrado_da_aproximadamente_90_grados():
    t = FaceTracker(alpha=1.0)  # sin suavizado, para ver el resultado inmediato
    t._cascada = FakeCascada([_bbox_para_centro(ANCHO // 2, ALTO // 2)])
    r = t.procesar(_frame_vacio())
    assert r["detectado"] is True
    assert 85 <= r["grado_x"] <= 95
    assert 85 <= r["grado_y"] <= 95


def test_rostro_a_la_izquierda_da_grado_bajo():
    t = FaceTracker(alpha=1.0)
    t._cascada = FakeCascada([_bbox_para_centro(0, ALTO // 2)])
    r = t.procesar(_frame_vacio())
    assert r["grado_x"] < 90


def test_zona_muerta_ignora_cambios_pequenos():
    t = FaceTracker(alpha=1.0, zona_muerta=50)
    # Primer frame lejos del centro inicial (90,90), para establecer una
    # posición base con un cambio real y significativo.
    t._cascada = FakeCascada([_bbox_para_centro(0, ALTO // 2)])
    r1 = t.procesar(_frame_vacio())
    assert r1["cambio_significativo"] is True

    # Un movimiento pequeño desde ahí no debe reportarse (dentro de la zona muerta).
    t._cascada = FakeCascada([_bbox_para_centro(5, ALTO // 2)])
    r2 = t.procesar(_frame_vacio())
    assert r2["cambio_significativo"] is False


def test_ema_suaviza_el_salto():
    t = FaceTracker(alpha=0.2)
    t._cascada = FakeCascada([_bbox_para_centro(0, ALTO // 2)])  # extremo izquierdo
    r = t.procesar(_frame_vacio())
    # Con alpha=0.2, un salto desde 90 no llega de golpe a 40.
    assert 40 < r["grado_x"] < 90


def test_deteccion_real_sobre_frame_negro_no_falla():
    """Confirma que el detector Haar real (sin cascada falsa) no explota sobre un
    frame sin rostro. No depende de cámara física, solo del cascade real de OpenCV
    que ya viene con el paquete opencv-python — sin marcar, no hace falta hardware."""
    t = FaceTracker()
    r = t.procesar(_frame_vacio())
    assert r["detectado"] is False
