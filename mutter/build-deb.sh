#!/bin/bash
# Rebuild Ubuntu's mutter (GNOME's compositor) with surface-kit patches
# (pen dot cursor) as local .debs.
#
# Prereqs (once, as root): deb-src enabled and
#   sudo apt build-dep mutter
#
# Then (as the normal user):  mutter/build-deb.sh
# and install what it prints (only the mutter packages already installed),
# then log out and in. An Ubuntu update to mutter replaces it; re-run.
# Back to Ubuntu's: sudo apt install --reinstall $(the same package names)
set -euo pipefail
SK="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SK")"
WORK="$ROOT/vendor/mutter-pkg"
OUT="$ROOT/vendor/mutter-debs"
SUFFIX="${SUFFIX:-+surfacekit$(date +%Y%m%d%H%M)}"
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT"
cd "$WORK"
apt-get source mutter
SRC=$(find . -maxdepth 1 -type d -name 'mutter-*' | head -1)
cd "$SRC"
for p in "$SK"/patches/*.patch; do
    name=$(basename "$p")
    cp "$p" "debian/patches/surfacekit-$name"
    echo "surfacekit-$name" >> debian/patches/series
    echo ">> added $name"
done
QUILT_PATCHES=debian/patches quilt push -a -q
ver=$(dpkg-parsechangelog -S Version)
DEBFULLNAME="surface-kit" DEBEMAIL="surface-kit@localhost" \
    dch -b -v "${ver}${SUFFIX}" "Surface Pro 7: $(ls "$SK"/patches | tr '\n' ' ')"
DEB_BUILD_OPTIONS="nocheck parallel=$(nproc)" dpkg-buildpackage -b -uc -us
mv ../*.deb "$OUT/" 2>/dev/null || true
mv ../*.ddeb "$OUT/" 2>/dev/null || true
echo ">> built:"
ls -1 "$OUT"
# install only what is installed now, at the new version
debs=()
for d in "$OUT"/*.deb; do
    pkg=$(dpkg-deb -f "$d" Package)
    dpkg-query -W -f '${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed' && debs+=("$d")
done
echo ">> install with (then log out and in):"
echo "   sudo apt install ${debs[*]}"
