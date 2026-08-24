#!/usr/bin/env python3
"""
Ciclo de expresiones cada 5 segundos + rastreo facial real por la cámara de
la Pi 5 — sin conversación de voz en este mismo proceso.

Retomado sin cambios de lógica de `../v12/rastreo_expresiones.py`. Existe en
v13 por un hallazgo real al validar en hardware (ver
[`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md)): combinar rastreo
facial y voz en tiempo real **en el mismo proceso** (el enfoque original de
`webrtc_server.py --tracking`) compite por CPU con el procesamiento de audio
lo bastante como para que se cuele eco — la carga del sistema medida pasó de
~2.1 con los dos procesos separados a ~3.25 combinados en uno. La
arquitectura validada y recomendada para usar voz + rastreo a la vez es dos
procesos independientes:

    Proceso 1 (este fichero):  rastreo facial + ciclo de expresiones + Pico
    Proceso 2:                 webrtc_server.py SIN --tracking (solo voz)

Cada proceso con su propio recurso — la cámara y la Pico aquí, el
micrófono/parlante allá — sin competir entre sí. Ver README-v13.md, sección
"Validación en hardware real", para la receta completa de arranque.

Esto no cambia el resto de v13: `realtime_voice.py --tracking` y
`webrtc_server.py --tracking` (rastreo dentro del mismo proceso de voz)
siguen existiendo y funcionando — útiles para una prueba rápida o para la
vía de terminal, donde no se validó el mismo problema de CPU — pero para la
vía de navegador, en producción, la combinación de dos procesos es la que
se confirmó funcionando sin eco ni degradación de audio.

Objetivo original (heredado de v12): conectar la Raspberry Pi 5 a la Pico
por USB (el mismo firmware de v9, `main.py`, sin cambios) y, con la cámara
de la Pi 5, hacer dos cosas a la vez:
  1. Rastrear el rostro en tiempo real y mandar su posición a la Pico.
  2. Ciclar las 10 expresiones de la Pico en un orden fijo, cambiando cada
     `--interval` segundos (5 por defecto, igual a `INTERVALO_EXPRESION_MS`
     en `main.py`, para que el pulso de una expresión nunca expire y caiga
     a NEUTRAL entre un cambio y el siguiente).

El firmware sigue sin ciclar solo (modelo dirigido por eventos desde v8):
este script hace de "reloj externo", mandando una `EMOCION` nueva por
serial cada `--interval` segundos.

Uso:
    python rastreo_expresiones.py
    python rastreo_expresiones.py --camera-index 0     # si no hay CSI y tu webcam no es /dev/video1
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

# Cadencia mínima entre envíos de mirada a la Pico, en segundos. Validado en
# hardware real: a más frecuencia (probado a 20 envíos/s) el buffer USB CDC de
# la Pico se saturaba (ver pico_serial.py, _drenar_entrada).
CADENCIA_ENVIO_S = 0.2

# Última posición real del rostro detectado por el hilo de rastreo (grados de
# servo, 40-140). Sin --tracking activo, o mientras no se detecte ningún
# rostro todavía, se queda en el centro (90,90).
ULTIMA_MIRADA = {"lr": 90, "ud": 90}
_LOCK_MIRADA = threading.Lock()

PICO = None


def _siguiente_indice(indice_actual: int) -> int:
    """Avanza el índice del ciclo de expresiones, volviendo a 0 tras la última.
    Aislado del temporizador real para poder probarlo sin esperar segundos de
    verdad (ver tests/test_rastreo_expresiones.py)."""
    return (indice_actual + 1) % len(CICLO_EMOCIONES)


def _hilo_rastreo(leer, detener: threading.Event):
    """Rastrea el rostro por cámara y manda su posición real a la Pico. Corre
    en un hilo de fondo, en paralelo al ciclo de expresiones del hilo
    principal.

    Recibe un *callable* `leer` (sin argumentos) que devuelve el par
    `(ret, frame)`, en vez de un objeto de cámara concreto — así funciona
    igual con `cv2.VideoCapture.read` (webcam USB) que con
    `lambda: leer_frame(picam2)` (cámara CSI, ver face_tracker.py).
    """
    import cv2
    from face_tracker import FaceTracker

    print("✅ Cámara lista: el rastreo facial está activo.")
    # Parámetros calibrados en hardware real: alpha alto + zona muerta 0 para
    # que el cliente apenas suavice y nunca retenga un comando — la Pico ya
    # suaviza internamente (ALPHA=0.1 en main.py).
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
            if ahora - ultimo_envio < CADENCIA_ENVIO_S:
                continue
            ultimo_envio = ahora
            # Se envía en CADA frame detectado dentro de la cadencia, no solo
            # cuando hay "cambio_significativo": el firmware de la Pico ya
            # suaviza el movimiento internamente, así que necesita un flujo
            # continuo de objetivos, no comandos discretos que se cortan al
            # converger el EMA del cliente.
            lr, ud = resultado["grado_x"], resultado["grado_y"]
            with _LOCK_MIRADA:
                ULTIMA_MIRADA["lr"], ULTIMA_MIRADA["ud"] = lr, ud
            if PICO is not None:
                PICO.enviar(lr, ud)
    finally:
        pass  # la cámara se libera en main(), según su tipo (picam2.stop() / cap.release())


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
        description="Ciclo de expresiones + rastreo facial real, Pi 5 + Pico, sin voz en este proceso.")
    parser.add_argument("--interval", type=float, default=INTERVALO_POR_DEFECTO_S,
                        help=f"Segundos entre cada cambio de expresión (por defecto: "
                             f"{INTERVALO_POR_DEFECTO_S}, igual al pulso de main.py).")
    parser.add_argument("--camera-index", type=int, default=1,
                        help="Índice de cámara para cv2.VideoCapture, usado solo como "
                             "respaldo si no hay cámara CSI disponible (por defecto: 1).")
    parser.add_argument("--no-tracking", dest="tracking", action="store_false",
                        help="No rastrear el rostro; la mirada se queda fija en 90,90.")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No envíes nada a la Pico aunque haya una conectada "
                             "(prueba solo la cámara y el ciclo en consola).")
    args = parser.parse_args()

    global PICO
    detener_rastreo = threading.Event()
    detener_ciclo = threading.Event()
    camara = None

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
        from face_tracker import ALTO, ANCHO, abrir_camara_csi, leer_frame

        leer = None

        # Cámara CSI (OV5647, conector CAM/DISP 1) vía picamera2 — el hardware
        # real de esta Pi 5, que no habla el API de cv2.VideoCapture.
        print("🔍 Iniciando cámara CSI (picamera2)...")
        try:
            camara = abrir_camara_csi(ANCHO, ALTO)
            leer = lambda: leer_frame(camara)
            print("✅ Cámara CSI lista (OV5647).")
        except ImportError:
            print("⚠️  Falta 'picamera2'. En Raspberry Pi OS se instala con:")
            print("      sudo apt install -y python3-picamera2 --no-install-recommends")
        except Exception as e:
            print(f"⚠️  No se pudo abrir la cámara CSI: {e}")
            print("    Revisa que esté bien conectada y que 'rpicam-hello --list-cameras'")
            print("    la detecte fuera de este script.")

        # Respaldo: webcam USB genérica (V4L2) si no hay CSI disponible.
        if leer is None:
            try:
                import cv2
            except ImportError:
                sys.exit(
                    "ERROR: el rastreo necesita 'opencv-python' + "
                    "'picamera2'. Instala con:\n  pip install -r requirements.txt\n"
                    "O usa --no-tracking para el ciclo de expresiones sin cámara."
                )
            print(f"🔍 Probando webcam USB (índice {args.camera_index})...")
            cap = cv2.VideoCapture(args.camera_index)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
            if not cap.isOpened():
                print(f"⚠️  No se pudo abrir la cámara (índice {args.camera_index}). "
                      "El rastreo facial no estará activo; sigue el ciclo con mirada fija.")
                cap.release()
            else:
                camara = cap
                leer = cap.read
                print("✅ Webcam USB lista.")

        if leer is not None:
            threading.Thread(
                target=_hilo_rastreo, args=(leer, detener_rastreo), daemon=True
            ).start()
        else:
            print("⚠️  Sin cámara disponible: el ciclo correrá con mirada fija en 90,90.")

    print(f"🟢 Ciclo de expresiones activo, cada {args.interval:.1f}s. Ctrl+C para salir.")
    try:
        _ciclar_expresiones(args.interval, detener_ciclo)
    except KeyboardInterrupt:
        print("\n👋 Deteniendo...")
    finally:
        detener_rastreo.set()
        detener_ciclo.set()
        # Liberar la cámara según su tipo: picamera2 usa stop(), cv2 usa release().
        if camara is not None:
            try:
                camara.stop()
            except AttributeError:
                camara.release()
        if PICO is not None:
            PICO.stop()


if __name__ == "__main__":
    main()
