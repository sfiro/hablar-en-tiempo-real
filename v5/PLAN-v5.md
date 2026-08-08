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

## Hito 4: Validación con hardware real ✅ (resuelto — cambio de arquitectura)

- [x] Desplegado `v5/main.py` en la Pico
- [x] Rastreo de ojos y movimiento arriba/abajo (TILT) confirmados funcionando
- [x] **PAN (rotación izquierda/derecha)** — no se movía con PCA9685 (Hito 4.1);
      **resuelto** al pasar a PWM directo (Hito 4.4/4.5) — ahora funciona
- [x] **Temblor aleatorio al conectar la alimentación** — arreglado primero con
      `/OE` (Hito 4.2) sobre PCA9685; el cambio a PWM directo (Hito 4.5) lo
      resuelve de raíz sin necesitar ese arreglo
- [x] **Temblor periódico/continuo del parpadeo** — Hitos 4.3, resuelto también
      por el cambio de arquitectura (Hito 4.5)
- [x] Confirmado por el usuario, con PWM directo: "todos los motores se mueven y
      parpadea sin vibraciones"
- [ ] Sesión larga (varios minutos): sin reinicios inesperados — no probado
      todavía de forma prolongada

**Resumen de la causa raíz:** los tres síntomas (PAN sin moverse, temblor de
encendido, temblor de parpadeo) apuntaban al mismo origen — el chip PCA9685 o la
comunicación I2C con él —, no a la fuente de alimentación ni a un bug de
temporización en el firmware. Ver [`README-v5.md`](README-v5.md), sección
"Historial de depuración completo", para la cronología detallada de cómo se llegó
a esta conclusión, incluyendo los intentos que no funcionaron.

### Hito 4.1: PAN no se mueve ✅ (resuelto, ver Hito 4.5)

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
- [x] **Resuelto sin necesitar `diagnostico_canal.py`:** al pasar a PWM directo
      (Hito 4.5), PAN empezó a funcionar sin ningún cambio específico a ese eje —
      confirma que la causa estaba en el PCA9685/I2C, no en el cableado mecánico
      del servo. `diagnostico_canal.py` queda como herramienta disponible para
      futuros problemas de un solo canal, pero no hizo falta usarlo aquí.

### Hito 4.2: Temblor aleatorio al conectar la alimentación ✅ (arreglado, luego superado)

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
- [x] **Confirmado por el usuario:** el arreglo de `/OE` eliminó el temblor al
      conectar la alimentación. El nivel lógico de 3.3V del GPIO de la Pico basta.
- [x] **Nota final:** este arreglo era específico del PCA9685 y ya no aplica en la
      arquitectura final (Hito 4.5, PWM directo) — se conserva documentado en
      `main_pca9685.py` y en el historial de README-v5.md por si se necesita en el
      futuro, pero no forma parte del firmware activo.

### Hito 4.3: Temblor periódico cada ~5s, tras arreglar el de encendido ✅ (causa confirmada, resuelto en Hito 4.5)

- [x] Dato relevante, mismo patrón que con PAN (Hito 4.1): **v5 es la primera
      versión que hace parpadear los párpados** después del arranque — v4 nunca
      volvía a tocar esos canales. Es plausible que el parpadeo esté ejercitando
      por primera vez una fragilidad eléctrica (pico de corriente al mover 4
      servos con solo 10ms de separación) que ya existía pero nunca se había
      puesto a prueba.
- [x] Añadido `PARPADEO_ACTIVO` en `main.py`: interruptor para desactivar el
      parpadeo sin tocar el resto del firmware, como prueba diagnóstica limpia —
      si el temblor de ~5s desaparece con `PARPADEO_ACTIVO = False`, confirma que
      el parpadeo es el disparador; si persiste igual, hay que buscar en otro lado
      (no se toca la lógica de rastreo/cuello a la vez, para no mezclar variables)
- [x] **Confirmado por el usuario:** con `PARPADEO_ACTIVO = False` no tiembla; con
      `True`, sí. El parpadeo es el disparador, confirmado, no solo sospechado.
- [x] Aumentado `ESPACIADO_PARPADEO_S` de 10ms a 50ms: menos servos acelerando a
      la vez durante el cierre/apertura, para que sus picos de corriente se
      solapen menos. El parpadeo completo pasa de ~230ms a ~550ms (más lento,
      pero sigue leyéndose como parpadeo, no como "ojos cerrándose").
- [x] **Resultado inesperado:** con el espaciado subido a 50ms, el usuario reporta
      que el temblor **empeoró**: pasó de "cada ~5s" a "continuo, sin pausas desde
      el arranque". Confirmado que el despliegue fue correcto (código nuevo en la
      Pico, reiniciada). Confirmado también que ocurre **sin `face_tracker.py`
      corriendo** — no es ruido de la cámara amplificado por PAN/TILT, es el
      firmware solo.
- [x] Releído `main.py` completo tres veces: la temporización (`time.ticks_add`/
      `time.ticks_diff`) es idéntica al patrón que ya usa `ojosMecanicos/main.py`
      con éxito. No se encontró ningún bug de lógica en la programación del
      temporizador de parpadeo.
- [x] Añadidos prints de diagnóstico en el disparador del parpadeo: cada vez que
      dispara, imprime cuánto tiempo pasó y cuántas vueltas de bucle dio desde el
      parpadeo anterior. Esto convierte "se siente continuo" en un dato medible:
      - Si imprime intervalos normales (2000-6000ms, cientos de vueltas) → el
        disparador funciona bien, y el temblor "continuo" no son parpadeos
        repetidos; hay que buscar la causa en otro lado (hardware, no el
        temporizador)
      - Si imprime intervalos casi nulos (~0ms, ~0 vueltas) repetidamente → el
        disparador SÍ está roto y parpadea sin parar
      - Si el mensaje de arranque ("v5: iniciando...") se repite solo, en vez de
        aparecer una sola vez → la Pico se está reiniciando en bucle (posible
        brownout: la fuente no aguanta ni la secuencia de arranque), y lo que se
        ve como "temblor continuo" sería en realidad la secuencia de apertura de
        párpados + centrado repitiéndose una y otra vez, no el parpadeo
- [x] **Superado, no llegó a usarse:** antes de que el usuario reportara los datos
      de estos prints, se decidió probar la vía del Hito 4.5 (PWM directo), que
      resolvió el problema de raíz. Los prints se retiraron de `main.py` en la
      limpieza final (siguen disponibles en `main_pca9685.py` si hiciera falta
      retomar esa vía).

### Hito 4.4: Alternativa sin PCA9685 — PWM directo desde la Pico ✅ (implementada)

- [x] Creado [`main_pwm_directo.py`](main_pwm_directo.py): misma funcionalidad
      (ojos+cuello+parpadeo, mismo protocolo serial), generando el PWM de cada
      servo directamente desde `machine.PWM` en 8 pines de la Pico
      (`LR=GP2 UD=GP3 TL=GP4 BL=GP5 TR=GP6 BR=GP7 PAN=GP8 TILT=GP9`), sin PCA9685
      ni I2C
- [x] Verificado sin hardware: la conversión de grados a pulso da la misma
      posición física que la fórmula del PCA9685 (diferencia < 5µs en todo el
      rango 0°-180°)
- [x] Documentado honestamente qué puede y qué no puede descartar esta prueba: SÍ
      descarta problemas propios del chip PCA9685/I2C; NO descarta un problema de
      capacidad de la fuente de alimentación, que afectaría igual sin importar
      quién genere el PWM
- [x] Documentado un riesgo sin confirmar, paralelo al de `/OE`: los GPIOs de la
      Pico también flotan hasta que el código los configura, así que el temblor de
      arranque original podría reaparecer aquí sin resistencias de pull-down (8
      en vez de la 1 que bastaba con `/OE`)
- [x] **Probado por el usuario y funciona** — ver Hito 4.5

### Hito 4.5: Despliegue y confirmación final ✅ (resuelto)

- [x] Dos intentos fallidos de cargar `main_pwm_directo.py`, ambos
      `SyntaxError: invalid syntax` con `File "<stdin>"` — diagnosticado como
      Thonny pegando el código por el REPL (botón ▶ Run) en vez de guardarlo en
      el sistema de archivos de la Pico. Se eliminaron también, por si acaso,
      todas las f-strings partidas en varias líneas del fichero (y de
      `main.py`, por consistencia)
- [x] Con el despliegue correcto (`Guardar como → Raspberry Pi Pico` + reinicio
      físico, no el botón ▶ Run): **funciona por completo**
- [x] **Confirmado por el usuario:** "todos los motores se mueven y parpadea sin
      vibraciones" — Y además, sin ningún cambio específico a ese eje, **PAN
      también funciona ahora**
- [x] Conclusión: los tres síntomas (PAN, temblor de encendido, temblor de
      parpadeo) tenían el mismo origen — el PCA9685/I2C
- [x] Reorganización de archivos: `main_pwm_directo.py` → `main.py` (oficial),
      `main.py` original → `main_pca9685.py` (archivado, con nota de "no usar"),
      limpiados los prints de diagnóstico ya innecesarios, `test_main_math.py`
      actualizado a la fórmula de PWM directo (con un test cruzado que confirma
      que ambas fórmulas de pulso dan la misma posición física)

---

## Definición de listo

v5.0.0 está lista — **completada**:

1. [x] Autonomía completa (no depende de v1/v2/v3/v4)
2. [x] Cuello y parpadeo implementados, con la matemática nueva verificada sin
   hardware
3. [x] Compatibilidad de protocolo con versiones anteriores mantenida
4. [x] Rastreo de ojos y TILT confirmados funcionando en hardware real
5. [x] PAN funcionando (resuelto con el cambio a PWM directo)
6. [x] Temblor de encendido y de parpadeo eliminados (mismo cambio de arquitectura)
7. [x] Validación funcional completa, confirmada por el usuario: "todos los
   motores se mueven y parpadea sin vibraciones"
8. [ ] Sesión larga sin problemas — no verificado todavía, no bloqueante

---

**Última actualización:** Agosto 8, 2026
**Estado actual:** v5.0.0 completa y validada en hardware real. Requirió abandonar
el controlador PCA9685 a mitad de la depuración, en favor de PWM directo desde la
Pico — cambio de arquitectura no anticipado al empezar la versión, documentado con
su cronología completa (incluyendo los intentos que no funcionaron) en
[`README-v5.md`](README-v5.md).
