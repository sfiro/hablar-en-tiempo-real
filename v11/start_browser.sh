#!/usr/bin/env bash
# start_browser.sh — Vía navegador del voice chat v11 (Firefox + auto-conexión)
#
# Validado en hardware real (Raspberry Pi 5, 22/08/2026): conversación fluida
# e interrupción por voz funcionando. Ver README-v11.md, sección "Validado en
# hardware real (vía navegador)", para el detalle de cada fix.
#
# Único añadido sobre la versión validada tal cual: el paso [0], que copia el
# perfil de Firefox desde el repo si no existe todavía en /tmp — así el script
# se autorrepara si /tmp se limpia entre reinicios, sin depender de que
# alguien haya corrido el paso de instalación manual primero.
#
# Uso: /home/pi/v11/start_browser.sh
set -u
V11=/home/pi/v11
PROFILE=/tmp/ff-v11-profile
URL="http://127.0.0.1:8000/?auto=1"

echo "▶️  [0/3] Perfil de Firefox..."
if [ ! -f "$PROFILE/user.js" ]; then
  mkdir -p "$PROFILE"
  cp "$V11/firefox-profile/user.js" "$PROFILE/user.js"
  echo "   creado en $PROFILE (no existía)"
fi

echo "▶️  [1/3] Servidor WebRTC..."
if ! ss -tln 2>/dev/null | grep -q ":8000 "; then
  cd "$V11" && setsid nohup .venv/bin/python webrtc_server.py --no-browser --verbose \
    > /tmp/v11_webrtc.log 2>&1 < /dev/null &
  sleep 2
fi
curl -s -o /dev/null -w "   server HTTP: %{http_code}\n" http://127.0.0.1:8000/

echo "▶️  [2/3] Firefox kiosk (auto-conectar)..."
pkill -9 -x firefox 2>/dev/null
sleep 1
DISPLAY=:0 setsid nohup firefox --profile "$PROFILE" --kiosk \
  --remote-debugging-port 9222 --remote-allow-origins=* \
  "$URL" > /tmp/v11_firefox.log 2>&1 < /dev/null &

echo "▶️  [3/3] Esperando conexión WebRTC (hasta 40s)..."
for i in $(seq 1 20); do
  sleep 2
  if tail -60 /tmp/v11_webrtc.log 2>/dev/null | grep -q "msg=ICE%3A%20connected"; then
    echo "✅ CONECTADO — habla al asistente (voz marin). Log: tail -f /tmp/v11_webrtc.log"
    exit 0
  fi
  if tail -40 /tmp/v11_firefox.log 2>/dev/null | grep -qiE "crash|fatal"; then
    echo "⚠️  Firefox reportó un error. Revisa: cat /tmp/v11_firefox.log"
    exit 1
  fi
done
echo "⚠️  Sin confirmación de ICE aún (puede tardar). Revisa: grep msg=ICE /tmp/v11_webrtc.log"
exit 1
