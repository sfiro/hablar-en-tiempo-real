#!/usr/bin/env python3
"""
Rastreo facial por cámara, adaptado de `rastreoCara_Mac.py` (proyecto ojosMecanicos).

`FaceTracker` es la lógica pura: detecta un rostro, suaviza su posición con un filtro
EMA, y la traduce a grados de servo (40-140). No abre ninguna ventana ni toca
`cv2.imshow`, a propósito — así se puede usar igual desde un hilo de fondo sin GUI.
`webrtc_server.py` importa `FaceTracker` directamente y la usa en un hilo de fondo
mientras la conversación de voz corre en el hilo principal (ver PLAN-v10.md).

Adaptado de `../v9/face_tracker.py` (que a su vez viene de v8, v7, v6, v5, v4, v3,
y originalmente de `ojosMecanicos/rastreoCara_Mac.py`) para el cambio de cliente de
v10: hasta v9 la cámara era la webcam del Mac, capturada con `cv2.VideoCapture`;
desde v10 es el módulo de cámara CSI de la Raspberry Pi 5, capturado con
`picamera2`/`libcamera`, que no habla el mismo API que `cv2.VideoCapture`. El único
cambio real está en cómo se obtienen los frames (`_run_standalone()`, más abajo);
`FaceTracker.procesar()` no cambió ni una línea — sigue recibiendo un frame BGR de
cualquier origen, sin saber ni importarle si vino de una webcam USB o de una cámara
CSI. Cada versión de este proyecto es autónoma y no importa código de otra carpeta
de versión, así que este fichero se duplica en vez de referenciarse — ver
CLAUDE.md, sección "Cada versión es independiente".

Por qué `picamera2` en vez de `cv2.VideoCapture(0)` también en la Pi 5: la Raspberry
Pi 5 sí podría tener una cámara USB y usar `cv2.VideoCapture` sin tocar nada más
(sería el cambio mínimo) — pero esta versión usa el módulo de cámara CSI, que en
Raspberry Pi OS (Bookworm en adelante) se accede por `libcamera`, no por el driver
V4L2 genérico que espera OpenCV. `picamera2` es el binding oficial de Raspberry Pi
para `libcamera` y se instala vía `apt` (paquete `python3-picamera2`), no por pip
puro — ver requirements.txt y README-v10.md para el detalle de instalación con venv.

**Nada de esto se ha podido probar contra hardware real todavía** (este código se
escribió en un Mac, sin una Raspberry Pi 5 ni cámara CSI delante) — a diferencia de
v9, que si llegó a validarse en hardware real. Verificado aquí: sintaxis, y que
`FaceTracker`/`_mapear` (la parte que no cambió) siguen pasando los mismos tests de
v9 sin necesitar `picamera2` instalado, porque su import es diferido dentro de
`_run_standalone()` — ver más abajo.

Corrección respecto al original: la conversión a gris usaba `cv2.COLOR_RGB2GRAY`
sobre un frame que en realidad viene en BGR (así entrega los frames
`cv2.VideoCapture` por defecto, y así se configura aquí también `picamera2`, con
`format="BGR888"`, para no tener que tocar `FaceTracker.procesar()`). El resultado
visual apenas cambia porque las ponderaciones de canal son parecidas, pero es la
conversión incorrecta; aquí se usa `COLOR_BGR2GRAY`.

Uso como script independiente (con ventana de depuración, para probar la cámara):
    python face_tracker.py
    python face_tracker.py --no-window
    python face_tracker.py --no-pico          # ignora la Pico aunque esté conectada
"""

import argparse
import sys
import time

import cv2

ANCHO = 640
ALTO = 480
ESCALA_DETECCION = 0.5   # analizar a mitad de tamaño, más rápido
ALPHA = 0.2              # filtro EMA: 0 = muy lento/suave, 1 = instantáneo/tembloroso
ZONA_MUERTA = 2          # grados de cambio mínimo para justificar un comando nuevo


def _mapear(valor: float, in_min: float, in_max: float, out_min: float, out_max: float) -> int:
    return int((valor - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


class FaceTracker:
    """Detecta un rostro y da su posición como grados de servo, suavizada.

    Headless por diseño: `procesar()` recibe un frame BGR (de la cámara que sea,
    ya con el flip de espejo aplicado si se quiere ese efecto) y devuelve la
    posición. No dibuja nada ni abre ventanas.
    """

    def __init__(self, ancho: int = ANCHO, alto: int = ALTO,
                 escala_deteccion: float = ESCALA_DETECCION,
                 alpha: float = ALPHA, zona_muerta: int = ZONA_MUERTA):
        self.ancho = ancho
        self.alto = alto
        self.escala_deteccion = escala_deteccion
        self.alpha = alpha
        self.zona_muerta = zona_muerta
        self._cascada = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        # Arrancan centrados (90°,90°), igual que el script original.
        self._suavizado_x = 90.0
        self._suavizado_y = 90.0
        self._ultimo_x = 90
        self._ultimo_y = 90

    def procesar(self, frame) -> dict:
        """Procesa un frame BGR. Devuelve:
            {"detectado": bool, "grado_x": int, "grado_y": int,
             "bbox": (x,y,w,h) | None, "cambio_significativo": bool}

        Si no hay rostro, devuelve la última posición conocida con
        `cambio_significativo=False` (no hay nada nuevo que reportar/enviar).
        """
        small = cv2.resize(frame, (0, 0), fx=self.escala_deteccion, fy=self.escala_deteccion)
        gris = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        rostros = self._cascada.detectMultiScale(gris, scaleFactor=1.3, minNeighbors=5)

        if len(rostros) == 0:
            return {
                "detectado": False, "grado_x": self._ultimo_x, "grado_y": self._ultimo_y,
                "bbox": None, "cambio_significativo": False,
            }

        (x, y, w, h) = (int(v / self.escala_deteccion) for v in rostros[0])
        centro_x = x + w // 2
        centro_y = y + h // 2

        grado_x = _mapear(centro_x, 0, self.ancho, 40, 140)
        grado_y = _mapear(centro_y, 0, self.alto, 140, 40)

        self._suavizado_x = (self.alpha * grado_x) + ((1 - self.alpha) * self._suavizado_x)
        self._suavizado_y = (self.alpha * grado_y) + ((1 - self.alpha) * self._suavizado_y)
        final_x, final_y = int(self._suavizado_x), int(self._suavizado_y)

        cambio = (abs(final_x - self._ultimo_x) >= self.zona_muerta
                  or abs(final_y - self._ultimo_y) >= self.zona_muerta)
        if cambio:
            self._ultimo_x, self._ultimo_y = final_x, final_y

        return {
            "detectado": True, "grado_x": final_x, "grado_y": final_y,
            "bbox": (x, y, w, h), "cambio_significativo": cambio,
        }


def abrir_camara_csi(ancho: int = ANCHO, alto: int = ALTO):
    """Abre la cámara CSI de la Raspberry Pi 5 vía `picamera2` y la deja lista para
    `leer_frame()`. Import diferido a propósito: así los tests (y cualquier otro uso
    de `FaceTracker`/`_mapear` sin cámara) no necesitan `picamera2` instalado — solo
    hace falta al ejecutar este fichero como script en la propia Pi 5.

    `format="BGR888"` hace que `capture_array()` devuelva frames en el mismo orden
    de canal (BGR) que `cv2.VideoCapture` entregaba en versiones anteriores, así que
    el resto del pipeline (`cv2.flip`, `FaceTracker.procesar()`) no tiene que
    distinguir de dónde vino el frame.
    """
    from picamera2 import Picamera2

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (ancho, alto), "format": "BGR888"}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)  # margen para que se estabilice la exposición/balance de blancos
    return picam2


def leer_frame(picam2):
    """Mismo contrato que `cv2.VideoCapture.read()` (par `(ret, frame)`), para que
    el resto del código no tenga que ramificar según el origen de la cámara.
    `capture_array()` no devuelve un booleano de éxito — si falla, lanza una
    excepción — así que aquí se traduce a `ret=False` en vez de dejarla propagar y
    tumbar el hilo de rastreo por un fallo puntual de un solo frame."""
    try:
        frame = picam2.capture_array()
    except Exception as e:
        print(f"⚠️  No se pudo leer el frame de la cámara CSI: {e}")
        return False, None
    return True, frame


def _run_standalone(mostrar_ventana: bool, usar_pico: bool):
    """Bucle de prueba: cámara CSI + FaceTracker + (opcional) ventana + (opcional) Pico.

    Esto es solo para validar la cámara y el detector solos, en la propia Pi 5. La
    versión headless real, integrada con la voz, vive en `webrtc_server.py`.
    """
    print("🔍 Iniciando cámara CSI (picamera2)...")
    try:
        picam2 = abrir_camara_csi()
    except ImportError:
        print("⚠️  Falta 'picamera2'. En Raspberry Pi OS se instala con:")
        print("      sudo apt install -y python3-picamera2 --no-install-recommends")
        print("    (y el venv debe crearse con --system-site-packages — ver README-v10.md)")
        sys.exit(1)
    except Exception as e:
        print(f"⚠️  No se pudo abrir la cámara CSI: {e}")
        print("    Revisa que esté habilitada (raspi-config → Interface Options → Camera)")
        print("    y que 'libcamera-hello' la detecte fuera de este script.")
        sys.exit(1)
    print("✅ Cámara lista")

    pico = None
    if usar_pico:
        from pico_serial import PicoLink, encontrar_puerto_pico
        puerto = encontrar_puerto_pico()
        if puerto:
            pico = PicoLink(port=puerto)
            pico.start()
            print(f"✅ Pico detectada en {puerto} (conectando en segundo plano)")
        else:
            print("⚠️  No se detectó ninguna Pico. Se rastreará sin enviar comandos.")

    tracker = FaceTracker()
    print("🟢 Rastreo iniciado."
          + (" Presiona 'q' en la ventana para salir." if mostrar_ventana else " Ctrl+C para salir."))

    try:
        while True:
            ret, frame = leer_frame(picam2)
            if not ret:
                break

            frame = cv2.flip(frame, 1)  # efecto espejo
            resultado = tracker.procesar(frame)

            if resultado["detectado"] and resultado["cambio_significativo"]:
                print(f"🎯 x={resultado['grado_x']}, y={resultado['grado_y']}")
                if pico is not None:
                    pico.enviar(resultado["grado_x"], resultado["grado_y"])

            if mostrar_ventana:
                if resultado["bbox"] is not None:
                    x, y, w, h = resultado["bbox"]
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.circle(frame, (x + w // 2, y + h // 2), 5, (0, 0, 255), -1)
                cv2.imshow("Rastreo Facial (v10, prueba standalone)", frame)
                if cv2.waitKey(20) & 0xFF == ord("q"):
                    print("\n🛑 Saliendo (tecla 'q')...")
                    break

    except KeyboardInterrupt:
        print("\n🛑 Saliendo por teclado (Ctrl+C)...")

    finally:
        picam2.stop()
        if mostrar_ventana:
            cv2.destroyAllWindows()
        if pico is not None:
            pico.stop()
        print("✅ Recursos liberados")


def main():
    parser = argparse.ArgumentParser(
        description="Prueba standalone del rastreo facial con la cámara CSI (ver PLAN-v10.md).")
    parser.add_argument("--no-window", dest="mostrar_ventana", action="store_false",
                        help="No abrir ventana de vídeo; solo imprime x,y en consola. "
                             "Necesario si se ejecuta sin escritorio (SSH puro).")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No intentar conectar con la Pico aunque esté enchufada.")
    args = parser.parse_args()
    _run_standalone(args.mostrar_ventana, args.usar_pico)


if __name__ == "__main__":
    main()
