#!/bin/bash
# System fixes for the Surface Pro 7: sudo system/install.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

# Clock: the firmware loads the RTC at every boot from a clock in the
# embedded controller that runs over a year behind and can't be set from
# Linux (ACPI _SRT is accepted and ignored; UEFI SetTime only reaches the
# CMOS RTC, which the firmware overwrites again). Have chrony restore at
# least the time of the last shutdown (its drift file's mtime) at boot
# whenever the RTC is behind that; NTP corrects the rest once online.
echo ">> chrony: restore the last known time at boot (-s)"
if ! grep -qE '^DAEMON_OPTS=.*(^|[" ])-s([" ]|$)' /etc/default/chrony; then
    sed -i -E 's/^DAEMON_OPTS="([^"]*)"/DAEMON_OPTS="\1 -s"/' /etc/default/chrony
fi
grep '^DAEMON_OPTS' /etc/default/chrony

# Remove the earlier attempt that wrote the time to the firmware clock
# (ACPI000E/_SRT): the firmware ignores it.
if [ -e /etc/systemd/system/surface-tad-sync.service ]; then
    systemctl disable --now surface-tad-sync.service || true
    rm -f /etc/systemd/system/surface-tad-sync.service /usr/local/sbin/surface-tad-sync
    systemctl daemon-reload
fi

systemctl restart chrony
