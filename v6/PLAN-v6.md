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

**Pendiente:** validar en la Pico real que los 8 servos llegan de verdad a una
posición visualmente centrada, y que el script se comporta bien desplegado
correctamente (guardado como archivo + reinicio físico, no con el botón ▶ Run).

## Hito 3: Secuencia de expresiones faciales ✅ (código completo, sin validar en hardware)

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

**Pendiente, necesita la Pico física:**
- Confirmar que las transiciones entre expresiones se ven suaves
- Confirmar que un parpadeo y un cambio de expresión coincidiendo en el tiempo
  no producen un comportamiento raro (los dos temporizadores son independientes,
  sin coordinación explícita — no se ha observado ni descartado un problema)
- Confirmar visualmente que SORPRENDIDO en efecto no se distingue de NEUTRAL,
  tal como predice la matemática

---

## Definición de listo

v6.0.0 está lista cuando:

1. [x] Base funcional de v5 traída completa y verificada de forma autónoma
2. [x] `estado_base.py` implementado, con la matemática verificada sin hardware
3. [x] Secuencia de expresiones implementada, con offsets y límites verificados
   sin hardware, incluyendo el hallazgo de SORPRENDIDO
4. [ ] `estado_base.py` validado en la Pico real: los 8 servos llegan a 90° y se
   quedan ahí de forma estable
5. [ ] Secuencia de expresiones validada en la Pico real: transiciones suaves,
   sin interacción rara entre parpadeo y cambio de expresión

---

**Última actualización:** Agosto 8, 2026
**Estado actual:** Hitos 1, 2 y 3 completos en código, con 35 tests. Falta la
validación con hardware real de `estado_base.py` y de la secuencia de
expresiones, que depende de que el usuario lo pruebe con la Pico física.
