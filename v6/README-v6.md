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

**Estado: completa y validada en hardware real.** La base de v5 (rastreo +
cuello + parpadeo), `estado_base.py`, la secuencia de expresiones y los diez
ajustes de realismo descritos abajo (reposo al 40%, SORPRENDIDO, DORMIDO,
FELIZ, SOSPECHA, DUDA, PENSATIVO, TRISTE, NERVIOSO, y el recentrado de mirada
al cambiar de expresión) fueron probados por el usuario en la Pico física —
confirmado: "todo ha funcionado bien".

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
`TILT` son los mismos 10 de `ojosMecanicos/main.py`, copiados literalmente,
salvo `FELIZ` y `SOSPECHA` (recalculados, ver más abajo). Se suman sobre la
**posición de reposo** de los párpados (`PARPADOS_REPOSO`, no el 100% abierto —
ver siguiente sección) y sobre el `TILT` que ya calcula el seguimiento del
cuello, y se recortan a los límites mecánicos de cada canal. Los cambios de
expresión pasan por el mismo suavizado EMA que ya usan los demás ejes, así que
la transición es gradual, no un salto. El offset de `PAN` no se aplica: en las
10 emociones originales siempre es 0.

**El parpadeo respeta la expresión activa:** mientras dura `DORMIDO`, no
parpadea (mismo criterio que el original — los párpados ya están casi cerrados
por el offset). Y cuando sí parpadea, reabre a la posición de la expresión
actual, no siempre a "abierto" — con `FELIZ` activo, por ejemplo, el párpado
inferior izquierdo vuelve a su posición elevada, no a la neutral.

### Ajustes de realismo tras probar en hardware real

El usuario probó la secuencia en la Pico física y pidió varios ajustes para que
las expresiones se vean más realistas y se distingan mejor entre sí. Cambios:

**1. Reposo (NEUTRAL) ya no arranca 100% abierto.** Antes, `NEUTRAL` dejaba los
párpados en el extremo mecánico de apertura (`PARPADOS_ABIERTOS`), y eso era la
causa raíz de que `SORPRENDIDO` no se distinguiera de `NEUTRAL` (ver más abajo,
sección histórica): su offset empuja hacia "más abierto todavía", pero sin
margen mecánico los 4 canales clampaban de vuelta al mismo valor. Ahora hay una
posición de reposo real, `PARPADOS_REPOSO`, al **40% del camino hacia
CERRADO** desde el extremo abierto (`TL=130, BL=42, TR=34, BR=132`, de un rango
mecánico donde `TL=170/BL=10/TR=10/BR=160` es 100% abierto y
`TL=70/BL=90/TR=70/BR=90` es 100% cerrado). 40% es el mínimo con margen cómodo
en los 4 canales de `SORPRENDIDO` — el canal `TR` es el más exigente, con un
mínimo teórico de ~34%. Todas las expresiones parten ahora de este reposo, no
del extremo abierto.

**2. SORPRENDIDO ahora sí se distingue de NEUTRAL — confirmado con test, no
solo esperado.** Con más margen en el reposo, los 4 offsets de `SORPRENDIDO` se
aplican sin clamping (antes clampaban los 4). Verificado en
`test_sorprendido_ahora_si_se_distingue_de_neutral_en_v6`.

**3. DORMIDO ahora cierra los párpados por completo.** Efecto colateral
esperado del reposo más cerrado: el offset de `DORMIDO` (que ya apuntaba hacia
"más cerrado") ahora clampa en los 4 canales (antes solo en 2), llegando
exactamente a `PARPADOS_CERRADOS` — coherente con la expresión de estar
dormido, no un problema.

**4. FELIZ recalculado: párpados inferiores suben un 50% del camino restante
hacia CERRADO desde el reposo, superiores sin cambio.** El offset original de
`ojosMecanicos` (`±30`, pensado para una base 100% abierta) apenas se notaba
sobre el nuevo reposo más cerrado. Recalculado en términos absolutos:
`BL: 42→66` (de un máximo cerrado de 90), `BR: 132→111` (de un mínimo cerrado
de 90). Los párpados superiores (`TL`/`TR`) se quedan en la posición de reposo
(offset 0) — "posición neutral abierta", tal como se pidió.

**5. SOSPECHA recalculado: los 4 canales cierran un 80% del camino restante
hacia CERRADO desde el reposo**, mismo motivo que FELIZ — con offsets
copiados del original habría quedado casi indistinguible de `DORMIDO` o
demasiado sutil sobre el nuevo reposo.

**6. DUDA: los ojos barren solos de un extremo a otro, en vez de seguir el
rastreo facial.** Mientras dura la expresión (5s), `LR` ignora el rastreo de
cámara y hace un barrido completo (40→140→40) a razón de 2.5s por tramo — un
tramo de ida, uno de vuelta, exactamente durante los 5s de la expresión.
Gesto de "pensando, mirando de lado a lado". El cuello (`PAN`, que sigue a
`LR`) acompaña el barrido porque `actualizar_objetivo_cuello()` sigue leyendo
`objetivo_actual[LR]` normalmente.

**7. PENSATIVO: la mirada se fija arriba a la izquierda, en vez de seguir el
rastreo facial.** Mientras dura la expresión, `LR=40` (extremo izquierdo) y
`UD=40` (extremo "arriba" en este montaje — mismo criterio que
`ojosMecanicos/main.py`, que usa valores bajos de `UD` para "mirar hacia
arriba"). El cuello acompaña el gesto por el mismo mecanismo que en DUDA.

**8. TRISTE baja la cabeza hasta el tope mecánico, no un offset relativo.**
Antes, el `TILT` de TRISTE (-20, el de `ojosMecanicos`) se sumaba sobre el
TILT que ya calculaba el seguimiento del cuello — así que cuánto bajaba la
cabeza dependía de hacia dónde estuviera mirando el rastreo facial en ese
momento, y podía no notarse si el cuello ya estaba cerca del extremo alto.
Ahora, mientras dura TRISTE, `TILT` se fuerza directamente a `TILT_MIN` (el
mínimo mecánico, cabeza gacha), ignorando lo que calculó el cuello esa vuelta
— siempre igual de marcado, sin importar el rastreo.

**9. NERVIOSO: ojos saltones, mirando a cualquier lado sin buscar contacto
visual.** Nuevo pedido explícito. Mientras dura la expresión, `LR`/`UD`
ignoran el rastreo facial y saltan a un punto al azar cada segundo, dentro de
un rango moderado (`65–115` en ambos ejes, no los extremos mecánicos) — el
mismo mecanismo de `actualizar_objetivo_mirada_expresion()` que ya usan DUDA y
PENSATIVO, pero con saltos discretos al azar en vez de un barrido continuo o
una posición fija. El cuello acompaña cada salto por el mismo motivo que en
los otros dos: sigue leyendo `objetivo_actual[LR]/[UD]`.

**10. Al salir de DUDA, PENSATIVO o NERVIOSO, la mirada vuelve al centro.**
Corrección de un bug real: como estas tres expresiones fijan `LR`/`UD` en vez
de seguir el rastreo facial, al terminar dejaban la mirada donde sea que el
barrido, la posición fija o el último salto la hubieran dejado (por ejemplo,
`LR=40` tras PENSATIVO), y la siguiente expresión heredaba esa posición en vez
de partir de un punto neutro. Ahora, al cambiar de expresión, si la que
termina era DUDA, PENSATIVO o NERVIOSO, `objetivo_actual[LR]`/`[UD]` se
reinician a 90 (centro) — la transición sigue siendo suave porque pasa por el
mismo suavizado EMA que ya usan estos ejes, no es un salto brusco.

**Ninguno de estos tres overrides de mirada (DUDA, PENSATIVO, NERVIOSO)
coordina con el parpadeo** — son mecanismos independientes, igual que ya lo
eran el parpadeo y el cambio de expresión entre sí. Probado en hardware real
sin que se observara ningún problema al coincidir en el tiempo.

#### Nota histórica: por qué existía la limitación de SORPRENDIDO

Antes de este ajuste, `NEUTRAL` usaba el 100% abierto como reposo, y por eso
`SORPRENDIDO` no tenía margen mecánico para distinguirse — los 4 canales
clampaban de vuelta al mismo valor. Quedó documentado en su momento (y en la
versión anterior de este README) como una limitación real, no un bug, esperada
mientras no hubiera sincronía párpado-mirada. Se resolvió aquí bajando el
reposo, no añadiendo esa sincronía — sigue pendiente como trabajo futuro (ver
"Próximos pasos").

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
- `tests/test_main_math.py`, con tests para la secuencia de expresiones y los
  ajustes de realismo: el reposo queda al 40% de cierre (no en el extremo
  abierto), ninguna emoción saca los párpados de su rango mecánico, FELIZ
  sube/baja los párpados inferiores en las cantidades recalculadas, SOSPECHA
  cierra claramente más que NEUTRAL, DORMIDO ahora cierra los 4 canales por
  completo, SORPRENDIDO ya no clampa y se distingue de NEUTRAL (el hallazgo
  original, resuelto y confirmado con test), el barrido de DUDA llega a los dos
  extremos y vuelve en 5s sin salirse de rango, y la mirada fija de PENSATIVO
  apunta arriba a la izquierda
- Los tests heredados de v5 (`face_tracker.py`, `pico_serial.py`), corriendo
  dentro del `.venv` propio de v6 — 49 tests en total

**Con la Pico física, por el usuario — confirmado, no solo esperado:**
- Los 8 servos llegan a una posición visualmente centrada con `estado_base.py`
- El nuevo reposo (40% de cierre) y las expresiones recalculadas (SORPRENDIDO,
  FELIZ, SOSPECHA, DORMIDO) se ven como se esperaba
- El barrido de ojos de DUDA, la mirada fija de PENSATIVO, los saltos al azar
  de NERVIOSO y la cabeza gacha de TRISTE se ven naturales, con el cuello
  acompañando sin sacudidas
- Las transiciones entre expresiones se ven suaves, no como saltos
- El bloqueo del parpadeo no interfiere con el cambio de expresión ni con los
  overrides de mirada de DUDA/PENSATIVO/NERVIOSO al coincidir en el tiempo
- El script se comporta bien en un despliegue real (guardado como archivo +
  reinicio, no con el botón ▶ Run — ver la lección de v5 sobre esto)

**Sin verificar todavía, fuera de esta versión:** sesión larga sin reinicios
ni degradación (igual que en v5), y una segunda vuelta completa del ciclo de
10 expresiones seguida sin interrupción (la validación cubrió el
comportamiento de cada expresión, no necesariamente muchas vueltas seguidas).

## Cómo probarlo

```bash
cd v6
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m pytest tests/ -v   # 49 tests
```

Para el firmware, en Thonny: abre `estado_base.py` o `main.py`, `Archivo →
Guardar como → Raspberry Pi Pico`, nómbralo `main.py`, y reinicia la placa
físicamente (no uses el botón ▶ Run — ver la sección de despliegue en
[`../v5/README-v5.md`](../v5/README-v5.md#historial-de-depuración-completo)).

## Próximos pasos (fuera de esta versión)

1. Sincronía de párpados con la mirada, si se quiere afinar aún más el
   realismo (la limitación original de SORPRENDIDO ya se resolvió sin esto,
   bajando el reposo — ver "Ajustes de realismo")
2. Reintroducir joystick y/o modo autónomo, si hacen falta
3. Retomar la integración de voz: que el sentimiento detectado elija la
   expresión, en vez de un temporizador fijo cada 5 segundos

## Referencias

- [`../v5/README-v5.md`](../v5/README-v5.md) — historial completo de por qué el
  firmware usa PWM directo en vez de PCA9685
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) — documentación de hardware
- [PLAN-v6.md](PLAN-v6.md) — hitos
