# mpc-vst-dx7

**DX7 (Dexed)** — a native VST2 instrument for Akai MPC OS standalone devices (MPC Live/One/X/Key,
Force), loaded by MPC's built-in JUCE plugin host with a native touchscreen skin (Q-Links included).

6-operator FM synthesis via a vendored copy of [schwung-dx7](https://github.com/charlesvestal/schwung-dx7)
(a `plugin_api_v2` build of the Dexed/MSFA engine, originally written for Ableton Move — see
`src/VENDORED.md` for exactly what's vendored, from which commit, and our one local source change),
wrapped as an MPC OS VST2 plugin with `mpc-vst-plugins`' shared tooling. The touchscreen skin and
cyan/slate DX7-editor theme are ported from [force-dx7](https://github.com/sd88me/force-dx7)'s Force
Shadow page — this repo is purely the VST port; `force-dx7` remains the separate MockbaMod/Force
Shadow addon for the Force's own on-device app (not a VST, no plugin host involved).

This repo is fully self-contained: no third-party source is fetched at build time. The only external
dependency is a sibling checkout of `mpc-vst-plugins` for the shared wrapper/build tooling, same as
every port in that ecosystem.

## Build

Needs a sibling checkout of [mpc-vst-plugins](https://github.com/sd88me/mpc-vst-plugins) (the shared
wrapper, `build_port.sh`, skin tooling) at `../mpc-vst-plugins`, or set `MPC_VST` to point at one.
Docker (with QEMU for arm32v7) is needed by `mpc-vst-plugins`' build pipeline; see its own docs. No
`force-shadow` checkout is needed (mpc-vst-plugins vendors the skin renderer).

```
./build.sh
```

Builds the vendored `src/dsp/` via `mpc-vst-plugins/tools/build_port.sh` — no network fetch. Output
in `build/`: `dx7_dexed.so`, the skin folder, and `pluginlist-entry.xml`.

## Install (just want it working on your MPC/Force)

Grab the latest release zip from the [Releases page](https://github.com/sd88me/mpc-vst-dx7/releases) —
no build tools needed. It unpacks to a folder with the built plugin, a default set of factory DX7
banks, and a script that does the whole install for you:

```
scp -r DX7-Dexed-<version> root@<device-ip>:/tmp/
ssh root@<device-ip> sh /tmp/DX7-Dexed-<version>/install.sh
```

That stops MPC, copies the plugin + skin + banks into place, registers it in `MPC.settings`
(backed up first), and starts MPC again. `uninstall.sh` reverses it. Full details, requirements and
a manual/no-script install path are in the zip's own `INSTALL.md`.

## Release (build + package a shareable zip)

```
./release.sh <version>              # e.g. ./release.sh 1.0.0
./release.sh <version> <device-ip>  # also runs tools/bench.sh on a real device first
```

Builds, generates an offline skin preview (`build/preview_*.png` — look at these before shipping),
and packages everything via `mpc-vst-plugins/tools/release.py` into
`dist/DX7-Dexed-<version>-mpc-armv7.zip`: the `.so`, the skin, a default `dx7_carts` bank folder
(`banks/`, schwung-dx7's own vendored factory banks), `install.sh`/`uninstall.sh`, a generated `INSTALL.md` and
`SHA256SUMS`. See `mpc-vst-plugins/docs/RELEASING.md` for the full checklist (device smoke test
before publishing, versioning rules, `gh release create`).

## Bank/patch carts

The plugin's `MODULE_DIR` is baked in as `/sdcard/vst/dx7_carts` on the device — drop `.syx` files
there (single 4104-byte banks or multi-bank ROM dumps, any size that's an exact multiple of 4104
bytes) and they show up via the bank/patch stepper on the GLOBAL tab.

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

## Status

Builds clean for armhf, real in-process audio confirmed (no IPC/shared-memory bridge — a plain
`plugin_api_v2` DSP callback), bank/patch loading and live text readouts working, passed
`tools/bench.sh` on real Force hardware with comfortable headroom. See the extracted git history
(this repo split out of `mpc-vst-plugins`' `force-dx7/vst-schwung/`) for the full trail of bugs
found and fixed along the way.
[docs/NOTES.md](docs/NOTES.md) has the port's findings: the retired control-socket attempt, the switch to
schwung-dx7, and each bug found on the device.
