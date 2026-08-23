#!/usr/bin/env python3
"""
Rastreo facial por cámara, adaptado de `rastreoCara_Mac.py` (proyecto ojosMecanicos).

`FaceTracker` es la lógica pura: detecta un rostro, suaviza su posición con un filtro
EMA, y la traduce a grados de servo (40-140). No abre ninguna ventana ni toca
`cv2.imshow`, a propósito — así se puede usar igual desde un hilo de fondo sin GUI.
`rastreo_expresiones.py` importa `FaceTracker` directamente y la usa en un hilo de
fondo mientras el ciclo de expresiones corre en el hilo principal (ver PLAN-v12.md).

Copia de `../v9/face_tracker.py` (que a su vez viene de v7, v6, v5, v4, v3, y
originalmente de `ojosMecanicos/rastreoCara_Mac.py`): la clase `FaceTracker` en sí
—EMA, zona muerta, mapeo a grados— **no cambió de estructura**. Cada versión de este
proyecto es autónoma y no importa código de otra carpeta de versión, así que este
fichero se duplica en vez de referenciarse — ver CLAUDE.md, sección "Cada versión es
independiente".

**Corregido tras la validación en hardware real (23/08/2026):** la spec original de
v12 asumía una webcam USB (`/dev/video1`, `cv2.VideoCapture`). La Raspberry Pi 5 real
usa en cambio la **cámara CSI OV5647** (conector CAM/DISP 1) — el mismo tipo de
cámara que v10, que no habla el API de `cv2.VideoCapture` (bus CSI, no V4L2
genérico). Por eso este fichero trae, portadas literalmente de v10,
`abrir_camara_csi()`/`leer_frame()` (envuelven `picamera2`, import diferido para que
los tests no lo necesiten instalado); `rastreo_expresiones.py` intenta la CSI primero
y solo si falla cae a `cv2.VideoCapture` (webcam USB) — ver su cabecera. `main.py`
(firmware) y `pico_serial.py` no se vieron afectados por este cambio de cámara.
Detalle completo de la depuración real: [`MODIFICACIONES-LOCALES.md`](MODIFICACIONES-LOCALES.md).

**Tres ajustes más, todos encontrados y corregidos con la cámara CSI real
delante** (detalle en `MODIFICACIONES-LOCALES.md`):
1. **Resolución y parámetros de la cascada:** a 640×480 (pensado para la webcam
   USB original) la OV5647 hace un crop del sensor que dejaba la cara casi sin
   detectar (0.4% de los frames). Subir a `ANCHO=1296, ALTO=972` y relajar
   `detectMultiScale` de `scaleFactor=1.3, minNeighbors=5` a `1.2, 4` llevó la
   detección al 100% de los frames, medido con una persona real delante de la
   cámara.
2. **Falso positivo fijo secuestrando la mirada:** la cascada Haar a veces
   detecta un objeto pequeño y estático del fondo antes que la cara real, y
   tomar `rostros[0]` (el primero) clavaba la mirada en ese objeto en vez de
   seguir al rostro. `procesar()` ahora elige el rostro de **mayor área** entre
   todas las detecciones, y descarta las menores de 80px de lado (un falso
   positivo típico es más pequeño que una cara real a esta distancia).
3. **EMA y zona muerta recalibrados:** `ALPHA` sube de 0.2 a 0.5 (más reactivo:
   la mirada alcanza antes al rostro real) y `ZONA_MUERTA` baja de 2 a 0 (el
   cliente ya casi no filtra — la Pico suaviza internamente con su propio
   `ALPHA=0.1` en `main.py`, así que retener comandos aquí solo añadía
   "congelamiento" al converger, sin aportar suavidad real).

Corrección heredada respecto al original: la conversión a gris usaba
`cv2.COLOR_RGB2GRAY` sobre un frame que en realidad viene en BGR (así entrega los
frames `cv2.VideoCapture` por defecto). Aquí se usa `COLOR_BGR2GRAY`.

Uso como script independiente (con ventana de depuración, para probar la webcam USB;
para la cámara CSI usa `rastreo_solo.py` o `rastreo_expresiones.py`, que sí la abren):
    python face_tracker.py
    python face_tracker.py --no-window
    python face_tracker.py --no-pico          # ignora la Pico aunque esté conectada
    python face_tracker.py --camera-index 0   # si tu webcam no es /dev/video1
"""

import argparse
import sys
import time

import cv2

ANCHO = 1296
ALTO = 972
ESCALA_DETECCION = 0.5   # analizar a mitad de tamaño, más rápido
ALPHA = 0.5              # filtro EMA: 0 = muy lento/suave, 1 = instantáneo/tembloroso
ZONA_MUERTA = 0          # grados de cambio mínimo: 0 = enviar siempre (la Pico ya suaviza)


def _mapear(valor: float, in_min: float, in_max: float, out_min: float, out_max: float) -> int:
    return int((valor - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)


class FaceTracker:
    """Detecta un rostro y da su posición como grados de servo, suavizada.

    Headless por diseño: `procesar()` recibe un frame BGR (de `cv2.VideoCapture` o
    de `leer_frame()` con la cámara CSI, ya con el flip de espejo aplicado si se
    quiere ese efecto) y devuelve la posición. No dibuja nada ni abre ventanas.
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
        rostros = self._cascada.detectMultiScale(gris, scaleFactor=1.2, minNeighbors=4)

        if len(rostros) == 0:
            return {
                "detectado": False, "grado_x": self._ultimo_x, "grado_y": self._ultimo_y,
                "bbox": None, "cambio_significativo": False,
            }

        # Elegir el rostro MÁS GRANDE, no el primero: la cascada Haar a veces
        # devuelve falsos positivos pequeños (objetos/fotos del fondo) ANTES que
        # la cara real, y tomar rostros[0] clavaba la mirada en el objeto fijo.
        # Hallazgo real con la cámara CSI de la Pi 5 (23/08/2026): con un falso
        # positivo estático de 64x64, los ojos se quedaban apuntando a él y no
        # seguían el rostro real. El rostro real delante de la cámara es casi
        # siempre el de mayor área; además se descartan detecciones diminutas
        # (< 80px de lado).
        x, y, w, h = max(
            ((int(r[0] / self.escala_deteccion), int(r[1] / self.escala_deteccion),
              int(r[2] / self.escala_deteccion), int(r[3] / self.escala_deteccion))
             for r in rostros),
            key=lambda bb: bb[2] * bb[3],
        )
        if w < 80 or h < 80:
            return {
                "detectado": False, "grado_x": self._ultimo_x, "grado_y": self._ultimo_y,
                "bbox": None, "cambio_significativo": False,
            }
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
    de `FaceTracker`/`_mapear` sin cámara) no necesitan `picamera2` instalado.

    Portado de v10: la cámara real de esta Pi 5 es la CSI OV5647 (conector
    CAM/DISP 1), que no habla el API de `cv2.VideoCapture` — el mismo motivo que
    documentó v10. `format="BGR888"` hace que `capture_array()` devuelva frames
    BGR, el mismo orden que entregaba `cv2.VideoCapture`, así que el resto del
    pipeline (`cv2.flip`, `FaceTracker.procesar`) no cambia.

    `FrameRate=15`: la cámara por defecto produce más frames de los que el bucle
    de detección a 1296×972 consume (~25 FPS); si se deja a su ritmo nativo, la
    cola interna de `picamera2` se acumula y el rastreo procesa frames cada vez
    más viejos (lag creciente — hallazgo real, ver `MODIFICACIONES-LOCALES.md`).
    Limitarla a 15 FPS, por debajo del consumo del bucle, evita que la cola
    crezca nunca.
    """
    from picamera2 import Picamera2

    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"size": (ancho, alto), "format": "BGR888"}
    )
    picam2.configure(config)
    picam2.start()
    picam2.set_controls({"FrameRate": 15})
    time.sleep(1)  # margen para que se estabilice la exposición/balance de blancos
    return picam2


def leer_frame(picam2):
    """Mismo contrato que `cv2.VideoCapture.read()` (par `(ret, frame)`), para que
    el resto del código no tenga que ramificar según el origen de la cámara.
    `capture_array()` no devuelve booleano de éxito — si falla, lanza excepción —
    así que aquí se traduce a `ret=False` en vez de tumbarse por un frame puntual."""
    try:
        frame = picam2.capture_array()
    except Exception as e:
        print(f"⚠️  No se pudo leer el frame de la cámara CSI: {e}")
        return False, None
    return True, frame


def _run_standalone(mostrar_ventana: bool, usar_pico: bool, camera_index: int):
    """Bucle de prueba: webcam USB + FaceTracker + (opcional) ventana + (opcional) Pico.

    Esto es solo para validar la webcam USB y el detector solos, sin el ciclo de
    expresiones de rastreo_expresiones.py. Para probar la cámara CSI real de esta
    Pi 5, usa `rastreo_solo.py` (que sí abre `abrir_camara_csi()`), no este script.
    """
    print("🔍 Iniciando cámara...")
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
    time.sleep(1)

    if not cap.isOpened():
        print(f"⚠️  No se pudo abrir la cámara (índice {camera_index}).")
        print("    Prueba con --camera-index 0 si tu webcam no enumera como "
              "/dev/video1, o revisa 'v4l2-ctl --list-devices'.")
        cap.release()
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
            ret, frame = cap.read()
            if not ret:
                print("⚠️  No se pudo leer el frame de la cámara")
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
                cv2.imshow("Rastreo Facial (v12, prueba standalone)", frame)
                if cv2.waitKey(20) & 0xFF == ord("q"):
                    print("\n🛑 Saliendo (tecla 'q')...")
                    break

    except KeyboardInterrupt:
        print("\n🛑 Saliendo por teclado (Ctrl+C)...")

    finally:
        cap.release()
        if mostrar_ventana:
            cv2.destroyAllWindows()
        if pico is not None:
            pico.stop()
        print("✅ Recursos liberados")


def main():
    parser = argparse.ArgumentParser(
        description="Prueba standalone del rastreo facial con webcam USB (ver PLAN-v12.md).")
    parser.add_argument("--no-window", dest="mostrar_ventana", action="store_false",
                        help="No abrir ventana de vídeo; solo imprime x,y en consola.")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No intentar conectar con la Pico aunque esté enchufada.")
    parser.add_argument("--camera-index", type=int, default=1,
                        help="Índice de cámara para cv2.VideoCapture (por defecto: 1, "
                             "donde esta Pi 5 enumera la webcam USB — /dev/video1).")
    args = parser.parse_args()
    _run_standalone(args.mostrar_ventana, args.usar_pico, args.camera_index)


if __name__ == "__main__":
    main()
