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

## Arranque limpio: /OE del PCA9685

**Síntoma encontrado al probar en hardware real:** al conectar la alimentación,
todos los servos se movían solos en direcciones aleatorias durante 1-2 segundos,
con cualquier firmware, incluso antes de que llegara a ejecutarse ningún código.

**Diagnóstico:** entre el instante en que llega la alimentación y el instante en
que la Pico termina de arrancar y configura el PCA9685 por I2C, las salidas PWM del
chip quedan en un estado indefinido. Los servos son sensibles a cualquier señal en
su cable de control y reaccionan a ese ruido como si fuera un comando válido.

**Arreglo, en dos partes:**

1. **Hardware (lo tienes que hacer tú):** el pin `/OE` (Output Enable, activo en
   bajo) del PCA9685 estaba puesto directo a GND — salidas siempre habilitadas.
   Hay que:
   - Quitar ese jumper/cable de `/OE` a GND
   - Añadir una resistencia de pull-up (10kΩ típico) de `/OE` a `VCC` en la misma
     placa PCA9685 — así `/OE` queda en HIGH (deshabilitado) por defecto incluso
     antes de que la Pico arranque
   - Cablear `/OE` a `GP2` de la Pico

2. **Firmware (ya en `main.py`):** `GP2` se configura como salida y se pone en
   HIGH (deshabilitado) como lo primero que hace el código. Las salidas se vuelven
   a habilitar justo después de inicializar el chip PCA9685, **antes** de los
   bucles de centrado — en ese punto los registros de posición siguen en su estado
   de reposo de fábrica (sin señal), así que habilitar ahí no causa ningún
   movimiento. Si se habilitara después de programar ya las posiciones, los 8
   servos saltarían todos a la vez al habilitar, justo lo que el espaciado de
   0.1s entre motores quiere evitar.

**Aviso eléctrico, sin confirmar:** esto asume que el pin `VCC` (lógica) de tu
PCA9685 está a 3.3V, o a un voltaje donde un GPIO de 3.3V de la Pico marque un HIGH
inequívoco. Si tu placa alimenta la lógica a 5V, el umbral de `VIH` podría quedar
por encima de lo que un GPIO de 3.3V puede garantizar, y el arreglo no sería fiable.
Si después de este cambio el temblor de encendido sigue apareciendo igual, ese
desajuste de nivel lógico es la explicación más probable a revisar.

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

**Verificado con la Pico real, por el usuario:**
- El rastreo de ojos y el movimiento arriba/abajo (TILT) funcionan bien
- El temblor aleatorio de encendido, diagnosticado y con arreglo propuesto (ver
  arriba) — pendiente de confirmar que el arreglo lo elimina de verdad

**No verificado todavía:**
- **Por qué PAN (rotación izquierda/derecha) no se mueve**, aunque el código es
  idéntico en estructura al de TILT (mismo sistema de ejes, mismo suavizado). No se
  encontró ningún bug de lógica revisando el fichero línea por línea — la hipótesis
  de trabajo es hardware (cable, servo, o un tope mecánico en ese eje concreto,
  nunca antes ejercitado activamente en v4). Diagnóstico en curso con
  [`diagnostico_canal.py`](diagnostico_canal.py), que mueve ese canal solo, sin
  nada de la lógica de rastreo de por medio
- Que el arreglo de `/OE` funcione de verdad con el nivel lógico real de la placa
  PCA9685 del usuario (ver aviso eléctrico arriba)
- Que el cuello se mueva de forma orgánica y que el parpadeo no cause tirones
  perceptibles en el rastreo — pendiente una vez resuelto lo de PAN
- Que los servos nuevos en movimiento simultáneo no sobrecarguen la fuente —
  v4 solo movía 2 ejes activamente, v5 mueve hasta 6

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
