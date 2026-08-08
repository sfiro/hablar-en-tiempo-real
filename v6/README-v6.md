# Versión 6.0 — Estado base (todos los servos a 90°) 👁️

**Objetivo:** un programa dedicado que lleve los 8 servos a la posición base
(90°, centrados) y los mantenga ahí — útil para dejar el rig en una posición
segura antes de desconectar la alimentación, o para recuperar un estado neutral
conocido tras un error, sin la lógica de rastreo/cuello/parpadeo de por medio.

v6 trae además **toda la base funcional de v5**: el firmware de rastreo completo
(ojos + cuello + parpadeo, PWM directo sin PCA9685), el rastreo facial del Mac, y
el enlace serial — sin cambios de lógica, solo para que v6 sea una versión
completa y autónoma, no solo la utilidad nueva.

**Estado:** código completo, con tests. `estado_base.py` no requiere validación de
comportamiento complejo (es una operación simple y determinista: centrar y
mantener), pero **no se ha probado en la Pico real todavía** — no hay una
conectada a este entorno.

**Totalmente autónoma:** no depende de ningún fichero de v1-v5. Copias propias de
`main.py`, `face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py` (todos de
v5, sin cambios de lógica), con su propio `.venv/` y tests.

---

## `estado_base.py` — lo nuevo de esta versión

```bash
# En la Pico, con Thonny: ábrelo y guárdalo, o ejecútalo directamente
python estado_base.py
```

Lleva los 8 servos (`LR, UD, TL, BL, TR, BR, PAN, TILT`) a 90°, uno a uno con
0.1s de espaciado (mismo criterio contra picos de corriente que usa `main.py` en
su secuencia de arranque), y luego se queda esperando indefinidamente — el PWM
de la Pico sigue manteniendo la señal en 90° en cada canal aunque el script no
haga nada más, así que "mantener posición" no requiere reenviar el comando en
un bucle activo.

**Casos de uso:**
- Antes de desconectar la alimentación, dejar el rig en una posición conocida en
  vez de apagar con los servos en cualquier ángulo
- Recuperar un estado neutral para inspeccionar o calibrar el hardware, sin que
  el rastreo facial o el parpadeo interfieran
- Punto de partida simple para verificar que el cableado PWM directo (sin
  PCA9685) sigue funcionando, sin la complejidad del firmware completo

**No reemplaza a `main.py`.** Son dos programas independientes: `main.py` hace
todo el rastreo activo, `estado_base.py` solo centra y mantiene. Para volver al
rastreo normal, hay que volver a desplegar `main.py`.

Usa la misma fórmula de conversión de grados a PWM y el mismo mapeo de pines que
`main.py` — verificado con un test que compara ambos directamente
(`tests/test_estado_base.py::test_duty_de_90_grados_coincide_con_main_py`), para
que "90°" signifique la misma posición física en los dos programas.

## Base funcional heredada de v5 (sin cambios)

- **`main.py`** — firmware completo: rastreo de ojos + cuello (PAN/TILT
  amortiguado) + parpadeo periódico, PWM directo desde la Pico (sin PCA9685). Ver
  [`../v5/README-v5.md`](../v5/README-v5.md) para la historia completa de por qué
  no usa PCA9685 — vale la pena leerla antes de tocar este fichero.
- **`face_tracker.py`** — rastreo facial por cámara (Mac), sin cambios desde v3.
- **`pico_serial.py`** — enlace serial hacia la Pico, sin cambios desde v3.
- **`diagnostico_canal.py`** — mueve un solo canal en barrido lento, para
  diagnósticos de hardware aislados de la lógica de rastreo.

Mapeo de pines (igual en `main.py` y en `estado_base.py`):

```
LR=GP2   UD=GP3   TL=GP4   BL=GP5   TR=GP6   BR=GP7   PAN=GP8   TILT=GP9
```

## Cómo se verificó

**Sin hardware:**
- Sintaxis de los 5 ficheros `.py` (`py_compile`)
- `tests/test_estado_base.py` (4 tests nuevos): 90° cae en el centro exacto del
  rango de pulso, el valor de `duty_u16` en 90° coincide con el que calcula
  `main.py` para el mismo ángulo, los 8 canales tienen un pin único sin solapes,
  y el mapeo de pines coincide con el de `main.py`
- Los 25 tests heredados de v5 (`face_tracker.py`, `pico_serial.py`,
  `main.py`), corriendo dentro del `.venv` propio de v6 — 29 tests en total

**No verificado, necesita la Pico física:**
- Que los 8 servos lleguen de verdad a una posición visualmente centrada
- Que el script se comporte igual de bien en un despliegue real (guardado como
  archivo + reinicio, no con el botón ▶ Run — ver la lección de v5 sobre esto)

## Cómo probarlo

```bash
cd v6
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest tests/ -v   # 29 tests
```

Para el firmware, en Thonny: abre `estado_base.py` o `main.py`, `Archivo →
Guardar como → Raspberry Pi Pico`, nómbralo `main.py`, y reinicia la placa
físicamente (no uses el botón ▶ Run — ver la sección de despliegue en
[`../v5/README-v5.md`](../v5/README-v5.md#historial-de-depuración-completo)).

## Próximos pasos (fuera de esta versión)

1. Validar `estado_base.py` en hardware real
2. Emociones y su sincronía con la mirada (offsets de párpados/cuello)
3. Retomar la integración de voz, con una base de movimiento y una utilidad de
   estado seguro ya confirmadas

## Referencias

- [`../v5/README-v5.md`](../v5/README-v5.md) — historial completo de por qué el
  firmware usa PWM directo en vez de PCA9685
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) — documentación de hardware
- [PLAN-v6.md](PLAN-v6.md) — hitos
