#!/bin/bash
# Build the out-of-tree IPU4P (Surface Pro 7) camera modules against the
# running kernel's *stock* headers. Output: camera/out/<kver>/*.ko
#
# Inputs (see camera/README.md for where they come from):
#   vendor/linux-6.19.8/drivers/media/   sp7-ipu4-camera overlaid on 6.19.8
#   camera/compat/include/               the 4 new IPU headers from
#                                        ruslanbay/ipu4-drivers 0001+0012+0015
#   camera/compat/ipu-abi-compat.h       additive uapi #defines (ours)
#   camera/patches/*.patch               our fixes on top of the vendor tree
#
# Only the ipu4 stack and the patched ov5693 are built; ipu-bridge is
# identical to upstream, so the stock module is used.
set -euo pipefail

KVER="${KVER:-$(uname -r)}"
KDIR="/lib/modules/$KVER/build"
CAM="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$CAM")"
KSRC="$ROOT/vendor/linux-6.19.8/drivers"
VENDOR="$KSRC/media"
BUILD="$CAM/.build"
OUT="$CAM/out/$KVER"
JOBS="$(nproc)"

for f in media/ipu-isys.h uapi/linux/ipu-isys.h uapi/linux/ipu-psys.h \
         uapi/linux/ipu-isys-isa-fw.h; do
    [ -f "$CAM/compat/include/$f" ] || { echo "missing compat/include/$f" >&2; exit 1; }
done

# Fresh copy of the vendor driver with our patches applied.
rm -rf "$BUILD"
mkdir -p "$BUILD"
cp -r "$VENDOR/pci/intel" "$BUILD/intel"
# DEBUG=1 adds the breadcrumb patches in patches/debug/ (load-time freeze
# hunting), applied in numeric order among the others.
PATCHES=("$CAM"/patches/[0-9]*.patch)
[ -n "${DEBUG:-}" ] && PATCHES+=("$CAM"/patches/debug/[0-9]*.patch)
for p in $(printf '%s\n' "${PATCHES[@]}" | awk -F/ '{print $NF"\t"$0}' | sort | cut -f2); do
    echo ">> applying $(basename "$p")"
    patch -d "$BUILD/intel" -p1 --forward --quiet < "$p"
done

# The ipu4 Kconfig symbols don't exist in the distro config: set them for
# make (Makefile ifdefs) and as -D (C #ifdefs). Blank out the sibling
# drivers that intel/Makefile would otherwise rebuild from auto.conf.
IPU_VARS=(
    CONFIG_VIDEO_INTEL_IPU=m
    CONFIG_VIDEO_INTEL_IPU4P=y
    CONFIG_VIDEO_INTEL_IPU_FW_LIB=y
    CONFIG_VIDEO_INTEL_IPU6=
    CONFIG_IPU_BRIDGE=
    CONFIG_VIDEO_IPU3_CIO2=
    CONFIG_INTEL_VSC=
)
IPU_KCFLAGS="-DCONFIG_VIDEO_INTEL_IPU4P=1 -DCONFIG_VIDEO_INTEL_IPU_FW_LIB=1"
IPU_KCFLAGS+=" -DCONFIG_VIDEO_INTEL_IPU_MODULE=1"
IPU_KCFLAGS+=" -I$CAM/compat/include -include $CAM/compat/ipu-abi-compat.h"

echo ">> ipu4p stack ($KVER)"
make -C "$KDIR" M="$BUILD/intel" srcpath="$BUILD/intel" \
    "${IPU_VARS[@]}" KCFLAGS="$IPU_KCFLAGS" \
    KBUILD_MODPOST_WARN=1 -j"$JOBS" modules

# Patched single-file in-tree drivers (sensors, lens, and gpio-keys for the
# power button), each built alone from a scratch Kbuild dir so we don't build
# whole subsystems; paths are under drivers/, patches in patches/<name>/.
SINGLE_MODS=(media/i2c/ov5693 media/i2c/ov8865 media/i2c/dw9719
             input/keyboard/gpio_keys)
for src in "${SINGLE_MODS[@]}"; do
    m="$(basename "$src")"
    echo ">> $m"
    mkdir -p "$BUILD/$m"
    cp "$KSRC/$src.c" "$BUILD/$m/"
    for p in "$CAM"/patches/"$m"/*.patch; do
        [ -e "$p" ] || continue
        echo ">> applying $m/$(basename "$p")"
        patch -d "$BUILD/$m" -p1 --forward --quiet < "$p"
    done
    echo "obj-m += $m.o" > "$BUILD/$m/Kbuild"
    make -C "$KDIR" M="$BUILD/$m" -j"$JOBS" modules
done

rm -rf "$OUT"
mkdir -p "$OUT"
find "$BUILD/intel" -name '*.ko' -exec cp {} "$OUT/" \;
for src in "${SINGLE_MODS[@]}"; do
    m="$(basename "$src")"
    cp "$BUILD/$m/$m.ko" "$OUT/"
done
echo ">> built:"
ls -l "$OUT"
