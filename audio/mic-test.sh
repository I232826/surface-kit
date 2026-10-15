#!/bin/bash
# Records the internal mic at each preamp step (Internal Mic Boost 0-3,
# +0/+10/+20/+30 dB) with the capture gain at 0 dB, 5 s each, while you
# talk at normal distance. Then puts the mixer back. Results in
# ~/surface-kit/audio/test/boost<N>.wav for audio/mic-levels.py.
set -euo pipefail
OUT="$(dirname "$0")/test"
mkdir -p "$OUT"
save=$(amixer -c0 sget 'Internal Mic Boost' | grep -o 'Left: [0-3]' | grep -o '[0-3]')
savecap=$(amixer -c0 sget Capture | grep -o 'Left: Capture [0-9]*' | grep -o '[0-9]*$')
echo "Start talking now (read something aloud, normal voice), keep going ~25 s..."
sleep 2
for b in 0 1 2 3; do
    amixer -q -c0 sset 'Internal Mic Boost' "$b"
    amixer -q -c0 sset Capture 0dB
    echo "  boost $b"
    timeout 5 pw-record --channels 2 --format s16 --rate 48000 "$OUT/boost$b.wav" || true
done
amixer -q -c0 sset 'Internal Mic Boost' "$save"
amixer -q -c0 sset Capture "$savecap"
echo "Done, you can stop."
