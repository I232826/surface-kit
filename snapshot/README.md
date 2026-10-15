# GNOME Camera (gnome-snapshot) with a document scanning mode

`patches/0001-document-scan-mode.patch` adds a fourth capture mode next to
picture, video and QR codes:

- the camera streams at full resolution in it (3200x2400 on the Surface
  Pro 7 rear camera instead of 1080p)
- while framing, the page is outlined live over the preview (aperture
  hands the app a 320 px copy of the feed 5 times a second; the same
  detection runs on it in a worker thread)
- after each shot the page is found (`src/document.rs`): grown out from
  the brightest paper across gradual changes, so a shadow over the page
  (often the tablet's own) is crossed while the page's edge stops it, and
  the corners moved to where the outline covers the most page; failing
  that, the brightest area at several thresholds, the paper's colour at
  any brightness, or colours rare along the border
- a dialog (`src/scan_adjust.rs`) shows the outline with draggable corners;
  a page lying on other white paper has no edge to find, so this is where
  it gets fixed
- Save warps the page upright and, with the filter on (Off / Filter /
  B&W in the dialog, remembered), evens the paper out to neutral white,
  lifting shadows (and cleaning harder where it had to lift); the scan
  lands next to the photo as `… (scan).jpeg`
- the focus button sits next to the shutter (it and a tap on the picture
  make the surface-kit libcamera autofocus sweep again)

Plain Rust and cairo, no new crates; builds offline from Ubuntu's vendored
crates.

## Build and install

```sh
sudo apt build-dep gnome-snapshot     # once
snapshot/build-deb.sh                 # prints the apt install command
```

An Ubuntu update to gnome-snapshot replaces it; re-run the script.

## Working on the page detection

`doctest/` builds just `document.rs` (from the unpacked tree in
`vendor/snapshot-src/gnome-snapshot-50.0`, see `apt-get source
gnome-snapshot`) into a command-line tool, in seconds instead of minutes:

```sh
cd snapshot/doctest && cargo build --release --offline
DOC_DEBUG=1 target/release/doctest photo.jpg ... > run.log   # writes "(scan)" files
python3 sheet.py run.log sheet.jpg     # photos with the outline, next to the scans
DOC_NOSAVE=1 target/release/doctest photo.jpg ... > run.log   # outlines only
python3 outlines.py run.log out.jpg    # just the outlines, 4 a row
target/release/doctest frame_320x240.rgb   # time the live detection on a raw frame
```

The patch is regenerated from the working tree with `snapshot/make-patch.sh`
(changed files against `vendor/snapshot-src/orig`).

Sample photos used for tuning: `camera/captures/doctest*/` (not in git;
`doctest3` has the shadowed binder pages).
