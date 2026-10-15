# Touch and pen (Surface Pro 7, IPTS + iptsd)

`sudo touch/install.sh` installs:

- `iptsd-restart.conf`: iptsd retries after a failed start (touch after
  resume)
- `iptsd-surface-pro-7.conf` → `/etc/iptsd.d/90-surface-pro-7.conf`: iptsd
  has no preset for this model and its defaults broke touch up. A sliding
  fingertip covers 1-2 cells of the coarse grid and, after iptsd's blur,
  missed the default ActivationThreshold (24) in about half the frames;
  each miss ended the touch, so 89 of 92 touches lasted under 50 ms and
  scrolling and pinching fell apart. ActivationThreshold 16 (replayed
  offline on a recording: no lost frames, no extra contacts) plus finger
  size limits from `iptsd-calibrate`.

`touch/iptsd/` builds a patched iptsd 3.1.0 (`build.sh`, then
`sudo touch/iptsd/install.sh`, `--remove` to undo):

- `0001-ignore-writing-hand-after-stylus.patch`: with DisableOnStylus, touch
  came back at the first frame after the pen left proximity, i.e. between
  every two strokes, and the resting palm became touches. Contacts already
  on the screen at that moment are now ignored until they are lifted.

Debugging: `sudo stdbuf -oL timeout -s INT 20 libinput debug-events > log`
(stdbuf: otherwise the buffered output is lost), `iptsd-dump /dev/hidraw0`
(writes /tmp/iptsd_*.bin), `IPTSD_CONFIG_FILE=x.conf iptsd-plot dump.bin dir`
renders every frame with its contacts (green valid, yellow unstable, red
rejected), so settings can be tried offline.

Pen top button: click Super+F20, double click Super+F19, hold Super+F18
(not bound yet).
