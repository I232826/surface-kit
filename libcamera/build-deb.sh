#!/bin/bash
# Rebuild Ubuntu's libcamera with surface-kit patches as local .debs.
#
# Prereqs (once, as root): deb-src enabled and the build deps installed:
#   sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources
#   sudo apt update && sudo apt build-dep libcamera
#
# Then (as the normal user):  libcamera/build-deb.sh
# and install what it prints: sudo apt install ./vendor/libcamera-debs/*.deb
#
# Keeps Ubuntu's version and soname, so libspa-0.2-libcamera and
# gstreamer1.0-libcamera stay ABI-compatible. An Ubuntu update to libcamera
# will replace these; re-run this script afterwards.
set -euo pipefail

LC="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$LC")"
WORK="$ROOT/vendor/libcamera-src"
OUT="$ROOT/vendor/libcamera-debs"
# unique, increasing per build so apt sees an upgrade over the last one
SUFFIX="${SUFFIX:-+surfacekit$(date +%Y%m%d%H%M)}"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT"
cd "$WORK"
apt-get source libcamera
SRC=$(find . -maxdepth 1 -type d -name 'libcamera-*' | head -1)
cd "$SRC"

for p in "$LC"/patches/*.patch; do
    name=$(basename "$p")
    cp "$p" "debian/patches/surfacekit-$name"
    echo "surfacekit-$name" >> debian/patches/series
    echo ">> added $name"
done
# apply now so a stale or conflicting patch fails here, not mid-build
QUILT_PATCHES=debian/patches quilt push -a -q

ver=$(dpkg-parsechangelog -S Version)
DEBFULLNAME="surface-kit" DEBEMAIL="surface-kit@localhost" \
    dch -b -v "${ver}${SUFFIX}" "Surface Pro 7: $(ls "$LC"/patches | tr '\n' ' ')"

# full speed by default (user prefers a fast build over a smooth desktop);
# LOWPRIO=1 builds at lowest priority on half the cores instead
if [ -n "${LOWPRIO:-}" ]; then
    DEB_BUILD_OPTIONS="nocheck parallel=$(( $(nproc) / 2 ))" nice -n 19 ionice -c3 dpkg-buildpackage -b -uc -us
else
    DEB_BUILD_OPTIONS="nocheck parallel=$(nproc)" dpkg-buildpackage -b -uc -us
fi
mv ../*.deb "$OUT/"
echo ">> built:"
ls -1 "$OUT"
echo ">> install the ones you have now:"
echo "   sudo apt install $(cd "$OUT" && for d in *.deb; do pkg=${d%%_*}; dpkg -s "$pkg" >/dev/null 2>&1 && printf '%s ' "$OUT/$d"; done)"
