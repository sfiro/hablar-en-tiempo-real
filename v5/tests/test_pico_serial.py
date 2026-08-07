"""
Tests de pico_serial.py.

Sin hardware real: se inyecta un `serial_factory` falso que registra lo escrito,
en vez de abrir un puerto de verdad. Verifica formato de comando, cola, latido y
reconexión — la lógica que en `ojosMecanicos` nunca se probó con un test explícito.

Ejecutar:
    python -m pytest tests/test_pico_serial.py -v
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pico_serial import PicoLink, _formatear_comando, EMOCIONES_VALIDAS


class FakeSerial:
    """Imita pyserial.Serial: registra lo escrito, puede simular una escritura rota."""

    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.escritos = []
        self.cerrado = False
        self.fallar_siguiente_escritura = False

    def write(self, data: bytes):
        if self.fallar_siguiente_escritura:
            raise OSError("puerto desconectado (simulado)")
        self.escritos.append(data.decode("utf-8"))

    def close(self):
        self.cerrado = True


def _fabrica_que_falla(port, baud):
    raise OSError("no se pudo abrir el puerto (simulado)")


# --- Formato de comando, sin hilos ni serial -------------------------------

def test_formato_con_emocion():
    assert _formatear_comando(90, 90, "FELIZ") == "90,90,FELIZ\n"


def test_formato_sin_emocion():
    assert _formatear_comando(90, 90, None) == "90,90\n"


def test_emocion_se_normaliza_a_mayusculas():
    assert _formatear_comando(90, 90, "feliz") == "90,90,FELIZ\n"


def test_emocion_invalida_lanza_error():
    with pytest.raises(ValueError):
        _formatear_comando(90, 90, "ALEGRIA")  # no está en el vocabulario de la Pico


def test_grados_se_recortan_al_rango_valido():
    # Fuera de 40-140: se recorta, no se rechaza (igual que mapear() del script original).
    assert _formatear_comando(500, -10, None) == "140,40\n"


def test_todas_las_emociones_documentadas_son_aceptadas():
    for emocion in EMOCIONES_VALIDAS:
        _formatear_comando(90, 90, emocion)  # no debe lanzar


# --- PicoLink con serial falso ----------------------------------------------

def test_enviar_sin_puerto_no_falla():
    """Sin Pico conectada, enviar() no debe lanzar ni bloquear (igual que pico=None)."""
    link = PicoLink(port=None, serial_factory=_fabrica_que_falla)
    link.start()
    try:
        link.enviar(90, 90, "NEUTRAL")  # no debe lanzar
        time.sleep(0.1)
        assert not link.esta_conectado()
    finally:
        link.stop()


def test_comando_llega_al_serial_falso():
    fakes = []

    def fabrica(port, baud):
        f = FakeSerial(port, baud)
        fakes.append(f)
        return f

    link = PicoLink(port="/dev/cu.usbmodemFAKE", serial_factory=fabrica)
    link.start()
    try:
        # Da tiempo a que el hilo conecte antes de enviar.
        for _ in range(20):
            if link.esta_conectado():
                break
            time.sleep(0.05)
        assert link.esta_conectado(), "el hilo no llegó a conectar con la fábrica falsa"

        link.enviar(120, 60, "FELIZ")
        time.sleep(0.2)
    finally:
        link.stop()

    assert len(fakes) == 1
    assert "120,60,FELIZ\n" in fakes[0].escritos


def test_latido_reenvia_el_ultimo_comando():
    """Sin enviar nada nuevo, el latido debe repetir el último comando cada heartbeat_s."""
    fakes = []

    def fabrica(port, baud):
        f = FakeSerial(port, baud)
        fakes.append(f)
        return f

    link = PicoLink(port="/dev/cu.usbmodemFAKE", serial_factory=fabrica, heartbeat_s=0.1)
    link.start()
    try:
        for _ in range(20):
            if link.esta_conectado():
                break
            time.sleep(0.05)
        link.enviar(90, 90, "NEUTRAL")
        time.sleep(0.5)  # deberían pasar varios latidos de 0.1s
    finally:
        link.stop()

    envios = fakes[0].escritos
    assert envios.count("90,90,NEUTRAL\n") >= 3, (
        f"esperaba varios reenvíos por latido, se registraron {len(envios)}: {envios}"
    )


def test_escritura_rota_se_trata_como_desconexion_y_reintenta():
    """Tras un fallo de escritura, el hilo debe marcar la conexión como caída y
    reintentar reconectar. Aquí forzamos que la reconexión también falle (el
    dispositivo está genuinamente desconectado), para poder observar el estado final
    "no conectado" sin que una reconexión exitosa lo enmascare de inmediato."""
    fakes = []
    intentos = {"n": 0}

    def fabrica(port, baud):
        intentos["n"] += 1
        if intentos["n"] == 1:
            f = FakeSerial(port, baud)
            fakes.append(f)
            return f
        raise OSError("dispositivo desconectado de verdad (simulado)")

    link = PicoLink(port="/dev/cu.usbmodemFAKE", serial_factory=fabrica, heartbeat_s=0.05)
    link.start()
    try:
        for _ in range(20):
            if link.esta_conectado():
                break
            time.sleep(0.05)
        assert link.esta_conectado()

        fakes[0].fallar_siguiente_escritura = True
        link.enviar(90, 90, "NEUTRAL")

        for _ in range(30):
            if not link.esta_conectado():
                break
            time.sleep(0.05)
        assert not link.esta_conectado(), (
            "debería quedar desconectado tras un fallo de escritura seguido de "
            "reconexiones fallidas"
        )
    finally:
        link.stop()

    assert intentos["n"] > 1, "debería haber intentado reconectar tras la desconexión"
