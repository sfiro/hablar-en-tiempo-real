# Versión 7.0 — Seguimiento visual real + secuencia de expresiones 👁️

**Objetivo:** juntar, por primera vez, las dos piezas que hasta ahora se habían
probado por separado: la secuencia fija de expresiones faciales de v6 (cambian
solas cada 5 segundos) y el rastreo facial real de una persona por cámara
(`face_tracker.py`, en el Mac, enviando `LR,UD` por serial a la Pico).

**No hay cambios de lógica respecto a v6.** El mecanismo que hace posible esto
ya existía en `main.py` desde que se añadió la secuencia de expresiones: cada
expresión, o bien deja que `LR`/`UD` sigan lo que llegue por serial (rastreo
real), o bien los fija/mueve por su cuenta, según cómo fue construida. v7 no
inventa un mecanismo nuevo — hace explícito, prueba y documenta como
**objetivo central de la versión** algo que en v6 era un detalle interno de
implementación.

**Estado: completa y validada en hardware real.** Confirmado por el usuario,
con cámara y Pico funcionando a la vez, secuencia de expresiones activa: "funcionó
perfecto". Los mismos 49 tests heredados de v6 (misma matemática, sin cambios)
siguen pasando.

**Totalmente autónoma:** no depende de ningún fichero de v1-v6. Copias propias
de `main.py`, `face_tracker.py`, `pico_serial.py`, `diagnostico_canal.py`,
`estado_base.py` (todos de v6, sin cambios de lógica), con su propio `.venv/`
y tests.

---

## Qué expresiones siguen el rostro y cuáles no

Esta es la pregunta que responde v7. La secuencia sigue siendo la misma de v6,
en el mismo orden fijo cada 5 segundos:

```
NEUTRAL → FELIZ → ENOJADO → TRISTE → SORPRENDIDO → DORMIDO → DUDA → SOSPECHA → PENSATIVO → NERVIOSO → (vuelve a NEUTRAL)
```

**Siguen el rostro real (7 de 10):** `NEUTRAL`, `FELIZ`, `ENOJADO`, `TRISTE`,
`SORPRENDIDO`, `DORMIDO`, `SOSPECHA`. Para estas, `LR`/`UD` se quedan con lo
último que haya llegado por el comando serial `"LR,UD"` — es decir, con la
posición real del rostro detectado por `face_tracker.py`. El offset de cada
emoción (párpados, y el `TILT` del cuello salvo en TRISTE) se aplica **encima**
de esa mirada real, no en lugar de ella. Por ejemplo: con `FELIZ` activo y una
persona moviéndose frente a la cámara, los ojos la siguen igual que en
`NEUTRAL`, pero con el párpado inferior más elevado.

**Ignoran el rostro real, a propósito (3 de 10):** `DUDA`, `PENSATIVO`,
`NERVIOSO`. Así fueron construidas desde que se implementó cada una en v6 (ver
`v6/README-v6.md`, puntos 6, 7 y 9 de "Ajustes de realismo") — no es una
limitación de v7, es la expresión misma: `DUDA` barre la mirada de un lado a
otro como gesto de "pensando", `PENSATIVO` la fija arriba a la izquierda, y
`NERVIOSO` la hace saltar al azar como si evitara el contacto visual. Estos
tres gestos dejarían de tener sentido si seguyeran el rostro real en vez de
hacer su propio movimiento. Al terminar cualquiera de las tres, la mirada
vuelve al centro (90/90) y la siguiente expresión retoma el rastreo real desde
ahí con normalidad.

**Mecanismo exacto (en `main.py`):**

```
if lector_serial.poll(0):
    procesar_comando(linea)              # LR/UD ← lo que diga la cámara

actualizar_objetivo_mirada_expresion()   # solo DUDA/PENSATIVO/NERVIOSO
                                          # sobreescriben LR/UD aquí; el resto
                                          # no toca nada y el rastreo queda
actualizar_objetivo_cuello()             # PAN/TILT siguen a LR/UD (el real
                                          # o el fijado, según la expresión)
actualizar_objetivo_expresion()          # offsets de párpados/TILT, encima
```

## Cómo probarlo

Hacen falta dos procesos a la vez: el firmware en la Pico, y el rastreo en el
Mac.

**1. Firmware (Pico):** despliega `main.py` como en v6 — Thonny,
`Archivo → Guardar como → Raspberry Pi Pico`, nómbralo `main.py`, y reinicia la
placa físicamente (no uses el botón ▶ Run, ver la lección de v5).

**2. Rastreo (Mac):**
```bash
cd v7
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python face_tracker.py            # detecta la Pico sola y le envía LR,UD
```
Por defecto intenta conectar con la Pico automáticamente
(`encontrar_puerto_mac()`); usa `--no-pico` para probar solo la detección de
rostro sin enviar nada, o `--no-window` para correr sin abrir la ventana de
vídeo.

**Qué observar:** durante `NEUTRAL/FELIZ/ENOJADO/TRISTE/SORPRENDIDO/DORMIDO/
SOSPECHA`, los ojos deberían seguir a la persona frente a la cámara, con el
gesto de cada emoción encima. Durante `DUDA/PENSATIVO/NERVIOSO`, los ojos
deberían dejar de seguir a la persona y hacer su propio movimiento, sin
importar dónde esté.

## Cómo se verificó

**Sin hardware:**
- Sintaxis de los 5 ficheros `.py` (`py_compile`)
- 49 tests heredados de v6 sin cambios (`tests/`), corriendo dentro del
  `.venv` propio de v7 — mismas fórmulas, mismos resultados, ninguno depende
  de si hay rastreo real o no (eso solo se puede probar con hardware)

**Con cámara y Pico reales, por el usuario — confirmado, no solo esperado:**
- Las 7 expresiones "de rastreo" siguen a una persona real moviéndose frente
  a la cámara, con el offset de cada emoción visible encima
- Las 3 expresiones "de mirada fija" (DUDA, PENSATIVO, NERVIOSO) ignoran a la
  persona sin verse interrumpidas por el rastreo llegando por serial mientras
  están activas
- La transición es limpia al pasar de una expresión de mirada fija a una de
  rastreo
- El latido/reconexión de `PicoLink` (heredado sin cambios desde v3) sigue
  funcionando bien con el firmware de v7 corriendo la secuencia de expresiones
  al mismo tiempo

## Base heredada de v6 (sin cambios de lógica)

- **`main.py`** — mismo firmware de v6: rastreo de ojos + cuello + parpadeo +
  secuencia de expresiones. Ver [`v6/README-v6.md`](../v6/README-v6.md) para
  el detalle completo de cada expresión y sus ajustes de realismo, y
  [`../v5/README-v5.md`](../v5/README-v5.md) para por qué usa PWM directo en
  vez de PCA9685.
- **`face_tracker.py`** — rastreo facial por cámara (Mac), sin cambios desde
  v3. Incluye ya, desde entonces, el envío por serial a una Pico real cuando
  se detecta una (`PicoLink`) — v7 es la primera vez que esto se documenta y
  prueba junto con la secuencia de expresiones activa.
- **`pico_serial.py`** — enlace serial hacia la Pico, sin cambios desde v3.
- **`estado_base.py`**, **`diagnostico_canal.py`** — sin cambios desde v6.

Mapeo de pines (igual en `main.py` y en `estado_base.py`):

```
LR=GP2   UD=GP3   TL=GP4   BL=GP5   TR=GP6   BR=GP7   PAN=GP8   TILT=GP9
```

## Próximos pasos (fuera de esta versión)

1. Sincronía de párpados con la mirada (mencionada como pendiente desde v6)
2. Reintroducir joystick y/o modo autónomo, si hacen falta
3. Retomar la integración de voz: que el sentimiento detectado elija la
   expresión, en vez de un temporizador fijo cada 5 segundos

## Referencias

- [`../v6/README-v6.md`](../v6/README-v6.md) — detalle completo de cada
  expresión, sus offsets, y los ajustes de realismo validados en v6
- [`../v5/README-v5.md`](../v5/README-v5.md) — historial completo de por qué
  el firmware usa PWM directo en vez de PCA9685
- [`ojosMecanicos/model.md`](/Users/debbie/Desktop/programacion/ojosMecanicos/model.md) — documentación de hardware
- [PLAN-v7.md](PLAN-v7.md) — hitos
