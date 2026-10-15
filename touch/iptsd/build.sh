#!/bin/bash
# Build iptsd 3.1.0 (the version linux-surface ships for Ubuntu) with the
# patches in this folder; only the daemon. Dependencies come from iptsd's own
# meson wraps (downloaded on first build), so no -dev packages are needed.
# Output: touch/iptsd/out/iptsd; install with: sudo touch/iptsd/install.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VER=3.1.0
WORK="$HERE/.build"
SRC="$WORK/iptsd-$VER"
mkdir -p "$WORK"
if [ ! -d "$SRC" ]; then
    curl -sfL "https://github.com/linux-surface/iptsd/archive/refs/tags/v$VER.tar.gz" | tar xz -C "$WORK"
    for p in "$HERE"/[0-9]*.patch; do
        echo ">> applying $(basename "$p")"
        patch -d "$SRC" -p1 --quiet < "$p"
    done
fi
cd "$SRC"
[ -d build ] || meson setup build --buildtype=release -Ddebug_tools=[] \
    -Dsample_config=false -Daccess_checks=false --wrap-mode=forcefallback
ninja -C build src/iptsd
mkdir -p "$HERE/out"
cp build/src/iptsd "$HERE/out/iptsd"
echo ">> built $HERE/out/iptsd"
