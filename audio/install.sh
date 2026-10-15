#!/bin/bash
# Install the audio fixes for the current user (no root): PipeWire mixer
# path overrides in ~/.config/alsa-card-profile, then restart WirePlumber
# so the card is set up again with them.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p ~/.config/alsa-card-profile/mixer/paths
install -m 0644 "$HERE"/alsa-card-profile/mixer/paths/*.conf ~/.config/alsa-card-profile/mixer/paths/
systemctl --user restart wireplumber
sleep 2
amixer -c0 sget 'Internal Mic Boost' | grep 'Front Left:'
amixer -c0 sget Capture | grep 'Front Left:'
