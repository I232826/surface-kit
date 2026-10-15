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

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const IFACE = `<node>
  <interface name="io.github.surfacekit.Shell">
    <method name="ActivateApp">
      <arg type="s" direction="in" name="desktop_id"/>
      <arg type="b" direction="out" name="found"/>
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
