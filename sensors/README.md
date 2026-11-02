# Sensor hub (auto-rotation)

The accelerometer, gyro and light sensor sit behind the Ice Lake sensor hub
(ISH, PCI 8086:34fc). The stock 6.19 `intel_ish_ipc` never finishes the hub's
start-up handshake ("HBM haven't started", linux-surface#2140), so there is no
auto-rotation. `camera/patches/intel-ish-ipc/` reverts the 6.19 handshake
changes; built by `camera/build.sh`.

What hangs the machine is bringing the hub up again after a sleep it didn't
survive: the driver's own re-initialisation on resume (when the hub was
powered off or didn't answer the resume message), and equally unbinding the
driver before sleep and binding it after (tried 2026-10-15, froze on bind).
Before the hub stopped answering, sleeps with it bound were fine: it naps in
D0i3 and wakes with a message.

- `camera/patches/intel-ish-ipc/0002`: if the hub didn't survive a sleep,
  the driver removes its sensors and leaves it off ("sensor hub ... not
  re-initialising it" in the kernel log): no rotation until the next boot,
  instead of a hung machine. `reinit_after_sleep=1` brings the old behaviour
  back for experiments.
- `surface-ish.conf` (`/etc/modprobe.d`): the stock driver is blacklisted, also
  in the initramfs. Once it has failed the handshake, only a cold start
  brings the hub back.
- `surface-ish.service` → `surface-ish`: loads the patched module from
  `/usr/local/lib/surface-kit/<kernel>/` (not the module tree, so nothing
  loads it at boot behind our back). Booting with `surface_kit.noish` on the
  kernel command line skips it (GRUB: `e`, add it to the `linux` line).
- `surface-sensors-sleep` (`/usr/lib/systemd/system-sleep/surface-sensors`):
  after a longer sleep the hub still answers direct reads but the data stream
  iio-sensor-proxy reads stays silent (rotation stuck at the old
  orientation); 3 s after every wake it restarts iio-sensor-proxy.

Install (then power off fully and start again; a reboot may not reset the
hub):

    sudo sensors/install.sh
    sudo sensors/install.sh --remove     # back to the stock driver

After a kernel update: `camera/build.sh`, then `sensors/install.sh` again
(without a build for the running kernel the service does nothing). A kernel from
`kernel/` already has the patches in tree, so it only needs `sensors/install.sh`.
