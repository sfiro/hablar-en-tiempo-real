# Plan de desarrollo — v6.0.0 Estado base + secuencia de expresiones

---

## Hito 1: Base funcional de v5, traída completa ✅ (completado)

- [x] Copiado `v5/main.py` → `v6/main.py` (firmware completo: rastreo + cuello +
      parpadeo, PWM directo sin PCA9685), sin cambios de lógica
- [x] Copiado `v5/face_tracker.py` → `v6/face_tracker.py`, sin cambios
- [x] Copiado `v5/pico_serial.py` → `v6/pico_serial.py`, sin cambios
- [x] Copiado `v5/diagnostico_canal.py` → `v6/diagnostico_canal.py`, sin cambios
- [x] Copiados los tests de `v5/tests/` → `v6/tests/`
- [x] `v6/requirements.txt`, `v6/requirements-dev.txt`, `v6/.venv` propios
- [x] Corregidas referencias de documentación que apuntaban a "v5" en los
      ficheros copiados (comentarios, mensajes de consola, nombre de ventana)
- [x] Verificado: los 25 tests heredados pasan dentro de `v6/.venv`, sin ninguna
      referencia a `v5/`
- [x] Confirmado que `v5/` sigue intacto y sus propios tests siguen pasando tras
      la copia (no se tocó nada de v5)

**Nota:** `main_pca9685.py` (la versión retirada con PCA9685) **no** se copió a
v6 — no es "base funcional", es código explícitamente no usado. Su historial
sigue disponible en `v5/README-v5.md`.

## Hito 2: `estado_base.py` ✅ (código completo, sin validar en hardware)

- [x] Nuevo programa: lleva los 8 servos a 90° con el mismo espaciado de 0.1s
      entre motores que usa `main.py` en su arranque (protección contra picos de
      corriente)
- [x] Misma fórmula de conversión de grados a PWM y mismo mapeo de pines que
      `main.py` — verificado con un test que compara ambos directamente
- [x] Tras centrar, se queda esperando indefinidamente (el PWM de la Pico
      mantiene la señal sola; no hace falta reenviar el comando en bucle)
- [x] Tests (`tests/test_estado_base.py`, 4 tests): 90° es el centro exacto del
      rango de pulso, el `duty_u16` de 90° coincide con el de `main.py`, los 8
      canales tienen un pin único sin solapes, el mapeo de pines coincide

**Validado en la Pico real por el usuario:** los 8 servos llegan a una
posición visualmente centrada y el script se comporta bien desplegado
correctamente (guardado como archivo + reinicio físico, no con el botón ▶ Run).

## Hito 3: Secuencia de expresiones faciales ✅ (completo y validado en hardware, ver Hito 4)

**Objetivo:** primer paso hacia expresiones faciales — un temporizador fijo que
cicla por las 10 emociones cada 5 segundos, sin depender de voz ni sentimiento
todavía (eso es trabajo futuro).

- [x] `OFFSETS_EMOCIONES` (10 emociones + neutral) copiado literalmente de
      `ojosMecanicos/main.py`, verificado contra el original antes de escribir
      código (no de memoria)
- [x] `LIMITES_PARPADOS` (mínimo, máximo por canal) añadido, copiado de
      `servo_limits` del original, para recortar los offsets sin forzar los
      servos más allá de su rango mecánico
- [x] `actualizar_objetivo_expresion()`: aplica el offset de la emoción actual
      sobre la base "abierta" fija de los párpados (v6 no sincroniza párpados
      con la mirada) y lo suma al `TILT` ya calculado por
      `actualizar_objetivo_cuello()`. El offset de `PAN` no se aplica: en las
      10 emociones originales siempre es 0
- [x] Los párpados (`TL/BL/TR/BR`) se incorporan al sistema de suavizado EMA que
      ya usaban `LR/UD/PAN/TILT`, para que el cambio de expresión sea una
      transición gradual, no un salto brusco
- [x] `parpadear()` actualizado: no parpadea con `DORMIDO` activo (mismo
      criterio que el original), y al reabrir vuelve a la posición de la
      expresión actual (`objetivo_actual`), no siempre a "abierto"
- [x] Temporizador de expresión (5000ms fijo), independiente del de parpadeo,
      cicla `SECUENCIA_EMOCIONES` en orden y envuelve al llegar al final

**Verificado antes de escribir el offset por completo:** un script aparte
calculó, para las 10 emociones × 4 canales, si el offset sobre la base abierta
se sale del rango mecánico — encontrando que **SORPRENDIDO clampa en los 4
canales** (la base ya está en el extremo hacia el que empuja el offset) y
**DORMIDO clampa en 2** (`TR`, `BR`). Esto se convirtió en tests explícitos
(`test_sorprendido_no_se_distingue_de_neutral_en_v6`,
`test_dormido_si_se_distingue_cierra_parcialmente_los_parpados`) y se documentó
en README-v6.md como limitación real, no un bug a arreglar en esta versión: sin
sincronía párpado-mirada, SORPRENDIDO no tiene margen para verse.

**Tests nuevos** (`tests/test_main_math.py`, 6 tests): todas las emociones de la
secuencia tienen offsets definidos, NEUTRAL no mueve nada, ninguna emoción sale
del rango mecánico, SORPRENDIDO no se distingue de NEUTRAL (confirmado, no
descrito), DORMIDO sí cierra parcialmente, FELIZ mueve los párpados inferiores
en direcciones opuestas correctamente.

**Validado en la Pico real por el usuario:** las transiciones entre
expresiones se ven suaves, y el parpadeo coincidiendo con un cambio de
expresión no produce comportamiento raro. La limitación de SORPRENDIDO
(no distinguirse de NEUTRAL) sí se confirmó visualmente en esta prueba —
resuelta después, en el Hito 4, bajando el reposo de los párpados.

## Hito 4: Ajustes de realismo tras probar en hardware real ✅ (completo y validado en hardware real)

**Objetivo:** el usuario probó Hitos 1-3 en la Pico real y pidió ajustes
concretos a varias expresiones para que se vean más realistas y se distingan
mejor entre sí.

- [x] `PARPADOS_REPOSO`: nueva posición de reposo al 40% del camino hacia
      CERRADO (antes NEUTRAL usaba el 100% abierto). Resuelve de raíz la
      limitación de SORPRENDIDO documentada en el Hito 3 — no fue necesario
      añadir sincronía párpado-mirada, solo dejar de partir del extremo
      mecánico. 40% es el mínimo con margen cómodo en los 4 canales de
      SORPRENDIDO (TR es el canal más exigente, ~34% mínimo teórico)
- [x] SORPRENDIDO: sin cambios en sus offsets, pero ahora se aplican sin
      clamping en los 4 canales — confirmado con test
      (`test_sorprendido_ahora_si_se_distingue_de_neutral_en_v6`), no solo
      esperado
- [x] DORMIDO: sin cambios en sus offsets; efecto colateral del nuevo reposo,
      ahora clampa en los 4 canales (antes 2) y cierra los párpados por
      completo — coherente con la expresión, documentado como hallazgo, no bug
- [x] FELIZ recalculado: párpados inferiores suben un 50% del camino restante
      hacia CERRADO desde el reposo (`BL: 42→66`, `BR: 132→111`); superiores
      sin offset, se quedan en la posición de reposo
- [x] SOSPECHA recalculado: los 4 canales cierran un 80% del camino restante
      hacia CERRADO desde el reposo (`TL:-48, TR:+29, BL:+38, BR:-34`)
- [x] DUDA: nuevo mecanismo `actualizar_objetivo_mirada_expresion()` — mientras
      dura la expresión, `LR` ignora el rastreo facial y barre 40↔140↔40 a
      razón de 2.5s por tramo (ida y vuelta completa en los 5s que dura DUDA).
      El cuello acompaña porque sigue leyendo el mismo `objetivo_actual[LR]`
- [x] PENSATIVO: mismo mecanismo, mirada fija en `LR=40, UD=40` (arriba a la
      izquierda; UD bajo = "arriba" en este montaje, mismo criterio que
      `ojosMecanicos/main.py`) mientras dura la expresión
- [x] `inicio_duda` se reinicia cada vez que la secuencia entra a DUDA, para
      que el barrido siempre empiece igual (en `LR_MIN`) sin importar en qué
      punto del ciclo global de tiempo ocurra
- [x] **Bug real encontrado y corregido:** al salir de DUDA o PENSATIVO, la
      mirada se quedaba donde el barrido o la posición fija la habían dejado
      (por ejemplo, en el extremo izquierdo) en vez de volver al centro para
      la siguiente expresión. Corregido: al cambiar de expresión, si la que
      termina fijaba la mirada, `objetivo_actual[LR]`/`[UD]` se reinician a 90
      — la transición sigue siendo suave porque pasa por el mismo EMA
- [x] TRISTE: pedido explícito de bajar la cabeza "hasta el mínimo inferior".
      En vez de sumar el offset de TILT (-20, relativo al TILT que calcula el
      seguimiento del cuello, y por tanto variable según hacia dónde mire el
      rastreo), `actualizar_objetivo_expresion()` fuerza `TILT` directamente a
      `TILT_MIN` mientras dura TRISTE — cabeza gacha, siempre igual de
      marcada. Al cambiar a la siguiente expresión, `TILT` vuelve a calcularse
      con la fórmula normal automáticamente (no necesita un reinicio como el
      de DUDA/PENSATIVO, porque el cuello se recalcula entero cada vuelta)
- [x] NERVIOSO: pedido explícito de "ojos saltones... sin intentar hacer
      contacto visual". Mismo mecanismo de `actualizar_objetivo_mirada_expresion()`
      que DUDA/PENSATIVO, pero con saltos discretos al azar: cada 1s,
      `LR`/`UD` saltan a un punto al azar dentro de un rango moderado
      (`65–115` en ambos ejes, no los extremos mecánicos). Extendida también
      la corrección de recentrado: al salir de NERVIOSO (además de DUDA y
      PENSATIVO), la mirada vuelve a 90/90 antes de la siguiente expresión

**Tests nuevos/actualizados** (`tests/test_main_math.py`, ahora 49 en total):
reposo confirmado al 40% de cierre y distinto del extremo abierto, NEUTRAL
igual al reposo, SORPRENDIDO ya no clampa (reemplaza el test que antes
confirmaba lo contrario), DORMIDO cierra los 4 canales por completo (reemplaza
el test de 2 canales), FELIZ y SOSPECHA verificados contra sus nuevos valores,
barrido de DUDA verificado en los puntos clave del ciclo (extremos e ida/vuelta
completa en 5s) y sin salirse de rango, mirada fija de PENSATIVO verificada.

**Validado en la Pico física por el usuario:** "todo ha funcionado bien" —
reposo más cerrado, SORPRENDIDO/FELIZ/SOSPECHA/DORMIDO recalculados, barrido
de DUDA, mirada fija de PENSATIVO, cabeza gacha de TRISTE y saltos al azar de
NERVIOSO, incluyendo su interacción con el parpadeo y el cambio de expresión.
Versión cerrada.

---

## Definición de listo

v6.0.0 está lista cuando:

1. [x] Base funcional de v5 traída completa y verificada de forma autónoma
2. [x] `estado_base.py` implementado, con la matemática verificada sin hardware
3. [x] Secuencia de expresiones implementada, con offsets y límites verificados
   sin hardware, incluyendo el hallazgo de SORPRENDIDO (resuelto en el Hito 4)
4. [x] `estado_base.py` validado en la Pico real: los 8 servos llegan a 90° y se
   quedan ahí de forma estable
5. [x] Base de v5 (rastreo + cuello + parpadeo) validada en la Pico real
6. [x] Ajustes de realismo (Hito 4) implementados y verificados sin hardware
7. [x] Ajustes de realismo del Hito 4 validados en la Pico real: reposo más
   cerrado, SORPRENDIDO/FELIZ/SOSPECHA/DORMIDO recalculados, barrido de DUDA,
   mirada fija de PENSATIVO, cabeza gacha de TRISTE, saltos de NERVIOSO

---

**Última actualización:** Agosto 9, 2026
**Estado actual:** v6.0.0 completa y validada en hardware real — Hitos 1-4,
con 49 tests, confirmados por el usuario en la Pico física ("todo ha
funcionado bien"). Versión cerrada.
