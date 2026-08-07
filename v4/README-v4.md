# Versión 4.0 — Firmware simplificado de la Pico 👁️

**Esta versión es distinta a v1/v2/v3.** No es código de Mac con su propio `.venv`:
es **firmware MicroPython** que corre *dentro* de la Raspberry Pi Pico. No hay
`requirements.txt` ni entorno virtual — se copia el fichero a la Pico y ahí se
ejecuta solo.

**Objetivo:** antes de retomar la integración de voz (v3), organizar el `main.py` de
la Pico para que funcione bien con lo mínimo imprescindible: **ojos abiertos +
rastreo x,y**. Nada de emociones, joystick, modo autónomo ni parpadeo todavía — eso
es la complejidad de `ojosMecanicos/main.py`, y se decidió apartarla para tener
primero una base simple y confiable.

**Estado:** código escrito y verificado en lo que se puede verificar sin hardware
(sintaxis, matemática de suavizado y de pulso PCA9685, parseo de comandos). **No
probado en la Pico real** — no hay una conectada a este entorno de trabajo.

---

## Qué hace `main.py`

Dos cosas, nada más:

1. **Al arrancar:** abre los 4 párpados una sola vez (a las posiciones documentadas
   en `ojosMecanicos/model.md`) y centra el cuello y los ojos. Después de esto, los
   párpados y el cuello **no se vuelven a tocar** — no hay parpadeo, no hay
   sincronía con la mirada, no hay emociones.
2. **En el bucle principal:** lee `"LR,UD\n"` por USB serial (idéntico al protocolo
   de v3) y mueve los ojos (canales LR/UD del PCA9685) hacia esa posición, con el
   mismo suavizado EMA (`ALPHA=0.1`) que ya usa `ojosMecanicos/main.py`.

Acepta también `"LR,UD,EMOCION\n"` **ignorando el tercer campo** — así el
`pico_serial.py` de v3 puede hablar con esta Pico sin ningún cambio.

## Qué se quitó, a propósito, respecto a `ojosMecanicos/main.py`

| Quitado | Por qué |
|---|---|
| Joystick (control manual) | No hace falta para validar rastreo x,y por serial |
| Modo autónomo (movimientos aleatorios) | Añade estado y ramas de código sin aportar a la pregunta "¿la Pico recibe x,y y mueve los ojos bien?" |
| Sistema de 10 emociones + offsets | Es la parte más compleja del firmware original; se reintroduce cuando la voz esté conectada de verdad, no antes |
| Parpadeo (automático y manual) | Los párpados quedan abiertos y quietos; simplifica la depuración eléctrica (menos picos de corriente que diagnosticar) |
| Sincronía párpado-mirada y cuello-mirada | Dependen de las emociones y del parpadeo, que no están aquí |

Todo lo quitado sigue existiendo, probado y documentado, en `ojosMecanicos/main.py`
y `ojosMecanicos/model.md`. Esto no es un rediseño: es un **subconjunto** deliberado.

## Cómo se probó (y qué falta)

**Verificado sin hardware:**
- Sintaxis válida (`py_compile`, parseo AST) — MicroPython no está instalado en este
  Mac, así que esto es lo más profundo que se puede comprobar sin la Pico
- La fórmula de pulso del PCA9685 (idéntica a `ojosMecanicos/main.py`, no
  reinventada) da los valores esperados en los extremos y el centro: 0°→102,
  90°→307, 180°→512
- El parseo de comandos acepta `"LR,UD"` y `"LR,UD,EMOCION"`, recorta valores fuera
  de 40-140, y rechaza basura (texto no numérico, líneas incompletas) sin lanzar

**No verificado, necesita la Pico física:**
- Que el PCA9685 responda de verdad por I2C con esta secuencia de inicialización
- Que los párpados lleguen a una posición que de verdad se vea "abierta" en el
  hardware (los valores vienen de `model.md`, pero solo se confirman mirando el rig)
- Que el suavizado EMA en el bucle real (con la latencia de I2C y `time.sleep`) se
  sienta igual de fluido que en `ojosMecanicos/main.py`, del que se copió tal cual

## Cómo desplegarlo

Este fichero **no se ejecuta con Python del Mac** — se copia a la Pico como
`main.py` (el nombre que MicroPython ejecuta automáticamente al arrancar).

**Con Thonny** (como ya se usa en `ojosMecanicos`, según sus propios avisos de "cierra
Thonny, bloquea el puerto USB"):
1. Abre `v4/main.py` en Thonny
2. Conecta la Pico, selecciona el intérprete MicroPython (RP2040) en la esquina
   inferior derecha
3. Guarda el fichero **en la Pico** con el nombre `main.py` (Archivo → Guardar como
   → Raspberry Pi Pico)
4. Reinicia la Pico (botón físico, o `Ctrl+D` en la consola de Thonny)

**Con `mpremote`** (si lo tienes instalado):
```bash
mpremote connect auto cp v4/main.py :main.py
mpremote connect auto reset
```

⚠️ **Esto sobrescribe el `main.py` que ya está en la Pico.** Si quieres conservar el
original con emociones/joystick/modo autónomo, haz una copia de seguridad primero
(cópialo de la Pico a tu Mac antes de sobrescribir), o simplemente recuerda que sigue
intacto en `ojosMecanicos/main.py` en tu Mac — la Pico y el Mac son sistemas de
archivos distintos.

## Cómo probarlo una vez desplegado

Desde el Mac, con la versión de v3 ya probada (`v3/pico_serial.py` funciona sin
cambios):

```bash
cd "../v3" && source .venv/bin/activate
python3 -c "
from pico_serial import PicoLink, encontrar_puerto_mac
puerto = encontrar_puerto_mac()
print('Puerto:', puerto)
with PicoLink(port=puerto) as pico:
    pico.enviar(140, 90)   # mirada a la derecha
    input('Enter para centrar...')
    pico.enviar(90, 90)
"
```

O más simple, con un monitor serial (Thonny, `screen`, `mpremote`) y escribiendo a
mano `120,60` + Enter — deberías ver el eco `Serial: LR=120, UD=60` y los ojos
moviéndose hacia esa posición, suavemente, sin saltos.

## Próximos pasos (fuera de esta versión)

Una vez confirmado que esta base simple funciona en el hardware real:
1. Reintroducir el parpadeo (sin emociones todavía)
2. Reintroducir las emociones y su sincronía con la mirada
3. Retomar la integración de voz (v3): cablear el sentimiento detectado hacia estas
   emociones, ahora que la base de movimiento es sólida y ya verificada por separado

## Referencias

- [`ojosMecanicos/main.py`](/Users/debbie/Desktop/programacion/ojosMecanicos/main.py) — firmware completo, del que se extrajo este subconjunto
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) — documentación de hardware, canales y protocolo
- [`../v3/pico_serial.py`](../v3/pico_serial.py) — cliente Mac, compatible sin cambios
- [PLAN-v4.md](PLAN-v4.md) — hitos
