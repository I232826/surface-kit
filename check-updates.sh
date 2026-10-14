#!/bin/bash
# Are the surface-kit builds of Ubuntu packages still installed, and does
# Ubuntu have a newer version to rebuild on? They are held (see
# install-apt-hook.sh), so Ubuntu updates don't replace them silently;
# this tells when it's time to rebuild instead. Runs after `apt update`.
#
#   ./check-updates.sh            report every package
#   ./check-updates.sh --quiet    print only what needs attention
QUIET=${1:-}
SK="$(cd "$(dirname "$0")" && pwd)"
declare -A BUILD=(
    [libcamera0.7]=libcamera/build-deb.sh
    [libcamera-ipa]=libcamera/build-deb.sh
    [libcamera-tools]=libcamera/build-deb.sh
    [libcamera-v4l2]=libcamera/build-deb.sh
    [gstreamer1.0-libcamera]=libcamera/build-deb.sh
    [gnome-snapshot]=snapshot/build-deb.sh
)
attention=0
for pkg in "${!BUILD[@]}"; do
    installed=$(dpkg-query -W -f='${Version}' "$pkg" 2>/dev/null) || continue
    # the newest version apt knows of that isn't ours
    ubuntu=$(apt-cache madison "$pkg" 2>/dev/null | awk -F'|' '{gsub(/ /,"",$2); print $2}' |
             grep -v surfacekit | sort -V | tail -1)
    base=${installed%%+surfacekit*}
    if [[ $installed != *surfacekit* ]]; then
        echo "surface-kit: $pkg $installed is Ubuntu's, not ours: rebuild with ${BUILD[$pkg]}"
        attention=1
    elif [[ -n $ubuntu ]] && dpkg --compare-versions "$ubuntu" gt "$base"; then
        echo "surface-kit: Ubuntu has $pkg $ubuntu (ours is on $base): rebuild with ${BUILD[$pkg]}"
        attention=1
    elif [[ -z $QUIET ]]; then
        echo "surface-kit: $pkg $installed ok"
    fi
done
[[ $attention == 1 ]] &&
    echo "surface-kit: after rebuilding: sudo apt-mark unhold <pkgs>, install the .debs, hold again (see $SK/install-apt-hook.sh)"
exit 0
