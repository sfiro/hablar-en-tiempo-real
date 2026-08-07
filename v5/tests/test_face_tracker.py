"""
Tests de face_tracker.py: la lógica pura de FaceTracker (mapeo, EMA, zona muerta),
inyectando una cascada falsa en vez de depender de que el detector real reconozca
un rostro en una imagen sintética (los Haar cascades necesitan rasgos faciales
reales; no tiene sentido intentar fabricar una imagen que los produzca de forma
fiable). Un test aparte, marcado, sí usa el detector real sobre un frame en negro
para confirmar al menos que "no hay rostro" se maneja sin explotar.

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


def test_rostro_en_el_borde_izquierdo_da_grado_x_bajo():
    t = FaceTracker(alpha=1.0)
    t._cascada = FakeCascada([_bbox_para_centro(0, ALTO // 2)])
    r = t.procesar(_frame_vacio())
    assert r["grado_x"] < 50  # cerca del mínimo (40)


def test_zona_muerta_ignora_cambios_pequenos():
    t = FaceTracker(alpha=1.0, zona_muerta=5)

    t._cascada = FakeCascada([_bbox_para_centro(200, ALTO // 2)])
    r1 = t.procesar(_frame_vacio())
    assert r1["cambio_significativo"] is True  # primer cambio real desde el centro inicial

    # Frame siguiente: el rostro se mueve solo unos pocos píxeles, por debajo de la
    # resolución que introduce el reescalado — no debería contar como cambio.
    t._cascada = FakeCascada([_bbox_para_centro(202, ALTO // 2)])
    r2 = t.procesar(_frame_vacio())
    assert r2["cambio_significativo"] is False
    assert r2["grado_x"] == r1["grado_x"]  # no se actualiza "último" sin cambio significativo


def test_ema_amortigua_un_salto_brusco():
    """Con alpha bajo, un salto de un extremo a otro no debe llegar de inmediato al
    valor final: eso es justamente lo que el filtro EMA existe para evitar."""
    t = FaceTracker(alpha=0.2)

    t._cascada = FakeCascada([_bbox_para_centro(ANCHO // 2, ALTO // 2)])
    t.procesar(_frame_vacio())  # asienta el suavizado cerca de 90°

    t._cascada = FakeCascada([_bbox_para_centro(0, ALTO // 2)])  # salto a la esquina
    r = t.procesar(_frame_vacio())

    # El objetivo real sería ~40°; con un solo frame de alpha=0.2 debe quedar bastante
    # por encima de ese mínimo, no haber saltado ya al valor final.
    assert r["grado_x"] > 55


def test_alpha_mas_alto_converge_mas_rapido_que_alpha_bajo():
    t_lento = FaceTracker(alpha=0.1)
    t_rapido = FaceTracker(alpha=0.8)

    for t in (t_lento, t_rapido):
        t._cascada = FakeCascada([_bbox_para_centro(ANCHO // 2, ALTO // 2)])
        t.procesar(_frame_vacio())
        t._cascada = FakeCascada([_bbox_para_centro(0, ALTO // 2)])

    r_lento = t_lento.procesar(_frame_vacio())
    r_rapido = t_rapido.procesar(_frame_vacio())

    assert r_rapido["grado_x"] < r_lento["grado_x"], (
        "un alpha más alto debería acercarse más al objetivo en el mismo número de frames"
    )


# --- Con el detector real (sin mock), solo para el caso "sin rostro" --------

def test_deteccion_real_sobre_frame_negro_no_encuentra_nada():
    """No verifica precisión de detección (imposible sin un rostro real), solo que
    el detector de verdad, corriendo sobre una imagen sin rasgos, no explota y
    responde "no hay rostro" de forma consistente con el resto de la lógica."""
    t = FaceTracker()
    r = t.procesar(_frame_vacio())
    assert r["detectado"] is False
