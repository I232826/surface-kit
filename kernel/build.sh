#!/bin/bash
# Surface Pro 7 kernel: mainline with linux-surface's patches, the IPU4P camera
# series and our sensor, power button and sensor hub fixes, as .debs.
#   kernel/build.sh prepare          patched tree only
#   kernel/build.sh build CONFIG     prepare, configure from CONFIG, build
# Needs: git flex bison bc pahole libssl-dev libelf-dev libdw-dev dwarves debhelper rsync
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
WORK="${WORK:-$ROOT/vendor/kernel-plan}"
KERNEL_TAG=v7.4-rc1
SURFACE_REV=668a020    # linux-surface, patches/7.3
RFC_REV=f0b3dfa        # ruslanbay/ipu4-drivers, RFC v2
CAM="$ROOT/camera/patches"
# not needed on the Surface Pro 7: 0001 secureboot, 0003 mwifiex (Intel wifi)
SURFACE_PATCHES="0002 0004 0005 0006 0007 0008 0009 0010 0011 0012 0013 0014 0015"
# hunks for other models, and the iommu.c defines kernel/patches/0001 replaces
EXPECTED_REJECTS="drivers/iommu/intel/iommu.c
drivers/media/i2c/ov5693.c
drivers/media/pci/intel/ipu-bridge.c
drivers/platform/x86/intel/int3472/discrete.c
drivers/platform/x86/intel/int3472/tps68470.c"

fetch() {  # url dir rev
    [ -d "$WORK/$2/.git" ] || git clone -q "$1" "$WORK/$2"
    git -C "$WORK/$2" cat-file -e "$3^{commit}" 2>/dev/null || git -C "$WORK/$2" fetch -q --tags --unshallow origin || git -C "$WORK/$2" fetch -q origin
    git -C "$WORK/$2" checkout -q "$3"
}

prepare() {
    mkdir -p "$WORK"
    [ -d "$WORK/linux/.git" ] || git clone -q --depth=1 -b "$KERNEL_TAG" https://github.com/torvalds/linux.git "$WORK/linux"
    fetch https://github.com/linux-surface/linux-surface.git linux-surface "$SURFACE_REV"
    fetch https://github.com/ruslanbay/ipu4-drivers.git ipu4-drivers "$RFC_REV"
    cd "$WORK/linux"
    git reset -q --hard "$KERNEL_TAG"
    git clean -qfdx -e .config
    for n in $SURFACE_PATCHES; do
        echo ">> linux-surface $n"
        git apply --reject "$WORK"/linux-surface/patches/7.3/"$n"-*.patch 2>/dev/null || true
    done
    got=$(find . -name "*.rej" | sed -e "s|^\./||" -e "s|\.rej$||" | LC_ALL=C sort)
    [ "$got" = "$EXPECTED_REJECTS" ] || { echo "unexpected rejects:"; echo "$got"; exit 1; }
    find . -name '*.rej' -delete
    git apply "$HERE/patches/0001-iommu-surface-defines.patch"
    for p in "$WORK"/ipu4-drivers/patches/v2-00*.patch; do
        case "$p" in *cover-letter*) continue ;; esac
        echo ">> $(basename "$p")"
        git apply "$p"
    done
    apply_to drivers/media/i2c "$CAM"/ov8865/000[2-6]*.patch "$CAM"/dw9719/000[23]*.patch "$CAM"/ov5693/0001*.patch
    git apply "$HERE/patches/0002-ov5693-report-bayer-order-with-mirror.patch"
    git apply "$HERE/patches/0003-ov5693-full-resolution-only.patch"
    git apply "$HERE/patches/0004-ov7251-link-freq-index.patch"
    git apply "$HERE/patches/0005-ipu4p-surface-pro-7-ir-camera.patch"
    git apply "$HERE/patches/0006-ov7251-strobe-for-ir-emitter.patch"
    apply_to drivers/input/keyboard "$CAM"/gpio_keys/*.patch
    apply_to drivers/hid/intel-ish-hid "$CAM"/intel-ish-ipc/*.patch
    echo ">> tree ready: $WORK/linux"
}

apply_to() {
    local dir=$1; shift
    for p in "$@"; do
        echo ">> $(basename "$p")"
        patch -d "$dir" -p1 --forward --quiet --no-backup-if-mismatch < "$p"
    done
}

configure() {
    cd "$WORK/linux"
    cp "$1" .config
    ./scripts/config --set-str LOCALVERSION "-surfacekit" \
        --disable LOCALVERSION_AUTO \
        --disable MODULE_SIG --disable MODULE_SIG_ALL --set-str MODULE_SIG_KEY "" \
        --set-str SYSTEM_TRUSTED_KEYS "" --set-str SYSTEM_REVOCATION_KEYS "" \
        --disable DEBUG_INFO_BTF --disable DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT \
        --disable DEBUG_INFO_DWARF4 --disable DEBUG_INFO_DWARF5 --enable DEBUG_INFO_NONE \
        --enable MEDIA_SUPPORT --enable MEDIA_PCI_SUPPORT --enable MEDIA_CAMERA_SUPPORT \
        --module VIDEO_INTEL_IPU6 --enable VIDEO_INTEL_IPU6_IPU7 --module IPU_BRIDGE \
        --module VIDEO_OV5693 --module VIDEO_OV7251 --module VIDEO_OV8865 --module VIDEO_DW9719 \
        --module INTEL_ISH_HID
    make olddefconfig
    for o in VIDEO_INTEL_IPU6 VIDEO_INTEL_IPU6_IPU7 IPU_BRIDGE VIDEO_OV5693 VIDEO_OV8865 VIDEO_DW9719 INTEL_ISH_HID; do
        echo "$o=$(./scripts/config --state $o)"
    done
}

case "${1:-}" in
prepare) prepare ;;
build)
    [ -n "${2:-}" ] || { echo "usage: build.sh build CONFIG" >&2; exit 2; }
    config=$(realpath "$2")
    prepare
    configure "$config"
    cd "$WORK/linux"
    make -j"$(nproc)" bindeb-pkg
    echo ">> packages:"; ls -l "$WORK"/*.deb
    ;;
*) echo "usage: build.sh prepare | build CONFIG" >&2; exit 2 ;;
esac
