#!/usr/bin/env python3
"""
Rastreo facial por cámara, adaptado de `rastreoCara_Mac.py` (proyecto ojosMecanicos).

`FaceTracker` es la lógica pura: detecta un rostro, suaviza su posición con un filtro
EMA, y la traduce a grados de servo (40-140). No abre ninguna ventana ni toca
`cv2.imshow`, a propósito — así se puede usar igual desde un hilo de fondo sin GUI
cuando se integre con la conversación de voz (ver PLAN-v5.md).

Copia idéntica de `../v4/face_tracker.py` (que a su vez viene de `../v3/`, y
originalmente de `ojosMecanicos/rastreoCara_Mac.py`). Cada versión de este proyecto
es autónoma y no importa código de otra carpeta de versión, así que este fichero se
duplica en vez de referenciarse — ver CLAUDE.md, sección "Cada versión es
independiente".

Corrección respecto al original: la conversión a gris usaba `cv2.COLOR_RGB2GRAY`
sobre un frame que en realidad viene en BGR (así entrega los frames
`cv2.VideoCapture` por defecto). El resultado visual apenas cambia porque las
ponderaciones de canal son parecidas, pero es la conversión incorrecta; aquí se usa
`COLOR_BGR2GRAY`.

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

    Headless por diseño: `procesar()` recibe un frame BGR (de `cv2.VideoCapture`,
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


def _run_standalone(mostrar_ventana: bool, usar_pico: bool, camera_index: int):
    """Bucle de prueba: cámara + FaceTracker + (opcional) ventana + (opcional) Pico.

    Esto es solo para el Hito 1 (validar la cámara y el detector solos). La versión
    headless real, integrada con la voz, vive en el Hito 2 — no en este bucle.
    """
    print("🔍 Iniciando cámara...")
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
    time.sleep(1)

    if not cap.isOpened():
        print(f"⚠️  No se pudo abrir la cámara (índice {camera_index}).")
        print("    En macOS, revisa el permiso de cámara para la Terminal en")
        print("    Ajustes del Sistema → Privacidad y seguridad → Cámara.")
        cap.release()
        sys.exit(1)
    print("✅ Cámara lista")

    pico = None
    if usar_pico:
        from pico_serial import PicoLink, encontrar_puerto_mac
        puerto = encontrar_puerto_mac()
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
                cv2.imshow("Rastreo Facial (v5, prueba standalone)", frame)
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
        description="Prueba standalone del rastreo facial (ver PLAN-v5.md).")
    parser.add_argument("--no-window", dest="mostrar_ventana", action="store_false",
                        help="No abrir ventana de vídeo; solo imprime x,y en consola.")
    parser.add_argument("--no-pico", dest="usar_pico", action="store_false",
                        help="No intentar conectar con la Pico aunque esté enchufada.")
    parser.add_argument("--camera-index", type=int, default=0,
                        help="Índice de cámara para cv2.VideoCapture (por defecto: 0).")
    args = parser.parse_args()
    _run_standalone(args.mostrar_ventana, args.usar_pico, args.camera_index)


if __name__ == "__main__":
    main()
