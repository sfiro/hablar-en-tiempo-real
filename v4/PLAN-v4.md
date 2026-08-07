# Plan de desarrollo — v4.0.0 Firmware simplificado de la Pico

---

## Hito 1: `main.py` mínimo ✅ (código completo, sin validar en hardware)

**Objetivo:** el firmware más simple que aún es útil: ojos abiertos + rastreo x,y.

- [x] Extraer de `ojosMecanicos/main.py` solo: driver PCA9685, canales LR/UD,
      posiciones de párpados abiertos, suavizado EMA, lectura serial
- [x] Quitar joystick, modo autónomo, emociones, parpadeo, sincronía mirada-párpados
      y mirada-cuello (documentado explícitamente en README-v4.md, con el porqué de
      cada uno)
- [x] Mantener compatibilidad de protocolo con v3: acepta `"LR,UD,EMOCION\n"`
      ignorando el tercer campo, así `v3/pico_serial.py` no necesita cambios
- [x] Verificado sin hardware: sintaxis (`py_compile`, AST), fórmula de pulso PCA9685
      (0°→102, 90°→307, 180°→512, igual que el original), parseo de comandos
      (acepta ambos formatos, recorta rango 40-140, rechaza basura sin lanzar)
- [ ] **Validar en la Pico real** — no se puede hacer desde este entorno, no hay
      hardware conectado. Necesita: confirmar que el PCA9685 responde por I2C,
      que los párpados se ven "abiertos" de verdad, y que el movimiento se siente
      tan fluido como en `ojosMecanicos/main.py`

**Bloqueante para cerrar este hito:** la validación con hardware real, que solo
puede hacer quien tenga la Pico físicamente delante.

---

## Hito 2: Validación con hardware 📋 (siguiente, necesita al usuario)

- [ ] Copiar `v4/main.py` a la Pico (Thonny o `mpremote`, ver README-v4.md)
- [ ] Confirmar visualmente: los 4 párpados quedan abiertos al arrancar y no se
      mueven después
- [ ] Enviar comandos `LR,UD` desde `v3/pico_serial.py` o un monitor serial manual,
      confirmar que los ojos se mueven hacia la posición indicada, con suavizado
- [ ] Probar los límites: `40,40` y `140,140` (las esquinas), confirmar que no hay
      sonidos de servo forzado ni el rig se traba
- [ ] Dejarlo corriendo unos minutos: confirmar que no hay reinicios inesperados ni
      errores de I2C acumulándose en la consola serial

## Hito 3: Reintroducir complejidad, por partes 📋 (después de validar Hito 2)

Una vez confirmada la base, añadir de vuelta lo quitado, un paso a la vez, en vez de
volver de golpe a la versión completa de `ojosMecanicos/main.py`:

1. Parpadeo (sin emociones)
2. Emociones + su sincronía con la mirada
3. Retomar v3: cablear el sentimiento de la conversación hacia las emociones de la
   Pico, ahora que el movimiento base ya está confirmado por separado

---

## Definición de listo

v4.0.0 está lista cuando:

1. [x] Firmware simplificado escrito, con la simplificación documentada y justificada
2. [x] Verificado todo lo que no requiere hardware (sintaxis, matemática, protocolo)
3. [ ] Validado en la Pico real: párpados abiertos, rastreo x,y funcionando, sin
   errores tras varios minutos de uso

---

**Última actualización:** Agosto 7, 2026
**Estado actual:** Hito 1 completo salvo la validación con hardware, que depende
enteramente de que el usuario lo pruebe con la Pico física.
