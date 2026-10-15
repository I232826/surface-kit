# Audio (Surface Pro 7: legacy HDA, Realtek ALC274)

One stereo speaker pin (0x1b), headphone jack (0x21), internal mic array
on pin 0x12. PipeWire/WirePlumber with the stock alsa-card-profile.

## Internal mic

The stock path merges "Internal Mic Boost" (+0/10/20/30 dB) and "Capture"
(-17.25..+30 dB) into the input slider, so 100% meant +60 dB and speech
clipped hard. Measured with `mic-test.sh` + `mic-levels.py` (capture at
0 dB, normal speech at laptop distance):

| boost | peak      | clipped | speech  | SNR   |
|-------|-----------|---------|---------|-------|
| +0    | -26.5 dBFS| 0       | -36 dB  | 20 dB |
| +10   | -18.4     | 0       | -32     | 19    |
| +20   | -8.9      | 0       | -20     | 26    |
| +30   | 0.0       | 12      | -11     | 22    |

`alsa-card-profile/mixer/paths/analog-input-internal-mic.conf` fixes the
boost at +20 dB and caps the slider at 0 dB capture gain. `install.sh`
puts it in `~/.config/alsa-card-profile` (no root) and restarts
WirePlumber.

## Speakers

Sometimes silent while everything is routed and unmuted (internal sink
default, Speaker/Master on). Suspect: codec power saving (snd_hda_intel
power_save=1 s by default) not bringing the speaker amp back.
`camera/install/surface-kit.conf` sets power_save=0 (live:
`echo 0 | sudo tee /sys/module/snd_hda_intel/parameters/power_save`).
Unconfirmed: next time it is silent, record `wpctl status`, `amixer -c0
sget Speaker/Master`, power_save, and the codec's EAPD/pin state.
