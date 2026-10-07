# Surface Pro 7 cameras (Intel IPU4P)

The SP7's Ice Lake ISP (`8086:8a19`) has no upstream driver. This builds the
out-of-tree IPU4P port as modules for the running Ubuntu linux-surface kernel.

## Sources

| What | From | Where |
|------|------|-------|
| Kernel 6.19.8 | cdn.kernel.org (sha256 verified) | `vendor/dl/linux-6.19.8.tar.xz` |
| IPU4P driver + ov5693 fixes | [thisiscamk/sp7-ipu4-camera](https://github.com/thisiscamk/sp7-ipu4-camera) | overlaid on `vendor/linux-6.19.8/drivers/media/` |
| 4 new IPU headers | [ruslanbay/ipu4-drivers](https://github.com/ruslanbay/ipu4-drivers) `patches/kernel/v6.19-ConsultingFuture4200/0001,0012,0015` | `camera/compat/include/` |
| Firmware `ipu4p_cpd.bin` | ruslanbay/ipu4-drivers `firmware/ipu4-20191030.bin` (LFS oid verified, Microsoft-signed) | `vendor/dl/` |

## Our changes

- `compat/ipu-abi-compat.h`: additive uapi `#define`s the port expects.
- `patches/0001-ipu4-build-against-stock-v4l2-headers.patch`: the port
  depends on Intel's edits to core v4l2 structs. As a module for a stock
  kernel that's an ABI break: `.get_routing` inserted into
  `v4l2_subdev_pad_ops` shifts `.set_routing`/`.enable_streams`, so the core
  calls the wrong function (e.g. `VIDIOC_SUBDEV_S_ROUTING` lands in
  `get_routing` with `set_routing`'s arguments). The patch builds against
  stock headers instead. Upstream candidate.

## Build

```sh
camera/build.sh        # -> camera/out/$(uname -r)/*.ko
```

Needs `build-essential` and `linux-headers-$(uname -r)`. The kernel was built
with gcc 11, we build with gcc 15 (kbuild warns; expected).
