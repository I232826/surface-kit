#!/bin/bash
# Face login on the login and lock screens, which share /etc/pam.d/gdm-password,
# and the unlock animation system-wide so the login screen can load it too.
#   sudo face/install-login.sh          install
#   sudo face/install-login.sh --undo   take it off those screens again
# Howdy is "sufficient": anything but a match falls through to the password.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
: "${SUDO_USER:?run with sudo}"

HERE=$(dirname "$(realpath "$0")")
PAM=/etc/pam.d/gdm-password
PAM_LINE="auth sufficient pam_howdy.so"
UUID=surface-face@surface-kit
SYSTEM_EXT=/usr/share/gnome-shell/extensions/$UUID
USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
PROFILE=/etc/dconf/profile/gdm
DCONF=/etc/dconf/db/gdm.d/90-surface-face

if [ "${1:-}" = --undo ]; then
    sed -i "/^$PAM_LINE\$/d" "$PAM"
    # the animation stays: sudo still uses it, and without this entry the login
    # screen doesn't load it
    rm -f "$DCONF"
    dconf update
    echo "Face login removed from the login and lock screens. sudo is unchanged."
    exit 0
fi

[ -e "$PAM.before-howdy" ] || cp -a "$PAM" "$PAM.before-howdy"
grep -qx "$PAM_LINE" "$PAM" ||
    sed -i "0,/^@include common-auth/s//$PAM_LINE\n&/" "$PAM"

rm -rf "$SYSTEM_EXT" "$USER_HOME/.local/share/gnome-shell/extensions/$UUID"
install -d "$SYSTEM_EXT"
install -m644 "$HERE/../shell/$UUID"/* "$SYSTEM_EXT/"

# the login screen runs as the gdm user, with its own enabled extensions
if [ ! -e "$PROFILE" ]; then
    if [ -e /usr/share/dconf/profile/gdm ]; then
        cp /usr/share/dconf/profile/gdm "$PROFILE"
    else
        : > "$PROFILE"
    fi
fi
grep -qx "system-db:gdm" "$PROFILE" || printf 'system-db:gdm\n' >> "$PROFILE"
install -d "$(dirname "$DCONF")"
cat > "$DCONF" <<EOF
[org/gnome/shell]
enabled-extensions=['$UUID']
EOF
dconf update

echo "Installed. Backup of the PAM file: $PAM.before-howdy"
echo "Log out and in to load the animation, then lock the screen to test."
