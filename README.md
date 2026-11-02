# surface-kit

Fixes and small apps that make Ubuntu good on a Surface Pro 7: working cameras,
face login, auto-rotation, a document scanner, a usable mic, better touch and
pen input, and a few touch-friendly apps.

Built for and tested on one machine: Surface Pro 7 (i5-1035G4), Ubuntu 26.04,
GNOME 50 on Wayland, kernel `6.19.8-surface-3` from
[linux-surface](https://github.com/linux-surface/linux-surface), and a 7.4-rc1
kernel built from `kernel/`, which face login needs. It is not a one-click
installer, and other models and kernels will need work. It replaces kernel
modules and system packages, so read the README in each folder first.

## What's here

| Folder | What it does | State |
|---|---|---|
| [`camera/`](camera/README.md) | Kernel modules for the Intel IPU4P camera hardware on 6.19, sensor and lens fixes | Rear and front cameras lock reliably. No infrared camera on this driver |
| [`kernel/`](kernel/build.sh) | Builds 7.4-rc1 with the upstream IPU4P patches and our fixes | Rear, front and infrared cameras, rotation and suspend work |
| [`face/`](face/install.sh) | Face login with [Howdy](https://github.com/boltgolt/howdy) through the infrared camera and its light | Works for sudo, the login screen and the lock screen, on the 7.4 kernel |
| [`libcamera/`](camera/README.md) | libcamera rebuilt with autofocus, exposure, white balance, colour matrices, shading and denoise | Works |
| [`snapshot/`](snapshot/README.md) | GNOME Camera with a document mode: page outline, crop, clean-up, multi-page PDF | Works |
| [`sensors/`](sensors/README.md) | Sensor hub driver for auto-rotation, safe across suspend | Works |
| [`rotate/`](rotate/) | Rotation animation (GNOME Shell extension) | Works |
| [`touch/`](touch/README.md) | iptsd tuning, palm rejection while writing, pen top-button keys | Works |
| [`mutter/`](mutter/README.md) | Mutter with a dot instead of an arrow under the pen | Works |
| [`audio/`](audio/README.md) | Internal mic levels | Mic works. Speakers sometimes go silent, not solved yet |
| [`power/`](camera/README.md) | Power button behaviour around suspend | Works |
| [`system/`](system/install.sh) | Clock fix (the firmware loads a clock over a year behind at boot) | Works |
| [`shell/`](shell/README.md) | GNOME Shell helper: focus-or-start an app, screenshot for Screen Ink. Face unlock animation | Works |
| [`apps/`](apps/) | Recorder, Pen settings, Screen Ink, Face settings | Work |

## Known problems

- Front camera: a thin magenta line along the top edge, a magenta picture at
  exactly 1296x972, and a mild colour shift when a bright lamp is in view.
- Speakers go silent now and then.
- Logging in by face leaves the GNOME keyring locked, because it needs your
  password to open. Apps that use it can ask for the password afterwards.
- Face login is a convenience, not extra security. Howdy's project says the same.
- After a touch on a fullscreen window, GNOME stops sending that window the
  pen. Screen Ink runs maximized because of this.
- If the sensor hub doesn't survive a sleep, the driver gives up on it and
  auto-rotation stays off until the next boot. That beats the alternative,
  which was a frozen machine.

## Installing

Each folder has its own `install.sh` or build script, and its README says what
it changes. Downloaded sources and build output live in `vendor/`, which isn't
in this repo; `camera/README.md` lists where the kernel source, driver and
firmware come from.

Rebuild after a kernel update:

```sh
camera/build.sh
sudo camera/install/install.sh
sudo sensors/install.sh
```

`install-apt-hook.sh` holds the rebuilt packages and runs `check-updates.sh`
after `apt update`, which says when Ubuntu has something newer to rebuild on.

## Windows driver data

`camera/windows/*-ccm.yaml` and the tuning built on them contain colour matrices
read from the calibration files in Microsoft's Surface driver package, for the
sensors in this machine. The Microsoft driver files themselves are not in this
repo.

## Credits

This stands on other people's work, above all
[linux-surface](https://github.com/linux-surface/linux-surface),
[iptsd](https://github.com/linux-surface/iptsd),
[ruslanbay/ipu4-drivers](https://github.com/ruslanbay/ipu4-drivers),
[thisiscamk/sp7-ipu4-camera](https://github.com/thisiscamk/sp7-ipu4-camera),
[libcamera](https://libcamera.org/), [Howdy](https://github.com/boltgolt/howdy),
and GNOME.

The infrared camera runs because of findings shared by loafecho and JValdivia23
in [linux-surface discussion 1353](https://github.com/linux-surface/linux-surface/discussions/1353).

## How this was made

This project was made with AI assistance. I directed the work and tested it on
my Surface Pro 7; most of the code, patches and documentation were written by
Anthropic's Claude, mostly the Opus 5.5 model, through Claude Code. Commits
carry a `Co-Authored-By` line saying so. Expect rough edges, and check anything
you reuse.

## Licence

GPL-3.0-or-later for the project's own code. Patches keep the licence of the
project they change. See [LICENSING.md](LICENSING.md).
