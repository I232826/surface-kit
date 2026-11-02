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

## Status (2026-10-14)

| Camera | State |
|--------|-------|
| Rear ov8865 (8 MP, autofocus) | **Works.** 3264x1836/1920x1080 at 20 fps in GNOME Camera; autofocus, white balance, colour, denoise. |
| Front ov5693 (5 MP) | **Locks reliably with the shifted data-lane timing** (`patches/0016`, `csi2_shifted_ticks_port`, on by default in `install/surface-kit.conf`), from [ruslanbay/ipu4-drivers](https://github.com/ruslanbay/ipu4-drivers) RFC v2 11/12, reverse-engineered there from the Windows driver. Measured 2026-11-02 through libcamera, alternating in the same boot: 24/24 clean 30-frame starts with no relock bounces, against 4/24 with the usual delay counters. Before this it looked like a failing cable, because the lock rate fell over days and every setting we swept failed; that was wrong. Colour: `patches/ov5693/0005` reports GBRG with `mirror=1` (the flip shifts the Bayer order; check with `scripts/bayer-sites.py`), tuning in `libcamera/patches/0019`. Open: thin magenta line along the top edge, magenta at exactly 1296x972 (SoftISP 2:1 scaling), mild colour shift with a bright lamp in view. |
| IR ov7251 | Never probes on this driver (`skip_fw_ports=6`). Works on the 7.4 kernel: see `kernel/` and `face/`. |

What makes the rear camera good, and where it lives:

- Kernel: IPU4P stack with our fixes (`patches/0001`-`0014`), ov8865
  (`patches/ov8865/`: mode registers on stream start, mirror fix, vblank
  reset, fine gain steps, 20 fps 1836 mode, SCLK pixel rate), dw9719 lens
  (`patches/dw9719/`).
- libcamera 0.7.0 rebuilt as .debs (`libcamera/patches/0001`-`0016`):
  SoftISP fixes, AGC (anti-flicker, proportional, highlight damping),
  sensor delays, contrast autofocus (fine sweep, approach from below,
  wobble tolerance, parked start), grey-locus AWB and colour matrices from
  the Windows calibration, lens shading, denoise pass, tuning files.
- Windows driver data: `scripts/win-regtables.py` (sensor register tables),
  `scripts/aiqb-to-lsc.py` (lens shading tables),
  `scripts/aiqb-dump.py` / `aiqb-to-ccm.py` (Intel AIQB tuning records;
  this SP7 is "Haven": front MSHW0190, rear MSHW0191).

The same build also carries two non-camera kernel fixes:

- `patches/intel-ish-ipc/`: reverts the 6.19 sensor-hub start-up changes
  (upstream 507561b00ac2, 9e097dc9df80). Without it the ISH never finishes
  its handshake ("HBM haven't started") and there is no accelerometer, so
  no auto-rotation (linux-surface#2140). Built here, installed by
  `sensors/install.sh` (see `sensors/README.md`): with it bound during
  suspend the machine eventually hung hard on every sleep.
- `patches/gpio_keys/0002`: ignores power-button presses for
  `resume_ignore_ms` (1500, set in `install/surface-kit.conf`) after resume,
  so the press that woke it or an impatient second press can't put it
  straight back to sleep. `power/` adds the matching user service that turns
  the screen off the moment suspend starts.

Install / update:

```sh
camera/build.sh && sudo camera/install/install.sh      # modules; reboot after
libcamera/build-deb.sh                                  # prints the install
# commands; stop PipeWire while installing the .debs (an old PipeWire that
# loads the new IPA module hangs), then start it again
```

Test tools: `scripts/focus-raw-sweep.py` (raw sharpness per lens position,
ground truth for autofocus), `scripts/awb-eval.py` (white balance methods
against a white-paper reference), `scripts/settle-sweep.sh` (front link
sweeps), `scripts/denoise-proto.py`. Sweeps and raw tests need PipeWire
stopped and GNOME Camera closed.
