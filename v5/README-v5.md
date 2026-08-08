# Versión 5.0 — + Cuello y parpadeo, mientras rastrea 👁️

**Objetivo:** v4 hacía dos cosas (párpados abiertos + rastreo x,y de los ojos). v5
añade, sin tocar el rastreo de ojos que ya está validado:

1. **Rotación de cabeza (PAN):** el cuello gira horizontalmente imitando a los ojos,
   amortiguado al 80% — no gira tanto como los ojos, los acompaña.
2. **Subir/bajar cabeza (TILT):** el cuello se inclina verticalmente imitando a los
   ojos, amortiguado al 60%.
3. **Parpadeo periódico:** cada 2-6 segundos, sin depender de si hay rastreo activo
   — los párpados se cierran y abren mientras los ojos siguen la cara.

Nada de emociones ni joystick ni modo autónomo todavía — sigue el plan que se dejó
en v4: primero el movimiento base (ojos), luego cuello y parpadeo (esta versión), y
las emociones más adelante.

**Estado: ✅ completa y validada en hardware real.** El usuario confirmó: "todos
los motores se mueven y parpadea sin vibraciones". Llegar hasta aquí llevó un
proceso de depuración largo, con un cambio de arquitectura de por medio (se
abandonó el controlador PCA9685) — la cronología completa está en la sección
["Historial de depuración"](#historial-de-depuración-completo) más abajo, porque
vale la pena dejar constancia de qué se intentó, qué falló y por qué, no solo el
estado final.

**Totalmente autónoma:** no depende de ningún fichero de v1/v2/v3/v4. Tiene sus
propias copias de `face_tracker.py` y `pico_serial.py` (idénticas a las de v4, que
a su vez vienen de v3 — el rastreo de ojos y el enlace serial no cambiaron, solo el
firmware de la Pico), su propio `.venv/` y sus propios tests.

---

## Arquitectura final: PWM directo desde la Pico, sin PCA9685

`main.py` genera el PWM de cada uno de los 8 servos directamente desde los pines
de la propia Raspberry Pi Pico (`machine.PWM`), **sin** pasar por un controlador
PCA9685 ni por I2C. Es distinto de cómo empezó v5 (ver historial abajo) — el
cambio de arquitectura fue necesario, no una preferencia de diseño de partida.

**Mapeo de pines** (cada par comparte "slice" de PWM en el RP2040, sin conflicto
porque los 8 servos usan la misma frecuencia de 50Hz):

```
LR=GP2   UD=GP3   TL=GP4   BL=GP5   TR=GP6   BR=GP7   PAN=GP8   TILT=GP9
```

| | v4 | v5 |
|---|---|---|
| Ojos (LR/UD) | ✅ rastreo con EMA | ✅ igual, sin cambios |
| Párpados | Abiertos una vez, quietos | Abiertos + **parpadeo cada 2-6s** |
| Cuello (PAN/TILT) | Centrado una vez, quieto | **Sigue a los ojos**, amortiguado |
| Controlador de servos | PCA9685 (I2C) | **PWM directo de la Pico** |
| Emociones | — | — (todavía no) |

**Cómo se calcula el cuello:** en cada vuelta del bucle, a partir del objetivo
actual de LR/UD (no del valor ya suavizado — mismo criterio que
`ojosMecanicos/main.py`):

```
objetivo_pan  = 90 + (objetivo_LR - 90) * 0.8
objetivo_tilt = 90 + (objetivo_UD - 90) * 0.6
```

Después, el cuello se mueve hacia ese objetivo con el mismo suavizado EMA
(`ALPHA=0.1`) que ya usan los ojos.

**Cómo funciona el parpadeo:** un temporizador aleatorio (2-6 segundos) dispara
`parpadear()`: cierra los 4 párpados con 50ms de separación entre cada uno, espera
150ms, y los reabre igual de escalonado. Bloquea el bucle principal ~550ms mientras
dura.

**Conversión de grados a PWM:** mismo rango de pulso que usaba el PCA9685
(500-2500µs), para que la misma posición en grados dé la misma posición física de
servo — verificado que ambas fórmulas difieren menos de 5µs en todo el rango
0°-180° (`tests/test_main_math.py`).

## Qué NO cambia (deliberado)

- El protocolo serial sigue siendo `"LR,UD\n"` o `"LR,UD,EMOCION\n"` (ignorando la
  emoción) — sin cambios en `pico_serial.py` ni en el Mac.
- `face_tracker.py` no se toca: el rastreo de ojos es exactamente el de v4.
- No hay emociones, joystick ni modo autónomo — eso sigue siendo trabajo futuro.

---

## Historial de depuración completo

Esta sección documenta, en orden, cada síntoma real encontrado en hardware, cada
hipótesis considerada, cada arreglo intentado y su resultado — incluyendo los que
no funcionaron. El objetivo es que quien retome esto después no repita el mismo
camino ni descarte de memoria una hipótesis que en realidad nunca se probó del
todo.

### 1. Temblor aleatorio al conectar la alimentación

**Síntoma:** al conectar la energía, todos los servos se movían solos en
direcciones aleatorias durante 1-2 segundos.

**Diagnóstico, por eliminación (tres preguntas, tres respuestas):**
- ¿Ocurre con cualquier firmware, incluso antes de ejecutar código? → **Sí**.
  Descarta un bug de software: el problema existe antes de que el código llegue a
  correr.
- ¿Se calma solo o continúa sin parar? → **Se calma en 1-2s**, justo cuando el
  firmware termina de arrancar y toma el control.
- ¿Cómo está alimentados los servos? → **Fuente dedicada**, separada de la Pico.
  Descarta el motivo más común de este síntoma (fuente compartida insuficiente).

**Causa:** entre el instante en que llega la alimentación y el instante en que la
Pico termina de arrancar y configura el PCA9685 por I2C, las salidas PWM del chip
quedan en un estado indefinido. Los servos reaccionan a esa señal indefinida como
si fuera un comando válido.

**Arreglo, en dos partes:**
1. **Hardware:** el pin `/OE` (Output Enable, activo en bajo) del PCA9685 estaba
   puesto directo a GND. Se quitó ese jumper, se añadió una resistencia de pull-up
   (10kΩ) de `/OE` a `VCC` en la placa PCA9685, y se cableó `/OE` a `GP2` de la Pico.
2. **Firmware:** `GP2` se configuraba como salida y se ponía en HIGH (deshabilitado)
   como lo primero que hacía el código, y se bajaba (habilitaba) justo después de
   inicializar el chip PCA9685 — antes de mover ningún servo, para no deshacer la
   protección contra picos de corriente del espaciado entre motores.

**Resultado: ✅ confirmado arreglado.** El temblor de encendido desapareció.

*(Este arreglo era específico del PCA9685. Al abandonarlo más adelante —ver punto
5— dejó de ser necesario: los GPIOs de la Pico no tienen un pin `/OE` único, así
que este mecanismo concreto no aplica a la arquitectura final. Ver el aviso sobre
esto en el punto 5.)*

### 2. PAN (rotación izquierda/derecha) no se movía

**Síntoma:** con la Pico ya funcionando (ojos y TILT bien), PAN no reaccionaba.

**Diagnóstico:** se releyó `main.py` línea por línea comparando PAN contra TILT —
misma estructura de código exacta (mismo diccionario de ejes, mismo suavizado EMA,
misma inicialización), solo cambiaban el canal (6 vs 7) y el factor de
amortiguación (0.8 vs 0.6). **No se encontró ningún bug de lógica.**

**Dato relevante:** en v4, el canal PAN nunca se movía de forma activa (solo se
centraba una vez al arrancar). Esta era la primera vez que se ejercitaba en todo su
rango — un problema de cableado o mecánico en ese eje concreto podría haber estado
ahí desde siempre sin que nadie lo notara.

**Herramienta creada:** [`diagnostico_canal.py`](diagnostico_canal.py), que mueve
un solo canal del PCA9685 en barrido lento, aislado de toda la lógica de rastreo —
para diferenciar hardware de firmware sin ambigüedad.

**Resultado: sin resolver por esta vía.** El diagnóstico con `diagnostico_canal.py`
quedó pendiente de ejecutar; el problema se resolvió por otro camino (punto 6): al
abandonar el PCA9685 por completo, PAN empezó a funcionar. Esto sugiere
retrospectivamente que la causa también estaba en el PCA9685/I2C, no en el cableado
mecánico del servo — pero no se confirmó de forma aislada con esa herramienta.

### 3. Temblor periódico cada ~5 segundos (tras arreglar el de encendido)

**Síntoma:** ya con el temblor de encendido resuelto, apareció uno nuevo: todos los
servos se movían en todas direcciones cada ~5 segundos, de forma recurrente.

**Hipótesis:** v5 es la primera versión que hace parpadear los párpados después
del arranque (v4 nunca volvía a tocar esos canales tras centrarlos). El intervalo
del temporizador de parpadeo (aleatorio 2-6s) encaja con "cada ~5s".

**Prueba diagnóstica:** se añadió `PARPADEO_ACTIVO` como interruptor. Con `False`,
no tiembla; con `True`, sí.

**Resultado: ✅ confirmado.** El parpadeo era el disparador.

### 4. Intento de arreglo: espaciar más los servos del parpadeo — empeoró

**Razonamiento:** si 4 servos moviéndose con solo 10ms de separación entre cada uno
generaban un pico de corriente que temblaba todo, subir ese espaciado debería
reducirlo.

**Cambio:** `ESPACIADO_PARPADEO_S` subido de 10ms a 50ms. El parpadeo completo pasó
de ~230ms a ~550ms.

**Resultado: ❌ empeoró, no mejoró.** El temblor pasó de "cada ~5s, con pausas
claras entre medio" a **"continuo, sin ninguna pausa, desde el momento en que se
conecta la alimentación"**. Confirmado que el despliegue del cambio fue correcto
(el usuario guardó el archivo en la Pico y la reinició antes de la prueba).
Confirmado también que el problema ocurría **incluso sin `face_tracker.py`
corriendo** — descartando que fuera ruido de la cámara amplificado por PAN/TILT.

Se releyó `main.py` completo tres veces buscando un bug que explicara por qué
alargar el espaciado empeoraría las cosas. No se encontró ninguno: la temporización
del parpadeo (`time.ticks_add`/`time.ticks_diff`) es idéntica al patrón que ya usa
`ojosMecanicos/main.py` con éxito.

Se añadieron prints de diagnóstico (`[parpadeo] han pasado Xms, Y vueltas de bucle
desde el anterior`) para convertir "se siente continuo" en datos medibles —
pensados también para detectar si la Pico se estaba reiniciando en bucle
(brownout), en cuyo caso el mensaje de arranque se repetiría solo. **Nunca se
llegaron a usar**: antes de que el usuario reportara esos datos, se decidió probar
una vía distinta (punto 5).

### 5. Pivote: PWM directo desde la Pico, sin PCA9685 — propuesto por el usuario

Ante el empeoramiento inexplicado del punto 4, el usuario propuso una vía
distinta: generar el PWM de cada servo directamente desde los pines de la Pico
(`machine.PWM`), eliminando el PCA9685 y el I2C de la ecuación por completo.

**Documentado honestamente antes de probarlo, qué podía y qué no podía demostrar
este cambio:**
- **Sí** podía descartar cualquier problema específico del chip PCA9685 o de la
  comunicación I2C con él.
- **No** podía arreglar un problema de capacidad de la fuente de alimentación —
  los servos seguirían tirando de la misma corriente, de la misma fuente, sin
  importar quién genere la señal PWM.

Se creó `main_pwm_directo.py` con la misma funcionalidad y el mismo protocolo
serial, en 8 pines independientes de la Pico
(`LR=GP2 UD=GP3 TL=GP4 BL=GP5 TR=GP6 BR=GP7 PAN=GP8 TILT=GP9`). Verificado sin
hardware que la conversión de grados a pulso da la misma posición física que la
fórmula del PCA9685 (diferencia < 5µs en todo el rango).

### 6. Dos intentos fallidos de cargarlo, por el mismo motivo

**Primer intento:** `SyntaxError: invalid syntax` en la línea 185, con
`File "<stdin>"` en el traceback. Se sospechó que una f-string partida en dos
líneas del código no era compatible con cómo Thonny estaba transmitiendo el
archivo. Se eliminaron todas las f-strings del fichero (y de `main.py`, por
consistencia), sustituyéndolas por `print()` con argumentos separados por comas.

**Segundo intento:** el mismo tipo de error, ahora en la línea 184 (desplazada
exactamente por la línea que se había quitado) — confirmando que sí se estaba
cargando el archivo actualizado, pero la línea 184 en ese momento era un `print()`
completamente estándar, sin nada inusual. Esto descartó que el contenido del
archivo fuera el problema real.

**Diagnóstico correcto:** `File "<stdin>"` junto con `MPY: soft reboot` es la
firma característica de que **Thonny estaba pegando el código directo en el REPL**
(botón ▶ "Run"), no ejecutando un `main.py` guardado de verdad en el sistema de
archivos de la Pico. Ese modo de pegado por REPL puede romperse con scripts largos
aunque el archivo en sí sea perfectamente válido.

**Arreglo:** instrucciones explícitas de despliegue — `Archivo → Guardar como →
Raspberry Pi Pico`, nombrarlo `main.py`, y reiniciar la placa físicamente
(desconectar/reconectar USB) en vez de pulsar ▶ Run.

**Resultado: ✅ funcionó.**

### 7. Resultado final: funciona, y además resuelve el problema de PAN

Con `main_pwm_directo.py` desplegado correctamente: **"todos los motores se mueven
y parpadea sin vibraciones"**, confirmado por el usuario. Y, sin que se hubiera
tocado nada relacionado con ese eje en este cambio: **PAN también funciona ahora.**

**Conclusión:** los tres síntomas (temblor de encendido, temblor de parpadeo, PAN
sin moverse) apuntaban al mismo origen: el chip PCA9685 o la comunicación I2C con
él — no a la fuente de alimentación, no a un bug de temporización en el firmware,
y no a un problema mecánico o de cableado del eje PAN en particular. El arreglo de
`/OE` del punto 1 probablemente mitigaba un síntoma del mismo problema de fondo sin
llegar a resolverlo del todo.

**Reorganización tras confirmar el resultado:**
- `main_pwm_directo.py` → renombrado a `main.py` (es ahora el firmware oficial)
- El `main.py` original (con PCA9685) → renombrado a `main_pca9685.py`, conservado
  como referencia histórica, con una nota clara de que no debe usarse
- Limpiados los prints de diagnóstico del punto 4 (`vueltas_de_bucle`,
  `transcurrido`) del `main.py` final, ya con la causa resuelta
- `tests/test_main_math.py` actualizado: verificaba la fórmula de pulso del
  PCA9685 (ya archivada); ahora verifica la fórmula real de PWM directo que usa
  `main.py`, más un test cruzado que confirma que ambas fórmulas dan la misma
  posición física (por si `main_pca9685.py` se necesita consultar en el futuro)

---

## Qué queda sin verificar

- Que el cuello se mueva de forma orgánica de verdad (la fórmula está verificada
  matemáticamente; cómo se ve/siente en el rig solo lo confirma mirarlo)
- Que el parpadeo no cause tirones perceptibles en el rastreo — el bloqueo de
  ~550ms durante cada parpadeo podría notarse como una pausa breve
- Que los 8 servos en PWM directo simultáneo no sobrecarguen la fuente de
  alimentación en un uso prolongado (validado en pruebas puntuales, no en una
  sesión larga)
- El aviso eléctrico de `main_pca9685.py` (nivel lógico de `/OE`) ya no aplica a
  la arquitectura actual, y se conserva solo por completitud del historial

## Cómo probarlo

```bash
cd v5
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python face_tracker.py    # cámara -> x,y -> servos, igual que en v4
```

Para el firmware, en Thonny: abre `main.py`, `Archivo → Guardar como →
Raspberry Pi Pico`, y reinicia la placa físicamente (no uses el botón ▶ Run para
la prueba final — ver punto 6 del historial de por qué).

**Qué deberías ver, si funciona:** los ojos siguen tu cara, la cabeza gira y se
inclina acompañando el movimiento (más suave, amortiguado), y cada pocos segundos
los párpados se cierran y abren solos, sin tirones, incluso con el rastreo activo.

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v   # 25 tests
```

## Próximos pasos (fuera de esta versión)

1. Validación de estabilidad a largo plazo (sesión larga, sin reinicios)
2. Emociones y su sincronía con la mirada (offsets de párpados/cuello)
3. Retomar la integración de voz: cablear el sentimiento detectado hacia las
   emociones, ahora con cuello y parpadeo ya funcionando sobre una base sólida

## Referencias

- [`ojosMecanicos/main.py`](/Users/debbie/Desktop/programacion/ojosMecanicos/main.py) — firmware completo (joystick, modo autónomo, emociones), con PCA9685
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) — documentación de hardware
- [`main_pca9685.py`](main_pca9685.py) — versión archivada de este firmware, con PCA9685 (no usar; ver historial de depuración arriba)
- [`../v4/README-v4.md`](../v4/README-v4.md) — versión anterior (solo ojos, también con PCA9685)
- [PLAN-v5.md](PLAN-v5.md) — hitos
