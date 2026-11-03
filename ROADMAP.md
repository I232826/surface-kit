# Roadmap

## Face login

- [x] IR camera delivers frames on the 7.4 kernel (`kernel/patches/0005`)
- [x] IR emitter runs from the sensor's strobe output (`kernel/patches/0006`)
- [x] Howdy reads the camera (`face/`)
- [x] Face match unlocks `sudo` in a local terminal, password still works
- [x] Draft the unlock animation. Approved look, "Strobe", on a near-black tile:
  - Scanning: a dot with three rings pulsing out, 1.5 s each, 0.5 s apart
  - Match: everything turns teal and a check mark draws itself
  - Failed: a coral ring and dot hold for 1 s, then shrink and fade over 0.8 s
- [x] Face settings app (`apps/face`)
- [x] Unlock animation for `sudo` (`shell/surface-face@surface-kit`,
      `face/surface_face_status.py`)
- [x] Face login and the animation on the login and lock screens
      (`face/install-login.sh`)

## Kernel 7.4

- [x] Auto-rotation on this kernel
- [x] Default boot
- [x] Suspend, short and long
- [x] Clean rebuild with all patches, installed

## Upstream

- [ ] `ov7251` link frequency fix, `ov8865` and `dw9719` patches to linux-media
- [x] What's new from here in linux-surface discussion 1353
