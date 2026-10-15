# Mutter (GNOME's compositor) with a pen dot cursor

`patches/0001-pen-dot-cursor.patch`: like on Windows, the pen and eraser
show a small dot (dark, light rim, drawn at the output scale) instead of
the arrow, text cursor, hand and other standard shapes, from apps and the
shell alike. It sits in `meta_sprite_update_cursor`, where a tablet
sprite's cursor reaches the renderer: patching the Wayland tablet-tool
cursor instead missed the shell's own cursor and the moment before an app
sets one, so the arrow flashed when the pen came near. Apps' own cursor
images (brush outlines) and hidden cursors are kept; the mouse is
unchanged. `MUTTER_PEN_DOT=0` turns it off.

Build and install (then log out and in):

```sh
sudo apt build-dep mutter     # once
mutter/build-deb.sh           # prints the apt install command
```

Not held like the camera packages (GNOME Shell and security updates track
mutter closely): an Ubuntu update replaces it and `check-updates.sh`
reports that it's time to rebuild. Back to Ubuntu's:
`sudo apt install --reinstall libmutter-18-0 mutter-common mutter-common-bin gir1.2-mutter-18`.
