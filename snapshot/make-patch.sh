#!/bin/bash
# Regenerate patches/0001-document-scan-mode.patch from the working tree
# vendor/snapshot-src/gnome-snapshot-50.0 against the pristine copies in
# vendor/snapshot-src/orig (changed files) or nothing (new files). The
# description at the top of the existing patch is kept.
set -euo pipefail
SK="$(cd "$(dirname "$0")" && pwd)"
SRC="$SK/../vendor/snapshot-src"
PATCH="$SK/patches/0001-document-scan-mode.patch"
NEW=(src/document.rs src/scan_adjust.rs aperture/src/frame_sampler.rs
     data/resources/icons/camera-autofocus-symbolic.svg)

out=$(mktemp)
sed -n '1,/^---$/p' "$PATCH" > "$out"
cd "$SRC"
for f in $(cd orig && find . -type f | sed 's#^\./##' | sort); do
    diff -u --label "a/$f" --label "b/$f" "orig/$f" "gnome-snapshot-50.0/$f" >> "$out" || true
done
for f in "${NEW[@]}"; do
    diff -u --label /dev/null --label "b/$f" /dev/null "gnome-snapshot-50.0/$f" >> "$out" || true
done
mv "$out" "$PATCH"
echo ">> $(grep -c '^+++ ' "$PATCH") files in $PATCH"
