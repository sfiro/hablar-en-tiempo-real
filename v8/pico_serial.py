#!/usr/bin/env python3
"""
Enlace serial hacia la Raspberry Pi Pico que mueve los servos ("ojos mecánicos").

Protocolo confirmado en el proyecto hermano `ojosMecanicos` (server_realtime.py +
firmware main.py), reutilizado tal cual:

    Formato:   LR,UD,EMOCION\n     (o LR,UD\n sin emoción)
    Ejemplo:   120,60,FELIZ\n
    LR, UD:    enteros 40-140 (grados de servo)
    EMOCION:   opcional, mayúsculas, uno de: NEUTRAL, FELIZ, ENOJADO, TRISTE,
               SORPRENDIDO, DORMIDO, DUDA, SOSPECHA, PENSATIVO, NERVIOSO
    Baud:      115200

Sin la Pico conectada, `PicoLink` sigue funcionando: `enviar()` no hace nada y no
lanza excepción, igual que `pico is None` en el script de referencia.

Copia idéntica de `../v7/pico_serial.py` (que a su vez viene de v6, v5, v4, v3),
compatible además con `main.py` en esta misma carpeta — que, a diferencia de v3-v7,
ya no ignora el campo EMOCION: lo usa para decidir la expresión facial (ver la
cabecera de `main.py`). Cada versión de este proyecto es autónoma y no importa
código de otra carpeta de versión — ver CLAUDE.md.
"""

import glob
import logging
import queue
import threading
import time

logger = logging.getLogger(__name__)

BAUD_RATE = 115200
HEARTBEAT_S = 1.0        # reenviar el último comando cada 1s, o la Pico vuelve a modo autónomo
RECONNECT_INTERVAL_S = 2.0
GRADO_MIN, GRADO_MAX = 40, 140

EMOCIONES_VALIDAS = {
    "NEUTRAL", "FELIZ", "ENOJADO", "TRISTE", "SORPRENDIDO",
    "DORMIDO", "DUDA", "SOSPECHA", "PENSATIVO", "NERVIOSO",
}


def encontrar_puerto_mac() -> str | None:
    """Busca el puerto serial de la Pico en macOS. None si no hay ninguna conectada."""
    puertos = glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/tty.usbmodem*")
    return puertos[0] if puertos else None


def _formatear_comando(lr: int, ud: int, emocion: str | None) -> str:
    lr = max(GRADO_MIN, min(GRADO_MAX, int(lr)))
    ud = max(GRADO_MIN, min(GRADO_MAX, int(ud)))
    if emocion is None:
        return f"{lr},{ud}\n"
    emocion = emocion.upper()
    if emocion not in EMOCIONES_VALIDAS:
        raise ValueError(f"Emoción no válida para la Pico: {emocion!r}. "
                         f"Usa una de {sorted(EMOCIONES_VALIDAS)}.")
    return f"{lr},{ud},{emocion}\n"


class PicoLink:
    """Enlace serial con reconexión y latido, en un hilo aparte.

    `serial_factory` es inyectable para poder probar la lógica de cola/latido sin
    hardware real (ver tests/test_pico_serial.py); por defecto abre `pyserial`.
    """

    def __init__(self, port: str | None = None, baud: int = BAUD_RATE,
                 heartbeat_s: float = HEARTBEAT_S, serial_factory=None):
        self._port = port
        self._baud = baud
        self._heartbeat_s = heartbeat_s
        self._serial_factory = serial_factory or self._pyserial_factory
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._lock = threading.Lock()
        self._ultimo_comando: str | None = None
        self._conexion = None
        self._detener = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    @staticmethod
    def _pyserial_factory(port: str, baud: int):
        import serial
        return serial.Serial(port, baud, timeout=0.1)

    def start(self):
        self._thread.start()

    def stop(self):
        self._detener.set()
        self._queue.put_nowait("")  # despierta el hilo si está bloqueado en get()
        self._thread.join(timeout=2)
        if self._conexion is not None:
            try:
                self._conexion.close()
            except Exception:
                pass

    def esta_conectado(self) -> bool:
        return self._conexion is not None

    def enviar(self, lr: int, ud: int, emocion: str | None = None):
        """Encola un comando. Válido llamarlo sin Pico conectada: no hace nada."""
        comando = _formatear_comando(lr, ud, emocion)
        with self._lock:
            self._ultimo_comando = comando
        self._queue.put_nowait(comando)

    def _intentar_conectar(self):
        port = self._port or encontrar_puerto_mac()
        if not port:
            return
        try:
            self._conexion = self._serial_factory(port, self._baud)
            self._port = port
            logger.info(f"Conectado a la Pico en {port}")
        except Exception as e:
            logger.warning(f"No se pudo conectar a la Pico en {port}: {e}")
            self._conexion = None

    def _puerto_sigue_existiendo(self) -> bool:
        # El chequeo de que el archivo /dev/... siga existiendo es un truco específico
        # de pyserial/macOS con hardware real (confirmado en ojosMecanicos). Con un
        # serial_factory inyectado (tests, sin filesystem real detrás) no aplica: se
        # confía solo en si la escritura falla o no.
        if self._serial_factory is not self._pyserial_factory:
            return True
        return bool(glob.glob(self._port)) if self._port else True

    def _escribir(self, comando: str):
        if self._conexion is None or not comando:
            return
        try:
            self._conexion.write(comando.encode("utf-8"))
        except Exception as e:
            logger.warning(f"Escritura serial falló, se asume desconexión: {e}")
            self._conexion = None

    def _run(self):
        ultimo_latido = 0.0
        while not self._detener.is_set():
            # Reconexión: si no hay conexión, o si el path del puerto ya no existe.
            if self._conexion is None:
                self._intentar_conectar()
                if self._conexion is None:
                    time.sleep(RECONNECT_INTERVAL_S)
                    continue
            elif not self._puerto_sigue_existiendo():
                logger.warning("El puerto de la Pico desapareció; se reintentará conectar.")
                self._conexion = None
                continue

            try:
                comando = self._queue.get(timeout=self._heartbeat_s)
            except queue.Empty:
                comando = None

            if comando:
                self._escribir(comando)
                ultimo_latido = time.monotonic()
            else:
                # Nada nuevo que enviar: si hay un último comando y toca latido, reenvía.
                ahora = time.monotonic()
                if ahora - ultimo_latido >= self._heartbeat_s:
                    with self._lock:
                        ultimo = self._ultimo_comando
                    if ultimo:
                        self._escribir(ultimo)
                    ultimo_latido = ahora

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    puerto = encontrar_puerto_mac()
    if not puerto:
        print("⚠️  No se detectó ninguna Pico. Prueba de humo solo con la lógica local.")
    else:
        print(f"Pico detectada en {puerto}")

    with PicoLink(port=puerto) as pico:
        print("Enviando comando de prueba: 90,90,NEUTRAL")
        pico.enviar(90, 90, "NEUTRAL")
        time.sleep(3)
        print(f"Conectada: {pico.esta_conectado()}")
