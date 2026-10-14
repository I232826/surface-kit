#!/bin/bash
# Rebuild Ubuntu's GNOME Camera (gnome-snapshot) with surface-kit patches
# (document scanning mode) as a local .deb.
#
# Prereqs (once, as root): deb-src enabled (see libcamera/build-deb.sh) and
#   sudo apt build-dep gnome-snapshot
#
# Then (as the normal user):  snapshot/build-deb.sh
# and install what it prints. An Ubuntu update to gnome-snapshot replaces
# it; re-run this script afterwards.
set -euo pipefail
SK="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SK")"
WORK="$ROOT/vendor/snapshot-pkg"
OUT="$ROOT/vendor/snapshot-debs"
SUFFIX="${SUFFIX:-+surfacekit$(date +%Y%m%d%H%M)}"
rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT"
cd "$WORK"
apt-get source gnome-snapshot
SRC=$(find . -maxdepth 1 -type d -name 'gnome-snapshot-*' | head -1)
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
mv ../*.deb "$OUT/"
echo ">> built:"
ls -1 "$OUT"
echo ">> install with:"
echo "   sudo apt install $(ls "$OUT"/gnome-snapshot_*.deb)"
