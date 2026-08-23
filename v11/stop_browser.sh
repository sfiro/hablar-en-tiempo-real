#!/usr/bin/env bash
# stop_browser.sh — Detiene la vía navegador del voice chat v11 (firefox + servidor)
#
# Validado en hardware real (Raspberry Pi 5, 22/08/2026), con un añadido: si el
# servidor lo arrancó systemd (ver systemd/v11-webrtc.service), un `kill -9`
# directo no sirve de nada porque `Restart=always` lo vuelve a levantar al
# instante — este script para el servicio con `systemctl` cuando existe, y
# solo cae al kill manual si no hay systemd de por medio (por ejemplo, si el
# servidor se arrancó a mano con start_browser.sh).
set -u
echo "⏹  Deteniendo Firefox..."
pkill -9 -x firefox 2>/dev/null

if systemctl is-active --quiet v11-webrtc.service 2>/dev/null; then
  echo "⏹  Deteniendo servicio systemd v11-webrtc..."
  sudo systemctl stop v11-webrtc.service
else
  PID=$(ss -tlnp 2>/dev/null | grep ":8000 " | grep -oP 'pid=\K[0-9]+' | head -1)
  if [ -n "${PID:-}" ]; then
    echo "⏹  Deteniendo servidor WebRTC (pid $PID)..."
    kill -9 "$PID" 2>/dev/null
  fi
fi

sleep 1
if pgrep -x firefox >/dev/null || ss -tln 2>/dev/null | grep -q ":8000 "; then
  echo "⚠️  Algo sigue corriendo. Revisa: pgrep -af firefox; ss -tlnp | grep :8000"
  exit 1
fi
echo "✅ Todo detenido."
