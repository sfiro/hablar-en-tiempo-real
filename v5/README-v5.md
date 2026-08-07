# Versión 5.0 — + Cuello y parpadeo, mientras rastrea 👁️

**Objetivo:** v4 hacía dos cosas (párpados abiertos + rastreo x,y de los ojos). v5
añade, sin tocar el rastreo de ojos que ya está validado:

1. **Rotación de cabeza (PAN):** el cuello gira horizontalmente imitando a los ojos,
   amortiguado al 80% — no gira tanto como los ojos, los acompaña.
2. **Subir/bajar cabeza (TILT):** el cuello se inclina verticalmente imitando a los
   ojos, amortiguado al 60%.
3. **Parpadeo periódico:** cada 2-6 segundos, sin depender de si hay rastreo activo
   — los párpados se cierran y abren mientras los ojos siguen la cara, igual que un
   parpadeo real durante cualquier actividad.

Nada de emociones ni joystick ni modo autónomo todavía — sigue el plan que se dejó
en v4: primero el movimiento base (ojos), luego cuello y parpadeo (esta versión), y
las emociones más adelante.

**Estado:** código completo, con tests. **No validado en la Pico real todavía** —
necesita que el usuario lo pruebe con el hardware físico, igual que pasó en v4 antes
de confirmarse.

**Totalmente autónoma:** no depende de ningún fichero de v1/v2/v3/v4. Tiene sus
propias copias de `face_tracker.py` y `pico_serial.py` (idénticas a las de v4, que
a su vez vienen de v3 — el rastreo de ojos y el enlace serial no cambiaron, solo el
firmware de la Pico), su propio `.venv/` y sus propios tests.

---

## Qué cambia en `main.py` respecto a v4

| | v4 | v5 |
|---|---|---|
| Ojos (LR/UD) | ✅ rastreo con EMA | ✅ igual, sin cambios |
| Párpados | Abiertos una vez, quietos | Abiertos + **parpadeo cada 2-6s** |
| Cuello (PAN/TILT) | Centrado una vez, quieto | **Sigue a los ojos**, amortiguado |
| Emociones | — | — (todavía no) |

**Cómo se calcula el cuello:** en cada vuelta del bucle, a partir del objetivo
actual de LR/UD (no del valor ya suavizado — mismo criterio que
`ojosMecanicos/main.py`):

```
objetivo_pan  = 90 + (objetivo_LR - 90) * 0.8
objetivo_tilt = 90 + (objetivo_UD - 90) * 0.6
```

Después, el cuello se mueve hacia ese objetivo con el mismo suavizado EMA
(`ALPHA=0.1`) que ya usan los ojos — no es instantáneo, converge igual de suave.

**Cómo funciona el parpadeo:** un temporizador aleatorio (2-6 segundos, igual que el
parpadeo automático de `ojosMecanicos/main.py` en modo inactivo) dispara
`parpadear()`: cierra los 4 párpados con 10ms de separación entre cada uno (para no
pedir toda la corriente de golpe), espera 150ms, y los reabre igual de escalonado.
Esto **bloquea el bucle principal ~230ms** mientras dura — es el mismo
comportamiento que en el original, no una regresión introducida aquí.

## Qué NO cambia (deliberado)

- El protocolo serial sigue siendo `"LR,UD\n"` o `"LR,UD,EMOCION\n"` (ignorando la
  emoción) — sin cambios en `pico_serial.py` ni en el Mac.
- `face_tracker.py` no se toca: el rastreo de ojos es exactamente el de v4.
- No hay emociones, joystick ni modo autónomo — eso sigue siendo trabajo futuro.

## Cómo se verificó (y qué falta)

**Verificado sin hardware, igual que en v4:**
- Sintaxis (`py_compile`, AST)
- Fórmula de pulso PCA9685, idéntica a v4: 0°→102, 90°→307, 180°→512
- **Nuevo en v5:** la fórmula de amortiguación del cuello, verificada de forma
  aislada (`tests/test_main_math.py`): el cuello se mueve siempre menos que los
  ojos (nunca al mismo ángulo ni más), y nunca sale de su rango 40-140 aunque los
  ojos estén en un extremo
- Los 19 tests de `face_tracker.py`/`pico_serial.py` heredados de v4, sin cambios,
  corriendo dentro del `.venv` propio de v5

**No verificado, necesita la Pico física:**
- Que el cuello se mueva de verdad de forma orgánica siguiendo los ojos (la fórmula
  está verificada matemáticamente, no cómo se ve/siente en el rig)
- Que el parpadeo no interfiera perceptiblemente con la fluidez del rastreo — el
  bloqueo de ~230ms durante cada parpadeo podría notarse como una pausa breve en el
  seguimiento; solo se confirma mirando el hardware real
- Que los 3 servos nuevos en movimiento simultáneo (cuello + parpadeo + ojos) no
  sobrecarguen la fuente de alimentación — v4 solo movía 2 ejes activamente, v5
  mueve hasta 6 (LR, UD, PAN, TILT, y los 4 párpados durante el parpadeo)

## Cómo probarlo

```bash
cd v5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python face_tracker.py    # igual que en v4: cámara -> x,y -> servos
```

Despliega `main.py` en la Pico igual que en v4 (Thonny o `mpremote`, ver
[`v4/README-v4.md`](../v4/README-v4.md) para el paso a paso — el procedimiento de
despliegue no cambió, solo el contenido del fichero).

**Qué deberías ver, si funciona:** los ojos siguen tu cara (igual que en v4), la
cabeza gira y se inclina acompañando el movimiento (más suave, no igual de brusco),
y cada pocos segundos los párpados se cierran y abren solos, sin que tengas que
hacer nada — incluso mientras el rastreo sigue activo.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v   # 24 tests
```

## Próximos pasos (fuera de esta versión)

1. Validar en hardware real (bloqueante para cerrar v5)
2. Emociones y su sincronía con la mirada (offsets de párpados/cuello)
3. Retomar la integración de voz: cablear el sentimiento detectado hacia las
   emociones, ahora con cuello y parpadeo ya funcionando

## Referencias

- [`ojosMecanicos/main.py`](/Users/debbie/Desktop/programacion/ojosMecanicos/main.py) — firmware completo (joystick, modo autónomo, emociones)
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) — documentación de hardware
- [`../v4/README-v4.md`](../v4/README-v4.md) — versión anterior (solo ojos)
- [PLAN-v5.md](PLAN-v5.md) — hitos
