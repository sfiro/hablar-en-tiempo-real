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

## Hito 4: Validación con hardware real 🔄 (en curso, dos hallazgos abiertos)

- [x] Desplegado `v5/main.py` en la Pico
- [x] Rastreo de ojos y movimiento arriba/abajo (TILT) confirmados funcionando
- [ ] **PAN (rotación izquierda/derecha) no se mueve** — ver Hito 4.1
- [ ] **Temblor aleatorio al conectar la alimentación** — ver Hito 4.2
- [ ] Confirmar visualmente que el cuello acompaña el movimiento de los ojos, de
      forma visiblemente más suave/amortiguada (pendiente de resolver 4.1 primero)
- [ ] Confirmar que no hay tirones perceptibles en el rastreo durante un parpadeo
- [ ] Sesión larga (varios minutos): sin reinicios inesperados, sin que la fuente
      de alimentación se sature con los ejes nuevos en movimiento

### Hito 4.1: PAN no se mueve 🔍 (diagnosticando)

- [x] Revisado `main.py` línea por línea comparando PAN contra TILT: la lógica es
      idéntica en estructura (mismo diccionario de ejes, mismo suavizado EMA, misma
      inicialización), solo cambian el canal (6 vs 7) y el factor de amortiguación
      (0.8 vs 0.6). No se encontró ningún bug de lógica.
- [x] Dato relevante: en v4, el canal PAN nunca se movía de forma activa (solo se
      centraba una vez al arrancar y quedaba quieto) — esta es la primera vez que
      se ejercita en todo su rango, así que un problema de cableado o mecánico en
      ese eje podría haber pasado desapercibido hasta ahora.
- [x] Creado [`diagnostico_canal.py`](diagnostico_canal.py): mueve un solo canal
      del PCA9685 (por defecto, el 6/PAN) en barrido lento, sin nada de la lógica
      de rastreo ni serial de por medio — para aislar si es hardware o firmware
- [ ] **Pendiente:** correr el diagnóstico y comparar canal 6 vs canal 7 (control),
      y reportar qué se observa exactamente (silencio total, vibra sin girar, gira
      poco, o gira bien aislado pero no durante el rastreo normal)

### Hito 4.2: Temblor aleatorio al conectar la alimentación 🔧 (arreglo propuesto, sin confirmar)

- [x] Diagnosticado: ocurre con cualquier firmware, incluso antes de que se
      ejecute código — descarta un bug de software. Se calma en 1-2s, coincidiendo
      con el tiempo de arranque + inicialización del PCA9685. Fuente de
      alimentación dedicada para los servos (descarta el motivo más común de este
      síntoma, un suministro compartido insuficiente).
- [x] Causa más probable: las salidas PWM del PCA9685 quedan en un estado
      indefinido en la ventana entre "llega la alimentación" y "la Pico termina de
      arrancar y configura el chip"; los servos reaccionan a esa señal como si
      fuera un comando válido.
- [x] Arreglo implementado en `main.py`: pin `/OE` cableado a `GP2`, deshabilitado
      explícitamente al inicio del código, habilitado justo después de inicializar
      el chip PCA9685 y **antes** de los bucles de centrado escalonado (para no
      deshacer la protección contra picos de corriente que ese espaciado ya daba)
- [ ] **Pendiente, hardware (el usuario):** quitar el jumper `/OE`→GND, añadir una
      resistencia de pull-up `/OE`→VCC en la placa PCA9685, cablear `/OE` a `GP2`
- [ ] **Pendiente, confirmar:** que el arreglo elimina el temblor. Riesgo conocido,
      sin confirmar: si la lógica del PCA9685 corre a 5V, un GPIO de 3.3V de la
      Pico podría no marcar un HIGH inequívoco en `/OE` — si el temblor persiste
      igual tras el cambio, revisar esto primero

---

## Definición de listo

v5.0.0 está lista cuando:

1. [x] Autonomía completa (no depende de v1/v2/v3/v4)
2. [x] Cuello y parpadeo implementados, con la matemática nueva verificada sin
   hardware
3. [x] Compatibilidad de protocolo con versiones anteriores mantenida
4. [x] Rastreo de ojos y TILT confirmados funcionando en hardware real
5. [ ] **PAN funcionando** (Hito 4.1, diagnóstico en curso)
6. [ ] **Temblor de encendido eliminado** (Hito 4.2, arreglo propuesto sin confirmar)
7. [ ] Validación completa: cuello, parpadeo, y ausencia de tirones en el rastreo,
   todo junto y funcionando, sesión larga sin problemas

---

**Última actualización:** Agosto 7, 2026
**Estado actual:** Código completo (Hitos 1-3). En validación con hardware real
(Hito 4): rastreo de ojos y TILT confirmados, dos hallazgos abiertos — PAN no se
mueve (diagnosticando, hipótesis hardware) y temblor aleatorio al encender
(diagnosticado, arreglo con `/OE` implementado, pendiente de confirmar).
