#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pen: settings for the Surface Pen and touchscreen (surface-kit).

- Pen: battery, pressure feel (GNOME's stylus pressure curve, which mutter
  applies), a test canvas, the Windows-style dot cursor (surface-kit mutter)
- Buttons: the top button's click / double click / hold (the pen sends
  Super+F20 / F19 / F18) bound to GNOME actions, an app or a command; the
  side button's action
- Touch: iptsd's palm and pen handling and touch sensitivity
  (/etc/iptsd.d/90-surface-pro-7.conf, written through pkexec)
"""
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = "io.github.surfacekit.Pen"
HERE = Path(__file__).resolve().parent
# brings an app forward if it runs, starts it if not (shell/activate-app)
ACTIVATE = str(HERE.parent.parent / "shell" / "activate-app")
INK = str(HERE.parent / "ink" / "ink.py")

# the Surface Pen through iptsd reports no serial: mutter's settings path
STYLUS_SCHEMA = "org.gnome.desktop.peripherals.tablet.stylus"
STYLUS_PATH = "/org/gnome/desktop/peripherals/stylus/default-045e:099f/"

# GNOME Settings' pressure curves, soft to firm
PRESSURE_CURVES = [
    (0, 75, 25, 100), (0, 50, 50, 100), (0, 25, 75, 100), (0, 0, 100, 100),
    (25, 0, 100, 75), (50, 0, 100, 50), (75, 0, 100, 25),
]

# top button gestures: the keys touch/61-surface-pen-buttons.hwdb maps the
# pen's Super+F20 / F19 / F18 to (the layouts leave those unbindable)
GESTURES = [
    ("click", "Click", "<Super>F10"),
    ("double", "Double click", "<Super>F11"),
    ("hold", "Press and hold", "<Super>F12"),
]
# what earlier versions bound, moved over on start
OLD_ACCELS = {}
for _old in (("<Super>F20", "<Super>XF86Launch3", "XF86Launch3", "<Super>F10"),
             ("<Super>F19", "<Super>XF86Launch2", "XF86Launch2", "<Super>F11"),
             ("<Super>F18", "<Super>XF86Launch1", "XF86Launch1", "<Super>F12")):
    for _accel in _old[:-1]:
        OLD_ACCELS[_accel] = _old[-1]
# built-in GNOME actions that take extra accelerators
SHELL_ACTIONS = [
    ("screenshot", "Screenshot", "org.gnome.shell.keybindings", "show-screenshot-ui"),
    ("overview", "Activities overview", "org.gnome.shell.keybindings", "toggle-overview"),
    ("apps", "App grid", "org.gnome.shell.keybindings", "toggle-application-view"),
    ("notifications", "Notifications", "org.gnome.shell.keybindings", "toggle-message-tray"),
]
MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = MEDIA_KEYS + ".custom-keybinding"
CUSTOM_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

SIDE_ACTIONS = [
    ("default", "Default (right click)"), ("right", "Right click"),
    ("middle", "Middle click"), ("back", "Back"), ("forward", "Forward"),
]

DOT_ENV = Path.home() / ".config/environment.d/90-surface-pen-dot.conf"
IPTSD_CONF = Path("/etc/iptsd.d/90-surface-pro-7.conf")


# ---------------------------------------------------------------- buttons
class TopButtons:
    """Binds the pen's top-button accelerators to GNOME actions or commands.

    A gesture is either added to one of GNOME Shell's keybinding lists, or
    is a custom keybinding of its own (surface-pen-<gesture>)."""

    def __init__(self):
        self.shell = {schema: Gio.Settings.new(schema)
                      for schema in {a[2] for a in SHELL_ACTIONS}}
        self.media = Gio.Settings.new(MEDIA_KEYS)
        self._migrate()

    def _migrate(self):
        for _id, _label, schema, key in SHELL_ACTIONS:
            accels = self.shell[schema].get_strv(key)
            moved = [OLD_ACCELS.get(a, a) for a in accels]
            if moved != accels:
                self.shell[schema].set_strv(key, moved)
        for gesture, _label, _accel in GESTURES:
            if self._custom_path(gesture) in self.media.get_strv("custom-keybindings"):
                custom = self._custom(gesture)
                binding = custom.get_string("binding")
                if binding in OLD_ACCELS:
                    custom.set_string("binding", OLD_ACCELS[binding])
                command = custom.get_string("command")
                if command.startswith("gtk-launch "):
                    custom.set_string("command", f"{ACTIVATE} {command[len('gtk-launch '):]}")

    def _custom_path(self, gesture):
        return f"{CUSTOM_BASE}surface-pen-{gesture}/"

    def _custom(self, gesture):
        return Gio.Settings.new_with_path(CUSTOM_SCHEMA, self._custom_path(gesture))

    def current(self, gesture, accel):
        """(kind, value): ('none', ''), ('shell', id), ('command', cmd)."""
        for action_id, _label, schema, key in SHELL_ACTIONS:
            if accel in self.shell[schema].get_strv(key):
                return "shell", action_id
        if self._custom_path(gesture) in self.media.get_strv("custom-keybindings"):
            custom = self._custom(gesture)
            if custom.get_string("binding") == accel:
                return "command", custom.get_string("command")
        return "none", ""

    def clear(self, gesture, accel):
        for _id, _label, schema, key in SHELL_ACTIONS:
            settings = self.shell[schema]
            accels = settings.get_strv(key)
            if accel in accels:
                settings.set_strv(key, [a for a in accels if a != accel])
        path = self._custom_path(gesture)
        paths = self.media.get_strv("custom-keybindings")
        if path in paths:
            self.media.set_strv("custom-keybindings", [p for p in paths if p != path])
            custom = self._custom(gesture)
            for key in ("name", "command", "binding"):
                custom.reset(key)

    def set_shell(self, gesture, accel, action_id):
        self.clear(gesture, accel)
        for aid, _label, schema, key in SHELL_ACTIONS:
            if aid == action_id:
                settings = self.shell[schema]
                settings.set_strv(key, settings.get_strv(key) + [accel])

    def set_command(self, gesture, accel, name, command):
        self.clear(gesture, accel)
        custom = self._custom(gesture)
        custom.set_string("name", name)
        custom.set_string("command", command)
        custom.set_string("binding", accel)
        paths = self.media.get_strv("custom-keybindings")
        self.media.set_strv("custom-keybindings", paths + [self._custom_path(gesture)])


# ---------------------------------------------------------------- widgets
class CurvePreview(Gtk.DrawingArea):
    """The pressure curve (a cubic Bezier from (0,0) to (1,1))."""

    def __init__(self):
        super().__init__()
        self.curve = (0, 0, 100, 100)
        self.set_content_width(96)
        self.set_content_height(96)
        self.set_draw_func(self._draw)

    def set_curve(self, curve):
        self.curve = curve
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        color = self.get_color()
        pad = 6
        sx, sy = w - 2 * pad, h - 2 * pad
        cr.set_source_rgba(color.red, color.green, color.blue, 0.25)
        cr.set_line_width(1)
        cr.rectangle(pad, pad, sx, sy)
        cr.stroke()
        x1, y1, x2, y2 = (v / 100 for v in self.curve)
        cr.set_source_rgba(0.21, 0.52, 0.89, 1)
        cr.set_line_width(3)
        cr.move_to(pad, pad + sy)
        cr.curve_to(pad + x1 * sx, pad + sy - y1 * sy, pad + x2 * sx, pad + sy - y2 * sy,
                    pad + sx, pad)
        cr.stroke()


class TestCanvas(Gtk.DrawingArea):
    """Draw with the pen: line width follows pressure; shows pressure and tilt."""

    def __init__(self, on_sample):
        super().__init__()
        self.on_sample = on_sample
        self.strokes = []  # lists of (x, y, pressure)
        self.set_content_height(260)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)
        stylus = Gtk.GestureStylus()
        stylus.connect("down", self._on_down)
        stylus.connect("motion", self._on_motion)
        stylus.connect("up", self._on_up)
        stylus.connect("proximity", self._on_proximity)
        self.add_controller(stylus)
        self.drawing = False

    def clear(self):
        self.strokes = []
        self.queue_draw()

    def _sample(self, gesture, x, y):
        ok, pressure = gesture.get_axis(Gdk.AxisUse.PRESSURE)
        pressure = pressure if ok else 0.0
        okx, tx = gesture.get_axis(Gdk.AxisUse.XTILT)
        oky, ty = gesture.get_axis(Gdk.AxisUse.YTILT)
        tool = gesture.get_device_tool()
        eraser = tool is not None and tool.get_tool_type() == Gdk.DeviceToolType.ERASER
        self.on_sample(pressure, tx if okx else None, ty if oky else None, eraser)
        return pressure, eraser

    def _on_down(self, gesture, x, y):
        pressure, eraser = self._sample(gesture, x, y)
        self.drawing = True
        if eraser:
            self._erase(x, y)
        else:
            self.strokes.append([(x, y, pressure)])
        self.queue_draw()

    def _on_motion(self, gesture, x, y):
        pressure, eraser = self._sample(gesture, x, y)
        if not self.drawing:
            return
        if eraser:
            self._erase(x, y)
        elif self.strokes:
            self.strokes[-1].append((x, y, pressure))
        self.queue_draw()

    def _on_up(self, gesture, x, y):
        self.drawing = False
        self.on_sample(0.0, None, None, False)

    def _on_proximity(self, gesture, x, y):
        self._sample(gesture, x, y)

    def _erase(self, x, y):
        r2 = 20 ** 2
        self.strokes = [s for s in self.strokes
                        if all((px - x) ** 2 + (py - y) ** 2 > r2 for px, py, _ in s)]

    def _draw(self, _area, cr, w, h):
        color = self.get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, 0.06)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        cr.set_source_rgba(color.red, color.green, color.blue, 1)
        cr.set_line_cap(1)  # round
        for stroke in self.strokes:
            for (x0, y0, p0), (x1, y1, p1) in zip(stroke, stroke[1:]):
                cr.set_line_width(1 + 9 * (p0 + p1) / 2)
                cr.move_to(x0, y0)
                cr.line_to(x1, y1)
                cr.stroke()
            if len(stroke) == 1:
                x, y, p = stroke[0]
                cr.arc(x, y, (1 + 9 * p) / 2, 0, 6.283)
                cr.fill()


# ---------------------------------------------------------------- pages
class PenPage(Adw.PreferencesPage):
    def __init__(self, window):
        super().__init__(title="Pen", icon_name="input-tablet-symbolic")
        self.window = window
        self.stylus = Gio.Settings.new_with_path(STYLUS_SCHEMA, STYLUS_PATH)

        # battery
        status = Adw.PreferencesGroup(title="Surface Pen")
        self.battery = Adw.ActionRow(title="Battery", subtitle="Not connected")
        self.battery_icon = Gtk.Image(icon_name="battery-missing-symbolic")
        self.battery.add_prefix(self.battery_icon)
        status.add(self.battery)
        self.add(status)
        self._watch_battery()

        # pressure
        feel = Adw.PreferencesGroup(title="Pressure",
                                    description="How hard you have to press for a thick line")
        self.preview = CurvePreview()
        row = Adw.ActionRow(title="Feel", subtitle="Soft  ↔  Firm")
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0,
                                              len(PRESSURE_CURVES) - 1, 1)
        self.scale.set_draw_value(False)
        self.scale.set_hexpand(True)
        self.scale.set_size_request(220, -1)
        for i in range(len(PRESSURE_CURVES)):
            self.scale.add_mark(i, Gtk.PositionType.BOTTOM, None)
        current = tuple(self.stylus.get_value("pressure-curve").unpack())
        index = PRESSURE_CURVES.index(current) if current in PRESSURE_CURVES else 3
        self.scale.set_value(index)
        self.preview.set_curve(PRESSURE_CURVES[index])
        self.scale.connect("value-changed", self._on_curve)
        row.add_suffix(self.scale)
        row.add_suffix(self.preview)
        feel.add(row)
        self.add(feel)

        # test canvas
        test = Adw.PreferencesGroup(title="Try it",
                                    description="Draw with the pen; turn it over to erase")
        clear = Gtk.Button(label="Clear", valign=Gtk.Align.CENTER)
        clear.add_css_class("flat")
        test.set_header_suffix(clear)
        self.readout = Gtk.Label(label="Pressure –", xalign=0)
        self.readout.add_css_class("dim-label")
        self.readout.add_css_class("numeric")
        self.level = Gtk.LevelBar(min_value=0, max_value=1, hexpand=True)
        bar = Gtk.Box(spacing=12, margin_bottom=6)
        bar.append(self.readout)
        bar.append(self.level)
        self.canvas = TestCanvas(self._on_sample)
        frame = Gtk.Frame(child=self.canvas)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(bar)
        box.append(frame)
        test.add(box)
        clear.connect("clicked", lambda *_: self.canvas.clear())
        self.add(test)

        # cursor
        cursor = Adw.PreferencesGroup(title="Cursor")
        self.dot = Adw.SwitchRow(title="Show a dot under the pen",
                                 subtitle="Instead of the arrow, like on Windows. "
                                          "Applies after logging out.")
        self.dot.set_active(not DOT_ENV.exists())
        self.dot.connect("notify::active", self._on_dot)
        cursor.add(self.dot)
        self.add(cursor)

    def _on_curve(self, scale):
        curve = PRESSURE_CURVES[int(round(scale.get_value()))]
        self.preview.set_curve(curve)
        value = GLib.Variant("ai", list(curve))
        self.stylus.set_value("pressure-curve", value)
        self.stylus.set_value("eraser-pressure-curve", value)

    def _on_sample(self, pressure, tx, ty, eraser):
        text = f"{'Eraser' if eraser else 'Pressure'} {pressure * 100:3.0f} %"
        if tx is not None and ty is not None:
            text += f"   Tilt {tx:+.0f}° {ty:+.0f}°"
        self.readout.set_label(text)
        self.level.set_value(pressure)

    def _on_dot(self, row, _pspec):
        if row.get_active():
            DOT_ENV.unlink(missing_ok=True)
        else:
            DOT_ENV.parent.mkdir(parents=True, exist_ok=True)
            DOT_ENV.write_text("# surface-kit pen app: no dot cursor for the pen\nMUTTER_PEN_DOT=0\n")
        self.window.toast("Log out and back in to apply")

    # battery through UPower
    def _watch_battery(self):
        self.pen_proxy = None
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
            "org.freedesktop.UPower", "/org/freedesktop/UPower",
            "org.freedesktop.UPower", None, self._on_upower)

    def _on_upower(self, _src, result):
        try:
            upower = Gio.DBusProxy.new_for_bus_finish(result)
        except GLib.Error:
            return
        upower.connect("g-signal", lambda *_: self._find_pen(upower))
        self._find_pen(upower)

    def _find_pen(self, upower):
        try:
            paths = upower.call_sync("EnumerateDevices", None, Gio.DBusCallFlags.NONE,
                                     -1, None).unpack()[0]
        except GLib.Error:
            return
        for path in paths:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
                "org.freedesktop.UPower", path, "org.freedesktop.UPower.Device", None)
            model = proxy.get_cached_property("Model")
            if model and "pen" in model.unpack().lower():
                self.pen_proxy = proxy
                proxy.connect("g-properties-changed", lambda *_: self._show_battery())
                self._show_battery()
                return
        self.pen_proxy = None
        self._show_battery()

    def _show_battery(self):
        if not self.pen_proxy:
            self.battery.set_subtitle("Not connected (pair it in Bluetooth settings)")
            self.battery_icon.set_from_icon_name("battery-missing-symbolic")
            return
        pct = self.pen_proxy.get_cached_property("Percentage")
        icon = self.pen_proxy.get_cached_property("IconName")
        self.battery.set_subtitle(f"{pct.unpack():.0f} %" if pct else "Unknown")
        if icon:
            self.battery_icon.set_from_icon_name(icon.unpack())


# icons for the actions a gesture can have
ACTION_ICONS = {
    "none": "action-unavailable-symbolic",
    "screenshot": "applets-screenshooter-symbolic",
    "overview": "focus-windows-symbolic",
    "apps": "view-app-grid-symbolic",
    "notifications": "preferences-system-notifications-symbolic",
    "ink": "io.github.surfacekit.Ink",
    "command": "utilities-terminal-symbolic",
}


def app_of(command):
    """The desktop id a gesture's command opens, or None."""
    for prefix in (ACTIVATE + " ", "gtk-launch "):
        if command.startswith(prefix):
            return command[len(prefix):].strip()
    return None


def describe(top, gesture, accel):
    """(title, gicon or icon name) of what a gesture does now."""
    kind, value = top.current(gesture, accel)
    if kind == "shell":
        label = next(a[1] for a in SHELL_ACTIONS if a[0] == value)
        return label, ACTION_ICONS[value]
    if kind == "command":
        if value == INK:
            return "Screen Ink", ACTION_ICONS["ink"]
        app = app_of(value)
        if app:
            try:
                info = Gio.DesktopAppInfo.new(app + ".desktop")
            except TypeError:
                info = None
            if info:
                return f"Open {info.get_display_name()}", info.get_icon()
        return value, ACTION_ICONS["command"]
    return "Nothing", ACTION_ICONS["none"]


def tile(label, icon, size=48):
    """A large touch target: icon over a label."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                  margin_top=12, margin_bottom=12, margin_start=6, margin_end=6)
    image = Gtk.Image(pixel_size=size)
    if isinstance(icon, str):
        image.set_from_icon_name(icon)
    elif icon:
        image.set_from_gicon(icon)
    box.append(image)
    text = Gtk.Label(label=label, wrap=True, justify=Gtk.Justification.CENTER,
                     max_width_chars=12, lines=2, ellipsize=3)
    box.append(text)
    return box


class ActionChooserPage(Adw.NavigationPage):
    """Pick what a top-button gesture does: an action tile or an app."""

    def __init__(self, window, buttons, gesture, label, accel):
        super().__init__(title=label)
        self.window, self.buttons = window, buttons
        self.gesture, self.accel = gesture, accel
        top = buttons.top

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                          margin_top=12, margin_bottom=24, margin_start=12, margin_end=12)

        heading = Gtk.Label(label="Actions", xalign=0)
        heading.add_css_class("heading")
        content.append(heading)
        actions = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                              homogeneous=True, min_children_per_line=3,
                              max_children_per_line=6, row_spacing=6, column_spacing=6)
        choices = [("none", "Nothing")] + [(a[0], a[1]) for a in SHELL_ACTIONS] + [
            ("ink", "Screen Ink"), ("command", "Command…")]
        for action_id, text in choices:
            child = Gtk.FlowBoxChild(child=tile(text, ACTION_ICONS[action_id], 40))
            child.add_css_class("card")
            child.choice = ("action", action_id)
            actions.append(child)
        actions.connect("child-activated", self._chosen)
        content.append(actions)

        apps_head = Gtk.Box(spacing=12)
        heading = Gtk.Label(label="Open an app", xalign=0, hexpand=True)
        heading.add_css_class("heading")
        apps_head.append(heading)
        content.append(apps_head)
        self.search = Gtk.SearchEntry(placeholder_text="Search apps")
        content.append(self.search)
        self.apps = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                homogeneous=True, min_children_per_line=3,
                                max_children_per_line=8, row_spacing=6, column_spacing=6)
        for app in sorted((a for a in Gio.AppInfo.get_all() if a.should_show()),
                          key=lambda a: a.get_display_name().lower()):
            child = Gtk.FlowBoxChild(child=tile(app.get_display_name(), app.get_icon(), 56))
            child.choice = ("app", app)
            self.apps.append(child)
        self.apps.set_filter_func(self._filter)
        self.search.connect("search-changed", lambda *_: self.apps.invalidate_filter())
        self.apps.connect("child-activated", self._chosen)
        content.append(self.apps)

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(Gtk.ScrolledWindow(
            child=Adw.Clamp(maximum_size=760, child=content),
            hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True))
        self.set_child(view)

    def _filter(self, child):
        text = self.search.get_text().strip().lower()
        return not text or text in child.choice[1].get_display_name().lower()

    def _chosen(self, _flowbox, child):
        kind, value = child.choice
        top = self.buttons.top
        if kind == "app":
            app_id = value.get_id().removesuffix(".desktop")
            top.set_command(self.gesture, self.accel, f"Pen: {value.get_display_name()}",
                            f"{ACTIVATE} {app_id}")
        elif value == "ink":
            top.set_command(self.gesture, self.accel, "Pen: Screen Ink", INK)
        elif value == "none":
            top.clear(self.gesture, self.accel)
        elif value == "command":
            self._ask_command()
            return
        else:
            top.set_shell(self.gesture, self.accel, value)
        self.buttons.refresh()
        self.window.nav.pop()

    def _ask_command(self):
        top = self.buttons.top
        kind, value = top.current(self.gesture, self.accel)
        dialog = Adw.AlertDialog(heading="Run a Command")
        entry = Gtk.Entry(text=value if kind == "command" and not app_of(value) and value != INK else "",
                          activates_default=True,
            placeholder_text="e.g. nautilus ~/Downloads")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("set", "Set")
        dialog.set_response_appearance("set", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("set")

        def response(_d, answer):
            command = entry.get_text().strip()
            if answer == "set" and command:
                top.set_command(self.gesture, self.accel, f"Pen: {command}", command)
                self.buttons.refresh()
                self.window.nav.pop()

        dialog.connect("response", response)
        dialog.present(self.window)


class ButtonsPage(Adw.PreferencesPage):
    def __init__(self, window):
        super().__init__(title="Buttons", icon_name="input-keyboard-symbolic")
        self.window = window
        self.top = TopButtons()
        self.stylus = Gio.Settings.new_with_path(STYLUS_SCHEMA, STYLUS_PATH)

        group = Adw.PreferencesGroup(title="Top button",
                                     description="The button at the pen's back end")
        self.rows = []
        for gesture, label, accel in GESTURES:
            row = Adw.ActionRow(title=label, activatable=True)
            row.icon = Gtk.Image(pixel_size=32)
            row.add_prefix(row.icon)
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.gesture, row.label, row.accel = gesture, label, accel
            row.connect("activated", self._open)
            group.add(row)
            self.rows.append(row)
        self.add(group)
        self.refresh()

        side = Adw.PreferencesGroup(title="Side button")
        self.side = Adw.ComboRow(title="When pressed",
                                 model=Gtk.StringList.new([s[1] for s in SIDE_ACTIONS]))
        ids = [s[0] for s in SIDE_ACTIONS]
        current = self.stylus.get_string("button-action")
        self.side.set_selected(ids.index(current) if current in ids else 0)
        self.side.connect("notify::selected", lambda r, _p: self.stylus.set_string(
            "button-action", ids[r.get_selected()]))
        side.add(self.side)
        self.add(side)

    def refresh(self):
        for row in self.rows:
            title, icon = describe(self.top, row.gesture, row.accel)
            row.set_subtitle(GLib.markup_escape_text(title))
            if isinstance(icon, str):
                row.icon.set_from_icon_name(icon)
            else:
                row.icon.set_from_gicon(icon)

    def _open(self, row):
        self.window.nav.push(ActionChooserPage(self.window, self, row.gesture,
                                               row.label, row.accel))


class TouchPage(Adw.PreferencesPage):
    def __init__(self, window):
        super().__init__(title="Touch", icon_name="input-touchpad-symbolic")
        self.window = window
        conf = self._read()

        group = Adw.PreferencesGroup(
            title="Touchscreen",
            description="Handled by iptsd; applying asks for your password")
        self.pen_near = Adw.SwitchRow(title="Ignore touch while the pen is near",
                                      subtitle="Your hand can rest on the screen while writing")
        self.pen_near.set_active(conf.get("DisableOnStylus", "true") == "true")
        self.palm = Adw.SwitchRow(title="Palm rejection",
                                  subtitle="Ignore all touches while a palm lies on the screen")
        self.palm.set_active(conf.get("DisableOnPalm", "true") == "true")
        group.add(self.pen_near)
        group.add(self.palm)

        self.sensitivity = Adw.SpinRow.new_with_range(1, 10, 1)
        self.sensitivity.set_title("Sensitivity")
        self.sensitivity.set_subtitle("Higher picks up lighter touches "
                                      "(and in the end, phantom ones)")
        threshold = int(conf.get("ActivationThreshold", "16"))
        self.sensitivity.set_value(max(1, min(10, (30 - threshold) // 2)))
        group.add(self.sensitivity)
        self.add(group)

        apply_group = Adw.PreferencesGroup()
        apply = Gtk.Button(label="Apply", halign=Gtk.Align.END)
        apply.add_css_class("suggested-action")
        apply.add_css_class("pill")
        apply.connect("clicked", self._apply)
        apply_group.add(apply)
        self.add(apply_group)

    def _read(self):
        values = {}
        try:
            for line in IPTSD_CONF.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = (p.strip() for p in line.split("=", 1))
                    values[key] = value.lower()
        except OSError:
            pass
        return values

    def _apply(self, _button):
        # sensitivity 1..10 -> ActivationThreshold 28..10 (7 = 16, the tuned default)
        threshold = 30 - 2 * int(self.sensitivity.get_value())
        args = ["pkexec", str(HERE / "pen-touch-apply"),
                "true" if self.pen_near.get_active() else "false",
                "true" if self.palm.get_active() else "false",
                str(threshold), str(max(4, threshold - 4))]
        try:
            proc = Gio.Subprocess.new(args, Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            self.window.toast(f"Could not apply: {e.message}")
            return

        def done(p, result):
            try:
                p.communicate_utf8_finish(result)
                ok = p.get_successful()
            except GLib.Error:
                ok = False
            self.window.toast("Touch settings applied" if ok else "Not applied")

        proc.communicate_utf8_async(None, None, done)


class PenWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Pen")
        self.set_default_size(620, 820)
        self.toasts = Adw.ToastOverlay()
        stack = Adw.ViewStack()
        for name, page in (("pen", PenPage(self)), ("buttons", ButtonsPage(self)),
                           ("touch", TouchPage(self))):
            stack.add_titled_with_icon(page, name, page.get_title(), page.get_icon_name())
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.ViewSwitcher(stack=stack,
                                                 policy=Adw.ViewSwitcherPolicy.WIDE))
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(stack)
        # pages like the action chooser slide in over the tabs
        self.nav = Adw.NavigationView()
        self.nav.add(Adw.NavigationPage(title="Pen", child=view))
        self.toasts.set_child(self.nav)
        self.set_content(self.toasts)

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text))


class PenApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        (self.get_active_window() or PenWindow(self)).present()


if __name__ == "__main__":
    sys.exit(PenApp().run(sys.argv))
