// Animated auto-rotation for GNOME Shell (surface-kit).
//
// Mutter rotates the screen from an idle callback after iio-sensor-proxy
// reports a new AccelerometerOrientation. We watch the same D-Bus property
// on the same connection: our handler runs at default priority, before that
// idle, so the old screen can still be captured. Once the monitors change,
// the capture is shown tilted the way it now physically sits and eased
// upright and to its new size while fading into the new layout.
//
// The accelerometer is not claimed here: the claim belongs to Mutter (same
// D-Bus sender), and the property signals reach us because it holds it.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Graphene from 'gi://Graphene';
import Mtk from 'gi://Mtk';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Mutter's transform per orientation, degrees counter-clockwise.
const TRANSFORM = {'normal': 0, 'left-up': 90, 'bottom-up': 180, 'right-up': 270};
// +1: Clutter's z rotation turns clockwise on screen (y points down).
const ROTATION_SIGN = 1;
const ROTATE_MS = 380;
const FADE_MS = 220;
const FADE_DELAY_MS = 220;
// The capture is only used if the monitors change this soon after it.
const PENDING_MS = 1500;

const SensorProxyIface = `<node>
  <interface name="net.hadess.SensorProxy">
    <property name="AccelerometerOrientation" type="s" access="read"/>
  </interface>
</node>`;
const SensorProxy = Gio.DBusProxy.makeProxyWrapper(SensorProxyIface);

export default class SurfaceRotateExtension extends Extension {
    enable() {
        this._pending = null;
        this._overlay = null;
        this._orientation = null;
        this._proxy = new SensorProxy(Gio.DBus.system,
            'net.hadess.SensorProxy', '/net/hadess/SensorProxy',
            (proxy, error) => {
                if (error)
                    return;
                this._orientation = proxy.AccelerometerOrientation;
            }, null, Gio.DBusProxyFlags.DO_NOT_AUTO_START);
        this._proxyId = this._proxy.connect('g-properties-changed',
            (proxy, changed) => {
                if (changed.lookup_value('AccelerometerOrientation', null))
                    this._onOrientation(proxy.AccelerometerOrientation);
            });
        this._monitorsId = Main.layoutManager.connect('monitors-changed',
            () => this._onMonitorsChanged());
    }

    disable() {
        Main.layoutManager.disconnect(this._monitorsId);
        this._proxy.disconnect(this._proxyId);
        this._proxy = null;
        this._pending = null;
        this._overlay?.destroy();
        this._overlay = null;
    }

    _onOrientation(orientation) {
        const from = this._orientation;
        this._orientation = orientation;
        if (!(from in TRANSFORM) || !(orientation in TRANSFORM) || from === orientation)
            return;

        let delta = (TRANSFORM[orientation] - TRANSFORM[from] + 360) % 360;
        if (delta > 180)
            delta -= 360;

        const width = global.screen_width;
        const height = global.screen_height;
        const rect = new Mtk.Rectangle({x: 0, y: 0, width, height});
        const [, , , scale] = global.stage.get_capture_final_size(rect);
        let content;
        try {
            content = global.stage.paint_to_content(rect, scale, null,
                Clutter.PaintFlag.NO_CURSORS);
        } catch (e) {
            logError(e, 'surface-rotate: capture failed');
            return;
        }
        this._pending = {content, width, height, delta, time: GLib.get_monotonic_time()};
    }

    _onMonitorsChanged() {
        const p = this._pending;
        this._pending = null;
        if (!p || GLib.get_monotonic_time() - p.time > PENDING_MS * 1000)
            return;

        const width = global.screen_width;
        const height = global.screen_height;
        const quarter = Math.abs(p.delta) === 90;
        if (quarter ? width !== p.height || height !== p.width
            : width !== p.width || height !== p.height)
            return;

        this._overlay?.destroy();
        const overlay = new St.Widget({
            x: 0, y: 0, width, height,
            style: 'background-color: black;',
        });
        const snap = new Clutter.Actor({
            content: p.content,
            width: p.width,
            height: p.height,
            x: (width - p.width) / 2,
            y: (height - p.height) / 2,
            pivot_point: new Graphene.Point({x: 0.5, y: 0.5}),
            rotation_angle_z: ROTATION_SIGN * p.delta,
        });
        overlay.add_child(snap);
        Main.uiGroup.add_child(overlay);
        Main.uiGroup.set_child_above_sibling(overlay, null);
        this._overlay = overlay;

        const fit = quarter ? Math.min(width / p.width, height / p.height) : 1;
        snap.ease({
            rotation_angle_z: 0,
            scale_x: fit,
            scale_y: fit,
            duration: ROTATE_MS,
            mode: Clutter.AnimationMode.EASE_OUT_CUBIC,
        });
        overlay.ease({
            opacity: 0,
            duration: FADE_MS,
            delay: FADE_DELAY_MS,
            mode: Clutter.AnimationMode.EASE_IN_QUAD,
            onStopped: () => {
                overlay.destroy();
                if (this._overlay === overlay)
                    this._overlay = null;
            },
        });
    }
}
