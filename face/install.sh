#!/bin/bash
# Install Howdy for the Surface Pro 7 IR camera. Run once with sudo. This puts
# the files in root-owned places and nothing else: PAM is left alone, so neither
# login nor sudo changes. pam-sudo.sh does that step.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
: "${SUDO_USER:?run with sudo}"

HERE=$(dirname "$(realpath "$0")")
VENDOR=$HERE/../vendor
VENV=/usr/local/lib/surface-kit/howdy-venv
MODELS=/usr/local/share/dlib-data
as_user() { sudo -u "$SUDO_USER" "$@"; }

# Login code runs as root, so its Python can't live anywhere a user can write
mkdir -p "$(dirname "$VENV")"
[ -x "$VENV/bin/python" ] || python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/python" -m pip install --quiet --no-index --no-deps "$VENDOR"/wheels/dlib-*.whl

as_user rm -rf "$VENDOR/howdy-build"
as_user meson setup "$VENDOR/howdy-build" "$VENDOR/howdy-src" --prefix=/usr/local \
    -Dpython_path="$VENV/bin/python" -Dconfig_dir=/etc/howdy \
    -Ddlib_data_dir="$MODELS" -Dpam_dir=/usr/lib/x86_64-linux-gnu/security
as_user meson compile -C "$VENDOR/howdy-build"
meson install -C "$VENDOR/howdy-build"

install -d "$MODELS"
install -m644 "$VENDOR"/howdy-models/*.dat "$MODELS/"

CONFIG=/etc/howdy/config.ini
set_option() { sed -i "s|^$1 = .*|$1 = $2|" "$CONFIG"; }
set_option device_path /dev/media0
set_option recording_plugin surface_ir
# The room behind the face is mostly dark under the emitter alone
set_option dark_threshold 90
chmod 644 "$CONFIG"

echo "Installed. PAM is unchanged. Next: sudo howdy add"
