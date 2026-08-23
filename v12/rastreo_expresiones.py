#!/usr/bin/env python3
"""
Raspberry Pi 5 + Pico, sin voz todavía: ciclo de expresiones cada 5 segundos +
rastreo facial real por la cámara de la Pi 5.

Objetivo de v12, pedido explícito: conectar la Raspberry Pi 5 a la Pico por USB
(el mismo firmware de v9, `main.py`, sin cambios) y, con la cámara de la Pi 5,
hacer dos cosas a la vez, todavía sin conversación de voz:
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

**Corregido tras la validación en hardware real (23/08/2026), tres cambios
sobre la spec original:**

1. **Cámara: CSI primero, webcam USB como respaldo.** La spec original de v12
   asumía una webcam USB; la Pi 5 real tiene una cámara CSI OV5647 (conector
   CAM/DISP 1), que no habla el API de `cv2.VideoCapture` — mismo motivo que
   v10. `main()` intenta `abrir_camara_csi()` (portada de v10 a
   `face_tracker.py`) primero, y solo si falla (por `ImportError` sin
   `picamera2`, o cualquier otro error) cae al `cv2.VideoCapture` original.
   `_hilo_rastreo()` ya no recibe un objeto de cámara concreto, sino un
   *callable* `leer` sin argumentos que devuelve `(ret, frame)` — así sirve
   igual para `cap.read` (webcam) que para `lambda: leer_frame(picam2)` (CSI),
   sin ramificar dentro del bucle.
2. **Cadencia y "enviar siempre que se detecte", no solo en cambio
   significativo.** El firmware de la Pico ya suaviza el movimiento
   internamente (`ALPHA=0.1` en `main.py`); lo que necesita del cliente es un
   flujo continuo de objetivos, no comandos discretos que se cortan al
   converger el EMA del cliente. Por eso se envía en cada frame con rostro
   detectado (no solo si `cambio_significativo`), con una cadencia mínima de
   200ms (5 envíos/s) entre mensajes — a más frecuencia (probado a 20/s) el
   buffer USB de la Pico se saturaba, ver `pico_serial.py`.
3. **`FaceTracker(alpha=0.5, zona_muerta=0)`** en el hilo de rastreo: mismos
   valores que se volvieron el nuevo default de `face_tracker.py` tras la
   calibración en hardware real — el cliente apenas suaviza, porque la Pico
   ya lo hace.

Detalle completo de la depuración (incluido el bug real más importante — el
buffer USB de la Pico desbordándose porque nadie leía su salida, corregido en
`pico_serial.py`, no en este fichero): [`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md).

Si solo quieres depurar el rastreo, sin el ciclo de expresiones de por medio
(las expresiones DUDA/PENSATIVO/NERVIOSO hacen que el firmware mueva la
mirada por su cuenta, lo que puede confundirse con un bug del rastreo),
usa [`rastreo_solo.py`](rastreo_solo.py) en su lugar.

Todavía NO implementa conversación de voz — a propósito, alcance explícito de
esta versión. Eso es un paso posterior, una vez validado que la Pi 5 controla
bien la Pico por USB y rastrea con su propia cámara.

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
# la Pico se saturaba (ver pico_serial.py, _drenar_entrada, y
# MODIFICACIONES-LOCALES.md). 200ms = 5 envíos/s.
CADENCIA_ENVIO_S = 0.2

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


def _hilo_rastreo(leer, detener: threading.Event):
    """Rastrea el rostro por cámara y manda su posición real a la Pico. Corre
    en un hilo de fondo, en paralelo al ciclo de expresiones del hilo
    principal.

    Recibe un *callable* `leer` (sin argumentos) que devuelve el par
    `(ret, frame)`, en vez de un objeto de cámara concreto — así funciona
    igual con `cv2.VideoCapture.read` (webcam USB) que con
    `lambda: leer_frame(picam2)` (cámara CSI, ver face_tracker.py). En v9 abrir
    la cámara fuera del hilo principal era imprescindible en macOS
    (AVFoundation no puede negociar el permiso de cámara desde un hilo
    secundario); en Linux/Pi 5 no está confirmado que haga falta, pero
    `main()` sigue abriendo la cámara antes de lanzar este hilo, por
    consistencia — igual criterio que documentó v10.
    """
    import cv2
    from face_tracker import FaceTracker

    print("✅ Cámara lista: el rastreo facial está activo.")
    # Parámetros calibrados en hardware real (23/08/2026): alpha alto + zona
    # muerta 0 para que el cliente apenas suavice y nunca retenga un comando —
    # la Pico ya suaviza internamente (ALPHA=0.1 en main.py).
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
        description="Ciclo de expresiones + rastreo facial real, Pi 5 + Pico, sin voz todavía.")
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
        # real de esta Pi 5, que no habla el API de cv2.VideoCapture (mismo
        # motivo que v10).
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
                    "ERROR: el rastreo necesita 'opencv-python' u 'opencv-python' + "
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
