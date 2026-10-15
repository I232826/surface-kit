// surface-kit shell helper: D-Bus methods on GNOME Shell's own bus name for
// what Wayland doesn't let other programs do themselves.
//
//   gdbus call --session --dest org.gnome.Shell \
//     --object-path /io/github/surfacekit/Shell \
//     --method io.github.surfacekit.Shell.ActivateApp org.gnome.Nautilus.desktop
//
// ActivateApp does what a click on the app in the dock does: focus its most
// recent window if it runs (with a fresh timestamp, see below), start it if not. Returns false for an unknown id.
// When GNOME hasn't tied an open window to the app (its Wayland app id is
// neither the desktop id nor StartupWMClass, like Saber's
// com.adilhanney.saber), a window whose class or app id matches any of the
// desktop file's names is brought forward instead of starting another copy.
//
// ListWindows returns (class, instance, gtk app id, sandboxed app id, the app
// GNOME tied it to, title) for each window, to see why matching fails.
//
// Screenshot(path) saves the whole screen as a PNG, for apps/ink. It is
// only answered for that app (its script in the caller's command line):
// anything else on the bus would otherwise get silent screenshots past
// GNOME's screenshot permission.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

Gio._promisify(Shell.Screenshot.prototype, 'screenshot');
Gio._promisify(Gio.DBusConnection.prototype, 'call');

// the only caller Screenshot answers: apps/ink/ink.py
const INK_SCRIPT = '/surface-kit/apps/ink/ink.py';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const IFACE = `<node>
  <interface name="io.github.surfacekit.Shell">
    <method name="ActivateApp">
      <arg type="s" direction="in" name="desktop_id"/>
      <arg type="b" direction="out" name="found"/>
    </method>
    <method name="Screenshot">
      <arg type="s" direction="in" name="path"/>
      <arg type="b" direction="out" name="done"/>
    </method>
    <method name="ListWindows">
      <arg type="a(ssssss)" direction="out" name="windows"/>
    </method>
  </interface>
</node>`;

export default class SurfaceKitShellExtension extends Extension {
    enable() {
        this._impl = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._impl.export(Gio.DBus.session, '/io/github/surfacekit/Shell');
    }

    disable() {
        this._impl?.unexport();
        this._impl = null;
    }

    ActivateApp(desktopId) {
        const id = desktopId.endsWith('.desktop') ? desktopId : `${desktopId}.desktop`;
        const app = Shell.AppSystem.get_default().lookup_app(id);
        if (!app)
            return false;
        // A D-Bus call is no input event: without a current timestamp mutter's
        // focus stealing prevention only marks the window as wanting attention.
        const time = global.display.get_current_time_roundtrip();
        const window = app.get_windows()[0] ?? this._findWindow(app, id);
        if (window) {
            Main.activateWindow(window, time);
            return true;
        }
        app.activate_full(-1, time);
        return true;
    }

    async ScreenshotAsync(params, invocation) {
        const [path] = params;
        try {
            if (!await this._callerIsInk(invocation))
                throw new Error('not the surface-kit ink app');
            const file = Gio.File.new_for_path(path);
            const stream = file.replace(null, false, Gio.FileCreateFlags.NONE, null);
            await new Shell.Screenshot().screenshot(false, stream);
            stream.close(null);
            invocation.return_value(new GLib.Variant('(b)', [true]));
        } catch (e) {
            invocation.return_error_literal(Gio.DBusError, Gio.DBusError.ACCESS_DENIED,
                `Screenshot failed: ${e.message}`);
        }
    }

    async _callerIsInk(invocation) {
        const [pid] = (await invocation.get_connection().call(
            'org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus',
            'GetConnectionUnixProcessID', new GLib.Variant('(s)', [invocation.get_sender()]),
            new GLib.VariantType('(u)'), Gio.DBusCallFlags.NONE, -1, null)).deepUnpack();
        const [ok, bytes] = GLib.file_get_contents(`/proc/${pid}/cmdline`);
        if (!ok)
            return false;
        // started through a link such as ~/.local/bin/ink: follow it
        const real = arg => GLib.file_test(arg, GLib.FileTest.IS_SYMLINK)
            ? GLib.file_read_link(arg) : arg;
        const args = new TextDecoder().decode(bytes).split('\0');
        return args.some(arg => arg && real(arg).endsWith(INK_SCRIPT));
    }

    ListWindows() {
        const tracker = Shell.WindowTracker.get_default();
        return global.get_window_actors().map(actor => {
            const w = actor.get_meta_window();
            return [w.get_wm_class() ?? '', w.get_wm_class_instance() ?? '',
                w.get_gtk_application_id() ?? '', w.get_sandboxed_app_id() ?? '',
                tracker.get_window_app(w)?.get_id() ?? '', w.get_title() ?? ''];
        });
    }

    // Names the app's windows may carry: the desktop id, StartupWMClass,
    // the Snap/Flatpak ids, each also by its last dotted part.
    _names(app, id) {
        const info = app.get_app_info();
        const names = [id.replace(/\.desktop$/, ''), info?.get_startup_wm_class(),
            info?.get_string('X-SnapCommonID'), info?.get_string('X-SnapInstanceName'),
            info?.get_string('X-Flatpak')];
        const all = new Set();
        for (const name of names) {
            if (!name)
                continue;
            all.add(name.toLowerCase());
            all.add(name.toLowerCase().split('.').pop());
        }
        return all;
    }

    _findWindow(app, id) {
        const names = this._names(app, id);
        const windows = global.display.list_all_windows()
            .filter(w => !w.skip_taskbar && [w.get_wm_class(), w.get_wm_class_instance(),
                w.get_gtk_application_id(), w.get_sandboxed_app_id()]
                .some(n => n && (names.has(n.toLowerCase()) ||
                    names.has(n.toLowerCase().split('.').pop()))));
        // the one used last
        windows.sort((a, b) => b.get_user_time() - a.get_user_time());
        return windows[0] ?? null;
    }
}
