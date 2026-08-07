# Plan de desarrollo — v4.0.0 Rastreo facial + servos, simplificado y autónomo

---

## Hito 1: `main.py` mínimo ✅✅ (completo y validado en hardware real)

**Objetivo:** el firmware más simple que aún es útil: ojos abiertos + rastreo x,y.

- [x] Extraer de `ojosMecanicos/main.py` solo: driver PCA9685, canales LR/UD,
      posiciones de párpados abiertos, suavizado EMA, lectura serial
- [x] Quitar joystick, modo autónomo, emociones, parpadeo, sincronía mirada-párpados
      y mirada-cuello (documentado explícitamente en README-v4.md, con el porqué de
      cada uno)
- [x] Mantener compatibilidad de protocolo con v3: acepta `"LR,UD,EMOCION\n"`
      ignorando el tercer campo, así el `pico_serial.py` (el de v3 o la copia propia
      de v4) no necesita cambios
- [x] Verificado sin hardware: sintaxis (`py_compile`, AST), fórmula de pulso PCA9685
      (0°→102, 90°→307, 180°→512, igual que el original), parseo de comandos
      (acepta ambos formatos, recorta rango 40-140, rechaza basura sin lanzar)
- [x] **Validado en la Pico real por el usuario:** el rastreo funciona, los ojos
      siguen la cara "perfectamente". Confirma que el PCA9685 responde bien por
      I2C, que los párpados quedan abiertos, y que el suavizado EMA se siente fluido
      con la latencia real — las tres cosas que no se podían verificar desde este
      entorno sin la Pico física.

**Hito cerrado.** La base de movimiento (ojos abiertos + rastreo x,y) está
confirmada como sólida antes de volver a montar complejidad encima.

---

## Hito 1.5: Autonomía completa ✅ (completado)

**Objetivo:** que `v4/` pueda ejecutarse borrando `v1/`, `v2/` y `v3/` enteros, sin
que nada se rompa. Pedido explícito del usuario, y regla que se adopta para todo el
proyecto de aquí en adelante: ninguna versión importa código de otra carpeta.

- [x] Copiar `v3/face_tracker.py` → `v4/face_tracker.py` (idéntico, solo se
      actualizaron las referencias de documentación que apuntaban a `PLAN-v3.md` y
      al título de la ventana de depuración, que decían "v3")
- [x] Copiar `v3/pico_serial.py` → `v4/pico_serial.py` (idéntico)
- [x] Copiar `v3/tests/test_face_tracker.py` y `test_pico_serial.py` →
      `v4/tests/`
- [x] `v4/requirements.txt` propio: solo `opencv-python<5` + `pyserial` — más ligero
      que el de v3, porque v4 no necesita `pysentimiento`/`torch` (no toca voz)
- [x] `v4/.venv` propio, creado e instalado
- [x] Los 19 tests corridos dentro de `v4/.venv`, sin ninguna ruta hacia `v3/`:
      todos pasan
- [x] Revisión de que no quedaran referencias colgantes a "v3" en textos visibles
      para el usuario (título de ventana, `--help`) — se encontraron dos y se
      corrigieron

**Nota para el futuro:** si se arregla un bug en `face_tracker.py` o
`pico_serial.py` estando en v4, ese arreglo no se propaga solo a la copia de v3 (ni
al revés). Replicarlo a mano si aplica también ahí.

---

## Hito 2: Validación con hardware ✅ (completado)

- [x] Copiar `v4/main.py` a la Pico
- [x] Rastreo x,y confirmado funcionando con la cámara real (vía `v3/face_tracker.py`
      + `v3/pico_serial.py`, o el flujo que el usuario haya usado)
- [x] Los ojos siguen el rostro de forma fluida — confirmado por el usuario
      ("los ojos lo siguen perfectamente")

**Pendiente, no bloqueante** (detalle fino, no hace falta para pasar al Hito 3):
- [ ] Probar explícitamente los límites (`40,40` y `140,140`, las esquinas) y una
      sesión larga (varios minutos) para descartar errores de I2C acumulados —
      razonable dejarlo como prueba de regresión antes de pasar a producción, no
      como condición para seguir avanzando ahora

## Hito 3: Reintroducir complejidad, por partes 📋 (siguiente)

Una vez confirmada la base, añadir de vuelta lo quitado, un paso a la vez, en vez de
volver de golpe a la versión completa de `ojosMecanicos/main.py`:

1. Parpadeo (sin emociones)
2. Emociones + su sincronía con la mirada
3. Retomar v3: cablear el sentimiento de la conversación hacia las emociones de la
   Pico, ahora que el movimiento base ya está confirmado por separado

---

## Definición de listo

v4.0.0 está lista — **completada**:

1. [x] Firmware simplificado escrito, con la simplificación documentada y justificada
2. [x] Verificado todo lo que no requiere hardware (sintaxis, matemática, protocolo)
3. [x] Validado en la Pico real: párpados abiertos, rastreo x,y funcionando,
   confirmado por el usuario ("los ojos lo siguen perfectamente")

---

**Última actualización:** Agosto 7, 2026
**Estado actual:** v4.0.0 completa y validada en hardware real. Siguiente paso:
Hito 3 — reintroducir parpadeo y emociones por partes, o directamente retomar la
integración de voz de v3 sobre esta base ya confirmada.
