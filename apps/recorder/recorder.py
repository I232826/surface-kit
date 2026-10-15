#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Recorder: a touch-friendly voice recorder for the Surface (surface-kit).

One big button records from the default microphone (whatever PipeWire
uses: the Surface mics or a headset) into Ogg Opus files in
~/<Music>/Recordings, with a live level graph, a timer and pause. The
recordings are listed below with play, rename, delete and show in Files.
While recording, the system is kept from suspending.
"""
import datetime
import math
import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")
from gi.repository import Adw, Gio, GLib, Gst, GstPbutils, Gtk  # noqa: E402

APP_ID = "io.github.surfacekit.Recorder"
LEVEL_INTERVAL_NS = 50 * Gst.MSECOND
LEVEL_HISTORY = 120  # bars in the level graph (6 s)


def recordings_dir() -> Path:
    music = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC)
    path = Path(music or Path.home() / "Music") / "Recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_time(seconds: float) -> str:
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class Recorder:
    """The GStreamer side: default mic -> mono 48 kHz -> level -> Opus/Ogg."""

    def __init__(self, on_level, on_error):
        self.on_level = on_level
        self.on_error = on_error
        self.pipeline = None
        self.path = None
        self.started = 0.0  # monotonic seconds of recorded time before the last resume
        self.resumed_at = None

    def start(self, path: Path):
        self.path = path
        desc = (
            "pipewiresrc ! audioconvert ! audioresample ! "
            "audio/x-raw,rate=48000,channels=1 ! "
            f"level interval={LEVEL_INTERVAL_NS} post-messages=true ! "
            "opusenc bitrate=64000 ! oggmux ! "
            f'filesink location="{path}"'
        )
        self.pipeline = Gst.parse_launch(desc)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_message)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.started = 0.0
        self.resumed_at = GLib.get_monotonic_time()

    @property
    def elapsed(self) -> float:
        running = 0.0
        if self.resumed_at is not None:
            running = (GLib.get_monotonic_time() - self.resumed_at) / 1e6
        return self.started + running

    @property
    def paused(self) -> bool:
        return self.pipeline is not None and self.resumed_at is None

    def pause(self):
        if self.pipeline and self.resumed_at is not None:
            self.started = self.elapsed
            self.resumed_at = None
            self.pipeline.set_state(Gst.State.PAUSED)

    def resume(self):
        if self.pipeline and self.resumed_at is None:
            self.resumed_at = GLib.get_monotonic_time()
            self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self, done):
        """Finish the file (EOS so the Ogg is complete), then call done(path)."""
        if not self.pipeline:
            return
        pipeline, path = self.pipeline, self.path
        self.pipeline = None
        self.resumed_at = None
        pipeline.set_state(Gst.State.PLAYING)
        bus = pipeline.get_bus()

        def finished(*_):
            pipeline.set_state(Gst.State.NULL)
            bus.remove_signal_watch()
            done(path)
            return False

        def on_eos(_bus, msg):
            if msg.type in (Gst.MessageType.EOS, Gst.MessageType.ERROR):
                GLib.idle_add(finished)

        bus.connect("message", on_eos)
        pipeline.send_event(Gst.Event.new_eos())
        GLib.timeout_add_seconds(3, finished)  # in case EOS never comes

    def _on_message(self, _bus, msg):
        if msg.type == Gst.MessageType.ELEMENT:
            s = msg.get_structure()
            if s and s.get_name() == "level":
                peak = s.get_value("peak")
                if peak:
                    self.on_level(max(peak))
        elif msg.type == Gst.MessageType.ERROR:
            err, _dbg = msg.parse_error()
            self.on_error(err.message)


class LevelGraph(Gtk.DrawingArea):
    """The last few seconds of input level, as bars from the middle."""

    def __init__(self):
        super().__init__()
        self.levels = [0.0] * LEVEL_HISTORY
        self.set_content_height(96)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def push(self, peak_db: float):
        # -60 dB .. 0 dB to 0 .. 1
        self.levels = self.levels[1:] + [min(1.0, max(0.0, (peak_db + 60) / 60))]
        self.queue_draw()

    def clear(self):
        self.levels = [0.0] * LEVEL_HISTORY
        self.queue_draw()

    def _draw(self, _area, cr, width, height):
        color = self.get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, 0.85)
        bar = width / LEVEL_HISTORY
        mid = height / 2
        for i, level in enumerate(self.levels):
            h = max(2.0, level * (height - 4))
            cr.rectangle(i * bar + bar * 0.15, mid - h / 2, bar * 0.7, h)
        cr.fill()


class RecordingRow(Adw.ActionRow):
    def __init__(self, window, path: Path, duration: float | None):
        super().__init__()
        self.window = window
        self.path = path
        self.set_title(GLib.markup_escape_text(path.stem))
        stamp = datetime.datetime.fromtimestamp(path.stat().st_mtime)
        sub = stamp.strftime("%d.%m.%Y %H:%M")
        if duration is not None:
            sub += f"  ·  {format_time(duration)}"
        self.set_subtitle(sub)
        self.set_activatable(True)

        self.play_button = Gtk.Button(icon_name="media-playback-start-symbolic",
                                      valign=Gtk.Align.CENTER,
                                      tooltip_text="Play")
        self.play_button.add_css_class("circular")
        self.play_button.set_size_request(48, 48)
        self.play_button.connect("clicked", lambda *_: window.toggle_play(self))
        self.add_prefix(self.play_button)
        self.connect("activated", lambda *_: window.toggle_play(self))

        menu = Gio.Menu()
        menu.append("Rename", f"row.rename")
        menu.append("Show in Files", f"row.show")
        menu.append("Delete", f"row.delete")
        more = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu,
                              valign=Gtk.Align.CENTER, tooltip_text="More")
        more.add_css_class("flat")
        more.set_size_request(48, 48)
        self.add_suffix(more)

        group = Gio.SimpleActionGroup()
        for name, handler in (("rename", window.rename), ("show", window.show_in_files),
                              ("delete", window.delete)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, h=handler: h(self))
            group.add_action(action)
        self.insert_action_group("row", group)

    def set_playing(self, playing: bool):
        self.play_button.set_icon_name(
            "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic")


class RecorderWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Recorder")
        self.set_default_size(560, 760)
        self.dir = recordings_dir()
        self.recorder = Recorder(self._on_level, self._on_error)
        self.inhibit_cookie = 0
        self.tick_id = 0
        self.media = None
        self.playing_row = None
        self.discoverer = GstPbutils.Discoverer.new(2 * Gst.SECOND)

        self.toasts = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        self.toasts.set_child(toolbar)
        self.set_content(self.toasts)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                      margin_top=12, margin_bottom=24, margin_start=12, margin_end=12)
        toolbar.set_content(box)

        # recordings
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list.add_css_class("boxed-list")
        self.empty = Adw.StatusPage(icon_name="audio-input-microphone-symbolic",
                                    title="No Recordings",
                                    description="Tap the red button to record")
        self.stack = Gtk.Stack(vexpand=True)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=640, child=self.list)
        scroller.set_child(clamp)
        self.stack.add_named(scroller, "list")
        self.stack.add_named(self.empty, "empty")
        box.append(self.stack)

        # recording controls
        self.graph = LevelGraph()
        box.append(self.graph)
        self.timer = Gtk.Label(label="0:00")
        self.timer.add_css_class("title-1")
        self.timer.add_css_class("numeric")
        box.append(self.timer)

        controls = Gtk.Box(spacing=24, halign=Gtk.Align.CENTER)
        self.pause_button = Gtk.Button(icon_name="media-playback-pause-symbolic",
                                       tooltip_text="Pause", valign=Gtk.Align.CENTER,
                                       sensitive=False)
        self.pause_button.add_css_class("circular")
        self.pause_button.set_size_request(64, 64)
        self.pause_button.connect("clicked", self._on_pause)
        self.record_button = Gtk.Button(tooltip_text="Record")
        self.record_button.add_css_class("circular")
        self.record_button.add_css_class("record-button")
        self.record_button.set_size_request(96, 96)
        self.record_icon = Gtk.Image(icon_name="media-record-symbolic", pixel_size=40)
        self.record_button.set_child(self.record_icon)
        self.record_button.connect("clicked", self._on_record)
        spacer = Gtk.Box()
        spacer.set_size_request(64, 64)
        controls.append(self.pause_button)
        controls.append(self.record_button)
        controls.append(spacer)
        box.append(controls)

        css = Gtk.CssProvider()
        css.load_from_string(
            ".record-button { background: #e01b24; color: white; }"
            ".record-button:hover { background: #ed333b; }"
            ".record-button.recording { background: #a51d2d; }"
            "row { min-height: 64px; }")
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.monitor = Gio.File.new_for_path(str(self.dir)).monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None)
        self.monitor.connect("changed", lambda *_: GLib.idle_add(self.reload))
        self.reload()
        self.connect("close-request", self._on_close)

    # recordings list
    def _duration(self, path: Path):
        try:
            info = self.discoverer.discover_uri(Gst.filename_to_uri(str(path)))
            return info.get_duration() / Gst.SECOND
        except GLib.Error:
            return None

    def reload(self, *_):
        playing = self.playing_row.path if self.playing_row else None
        self.list.remove_all()
        files = sorted(
            (p for p in self.dir.iterdir()
             if p.suffix in (".ogg", ".opus", ".wav", ".flac", ".m4a", ".mp3")
             and p != self.recorder.path),
            key=lambda p: p.stat().st_mtime, reverse=True)
        self.playing_row = None
        for path in files:
            row = RecordingRow(self, path, self._duration(path))
            if path == playing:
                self.playing_row = row
                row.set_playing(self.media is not None and self.media.get_playing())
            self.list.append(row)
        self.stack.set_visible_child_name("list" if files else "empty")
        return False

    def toggle_play(self, row: RecordingRow):
        if self.playing_row is row and self.media:
            if self.media.get_playing():
                self.media.pause()
            else:
                self.media.play()
            row.set_playing(self.media.get_playing())
            return
        self._stop_playback()
        self.media = Gtk.MediaFile.new_for_filename(str(row.path))
        self.media.connect("notify::ended", self._on_ended)
        self.media.play()
        self.playing_row = row
        row.set_playing(True)

    def _on_ended(self, media, _pspec):
        if media.get_ended() and self.playing_row:
            self.playing_row.set_playing(False)
            media.seek(0)

    def _stop_playback(self):
        if self.media:
            self.media.pause()
            self.media = None
        if self.playing_row:
            self.playing_row.set_playing(False)
            self.playing_row = None

    def rename(self, row: RecordingRow):
        dialog = Adw.AlertDialog(heading="Rename Recording")
        entry = Gtk.Entry(text=row.path.stem, activates_default=True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")

        def on_response(_d, response):
            name = entry.get_text().strip().replace("/", "-")
            if response != "rename" or not name or name == row.path.stem:
                return
            target = row.path.with_name(name + row.path.suffix)
            if target.exists():
                self.toast(f"“{name}” already exists")
                return
            if self.playing_row is row:
                self._stop_playback()
            row.path.rename(target)

        dialog.connect("response", on_response)
        dialog.present(self)

    def delete(self, row: RecordingRow):
        if self.playing_row is row:
            self._stop_playback()
        Gio.File.new_for_path(str(row.path)).trash(None)
        self.toast(f"“{row.path.stem}” moved to the bin")

    def show_in_files(self, row: RecordingRow):
        Gtk.FileLauncher.new(Gio.File.new_for_path(str(row.path))).open_containing_folder(
            self, None, None)

    def toast(self, text: str):
        self.toasts.add_toast(Adw.Toast(title=text))

    # recording
    def _on_record(self, _button):
        if self.recorder.pipeline:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._stop_playback()
        name = datetime.datetime.now().strftime("Recording %Y-%m-%d %H-%M-%S")
        path = self.dir / f"{name}.ogg"
        try:
            self.recorder.start(path)
        except GLib.Error as e:
            self._on_error(e.message)
            return
        self.inhibit_cookie = self.get_application().inhibit(
            self, Gtk.ApplicationInhibitFlags.SUSPEND | Gtk.ApplicationInhibitFlags.LOGOUT,
            "Recording audio")
        self.record_button.add_css_class("recording")
        self.record_icon.set_from_icon_name("media-playback-stop-symbolic")
        self.record_button.set_tooltip_text("Stop")
        self.pause_button.set_sensitive(True)
        self.graph.clear()
        self.tick_id = GLib.timeout_add(200, self._tick)

    def _stop_recording(self):
        self.recorder.stop(self._finished)
        if self.inhibit_cookie:
            self.get_application().uninhibit(self.inhibit_cookie)
            self.inhibit_cookie = 0
        if self.tick_id:
            GLib.source_remove(self.tick_id)
            self.tick_id = 0
        self.record_button.remove_css_class("recording")
        self.record_icon.set_from_icon_name("media-record-symbolic")
        self.record_button.set_tooltip_text("Record")
        self.pause_button.set_sensitive(False)
        self.pause_button.set_icon_name("media-playback-pause-symbolic")

    def _finished(self, path: Path):
        self.recorder.path = None
        self.timer.set_label("0:00")
        self.graph.clear()
        self.reload()
        if path and path.exists():
            self.toast(f"Saved “{path.stem}”")

    def _on_pause(self, _button):
        if self.recorder.paused:
            self.recorder.resume()
            self.pause_button.set_icon_name("media-playback-pause-symbolic")
            self.pause_button.set_tooltip_text("Pause")
        else:
            self.recorder.pause()
            self.pause_button.set_icon_name("media-record-symbolic")
            self.pause_button.set_tooltip_text("Resume")

    def _tick(self):
        self.timer.set_label(format_time(self.recorder.elapsed))
        return True

    def _on_level(self, peak_db):
        if not math.isfinite(peak_db):
            peak_db = -60.0
        self.graph.push(peak_db)

    def _on_error(self, message):
        self.toast(f"Recording failed: {message}")
        if self.recorder.pipeline:
            self._stop_recording()

    def _on_close(self, *_):
        if self.recorder.pipeline:
            self._stop_recording()
        self._stop_playback()
        return False


class RecorderApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        window = self.get_active_window() or RecorderWindow(self)
        window.present()


def main():
    Gst.init(None)
    return RecorderApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
