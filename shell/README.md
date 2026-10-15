# surface-kit shell helper (GNOME Shell extension)

`shell/install.sh` installs `surface-kit-shell@surface-kit` (log out and in
once). It puts methods on GNOME Shell's own D-Bus name for things Wayland
doesn't let other programs do:

- `io.github.surfacekit.Shell.ActivateApp(desktop_id)`: what a click on the
  app in the dock does. Focuses its most recent window if it runs (also a
  window GNOME didn't tie to the app but whose class or app id matches a name
  in the desktop file), starts it if not. Windows are activated with a fresh
  server timestamp; with the time of the D-Bus call (none) mutter's focus
  stealing prevention only flagged the window.
- `Screenshot(path)`: writes a PNG of the screen. Only answers Screen Ink
  (`apps/ink/ink.py`, checked through the caller's command line), so nothing
  else can grab the screen silently through it.
- `ListWindows()`: class, instance, GTK app id, sandboxed app id, the app
  GNOME tied each window to, title.

`shell/activate-app <desktop id>` calls ActivateApp and falls back to
starting the app; the Pen app's "Open an app" uses it.
