# Plan de desarrollo — v5.0.0 Cuello y parpadeo

---

## Hito 1: Autonomía completa ✅ (completado, siguiendo el patrón de v4)

- [x] Copiar `v4/face_tracker.py` → `v5/face_tracker.py` (sin cambios de lógica,
      solo referencias de documentación actualizadas de v4→v5)
- [x] Copiar `v4/pico_serial.py` → `v5/pico_serial.py` (sin cambios)
- [x] Copiar los tests de `v4/tests/` → `v5/tests/`
- [x] `v5/requirements.txt`, `v5/requirements-dev.txt`, `v5/.venv` propios
- [x] Verificado: los 19 tests heredados pasan dentro de `v5/.venv`, sin ninguna
      referencia a `v3/` ni `v4/`

## Hito 2: Cuello (PAN/TILT) ✅ (código completo, sin validar en hardware)

- [x] `objetivo_actual`/`posicion_actual` extendidos a 4 ejes (LR, UD, PAN, TILT),
      todos con el mismo suavizado EMA (`ALPHA=0.1`)
- [x] `actualizar_objetivo_cuello()`: deriva el objetivo de PAN/TILT del objetivo de
      LR/UD en cada vuelta del bucle, con los mismos factores de amortiguación que
      `ojosMecanicos/main.py` (0.8 para PAN, 0.6 para TILT)
- [x] Límites 40-140 respetados con `clamp()` (aunque con estos factores nunca se
      alcanzan en la práctica, ver test correspondiente)
- [x] Test (`tests/test_main_math.py`): confirma que el cuello siempre se mueve
      *menos* que los ojos, nunca igual ni más, y que nunca sale de su rango ni en
      los extremos de los ojos

**Pendiente:** validar que el movimiento se ve orgánico en el rig real, no solo
correcto en la fórmula.

## Hito 3: Parpadeo periódico ✅ (código completo, sin validar en hardware)

- [x] `PARPADOS_CERRADOS` añadido junto a `PARPADOS_ABIERTOS` (ya existía en v4)
- [x] `parpadear()`: cierra los 4 párpados escalonados (10ms), espera 150ms, reabre
      escalonado — mismo patrón que `ojosMecanicos/main.py`, sin depender de
      emociones (reabre siempre a la posición "abierta" fija, no a un objetivo que
      varíe por mirada o emoción, porque v5 no tiene ninguna de esas dos cosas)
- [x] Temporizador aleatorio (2-6s) independiente del estado de rastreo: parpadea
      igual si hay comandos serial llegando o no
- [x] Test: confirma que las posiciones abierta y cerrada son distintas por canal
      (chequeo mínimo — la temporización y el bloqueo real solo se confirman con
      hardware, no tiene sentido testear `time.sleep` con mocks aquí)

**Pendiente:** confirmar que el bloqueo de ~230ms durante cada parpadeo no se note
como un tirón perceptible en el rastreo de ojos, y que la fuente de alimentación
aguanta los 3 subsistemas (ojos + cuello + párpados) moviéndose a la vez.

---

## Hito 4: Validación con hardware real 📋 (siguiente, necesita al usuario)

- [ ] Desplegar `v5/main.py` en la Pico (mismo procedimiento que v4)
- [ ] Confirmar visualmente: el cuello acompaña el movimiento de los ojos, de forma
      visiblemente más suave/amortiguada, no igual de brusca
- [ ] Confirmar que el parpadeo ocurre cada pocos segundos sin intervención, incluso
      con el rastreo activo
- [ ] Confirmar que no hay tirones perceptibles en el rastreo durante un parpadeo
- [ ] Sesión larga (varios minutos): sin reinicios inesperados, sin que la fuente
      de alimentación se sature con los ejes nuevos en movimiento

---

## Definición de listo

v5.0.0 está lista cuando:

1. [x] Autonomía completa (no depende de v1/v2/v3/v4)
2. [x] Cuello y parpadeo implementados, con la matemática nueva verificada sin
   hardware
3. [x] Compatibilidad de protocolo con versiones anteriores mantenida
4. [ ] Validado en la Pico real: cuello, parpadeo, y ausencia de tirones en el
   rastreo, todo junto y funcionando

---

**Última actualización:** Agosto 7, 2026
**Estado actual:** Código completo (Hitos 1-3). Falta la validación con hardware
real (Hito 4), que depende enteramente de que el usuario lo pruebe con la Pico
física — igual que pasó con v4 antes de confirmarse.
