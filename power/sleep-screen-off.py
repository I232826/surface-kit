#!/usr/bin/env python3
"""Turn the screen off the moment the system is asked to sleep.

Between the power button press and the actual suspend the system spends
~0.8 s getting ready (GNOME locking the screen, NetworkManager, ...) with
the screen still lit. It looks as if nothing happened, a second press
follows, and that press wakes the Surface right back up. logind announces
the sleep (PrepareForSleep) right at the press: blank the display through
Mutter then, and switch it back on when the system wakes.

Runs as a user service (power/surface-sleep-screen-off.service).
"""
from gi.repository import Gio, GLib

MUTTER = ("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig")
OFF, ON = 3, 0

session = Gio.bus_get_sync(Gio.BusType.SESSION)
system = Gio.bus_get_sync(Gio.BusType.SYSTEM)


def power_save(mode):
    try:
        session.call_sync(
            MUTTER[0], MUTTER[1], "org.freedesktop.DBus.Properties", "Set",
            GLib.Variant("(ssv)", (MUTTER[0], "PowerSaveMode", GLib.Variant("i", mode))),
            None, Gio.DBusCallFlags.NONE, 500, None)
    except GLib.Error as err:
        print(f"PowerSaveMode {mode}: {err.message}", flush=True)


def prepare_for_sleep(_conn, _sender, _path, _iface, _signal, params):
    going = params.unpack()[0]
    power_save(OFF if going else ON)


system.signal_subscribe(
    "org.freedesktop.login1", "org.freedesktop.login1.Manager", "PrepareForSleep",
    "/org/freedesktop/login1", None, Gio.DBusSignalFlags.NONE, prepare_for_sleep)
GLib.MainLoop().run()
