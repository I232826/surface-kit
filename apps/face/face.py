#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Face: settings for face login on the Surface Pro 7 (surface-kit).

- Camera: a live picture from the IR camera, to check the framing
- Scans: add and remove face scans, try recognition
- Use: face login on or off, and for sudo
- Settings: how strict a match has to be and how long to look

Anything that needs root goes through pkexec and face-apply.
"""
import configparser
import getpass
import json
import sys
import threading
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = "io.github.surfacekit.Face"
HERE = Path(__file__).resolve().parent
APPLY = str(HERE / "face-apply")
# the IR camera reader Howdy uses as well
sys.path.insert(0, str(HERE.parent.parent / "face"))

CONFIG = Path("/etc/howdy/config.ini")
MODELS = Path("/etc/howdy/models") / f"{getpass.getuser()}.dat"
PAM_SUDO = Path("/etc/pam.d/sudo")
PAM_LINE = "auth sufficient pam_howdy.so"

# compare.py's exit codes (howdy/src/pam/main.hh)
TEST_RESULTS = {
    0: "Recognised you",
    10: "No face scans yet",
    11: "No match before the time ran out",
    12: "Face login is switched off",
    13: "Too dark to see a face",
    14: "Couldn't open the camera",
}
PKEXEC_DISMISSED = 126


def read_config():
    config = configparser.ConfigParser()
    try:
        config.read(CONFIG)
    except configparser.Error:
        pass
    return config


def read_scans():
    try:
        return json.loads(MODELS.read_text())
    except (OSError, ValueError):
        return []


def sudo_enabled():
    try:
        return PAM_LINE in PAM_SUDO.read_text().splitlines()
    except OSError:
        return False


def apply(args, done):
    """Run face-apply as root. done(exit status or None, output)."""
    try:
        proc = Gio.Subprocess.new(
            ["pkexec", APPLY, *args],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
    except GLib.Error as e:
        done(None, e.message)
        return

    def finished(p, result):
        try:
            _ok, out, _err = p.communicate_utf8_finish(result)
            status = p.get_exit_status() if p.get_if_exited() else None
        except GLib.Error as e:
            status, out = None, e.message
        done(status, out or "")

    proc.communicate_utf8_async(None, None, finished)


def last_line(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else "No output"


class Preview:
    """Frames from the IR camera on a thread, shown in a Gtk.Picture."""

    def __init__(self, picture, on_stopped):
        self.picture = picture
        self.on_stopped = on_stopped
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=8)
            self.thread = None

    def _run(self):
        error = None
        reader = None
        try:
            from surface_ir_reader import surface_ir_reader
            reader = surface_ir_reader()
            while self.running:
                ok, frame = reader.read()
                if not ok:
                    error = "The camera stopped sending pictures"
                    break
                GLib.idle_add(self._show, frame.tobytes(), frame.shape[1], frame.shape[0])
                time.sleep(0.03)
        except Exception as e:  # the camera or a missing tool; show it, keep the app up
            error = f"Couldn't start the camera: {e}"
        finally:
            if reader:
                reader.release()
            GLib.idle_add(self.on_stopped, error)

    def _show(self, data, width, height):
        if self.running:
            texture = Gdk.MemoryTexture.new(width, height, Gdk.MemoryFormat.B8G8R8,
                                            GLib.Bytes.new(data), width * 3)
            self.picture.set_paintable(texture)
        return GLib.SOURCE_REMOVE


class FaceWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Face")
        self.set_default_size(480, 760)
        self.toasts = Adw.ToastOverlay()
        self.busy = False

        page = Adw.PreferencesPage()
        page.add(self._camera_group())
        page.add(self._scans_group())
        page.add(self._use_group())
        page.add(self._settings_group())

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(page)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        self.connect("close-request", self._on_close)
        self._refresh()

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text))

    # Camera

    def _camera_group(self):
        group = Adw.PreferencesGroup(
            title="Camera",
            description="The IR light is on while the picture shows. Keep your "
                        "face in the middle, about 40 cm away.")
        self.picture = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, height_request=360,
                                   visible=False)
        self.picture.add_css_class("card")
        group.add(self.picture)
        self.preview = Preview(self.picture, self._preview_stopped)
        self.preview_row = Adw.SwitchRow(title="Show the camera picture")
        self.preview_row.connect("notify::active", self._on_preview)
        group.add(self.preview_row)
        return group

    def _on_preview(self, row, _pspec):
        if row.get_active() and not self.preview.running:
            self.picture.set_visible(True)
            self.preview.start()
        elif not row.get_active() and self.preview.running:
            self._stop_preview()

    def _stop_preview(self):
        self.preview.stop()
        self.preview_row.set_active(False)
        self.picture.set_visible(False)

    def _preview_stopped(self, error):
        if error and self.preview.running:
            self.preview.running = False
            self.preview_row.set_active(False)
            self.picture.set_visible(False)
            self.toast(error)
        return GLib.SOURCE_REMOVE

    # Scans

    def _scans_group(self):
        self.scans = Adw.PreferencesGroup(title="Face scans")
        self.scan_rows = []
        add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add a face scan")
        add.add_css_class("flat")
        add.connect("clicked", self._ask_label)
        self.scans.set_header_suffix(add)
        self.scan_status = Adw.ActionRow(title="Scanning", subtitle="Look at the camera",
                                         visible=False)
        self.scan_status.add_prefix(Adw.Spinner())
        self.scans.add(self.scan_status)
        self.test_row = Adw.ActionRow(title="Try it",
                                      subtitle="Check that the camera recognises you")
        self.test_button = Gtk.Button(label="Test", valign=Gtk.Align.CENTER)
        self.test_button.connect("clicked", self._test)
        self.test_row.add_suffix(self.test_button)
        self.scans.add(self.test_row)
        return self.scans

    def _refresh_scans(self):
        for row in self.scan_rows:
            self.scans.remove(row)
        self.scan_rows = []
        for scan in read_scans():
            when = GLib.DateTime.new_from_unix_local(scan.get("time", 0))
            row = Adw.ActionRow(title=GLib.markup_escape_text(scan.get("label", "Scan")),
                                subtitle=when.format("%x") if when else "")
            remove = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                tooltip_text="Remove this scan")
            remove.add_css_class("flat")
            remove.connect("clicked", self._ask_remove, scan)
            row.add_suffix(remove)
            self.scans.add(row)
            self.scan_rows.append(row)

    def _ask_label(self, _button):
        dialog = Adw.AlertDialog(heading="Add a face scan",
                                 body="Name it after what's different, like glasses. "
                                      "The scan starts after you enter your password, so "
                                      "get ready to look at the camera.")
        entry = Gtk.Entry(placeholder_text="glasses", max_length=24,
                          activates_default=True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("add", "Scan")
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("add")
        dialog.set_close_response("cancel")

        def response(_d, answer):
            if answer != "add":
                return
            label = entry.get_text().strip() or "Scan"
            if not GLib.Regex.match_simple(r"^[[:alnum:] _-]{1,24}$", label, 0, 0):
                self.toast("Use letters, numbers, spaces, - and _ in the name")
                return
            self._add(label)

        dialog.connect("response", response)
        dialog.present(self)

    def _claim_camera(self):
        """Only one thing can stream at a time."""
        if self.busy:
            self.toast("The camera is busy")
            return False
        self._stop_preview()
        self.busy = True
        return True

    def _add(self, label):
        if not self._claim_camera():
            return
        self.scan_status.set_visible(True)

        def done(status, out):
            self.busy = False
            self.scan_status.set_visible(False)
            if status == 0:
                self.toast(f"Added {label}")
            elif status != PKEXEC_DISMISSED:
                self.toast(f"No scan added: {last_line(out)}")
            self._refresh_scans()

        apply(["add", label], done)

    def _ask_remove(self, _button, scan):
        label = scan.get("label", "Scan")
        last = len(read_scans()) == 1
        dialog = Adw.AlertDialog(
            heading=f"Remove {label}?",
            body="It's your only scan, so face login won't recognise you until you "
                 "add another." if last else "")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response("cancel")

        def response(_d, answer):
            if answer == "remove":
                apply(["remove", str(scan["id"])], removed)

        def removed(status, out):
            if status == 0:
                self.toast(f"Removed {label}")
            elif status != PKEXEC_DISMISSED:
                self.toast(f"Not removed: {last_line(out)}")
            self._refresh_scans()

        dialog.connect("response", response)
        dialog.present(self)

    def _test(self, _button):
        if not self._claim_camera():
            return
        self.test_button.set_sensitive(False)
        self.test_row.set_subtitle("Look at the camera")

        def done(status, out):
            self.busy = False
            self.test_button.set_sensitive(True)
            if status == PKEXEC_DISMISSED:
                self.test_row.set_subtitle("Check that the camera recognises you")
            else:
                self.test_row.set_subtitle(TEST_RESULTS.get(status, last_line(out)))

        apply(["test"], done)

    # Use

    def _use_group(self):
        group = Adw.PreferencesGroup(title="Use face login for")
        self.enabled = Adw.SwitchRow(title="Face login",
                                     subtitle="Off skips the camera everywhere")
        self.sudo = Adw.SwitchRow(title="sudo",
                                  subtitle="Your password still works. Skipped over SSH.")
        self.enabled.connect("notify::active", self._on_enabled)
        self.sudo.connect("notify::active", self._on_sudo)
        group.add(self.enabled)
        group.add(self.sudo)
        return group

    def _on_enabled(self, row, _pspec):
        if self.refreshing:
            return
        self._apply_switch(["enabled", "true" if row.get_active() else "false"])

    def _on_sudo(self, row, _pspec):
        if self.refreshing:
            return
        self._apply_switch(["sudo", "on" if row.get_active() else "off"])

    def _apply_switch(self, args):
        def done(status, out):
            if status not in (0, PKEXEC_DISMISSED):
                self.toast(f"Not changed: {last_line(out)}")
            self._refresh()

        apply(args, done)

    # Settings

    def _settings_group(self):
        group = Adw.PreferencesGroup(title="Matching")
        self.certainty = Adw.SpinRow.new_with_range(1.0, 5.0, 0.1)
        self.certainty.set_title("Certainty")
        self.certainty.set_subtitle("Lower is stricter, higher is easier to fool")
        self.certainty.set_digits(1)
        self.timeout = Adw.SpinRow.new_with_range(1, 15, 1)
        self.timeout.set_title("Time to look")
        self.timeout.set_subtitle("Seconds before falling back to your password")
        self.quiet = Adw.SwitchRow(title="Say when it recognises you")
        for row in (self.certainty, self.timeout, self.quiet):
            group.add(row)
        apply_row = Adw.ActionRow(title="Apply matching settings")
        button = Gtk.Button(label="Apply", valign=Gtk.Align.CENTER)
        button.connect("clicked", self._apply_settings)
        apply_row.add_suffix(button)
        group.add(apply_row)
        return group

    def _apply_settings(self, _button):
        # one password prompt per setting that changed, so only send those
        config = read_config()
        wanted = {
            "certainty": f"{self.certainty.get_value():.1f}",
            "timeout": str(int(self.timeout.get_value())),
            "no_confirmation": "false" if self.quiet.get_active() else "true",
        }
        current = {
            "certainty": f"{config.getfloat('video', 'certainty', fallback=3.5):.1f}",
            "timeout": str(config.getint("video", "timeout", fallback=4)),
            "no_confirmation": "true" if config.getboolean(
                "core", "no_confirmation", fallback=False) else "false",
        }
        changes = [(k, v) for k, v in wanted.items() if current[k] != v]
        if not changes:
            self.toast("Nothing to change")
            return

        def step(status, out):
            if status not in (None, 0):
                if status != PKEXEC_DISMISSED:
                    self.toast(f"Not applied: {last_line(out)}")
                self._refresh()
                return
            if changes:
                key, value = changes.pop(0)
                apply(["set", key, value], step)
            else:
                self.toast("Settings applied")
                self._refresh()

        step(None, "")

    def _refresh(self):
        self.refreshing = True
        config = read_config()
        self.enabled.set_active(not config.getboolean("core", "disabled", fallback=False))
        self.sudo.set_active(sudo_enabled())
        self.certainty.set_value(config.getfloat("video", "certainty", fallback=3.5))
        self.timeout.set_value(config.getint("video", "timeout", fallback=4))
        self.quiet.set_active(not config.getboolean("core", "no_confirmation", fallback=False))
        self.refreshing = False
        self._refresh_scans()

    def _on_close(self, _window):
        self.preview.stop()
        return False


class FaceApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)

    def do_activate(self):
        window = self.props.active_window or FaceWindow(self)
        window.present()


if __name__ == "__main__":
    sys.exit(FaceApp().run(sys.argv))
