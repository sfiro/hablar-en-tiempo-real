# Plan de desarrollo — v7.0.0 Seguimiento visual real + secuencia de expresiones

---

## Hito 1: Base funcional de v6, traída completa ✅ (completado)

- [x] Copiado `v6/main.py` → `v7/main.py`, sin cambios de lógica (solo
      referencias de documentación actualizadas: título, prints, punteros a
      README-v7.md/PLAN-v7.md)
- [x] Copiado `v6/face_tracker.py` → `v7/face_tracker.py`, sin cambios de
      lógica (mismas correcciones de referencias)
- [x] Copiado `v6/pico_serial.py` → `v7/pico_serial.py`, sin cambios de lógica
- [x] Copiado `v6/estado_base.py` → `v7/estado_base.py`, sin cambios de lógica
- [x] Copiado `v6/diagnostico_canal.py` → `v7/diagnostico_canal.py`, sin
      cambios (no tenía referencias a corregir)
- [x] Copiados los tests de `v6/tests/` → `v7/tests/`
- [x] `v7/requirements.txt`, `v7/requirements-dev.txt`, `v7/.venv` propios
- [x] Verificado: los 49 tests heredados pasan dentro de `v7/.venv`, sin
      ninguna referencia a `v6/`
- [x] Confirmado que `v6/` sigue intacto y sus propios tests siguen pasando
      tras la copia (no se tocó nada de v6)

**Corregidas de paso, encontradas al revisar los ficheros copiados** (stale
desde hacía varias versiones, no introducidas por v7):
- `requirements.txt` seguía con un comentario de cabecera que decía "v4"
  (arrastrado sin corregir desde v4 → v5 → v6)
- El docstring de `face_tracker.py`/`pico_serial.py` decía "copia idéntica de
  `../v4/...`" en vez de mencionar la copia inmediata real (`../v6/...`)
- El docstring de `tests/test_main_math.py` apuntaba a "README-v6.md,
  Historial de depuración" para la historia del PCA9685 — esa sección en
  realidad vive en `v5/README-v5.md`, nunca se copió a v6; corregido el
  puntero a `../v5/README-v5.md`

## Hito 2: Documentar y validar el seguimiento visual real junto a la secuencia ✅ (completo y validado en hardware real)

**Objetivo:** v6 ya tenía, sin proponérselo como objetivo explícito, el
mecanismo que hace posible correr el rastreo facial real (`face_tracker.py`)
y la secuencia de expresiones (`main.py`) al mismo tiempo: para 7 de las 10
expresiones, `LR`/`UD` simplemente no se tocan y quedan con lo último que
llegó por el comando serial `"LR,UD"` (el rastreo real); para las otras 3
(DUDA, PENSATIVO, NERVIOSO), `actualizar_objetivo_mirada_expresion()` las
sobreescribe a propósito. v7 promueve esto a objetivo central de la versión:
documentarlo con claridad, y validar que en efecto funciona con hardware real
funcionando a la vez (cámara + Pico).

- [x] Ningún cambio de código necesario en `main.py`: el mecanismo de
      `actualizar_objetivo_mirada_expresion()` ya distingue correctamente las
      expresiones que ignoran el rastreo de las que no — verificado leyendo el
      código, no solo asumido
- [x] `README-v7.md`: nueva sección "Qué expresiones siguen el rostro y cuáles
      no", con la lista explícita de las 7 que sí y las 3 que no, y por qué
- [x] Instrucciones de prueba con los dos procesos a la vez (firmware en la
      Pico + `face_tracker.py` en el Mac)
- [x] **Validado en la Pico real por el usuario, con la cámara conectada:**
      "funcionó perfecto" — las 7 expresiones de rastreo siguen a una persona
      real, las 3 de mirada fija la ignoran sin interrupción, la transición
      entre ambos grupos es limpia, y el latido/reconexión de `PicoLink` sigue
      funcionando con la secuencia de expresiones activa

**Tests:** ninguno nuevo — la matemática de `main.py` no cambió, así que los
49 tests heredados de v6 siguen siendo la verificación completa sin hardware.
Lo que falta verificar en este hito (la integración con una cámara y una
persona reales) no es matemática pura y no se puede expresar como test de
`pytest` — solo se puede confirmar con hardware real.

---

## Definición de listo

v7.0.0 está lista cuando:

1. [x] Base funcional de v6 traída completa y verificada de forma autónoma
2. [x] Mecanismo de seguimiento real + expresiones documentado con claridad
   (qué expresiones siguen el rostro y cuáles no, y por qué)
3. [x] Validado en hardware real: cámara + Pico funcionando a la vez, con la
   secuencia de expresiones activa, confirmando el comportamiento esperado de
   las 7 expresiones de rastreo y las 3 de mirada fija

---

**Última actualización:** Agosto 9, 2026
**Estado actual:** v7.0.0 completa y validada en hardware real — confirmado
por el usuario: "funcionó perfecto". 49 tests (heredados de v6, sin cambios).
Versión cerrada.
