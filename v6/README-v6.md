# Versión 6.0 — Estado base + secuencia de expresiones 👁️

**Objetivo (parte 1):** un programa dedicado (`estado_base.py`) que lleve los 8
servos a la posición base (90°, centrados) y los mantenga ahí — útil para dejar
el rig en una posición segura antes de desconectar la alimentación, o para
recuperar un estado neutral conocido tras un error.

**Objetivo (parte 2):** empezar a implementar las expresiones faciales en
`main.py`. Por ahora, sin voz ni sentimiento todavía: **cambian solas cada 5
segundos**, cicladas en un orden fijo — es el primer paso, no la versión final.

v6 trae además **toda la base funcional de v5**: el firmware de rastreo (ojos +
cuello + parpadeo, PWM directo sin PCA9685), el rastreo facial del Mac, y el
enlace serial — sin cambios de lógica salvo la incorporación de expresiones a
`main.py`.

**Estado:** código completo, con tests. **No se ha probado en la Pico real
todavía** — no hay una conectada a este entorno.

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

## Secuencia de expresiones faciales — lo nuevo en `main.py`

`main.py` ahora cicla automáticamente por las 10 expresiones de
`ojosMecanicos/main.py` (`OFFSETS_EMOCIONES`), una cada 5 segundos, en este
orden fijo:

```
NEUTRAL → FELIZ → ENOJADO → TRISTE → SORPRENDIDO → DORMIDO → DUDA → SOSPECHA → PENSATIVO → NERVIOSO → (vuelve a NEUTRAL)
```

**Todavía no depende de voz ni de sentimiento** — es deliberadamente el paso más
simple posible: un temporizador fijo, no una reacción a nada. Cablear esto a la
conversación de voz es trabajo futuro (ver "Próximos pasos").

**Cómo se aplica cada expresión:** los offsets de párpados (`TL/BL/TR/BR`) y de
`TILT` son los mismos 10 de `ojosMecanicos/main.py`, copiados literalmente — no
reinventados. Se suman sobre la posición "abierta" fija de los párpados (v6
**no** sincroniza los párpados con la mirada, a diferencia del original) y sobre
el `TILT` que ya calcula el seguimiento del cuello, y se recortan a los límites
mecánicos de cada canal. Los cambios de expresión pasan por el mismo suavizado
EMA que ya usan los demás ejes, así que la transición es gradual, no un salto.
El offset de `PAN` no se aplica: en las 10 emociones originales siempre es 0.

**El parpadeo respeta la expresión activa:** mientras dura `DORMIDO`, no
parpadea (mismo criterio que el original — los párpados ya están casi cerrados
por el offset). Y cuando sí parpadea, reabre a la posición de la expresión
actual, no siempre a "abierto" — con `FELIZ` activo, por ejemplo, el párpado
inferior izquierdo vuelve a su posición elevada, no a la neutral.

### Limitación real encontrada: SORPRENDIDO no se distingue de NEUTRAL en v6

Verificado con un test, no solo sospechado: los 4 offsets de párpados de
`SORPRENDIDO` empujan hacia "más abierto todavía" — pero en v6 los párpados ya
empiezan en su posición máxima de apertura (no hay sincronía con la mirada que
los mantenga parcialmente cerrados como en el original). El resultado es que
los 4 canales recortan de vuelta exactamente al valor de "abierto", y la
expresión **no se ve** — es visualmente idéntica a NEUTRAL.

`DORMIDO`, en cambio, sí se distingue: su offset empuja hacia "más cerrado", que
sí tiene margen desde la base abierta.

Esto no es un bug que arreglar ahora — es una consecuencia esperada de no tener
todavía sincronía párpado-mirada (fuera de alcance de esta versión), y queda
documentado para no sorprender a quien pruebe la secuencia en hardware y no vea
diferencia entre NEUTRAL y SORPRENDIDO.

## Base funcional heredada de v5 (sin cambios, salvo `main.py`)

- **`main.py`** — firmware completo: rastreo de ojos + cuello (PAN/TILT
  amortiguado) + parpadeo periódico + secuencia de expresiones (nuevo en v6),
  PWM directo desde la Pico (sin PCA9685). Ver
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
- Sintaxis de los 6 ficheros `.py` (`py_compile`)
- `tests/test_estado_base.py` (4 tests): 90° cae en el centro exacto del rango
  de pulso, el valor de `duty_u16` en 90° coincide con el que calcula `main.py`
  para el mismo ángulo, los 8 canales tienen un pin único sin solapes, y el
  mapeo de pines coincide con el de `main.py`
- `tests/test_main_math.py`, ampliado con 6 tests nuevos para la secuencia de
  expresiones: NEUTRAL no mueve nada respecto a "abierto", ninguna emoción saca
  los párpados de su rango mecánico, FELIZ sube/baja los párpados inferiores en
  direcciones opuestas correctamente, DORMIDO sí cierra parcialmente los
  párpados, y — el hallazgo real — SORPRENDIDO recorta de vuelta exactamente al
  valor de "abierto" en los 4 canales (confirmado con un test, no solo descrito)
- Los tests heredados de v5 (`face_tracker.py`, `pico_serial.py`), corriendo
  dentro del `.venv` propio de v6 — 35 tests en total

**No verificado, necesita la Pico física:**
- Que los 8 servos lleguen de verdad a una posición visualmente centrada
  (`estado_base.py`)
- Que las transiciones entre expresiones se vean suaves y no como saltos
- Que el bloqueo del parpadeo no interfiera con el cambio de expresión si
  ambos coinciden en el tiempo (no hay coordinación explícita entre los dos
  temporizadores — un parpadeo y un cambio de expresión podrían solaparse)
- Que el script se comporte igual de bien en un despliegue real (guardado como
  archivo + reinicio, no con el botón ▶ Run — ver la lección de v5 sobre esto)

## Cómo probarlo

```bash
cd v6
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest tests/ -v   # 35 tests
```

Para el firmware, en Thonny: abre `estado_base.py` o `main.py`, `Archivo →
Guardar como → Raspberry Pi Pico`, nómbralo `main.py`, y reinicia la placa
físicamente (no uses el botón ▶ Run — ver la sección de despliegue en
[`../v5/README-v5.md`](../v5/README-v5.md#historial-de-depuración-completo)).

## Próximos pasos (fuera de esta versión)

1. Validar `estado_base.py` y la secuencia de expresiones en hardware real
2. Sincronía de párpados con la mirada (resolvería la limitación de SORPRENDIDO)
3. Reintroducir joystick y/o modo autónomo, si hacen falta
4. Retomar la integración de voz: que el sentimiento detectado elija la
   expresión, en vez de un temporizador fijo cada 5 segundos

## Referencias

- [`../v5/README-v5.md`](../v5/README-v5.md) — historial completo de por qué el
  firmware usa PWM directo en vez de PCA9685
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) — documentación de hardware
- [PLAN-v6.md](PLAN-v6.md) — hitos
