#!/usr/bin/env python3
"""
Rastreo facial SOLO — sin ciclo de expresiones (v12-lite).

Creado el 23/08/2026 durante la depuración en hardware real: el ciclo de
expresiones de `rastreo_expresiones.py` envía EMOCION cada 5s, y las
expresiones DUDA/PENSATIVO/NERVIOSO hacen que el firmware de la Pico mueva la
mirada por su cuenta (secuestran LR/UD) — eso producía "saltos" y lentitud
que en un primer momento parecían bugs del rastreo, pero eran el
comportamiento esperado de esas tres expresiones. Este script aísla el
rastreo puro: envía SOLO la posición real del rostro (LR,UD) en cada frame
detectado, sin EMOCION jamás — el firmware se queda en NEUTRAL (que no fija
la mirada) y los ojos siguen al rostro de forma continua, sin la variable de
las expresiones de por medio. Útil para depurar el rastreo aislado del ciclo
de expresiones; para el comportamiento completo, usa `rastreo_expresiones.py`.

Diferencias vs rastreo_expresiones.py:
  - Sin CICLO_EMOCIONES, sin temporizador de 5s, sin enviar EMOCION nunca.
  - Envía en cada frame con rostro detectado (respetando la misma cadencia
    mínima que rastreo_expresiones.py); el suavizado interno de la Pico
    (ALPHA=0.1 en main.py) hace el resto.
  - Mismos parámetros de FaceTracker calibrados en hardware real
    (alpha=0.5, zona_muerta=0): el cliente apenas suaviza, la Pico ya lo hace.
  - Misma cámara CSI-primero-USB-de-respaldo que rastreo_expresiones.py.

Uso:
    python rastreo_solo.py
    python rastreo_solo.py --interval-ms 50     # cadencia mínima entre envíos
    python rastreo_solo.py --no-pico            # solo probar cámara + detección
    python rastreo_solo.py --debug              # imprime cada envío
"""

import argparse
import sys
import threading
import time

ULTIMA_MIRADA = {"lr": 90, "ud": 90}
_LOCK = threading.Lock()
PICO = None
DEBUG = False


def _hilo_rastreo(leer, detener: threading.Event, intervalo_ms: int):
    """Rastrea el rostro y envía LR,UD a la Pico en cada frame detectado,
    con una cadencia mínima de `intervalo_ms` entre envíos (por defecto 200ms
    = 5 envíos/s — a 50ms/20 por segundo, probado en hardware real, el buffer
    USB CDC de la Pico se desbordaba cuando el firmware parpadea, ~1.5s sin
    leer el serial; ver `pico_serial.py`)."""
    import cv2
    from face_tracker import FaceTracker

    print("✅ Cámara lista: rastreo facial activo (solo mirada, sin expresiones).")
    # alpha alto + zona muerta 0: el cliente apenas suaviza y nunca retiene un
    # comando por "cambio no significativo" — la Pico ya suaviza internamente
    # (ALPHA=0.1 en main.py), así que lo que necesita es el objetivo fresco en
    # cada envío, sin que el filtro del cliente lo retrase ni lo congele.
    tracker = FaceTracker(alpha=0.5, zona_muerta=0)
    ultimo_envio = 0.0
    try:
        while not detener.is_set():
            ret, frame = leer()
            if not ret:
                print("⚠️  No se pudo leer el frame de la cámara")
                break
            frame = cv2.flip(frame, 1)  # efecto espejo
            resultado = tracker.procesar(frame)
            if not resultado["detectado"]:
                continue
            ahora = time.monotonic()
            if ahora - ultimo_envio < intervalo_ms / 1000:
                continue
            ultimo_envio = ahora
            lr, ud = resultado["grado_x"], resultado["grado_y"]
            with _LOCK:
                ULTIMA_MIRADA["lr"], ULTIMA_MIRADA["ud"] = lr, ud
            if PICO is not None:
                PICO.enviar(lr, ud)
            if DEBUG:
                print(f"🎯 lr={lr}, ud={ud}", flush=True)
    finally:
        pass  # la cámara se libera en main()


def main():
    global PICO, DEBUG
    parser = argparse.ArgumentParser(
        description="Rastreo facial SOLO (sin expresiones) — Pi 5 + Pico + cámara.")
    parser.add_argument("--interval-ms", type=int, default=200,
                        help="Cadencia entre envíos a la Pico, en ms (por defecto: 200 = 5/s). "
                             "Validado en hardware real: a 50ms (20/s) el buffer USB de la "
                             "Pico se desborda cuando el firmware parpadea (~1.5s sin leer "
                             "serial) → comandos perdidos → ojos lentos con pequeños saltos.")
    parser.add_argument("--camera-index", type=int, default=1,
                        help="Índice de cámara USB, usado solo como respaldo si no hay "
                             "cámara CSI disponible (por defecto: 1).")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No enviar a la Pico (prueba solo cámara + detección).")
    parser.add_argument("--debug", action="store_true", help="Imprime cada envío.")
    args = parser.parse_args()
    DEBUG = args.debug

    detener = threading.Event()

    if args.usar_pico:
        from pico_serial import PicoLink, encontrar_puerto_pico
        puerto = encontrar_puerto_pico()
        if puerto:
            PICO = PicoLink(port=puerto)
            PICO.start()
            print(f"✅ Pico detectada en {puerto}.")
        else:
            print("⚠️  No se detectó ninguna Pico. Rastreo sin enviar comandos.")

    camara = None
    leer = None
    try:
        import cv2
        from face_tracker import ALTO, ANCHO, abrir_camara_csi, leer_frame
        print("🔍 Iniciando cámara CSI (picamera2)...")
        camara = abrir_camara_csi(ANCHO, ALTO)
        leer = lambda: leer_frame(camara)
        print("✅ Cámara CSI lista (OV5647).")
    except Exception as e:
        print(f"⚠️  Cámara CSI no disponible ({e}); probando webcam USB...")
        cap = cv2.VideoCapture(args.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
        if not cap.isOpened():
            print("⚠️  Sin cámara disponible. Saliendo.")
            sys.exit(1)
        camara = cap
        leer = cap.read
        print("✅ Webcam USB lista.")

    threading.Thread(target=_hilo_rastreo, args=(leer, detener, args.interval_ms),
                     daemon=True).start()

    print("🟢 Rastreo activo. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Deteniendo...")
    finally:
        detener.set()
        if camara is not None:
            try:
                camara.stop()
            except AttributeError:
                camara.release()
        if PICO is not None:
            PICO.stop()


if __name__ == "__main__":
    main()
