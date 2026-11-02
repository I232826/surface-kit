// The face unlock animation ("Strobe", ROADMAP.md), drawn by the shell because on
// Wayland nothing else can stay above other windows without taking the focus
// from the terminal asking for sudo. It sits under the front camera, follows
// /run/surface-kit-face/state (face/surface_face_status.py) and takes no input.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const STATE_PATH = '/run/surface-kit-face/state';
const SIZE = 104;
const RING = 84;
const DOT = 14;
const GREY = '#d3d1c7';
const TEAL = [0x5d / 255, 0xca / 255, 0xa5 / 255];
const CORAL = '#f0997b';
const PULSE_MS = 1500;
const PULSE_GAP_MS = 500;
const CHECK_MS = 450;
const MATCH_HOLD_MS = 1000;
const FAIL_HOLD_MS = 1000;
const FAIL_FADE_MS = 800;
const FADE_MS = 200;
// howdy looks for up to 15 s (apps/face); never leave the picture up if it dies
const SCAN_LIMIT_S = 30;

export class FaceOverlay {
    constructor() {
        this._last = '';
        this._sources = new Set();
        this._file = Gio.File.new_for_path(STATE_PATH);
        this._monitor = this._file.monitor_file(Gio.FileMonitorFlags.NONE, null);
        this._monitor.connect('changed', () => this._read());
        // what's there from before this session is old news
        this._read(true);
    }

    destroy() {
        this._monitor.cancel();
        this._clear();
        this._tile?.destroy();
        this._tile = null;
    }

    _read(quiet = false) {
        let line;
        try {
            const [, bytes] = this._file.load_contents(null);
            line = new TextDecoder().decode(bytes).trim();
        } catch {
            return;
        }
        if (line === this._last)
            return;
        this._last = line;
        if (quiet)
            return;
        const state = line.split(' ')[0];
        if (state === 'scan')
            this._scan();
        else if (state === 'match')
            this._match();
        else if (state === 'fail')
            this._fail();
        else
            this._hide();
    }

    _build() {
        if (this._tile)
            return;
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        this._scale = scale;
        this._tile = new St.Widget({
            style: 'background-color: #1c1c1a; border-radius: 24px;',
            width: SIZE * scale, height: SIZE * scale,
            reactive: false, visible: false,
        });
        this._rings = [0, 1, 2].map(() => this._circle(RING, `border: 2px solid ${GREY};`));
        this._failRing = this._circle(RING * 0.7, `border: 2px solid ${CORAL};`);
        this._dot = this._circle(DOT, '');
        this._check = new St.DrawingArea({width: SIZE * scale, height: SIZE * scale, reactive: false});
        this._check.connect('repaint', area => this._drawCheck(area));
        this._tile.add_child(this._check);
        Main.layoutManager.addTopChrome(this._tile, {affectsInputRegion: false});
    }

    _circle(size, style) {
        const px = size * this._scale;
        const circle = new St.Widget({
            style: `border-radius: ${size / 2}px; ${style}`,
            width: px, height: px,
            x: (SIZE * this._scale - px) / 2, y: (SIZE * this._scale - px) / 2,
            reactive: false,
        });
        circle.set_pivot_point(0.5, 0.5);
        this._tile.add_child(circle);
        return circle;
    }

    _clear() {
        for (const id of this._sources)
            GLib.source_remove(id);
        this._sources.clear();
        this._state = null;
        this._checkTimeline?.stop();
        this._checkTimeline = null;
        if (!this._tile)
            return;
        this._tile.remove_all_transitions();
        for (const actor of [...this._rings, this._failRing, this._dot])
            actor.remove_all_transitions();
    }

    _after(ms, callback) {
        const id = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            this._sources.delete(id);
            callback();
            return GLib.SOURCE_REMOVE;
        });
        this._sources.add(id);
    }

    _present() {
        const monitor = Main.layoutManager.primaryMonitor;
        const size = SIZE * this._scale;
        this._tile.set_position(monitor.x + (monitor.width - size) / 2,
            monitor.y + Main.panel.height + 12 * this._scale);
        this._tile.show();
        if (this._tile.opacity !== 255) {
            this._tile.ease({opacity: 255, duration: FADE_MS,
                mode: Clutter.AnimationMode.EASE_OUT_QUAD});
        }
        for (const ring of this._rings)
            ring.opacity = 0;
        this._failRing.opacity = 0;
        this._progress = 0;
        this._check.queue_repaint();
    }

    _setDot(color) {
        this._dot.set_style(`border-radius: ${DOT / 2}px; background-color: ${color};`);
        this._dot.set_scale(1, 1);
        this._dot.opacity = 255;
    }

    _scan() {
        this._build();
        this._clear();
        this._state = 'scan';
        this._tile.opacity = this._tile.visible ? this._tile.opacity : 0;
        this._present();
        this._setDot(GREY);
        if (St.Settings.get().enable_animations) {
            this._rings.forEach((ring, i) => this._after(i * PULSE_GAP_MS + 1, () => this._pulse(ring)));
        } else {
            // eased actors finish at once with animations off: no pulsing, a still picture
            this._rings[0].set_scale(1, 1);
            this._rings[0].opacity = 255;
        }
        this._after(SCAN_LIMIT_S * 1000, () => this._hide());
    }

    _pulse(ring) {
        if (this._state !== 'scan')
            return;
        ring.set_scale(0.25, 0.25);
        ring.opacity = 230;
        ring.ease({
            scale_x: 1, scale_y: 1, opacity: 0, duration: PULSE_MS,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onStopped: finished => {
                if (finished)
                    this._pulse(ring);
            },
        });
    }

    _match() {
        this._build();
        this._clear();
        this._state = 'match';
        if (!this._tile.visible)
            this._tile.opacity = 0;
        this._present();
        this._dot.opacity = 0;
        this._checkTimeline = new Clutter.Timeline({actor: this._check, duration: CHECK_MS});
        this._checkTimeline.connect('new-frame', timeline => {
            this._progress = timeline.get_progress();
            this._check.queue_repaint();
        });
        this._checkTimeline.connect('completed', () => {
            this._progress = 1;
            this._check.queue_repaint();
        });
        this._checkTimeline.start();
        this._after(CHECK_MS + MATCH_HOLD_MS, () => this._fadeOut(FADE_MS));
    }

    _drawCheck(area) {
        const cr = area.get_context();
        const progress = this._progress ?? 0;
        if (progress > 0) {
            const [width] = area.get_surface_size();
            const k = width / 100;
            // the check mark, from the short stroke to the long one
            const a = [33, 51], b = [46, 64], c = [69, 38];
            const first = Math.hypot(b[0] - a[0], b[1] - a[1]);
            const second = Math.hypot(c[0] - b[0], c[1] - b[1]);
            const drawn = progress * (first + second);
            cr.setSourceRGB(...TEAL);
            cr.setLineWidth(5 * k);
            cr.setLineCap(1);
            cr.setLineJoin(1);
            cr.moveTo(a[0] * k, a[1] * k);
            if (drawn <= first) {
                const t = drawn / first;
                cr.lineTo((a[0] + (b[0] - a[0]) * t) * k, (a[1] + (b[1] - a[1]) * t) * k);
            } else {
                const t = (drawn - first) / second;
                cr.lineTo(b[0] * k, b[1] * k);
                cr.lineTo((b[0] + (c[0] - b[0]) * t) * k, (b[1] + (c[1] - b[1]) * t) * k);
            }
            cr.stroke();
        }
        cr.$dispose();
    }

    _fail() {
        this._build();
        this._clear();
        this._state = 'fail';
        if (!this._tile.visible)
            this._tile.opacity = 0;
        this._present();
        this._setDot(CORAL);
        const mode = Clutter.AnimationMode.EASE_OUT_QUAD;
        this._failRing.set_scale(1, 1);
        this._failRing.opacity = 255;
        this._failRing.ease({scale_x: 0.8, scale_y: 0.8, duration: FAIL_HOLD_MS, mode});
        this._after(FAIL_HOLD_MS, () => {
            this._failRing.ease({scale_x: 0.6, scale_y: 0.6, opacity: 0, duration: FAIL_FADE_MS, mode});
            this._dot.ease({scale_x: 0.7, scale_y: 0.7, opacity: 0, duration: FAIL_FADE_MS, mode});
            this._fadeOut(FAIL_FADE_MS);
        });
    }

    _fadeOut(duration) {
        this._tile.ease({
            opacity: 0, duration, mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onStopped: finished => {
                if (finished)
                    this._tile.hide();
            },
        });
    }

    _hide() {
        if (!this._tile)
            return;
        this._clear();
        this._fadeOut(FADE_MS);
    }
}
