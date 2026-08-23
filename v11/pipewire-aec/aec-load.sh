#!/bin/bash
# Carga la cancelacion de eco (AEC) de PipeWire si no esta cargada.
# VIA pactl (pipewire-pulse) — la unica que funciona en esta build rpt3:
# la ruta pipewire.conf.d (libpipewire-module-echo-cancel) crashea con
# "Error initialising webrtc audio processing module: -9".
#
# Micro USB (C-Media) y altavoz USB (Jieli) = relojes independientes:
# webrtc extended_filter + delay_agnostic compensan la deriva.
set -u

MIC="alsa_input.usb-C-Media_Electronics_Inc._USB_PnP_Sound_Device-00.analog-mono"
SPK="alsa_output.usb-Jieli_Technology_UACDemoV1.0_4150353131373114-00.analog-stereo"
AEC_ARGS="webrtc.echo_cancellation=true webrtc.echo_cancellation_level=3 webrtc.extended_filter=true webrtc.delay_agnostic=true webrtc.noise_suppression=true webrtc.noise_suppression_level=3 webrtc.high_pass_filter=true"

if ! pactl list short modules 2>/dev/null | grep -q "module-echo-cancel"; then
    pactl load-module module-echo-cancel \
        source="$MIC" \
        sink="$SPK" \
        aec_method=webrtc \
        "aec_args=$AEC_ARGS"
fi

# Usar los nodos con AEC como predeterminados del sistema
pactl set-default-source echo-cancel-source 2>/dev/null
pactl set-default-sink echo-cancel-sink 2>/dev/null

# Volumen de parlante: el sink fisico Jieli amanece a 40% (-23.8 dB) y se escucha bajo.
# Subir a 90% (el echo-cancel-sink ya queda a 100%).
pactl set-sink-volume "$SPK" 90% 2>/dev/null
pactl set-sink-volume echo-cancel-sink 100% 2>/dev/null
