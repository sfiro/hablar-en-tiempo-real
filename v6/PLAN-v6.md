# Plan de desarrollo — v6.0.0 Estado base

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

---

## Definición de listo

v6.0.0 está lista cuando:

1. [x] Base funcional de v5 traída completa y verificada de forma autónoma
2. [x] `estado_base.py` implementado, con la matemática verificada sin hardware
3. [ ] `estado_base.py` validado en la Pico real: los 8 servos llegan a 90° y se
   quedan ahí de forma estable

---

**Última actualización:** Agosto 8, 2026
**Estado actual:** Hito 1 y 2 completos en código. Falta la validación con
hardware real de `estado_base.py`, que depende de que el usuario lo pruebe con la
Pico física.
