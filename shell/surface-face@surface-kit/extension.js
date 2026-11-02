// Face unlock animation, on the desktop, lock and login screens. Separate from
// surface-kit-shell, whose D-Bus methods must not stay up while the screen is
// locked. See faceOverlay.js.

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

import {FaceOverlay} from './faceOverlay.js';

export default class SurfaceFaceExtension extends Extension {
    enable() {
        this._overlay = new FaceOverlay();
    }

    disable() {
        this._overlay?.destroy();
        this._overlay = null;
    }
}
