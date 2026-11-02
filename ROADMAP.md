# Roadmap

## Face login

- [x] IR camera delivers frames on the 7.4 kernel (`kernel/patches/0005`)
- [x] IR emitter runs from the sensor's strobe output (`kernel/patches/0006`)
- [x] Howdy reads the camera (`face/`)
- [x] Face match unlocks `sudo` in a local terminal, password still works
- [ ] UI and animations for the unlock, in the spirit of Windows Hello but with
      its own look:
  1. Draft the animations
  2. Build them once the look is approved
- [ ] Login and lock screen (GDM), once `sudo` has proven itself

## Kernel 7.4

- [ ] Auto-rotation on this kernel
- [ ] Suspend test
- [ ] Clean rebuild with all patches, then make it the default boot

## Upstream

- [ ] `ov7251` link frequency fix, `ov8865` and `dw9719` patches to linux-media
- [ ] What's new from here in linux-surface discussion 1353
