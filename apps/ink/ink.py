#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Screen Ink: draw on a snapshot of the screen (surface-kit).

Takes a screenshot as it starts (through the surface-kit-shell extension,
before its own window appears), shows it in a maximized window, and lets you write on
it with the pen (pressure), a finger or the mouse: pen, highlighter, eraser,
colours, undo/redo. Save writes a PNG to ~/<Pictures>/Screenshots; Copy puts
it on the clipboard (the app then waits in the background until something
else is copied, since a Wayland clipboard empties when its owner quits).
Esc or the close button discards it.
"""
import datetime
import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Graphene", "1.0")
import cairo  # noqa: E402
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Graphene, Gtk  # noqa: E402

APP_ID = "io.github.surfacekit.Ink"
COLORS = [
    ("Black", (0.12, 0.12, 0.12)), ("Red", (0.88, 0.11, 0.14)),
    ("Blue", (0.11, 0.44, 0.85)), ("Green", (0.15, 0.64, 0.25)),
    ("Yellow", (0.96, 0.83, 0.18)),
]
PEN_WIDTH = (1.5, 7.0)  # width at no / full pressure, logical px
HIGHLIGHTER_WIDTH = 18.0
ERASER_RADIUS = 14.0
CLIPBOARD_WAIT_S = 30 * 60
DEBUG = bool(os.environ.get("INK_DEBUG"))


def take_screenshot(path: str) -> str | None:
    """Ask the shell helper for a screenshot; None if it worked, else why not."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.gnome.Shell", "/io/github/surfacekit/Shell",
                      "io.github.surfacekit.Shell", "Screenshot",
                      GLib.Variant("(s)", (path,)), GLib.VariantType("(b)"),
                      Gio.DBusCallFlags.NONE, 5000, None)
        return None
    except GLib.Error as e:
        if "UnknownMethod" in e.message or "ServiceUnknown" in e.message:
            return ("The surface-kit shell helper isn't running "
                    "(shell/install.sh, then log out and back in).")
        return e.message


class Stroke:
    def __init__(self, tool, color):
        self.tool = tool  # "pen" or "highlighter"
        self.color = color
        self.points = []  # (x, y, pressure) in logical px

    def near(self, x, y, r):
        r2 = r * r
        return any((px - x) ** 2 + (py - y) ** 2 <= r2 for px, py, _ in self.points)

    def draw(self, cr):
        if not self.points:
            return
        r, g, b = self.color
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        if self.tool == "highlighter":
            # one path, so overlaps within the stroke don't darken
            cr.set_source_rgba(r, g, b, 0.38)
            cr.set_line_width(HIGHLIGHTER_WIDTH)
            x, y, _ = self.points[0]
            cr.move_to(x, y)
            for x, y, _ in self.points[1:]:
                cr.line_to(x, y)
            if len(self.points) == 1:
                cr.line_to(x + 0.1, y)
            cr.stroke()
            return
        cr.set_source_rgb(r, g, b)
        lo, hi = PEN_WIDTH
        if len(self.points) == 1:
            x, y, p = self.points[0]
            cr.arc(x, y, (lo + (hi - lo) * p) / 2, 0, 6.2832)
            cr.fill()
            return
        for (x0, y0, p0), (x1, y1, p1) in zip(self.points, self.points[1:]):
            cr.set_line_width(lo + (hi - lo) * (p0 + p1) / 2)
            cr.move_to(x0, y0)
            cr.line_to(x1, y1)
            cr.stroke()


class InkCanvas(Gtk.DrawingArea):
    """The strokes, over the screenshot (a Gtk.Picture underneath)."""

    def __init__(self, window):
        super().__init__(hexpand=True, vexpand=True)
        self.window = window
        self.strokes = []
        self.undo_stack = []  # ("add", stroke) | ("erase", [strokes]) | ("clear", [strokes])
        self.redo_stack = []
        self.current = None
        self.erased = []
        self.set_draw_func(self._draw)

        # raw events rather than gestures: nothing to lose an arbitration to.
        # One pointer or touch sequence draws at a time.
        self.sequence = None  # the sequence drawing now (None = pointer)
        self.drawing = False
        legacy = Gtk.EventControllerLegacy()
        legacy.connect("event", self._on_event)
        self.add_controller(legacy)

    # input
    def _local(self, x, y):
        """Surface coordinates to canvas coordinates."""
        native = self.get_native()
        nx, ny = native.get_surface_transform()
        ok, point = native.compute_point(self, Graphene.Point().init(x - nx, y - ny))
        return (point.x, point.y) if ok else (x, y)

    def _on_event(self, ctrl, event):
        # PyGObject can't marshal the GdkEvent signal argument (it arrives as None)
        event = event or ctrl.get_current_event()
        if event is None:
            return False
        kind = event.get_event_type()
        T = Gdk.EventType
        if kind not in (T.BUTTON_PRESS, T.BUTTON_RELEASE, T.MOTION_NOTIFY, T.TOUCH_BEGIN,
                        T.TOUCH_UPDATE, T.TOUCH_END, T.TOUCH_CANCEL):
            return False
        tool = event.get_device_tool()
        if DEBUG:
            ok, p = event.get_axis(Gdk.AxisUse.PRESSURE)
            print(kind.value_nick, tool and tool.get_tool_type().value_nick,
                  event.get_position()[1:], p if ok else "-", flush=True)
        sequence = event.get_event_sequence()

        if kind in (T.BUTTON_PRESS, T.TOUCH_BEGIN):
            if kind == T.BUTTON_PRESS and event.get_button() != 1 and tool is None:
                return False
            if self.drawing:
                if kind == T.TOUCH_BEGIN:
                    return True  # a second finger or the palm: ignore
                self._end()      # the pen wins over a finger in progress
            self.drawing, self.sequence = True, sequence
            pressure, eraser = self._info(event, tool)
            self._begin(*self._local(*event.get_position()[1:]), pressure, eraser)
            return True

        if not self.drawing or sequence != self.sequence:
            return kind != T.MOTION_NOTIFY

        if kind in (T.MOTION_NOTIFY, T.TOUCH_UPDATE):
            # the compositor batches motion; the history has the dropped samples
            history = event.get_history() if kind == T.MOTION_NOTIFY else None
            for sample in history or []:
                if DEBUG:
                    print("  history", sample.flags, sample.axes[1:3], flush=True)
                xy = Gdk.AxisFlags.X | Gdk.AxisFlags.Y
                if sample.flags & xy != xy:
                    continue  # no position in this sample
                axes = sample.axes
                pressure = (axes[Gdk.AxisUse.PRESSURE]
                            if tool and sample.flags & Gdk.AxisFlags.PRESSURE else 0.5)
                self._move(*self._local(axes[Gdk.AxisUse.X], axes[Gdk.AxisUse.Y]),
                           pressure, redraw=False)
            pressure, _ = self._info(event, tool)
            self._move(*self._local(*event.get_position()[1:]), pressure)
            return True

        self._end()  # release, touch end or cancel
        self.drawing, self.sequence = False, None
        return True

    @staticmethod
    def _info(event, tool):
        """(pressure, eraser) of an event."""
        if tool is None:
            return 0.5, False
        ok, p = event.get_axis(Gdk.AxisUse.PRESSURE)
        return (p if ok else 0.5), tool.get_tool_type() == Gdk.DeviceToolType.ERASER

    def _begin(self, x, y, pressure, eraser):
        if eraser or self.window.tool == "eraser":
            self.current, self.erased = None, []
            self._erase_at(x, y)
        else:
            self.erased = None
            self.current = Stroke(self.window.tool, self.window.color)
            self.current.points.append((x, y, pressure))
            self.strokes.append(self.current)
        self.queue_draw()

    def _move(self, x, y, pressure, redraw=True):
        if self.current is not None:
            self.current.points.append((x, y, pressure))
        elif self.erased is not None:
            self._erase_at(x, y)
        if redraw:
            self.queue_draw()

    def _end(self):
        if self.current is not None:
            self.undo_stack.append(("add", self.current))
            self.redo_stack.clear()
        elif self.erased:
            self.undo_stack.append(("erase", self.erased))
            self.redo_stack.clear()
        self.current, self.erased = None, None
        self.window.update_buttons()

    def _erase_at(self, x, y):
        hit = [s for s in self.strokes if s.near(x, y, ERASER_RADIUS)]
        for s in hit:
            self.strokes.remove(s)
            self.erased.append(s)

    # history
    def undo(self):
        if not self.undo_stack:
            return
        kind, item = self.undo_stack.pop()
        if kind == "add":
            self.strokes.remove(item)
        else:
            self.strokes.extend(item)
        self.redo_stack.append((kind, item))
        self.queue_draw()

    def redo(self):
        if not self.redo_stack:
            return
        kind, item = self.redo_stack.pop()
        if kind == "add":
            self.strokes.append(item)
        else:
            for s in item:
                self.strokes.remove(s)
        self.undo_stack.append((kind, item))
        self.queue_draw()

    def clear(self):
        if self.strokes:
            self.undo_stack.append(("clear", list(self.strokes)))
            self.redo_stack.clear()
            self.strokes.clear()
            self.queue_draw()

    def _draw(self, _area, cr, _w, _h):
        for stroke in self.strokes:
            stroke.draw(cr)


class InkWindow(Adw.ApplicationWindow):
    def __init__(self, app, shot: str):
        super().__init__(application=app, title="Screen Ink")
        self.shot = shot
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(shot)
        self.tool = "pen"
        self.color = COLORS[1][1]

        # The screenshot scaled to the window, aspect kept, strokes on top of it
        picture = Gtk.Picture.new_for_filename(shot)
        picture.set_content_fit(Gtk.ContentFit.FILL)
        picture.set_can_shrink(True)
        page = Gtk.Overlay(child=picture)
        self.canvas = InkCanvas(self)
        page.add_overlay(self.canvas)
        frame = Gtk.AspectFrame(child=page, obey_child=False,
                                ratio=self.pixbuf.get_width() / self.pixbuf.get_height())
        overlay = Gtk.Overlay(child=frame)
        overlay.add_overlay(self._toolbar())
        self.toasts = Adw.ToastOverlay(child=overlay)
        self.set_content(self.toasts)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self._css()
        self.update_buttons()
        # Not fullscreen: after a touch on a fullscreen window mutter stops
        # sending it the pen (GNOME 50), so a maximized window it is.
        self.maximize()

    def _css(self):
        css = Gtk.CssProvider()
        rules = [".ink-bar { border-radius: 999px; padding: 6px 10px; }",
                 ".swatch { min-width: 30px; min-height: 30px; padding: 0; border-radius: 999px;"
                 " border: 3px solid transparent; }",
                 ".swatch:checked { border-color: white; }"]
        for name, (r, g, b) in COLORS:
            rules.append(f".swatch-{name.lower()} {{ background: rgb({r*255:.0f},{g*255:.0f},{b*255:.0f}); }}")
        css.load_from_string("\n".join(rules))
        Gtk.StyleContext.add_provider_for_display(self.get_display(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _button(self, icon, tooltip, callback):
        button = Gtk.Button(icon_name=icon, tooltip_text=tooltip)
        button.add_css_class("circular")
        button.add_css_class("flat")
        button.set_size_request(44, 44)
        button.connect("clicked", lambda *_: callback())
        return button

    def _toolbar(self):
        bar = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER, valign=Gtk.Align.START,
                      margin_top=12)
        bar.add_css_class("osd")
        bar.add_css_class("ink-bar")

        group = None
        self.tool_buttons = {}
        for tool, icon, tip in (("pen", "document-edit-symbolic", "Pen"),
                                ("highlighter", "format-text-highlight-symbolic", "Highlighter"),
                                ("eraser", "edit-clear-symbolic", "Eraser")):
            button = Gtk.ToggleButton(icon_name=icon, tooltip_text=tip, group=group)
            button.add_css_class("circular")
            button.add_css_class("flat")
            button.set_size_request(44, 44)
            group = group or button
            button.connect("toggled", self._on_tool, tool)
            self.tool_buttons[tool] = button
            bar.append(button)
        self.tool_buttons["pen"].set_active(True)

        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_start=4,
                                 margin_end=4))
        group = None
        for name, rgb in COLORS:
            swatch = Gtk.ToggleButton(tooltip_text=name, group=group, valign=Gtk.Align.CENTER)
            swatch.add_css_class("swatch")
            swatch.add_css_class(f"swatch-{name.lower()}")
            group = group or swatch
            swatch.connect("toggled", self._on_color, rgb)
            if rgb == self.color:
                swatch.set_active(True)
            bar.append(swatch)

        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_start=4,
                                 margin_end=4))
        self.undo_button = self._button("edit-undo-symbolic", "Undo", self._undo)
        self.redo_button = self._button("edit-redo-symbolic", "Redo", self._redo)
        self.clear_button = self._button("edit-delete-symbolic", "Clear", self._clear)
        bar.append(self.undo_button)
        bar.append(self.redo_button)
        bar.append(self.clear_button)
        bar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_start=4,
                                 margin_end=4))
        bar.append(self._button("edit-copy-symbolic", "Copy", self.copy))
        save = self._button("document-save-symbolic", "Save", self.save)
        bar.append(save)
        bar.append(self._button("window-close-symbolic", "Discard (Esc)", self.close))
        return bar

    def _on_tool(self, button, tool):
        if button.get_active():
            self.tool = tool

    def _on_color(self, button, rgb):
        if button.get_active():
            self.color = rgb
            if self.tool == "eraser":
                self.tool_buttons["pen"].set_active(True)

    def _undo(self):
        self.canvas.undo()
        self.update_buttons()

    def _redo(self):
        self.canvas.redo()
        self.update_buttons()

    def _clear(self):
        self.canvas.clear()
        self.update_buttons()

    def update_buttons(self):
        self.undo_button.set_sensitive(bool(self.canvas.undo_stack))
        self.redo_button.set_sensitive(bool(self.canvas.redo_stack))
        self.clear_button.set_sensitive(bool(self.canvas.strokes))

    def _on_key(self, _ctrl, keyval, _code, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if keyval == Gdk.KEY_Escape:
            self.close()
        elif ctrl and keyval in (Gdk.KEY_z, Gdk.KEY_Z):
            self._redo() if state & Gdk.ModifierType.SHIFT_MASK else self._undo()
        elif ctrl and keyval == Gdk.KEY_s:
            self.save()
        elif ctrl and keyval == Gdk.KEY_c:
            self.copy()
        else:
            return False
        return True

    # output
    def _composite(self) -> GdkPixbuf.Pixbuf:
        """The screenshot at full resolution with the strokes on it."""
        w, h = self.pixbuf.get_width(), self.pixbuf.get_height()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surface)
        Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
        cr.paint()
        cw, ch = self.canvas.get_width(), self.canvas.get_height()
        if cw and ch:
            cr.scale(w / cw, h / ch)
        for stroke in self.canvas.strokes:
            stroke.draw(cr)
        surface.flush()
        return Gdk.pixbuf_get_from_surface(surface, 0, 0, w, h)

    def save(self):
        pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        folder = Path(pictures or Path.home()) / "Screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        path = folder / f"Screen ink {stamp}.png"
        self._composite().savev(str(path), "png", [], [])
        self.get_application().saved = path
        self.close()

    def copy(self):
        ok, data = self._composite().save_to_bufferv("png", [], [])
        texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
        clipboard = self.get_display().get_clipboard()
        clipboard.set(texture)
        self.get_application().keep_clipboard(clipboard)
        self.close()


class InkApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.shot = None
        self.saved = None
        self.held = False

    def do_activate(self):
        window = self.get_active_window()
        if window:
            window.present()
            return
        fd, self.shot = GLib.file_open_tmp("surface-ink-XXXXXX.png")
        os.close(fd)
        error = take_screenshot(self.shot)
        if error:
            dialog = Adw.AlertDialog(heading="No Screenshot", body=error)
            dialog.add_response("close", "Close")
            holder = Adw.ApplicationWindow(application=self, default_width=1, default_height=1)
            dialog.connect("closed", lambda *_: holder.close())
            holder.present()
            dialog.present(holder)
            return
        InkWindow(self, self.shot).present()

    def keep_clipboard(self, clipboard):
        """Stay alive (windowless) while our image is on the clipboard."""
        if self.held:
            return
        self.held = True
        self.hold()

        def lost(*_):
            if not clipboard.is_local() and self.held:
                self.held = False
                self.release()

        clipboard.connect("notify::local", lost)
        GLib.timeout_add_seconds(CLIPBOARD_WAIT_S, lambda: lost() or False)

    def do_shutdown(self):
        if self.shot:
            Path(self.shot).unlink(missing_ok=True)
        Adw.Application.do_shutdown(self)


if __name__ == "__main__":
    sys.exit(InkApp().run(sys.argv))
