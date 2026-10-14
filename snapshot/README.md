# GNOME Camera (gnome-snapshot) with a document scanning mode

`patches/0001-document-scan-mode.patch` adds a fourth capture mode next to
picture, video and QR codes:

- the camera streams at full resolution in it (3200x2400 on the Surface
  Pro 7 rear camera instead of 1080p)
- after each shot the page is found (`src/document.rs`: brightest area at
  several thresholds, the paper's colour at any brightness so shadows stay
  on the page, colours rare along the border; the largest mostly filled
  outline with real edges wins)
- a dialog (`src/scan_adjust.rs`) shows the outline with draggable corners;
  a page lying on other white paper has no edge to find, so this is where
  it gets fixed
- Save warps the page upright and evens the paper out to neutral white;
  the scan lands next to the photo as `… (scan).jpeg`

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
```

Sample photos used for tuning: `camera/captures/doctest*/` (not in git).
