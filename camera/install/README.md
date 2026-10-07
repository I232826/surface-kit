# Camera autostart

`sudo camera/install/install.sh` installs the patched modules from
`camera/out/<kernel>/` into `/lib/modules/<kernel>/updates/surface-kit`
(they take precedence over the stock ov5693/ov8865/dw9719), the module
options and blacklist in `/etc/modprobe.d/surface-kit.conf`, and
`surface-camera.service`, which runs `/usr/local/sbin/surface-camera-load`
at boot.

- The IPU modules are blacklisted from auto-loading; only the service loads
  them, after switching the IPU's IOMMU group to passthrough. Loading them
  before that freezes the machine.
- Passthrough means the IPU can DMA to all of memory, as if there were no
  IOMMU for that one device.
- After a kernel update the service finds no modules and skips; rebuild
  (`camera/build.sh`) and rerun `install.sh`.
- `camera/scripts/debug-isys.sh` stays the tool for load-time debugging.

Remove: `sudo systemctl disable surface-camera`, delete
`/etc/modprobe.d/surface-kit.conf` and
`/lib/modules/*/updates/surface-kit`, run `sudo depmod`.
