#!/usr/bin/env python3
"""
Raspberry Pi 5 + Pico, sin voz todavía: ciclo de expresiones cada 5 segundos +
rastreo facial real por la cámara USB de la Pi 5.

Objetivo de v12, pedido explícito: conectar la Raspberry Pi 5 a la Pico por USB
(el mismo firmware de v9, `main.py`, sin cambios) y, con la cámara de la Pi 5
(webcam USB en `/dev/video1`), hacer dos cosas a la vez, todavía sin conversación
de voz:
  1. Rastrear el rostro en tiempo real y mandar su posición a la Pico (igual
     mecanismo que `_hilo_rastreo()` en v9/webrtc_server.py).
  2. Ciclar las 10 expresiones de la Pico en un orden fijo, cambiando cada
     `--interval` segundos (5 por defecto — el mismo valor que
     `INTERVALO_EXPRESION_MS` en main.py, para que el pulso de una expresión
     nunca expire y caiga a NEUTRAL entre un cambio y el siguiente).

La diferencia con v6/v7 (que también ciclaban las 10 expresiones cada 5s) es
dónde vive el temporizador: allá el firmware las ciclaba solo, sin nada
externo. Desde v8/v9, `main.py` pasó a un modelo dirigido por eventos — solo
cambia de expresión cuando recibe un EMOCION por serial, y mantiene lo último
recibido durante el pulso. v12 no toca ese firmware: en vez de que la Pico
cicle sola, es este script, del lado de la Pi 5, el que manda una EMOCION
nueva cada 5 segundos — el efecto que se ve en el robot es el mismo ciclo de
v6/v7, pero ahora el firmware es el mismo de v9 (reutilizable también para
voz+sentimiento el día que se retome, sin ningún cambio adicional).

Cada expresión enviada lleva la posición REAL del rostro rastreado (no un
90,90 fijo como hacía v8 sin cámara) — igual razonamiento que
`ULTIMA_MIRADA`/`_handle_analyze_sentiment()` en v9/webrtc_server.py, aquí sin
necesitar un servidor HTTP porque no hay navegador ni voz de por medio: es un
único proceso con dos hilos.

Todavía NO implementa conversación de voz — a propósito, alcance explícito de
esta versión. Eso es un paso posterior, una vez validado que la Pi 5 controla
bien la Pico por USB y rastrea con su propia cámara.

Uso:
    python rastreo_expresiones.py
    python rastreo_expresiones.py --camera-index 0     # si tu webcam no es /dev/video1
    python rastreo_expresiones.py --interval 2          # ciclo más rápido, para probar
    python rastreo_expresiones.py --no-pico              # solo prueba la cámara y el ciclo, sin enviar nada
    python rastreo_expresiones.py --no-tracking          # solo el ciclo de expresiones, mirada fija en 90,90
"""

import argparse
import sys
import threading
import time

# Orden fijo del ciclo: idéntico al que usaban v6/v7 cuando el propio firmware
# ciclaba solo (ver CLAUDE.md, sección v6) — mismo orden en el que están
# declaradas en OFFSETS_EMOCIONES de main.py. Aquí es una tupla explícita, no
# una lectura de main.py (ese fichero es firmware MicroPython, no se importa
# desde el cliente).
CICLO_EMOCIONES = (
    "NEUTRAL", "FELIZ", "ENOJADO", "TRISTE", "SORPRENDIDO",
    "DORMIDO", "DUDA", "SOSPECHA", "PENSATIVO", "NERVIOSO",
)

INTERVALO_POR_DEFECTO_S = 5.0  # igual a INTERVALO_EXPRESION_MS/1000 en main.py

# Última posición real del rostro detectado por el hilo de rastreo (grados de
# servo, 40-140). Sin --tracking activo, o mientras no se detecte ningún
# rostro todavía, se queda en el centro (90,90) — mismo valor fijo que usaba
# v8 antes de tener cámara.
ULTIMA_MIRADA = {"lr": 90, "ud": 90}
_LOCK_MIRADA = threading.Lock()

PICO = None


def _siguiente_indice(indice_actual: int) -> int:
    """Avanza el índice del ciclo de expresiones, volviendo a 0 tras la última.
    Aislado del temporizador real para poder probarlo sin esperar segundos de
    verdad (ver tests/test_rastreo_expresiones.py)."""
    return (indice_actual + 1) % len(CICLO_EMOCIONES)


def _hilo_rastreo(cap, detener: threading.Event):
    """Rastrea el rostro por cámara y manda su posición real a la Pico mientras
    haya cambios significativos. Corre en un hilo de fondo, en paralelo al
    ciclo de expresiones del hilo principal.

    Recibe un `cv2.VideoCapture` ya abierto, en vez de abrirlo aquí. En v9 esto
    era imprescindible en macOS (AVFoundation no puede negociar el permiso de
    cámara fuera del hilo principal); en Linux/Pi 5 no está confirmado que haga
    falta, pero se mantiene el mismo patrón por consistencia — igual criterio
    que v10 documentó explícitamente para su propio hilo de cámara.
    """
    import cv2
    from face_tracker import FaceTracker

    print("✅ Cámara lista: el rastreo facial está activo.")
    tracker = FaceTracker()
    try:
        while not detener.is_set():
            ret, frame = cap.read()
            if not ret:
                print("⚠️  No se pudo leer el frame de la cámara")
                break
            frame = cv2.flip(frame, 1)  # efecto espejo
            resultado = tracker.procesar(frame)
            if resultado["detectado"] and resultado["cambio_significativo"]:
                lr, ud = resultado["grado_x"], resultado["grado_y"]
                with _LOCK_MIRADA:
                    ULTIMA_MIRADA["lr"], ULTIMA_MIRADA["ud"] = lr, ud
                if PICO is not None:
                    PICO.enviar(lr, ud)
    finally:
        cap.release()


def _ciclar_expresiones(intervalo_s: float, detener: threading.Event):
    """Bucle principal: cada `intervalo_s` segundos, manda la siguiente
    expresión del ciclo fijo a la Pico, con la mirada real del rastreo en ese
    instante. Corre en el hilo principal."""
    indice = 0
    while not detener.is_set():
        emocion = CICLO_EMOCIONES[indice]
        with _LOCK_MIRADA:
            lr, ud = ULTIMA_MIRADA["lr"], ULTIMA_MIRADA["ud"]
        if PICO is not None:
            PICO.enviar(lr, ud, emocion)
        print(f"😀 Expresión: {emocion} (mirada lr={lr}, ud={ud})")
        indice = _siguiente_indice(indice)
        detener.wait(intervalo_s)


def main():
    parser = argparse.ArgumentParser(
        description="Ciclo de expresiones + rastreo facial real, Pi 5 + Pico, sin voz todavía.")
    parser.add_argument("--interval", type=float, default=INTERVALO_POR_DEFECTO_S,
                        help=f"Segundos entre cada cambio de expresión (por defecto: "
                             f"{INTERVALO_POR_DEFECTO_S}, igual al pulso de main.py).")
    parser.add_argument("--camera-index", type=int, default=1,
                        help="Índice de cámara para cv2.VideoCapture (por defecto: 1, "
                             "donde esta Pi 5 enumera la webcam USB — /dev/video1).")
    parser.add_argument("--no-tracking", dest="tracking", action="store_false",
                        help="No rastrear el rostro; la mirada se queda fija en 90,90.")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No envíes nada a la Pico aunque haya una conectada "
                             "(prueba solo la cámara y el ciclo en consola).")
    args = parser.parse_args()

    global PICO
    detener_rastreo = threading.Event()
    detener_ciclo = threading.Event()

    if args.usar_pico:
        from pico_serial import PicoLink, encontrar_puerto_pico
        puerto_pico = encontrar_puerto_pico()
        if puerto_pico:
            PICO = PicoLink(port=puerto_pico)
            PICO.start()
            print(f"✅ Pico detectada en {puerto_pico}.")
        else:
            print("⚠️  No se detectó ninguna Pico. El ciclo sigue igual, "
                  "sin mover los servos.")

    if args.tracking:
        try:
            import cv2
        except ImportError:
            sys.exit(
                "ERROR: el rastreo necesita 'opencv-python'. Instala con:\n"
                "  pip install -r requirements.txt\n"
                "O usa --no-tracking para el ciclo de expresiones sin cámara."
            )
        from face_tracker import ALTO, ANCHO
        print("🔍 Iniciando cámara para el rastreo facial...")
        cap = cv2.VideoCapture(args.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
        if not cap.isOpened():
            print(f"⚠️  No se pudo abrir la cámara (índice {args.camera_index}). "
                  "El rastreo facial no estará activo; sigue el ciclo con mirada fija.")
            cap.release()
        else:
            threading.Thread(
                target=_hilo_rastreo, args=(cap, detener_rastreo), daemon=True
            ).start()

    print(f"🟢 Ciclo de expresiones activo, cada {args.interval:.1f}s. Ctrl+C para salir.")
    try:
        _ciclar_expresiones(args.interval, detener_ciclo)
    except KeyboardInterrupt:
        print("\n👋 Deteniendo...")
    finally:
        detener_rastreo.set()
        detener_ciclo.set()
        if PICO is not None:
            PICO.stop()


if __name__ == "__main__":
    main()
