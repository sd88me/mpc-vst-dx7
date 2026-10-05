# Dexed (DX7) VST Plugin for MPC OS

💬 Questions or feedback? Join the [Open MPC Discord](https://discord.gg/sRRysZSgu3).

> **MPC OS.** From 1.0.6 the skin is written in the format **MPC OS 2.x** draws, which MPC OS 3.x reads too, so the catalog
> labels this release "MPC OS 2.x + 3.x". That label is a check of the skin and library against MPC OS 2.15.1's own skins,
> not a test of this release on a 2.x unit. This exact skin (the 2.x shape with the new BANKS page) had not been tried on
> any device when 1.0.6 was released: the 2.x shape with 1.0.4's pages worked on a Force and on a 2.15.1 MPC Live, and
> 1.0.5's BANKS page worked on a Force in the 3.x shape. Reports from 2.x and 3.x units are welcome; 1.0.5 is the
> fallback (3.x only).
> See [MPC OS 2.x vs 3.x](https://github.com/sd88me/mpc-vst-plugins#mpc-os-2x-vs-3x) in the main repo.

**Dexed (DX7)** as a native VST2 instrument for Akai MPC OS standalone devices (MPC Live/One/X/Key,
Force). It loads in MPC's built-in plugin host and has its own touchscreen skin with Q-Link support.

Current release: **v1.0.6** — see [Releases](https://github.com/sd88me/mpc-vst-dx7/releases).

## Screenshots

<img width="640" height="400" alt="2026-09-29T100343483Z" src="https://github.com/user-attachments/assets/be0c4576-9921-4fca-894b-85747d8ebd08" /><img width="640" height="400" alt="2026-09-29T100347135Z" src="https://github.com/user-attachments/assets/bc4792a0-3c24-4faa-96d3-910613d4506f" /><img width="640" height="400" alt="2026-09-29T100358065Z" src="https://github.com/user-attachments/assets/71fb35f1-e361-4171-98be-2c9c179aad13" />

## Features

- Yamaha DX7-style 6-operator FM synthesis (the Dexed/MSFA engine), with all 32 algorithms, feedback,
  oscillator sync, the LFO (six waveforms, key sync) and the pitch envelope.
- **GLOBAL page**: bank and patch steppers with live names along the top, then voice (preset, algorithm,
  feedback, output, octave, transpose, oscillator sync), LFO and pitch envelope.
- **OP1-6 pages**: one page per operator with level, coarse, fine, detune, velocity sensitivity, amp
  mod sensitivity, rate scaling, RATIO/FIXED mode, key scaling (breakpoint, depths, curves), the
  four-stage envelope and an **ON** switch that mutes the operator. A small diagram of the current
  algorithm sits on every operator page.
- **ALGORITHM page**: Dexed's own diagram for each of the 32 algorithms (drawn from Dexed's layout
  table), following the algorithm and feedback knobs and the patch you load.
- **BANKS page**: a paginated list of every `.syx` bank on the device and the 32 patches of the loaded
  bank; tap a bank to load it, tap a patch to play it. Both lists number top to bottom (carts 1-11 down the left
  column, then 12-22; patches 1-16, then 17-32), and the bank and patch each have a stepper with arrows. The page
  follows the bank you select, so stepping with a Q-Link or the wheel never leaves the highlight off screen.
- **`.syx` carts**: single 4104-byte banks or multi-bank ROM dumps (any size that is an exact multiple
  of 4104 bytes). A set of factory banks is included in the release zip.
- 16 Q-Links per page, following the page you are on. On the BANKS page they are bank, patch, page back and page
  forward: a Q-Link turn or a wheel click moves one cart or one patch. The left and right key-scaling curves on the
  operator pages take three Q-Link events per option, so a turn no longer races through the four curves.
- Dark slate panel with the DX7's "DX Green" accent and a light-grey LCD-style readout for bank and
  patch names.

## Requirements

- A first-generation MPC OS standalone device (32-bit ARM: Force, MPC Live / Live II, One, X, Key 61).
  Tested on a Force.
- Root SSH access to the device. Installing plugins this way is unofficial: back up first, use at your
  own risk.

## Install

1. Download `Dexed-DX7-1.0.0-mpc-armv7.zip` from the [latest release](https://github.com/sd88me/mpc-vst-dx7/releases/latest)
   and unzip it.
2. Copy the folder to the device and run the installer (it stops MPC, so save your project first):

   ```
   scp -r Dexed-DX7-1.0.0 root@<device-ip>:/tmp/
   ssh root@<device-ip> sh /tmp/Dexed-DX7-1.0.0/install.sh
   ```

3. Add **Dexed (DX7)** to a track from the plugin browser (Instrument plugins).

The zip's `INSTALL.md` has the manual steps and the uninstall command. Running the installer again
upgrades in place. After replacing the plugin file on a running device, remove and re-insert the plugin
on any track that uses it. If you had 0.4.0 (called "DX7 (Dexed)"), the old skin folder
`/sdcard/Synths/sd88me - VST - DX7 (Dexed)` is left behind and can be deleted.

### Bank and patch carts

The plugin reads `.syx` files from the `dx7_carts` folder inside its own plugin folder
(`/sdcard/Synths/sd88me - VST - Dexed (DX7)/dx7_carts`). The installer puts the factory banks there; drop your own files in the same folder and they appear in the bank stepper on the
GLOBAL page and in the BANKS page's list.

## Build from source

Needs a sibling checkout of [mpc-vst-plugins](https://github.com/sd88me/mpc-vst-plugins) (the shared
wrapper, `build_port.sh`, skin tooling) at `../mpc-vst-plugins`, or set `MPC_VST` to point at one.
Docker (with QEMU for arm32v7) is needed by its build pipeline.

```
./build.sh
```

Output in `build/`: `dx7_dexed.so`, the skin folder, and `pluginlist-entry.xml`. No third-party source is
fetched at build time. To put a build on a device, package it and use the installer (the plugin is one folder in
`/sdcard/Synths`, so there is nothing to copy by hand):

```
./release.sh <version>      # dist/Dexed-DX7-<version>-mpc-armv7.zip, then install it as described above
```

A skin-only change needs no MPC restart: re-insert the plugin or reload the project. Registering the
plugin in `MPC.settings` and the rest of the device workflow are in `mpc-vst-plugins`'
`docs/PORTING.md` and `.claude/skills/mpc-vst-plugin/SKILL.md`.

The skin fonts `EurostileExtendedBlack.ttf`, `Helvetica.ttf` and `FilmotypeFord.ttf` (used for the DEXED
logo text and `skin.css`) are not in the repo. Put your own copies in `fonts/` and next to `skin.css`,
or change the `text` line in `layout.conf`, before building the skin.

To package a release zip: `./release.sh <version> [device-ip]` (see `mpc-vst-plugins`' `docs/RELEASING.md`).
The 32 algorithm diagrams in `images/` are generated by `tools/gen_algo_svgs.py`.

## Status

v1.0.6 (the skin in the MPC OS 2.x shape; the library is the same as 1.0.5). Builds clean for armhf (needs glibc 2.29) and runs on a real Force: audio, bank and patch loading, live names,
the operator switches, the algorithm diagrams and Q-Link control are checked on that hardware. New in 1.0.5, tried
by hand on a Force (2026-10-05): Q-Links and steppers for bank and patch on the BANKS page, one cart per Q-Link
turn or wheel click (the bank index spans 0-998, which made a turn skip eight to ten carts before), the lists
numbering top to bottom, and three Q-Link events per option on the key-scaling curves. The 1.0.5 package was labelled MPC OS 3.x only (its skin was in the 3.x format); 1.0.6 passes the
catalog check as MPC OS 2.x + 3.x.

**CPU (Force, `tools/bench.sh`, 2026-10-05).** Worst block 5.4% of the audio budget and worst p99 4.0% (PASS):

| State | mean | p99 |
|---|---|---|
| 1 voice | 0.7% | 2.4% |
| 8 voices | 1.2% | 3.0% |
| 16 voices | 1.7% | 3.5% |
| Q-Link sweep | 1.2% | 4.0% |

The synthesis runs in the audio callback, so unlike some other ports this bench measures all of it. The 1.0.0 bench
(2026-09-29) read higher (worst block 15.7%); the bench tool and the load on the device have changed since, so do not
read the difference as a speed-up from this release.

The x86 host test (`tools/test_port.sh`) has four failing checks, all from one cause: the test machine has no
`dx7_carts` folder to load presets from, so "set preset" and the `preset` stepping checks that follow from it fail.
They fail the same way on 1.0.4.

## Background

The sound engine is a vendored copy of [schwung-dx7](https://github.com/charlesvestal/schwung-dx7),
a `plugin_api_v2` build of the Dexed/MSFA engine originally written for Ableton Move. `src/VENDORED.md`
lists exactly what is vendored, from which commit, and our local source changes. It is wrapped as an
MPC OS VST2 plugin with `mpc-vst-plugins`' shared tooling.

The screen layout started from [force-dx7](https://github.com/sd88me/force-dx7)'s Force Shadow page,
then was reworked for this plugin (the OP pages, ALGORITHM page, per-operator switches and palette are
specific to this port). This repo is purely the VST port; `force-dx7` remains the separate
MockbaMod/Force Shadow addon for the Force's own on-device app, a different architecture (a separate
host process, not a VST).

More detail: [docs/NOTES.md](docs/NOTES.md) (this port's findings, including the retired control-socket
attempt and each bug found on the device), [src/VENDORED.md](src/VENDORED.md) (what is vendored and why).

## Credits

- **Yamaha** — the original DX7 hardware and its 6-operator FM synthesis architecture.
- **[asb2m10](https://github.com/asb2m10)** — [Dexed](https://github.com/asb2m10/dexed), the
  original DX7 emulator/VST this all traces back to.
- **Google** — [MSFA](https://github.com/google/music-synthesizer-for-android), the FM synthesis
  core Dexed itself is built on (Apache-2.0, headers preserved as-is in `src/dsp/msfa/`).
- **[charlesvestal](https://github.com/charlesvestal)** —
  [schwung-dx7](https://github.com/charlesvestal/schwung-dx7), the `plugin_api_v2` build for Ableton
  Move this port vendors directly (see `src/VENDORED.md`).
- **[sd88me](https://github.com/sd88me)** — this MPC OS VST2 port, and
  [force-dx7](https://github.com/sd88me/force-dx7) (the separate Force Shadow addon this skin's
  layout and palette are ported from).

## License

GPL-3.0 (see `LICENSE`). The algorithm diagrams follow the layout table in Dexed's `AlgoDisplay.cpp`
(GPL-3.0); individual MSFA files keep their own Apache-2.0 headers.
