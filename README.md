# mpc-vst-dx7

**DX7 (Dexed)** — a native VST2 instrument for Akai MPC OS standalone devices (MPC Live/One/X/Key,
Force), loaded by MPC's built-in JUCE plugin host with a native touchscreen skin (Q-Links included).

6-operator FM synthesis via [schwung-dx7](https://github.com/charlesvestal/schwung-dx7) (a
`plugin_api_v2` build of the Dexed/MSFA engine, originally written for Ableton Move), wrapped as an
MPC OS VST2 plugin with `mpc-vst-plugins`' shared tooling. The touchscreen skin and cyan/slate
DX7-editor theme are ported from [force-dx7](https://github.com/sd88me/force-dx7)'s Force Shadow
page — this repo is purely the VST port; `force-dx7` remains the separate MockbaMod/Force Shadow
addon for the Force's own on-device app (not a VST, no plugin host involved).

## Build

Needs a sibling checkout of [mpc-vst-plugins](https://github.com/sd88me/mpc-vst-plugins) (the shared
wrapper, `build_port.sh`, skin tooling) at `../mpc-vst-plugins`, or set `MPC_VST` to point at one.
Docker (with QEMU for arm32v7) and a `force-shadow` checkout are needed transitively by
`mpc-vst-plugins`' build pipeline — see its own docs.

```
./build.sh
```

Clones `schwung-dx7` into `.scratch/schwung-dx7` (gitignored) on first run, applies
`patches/schwung-dx7-multibank-syx.patch` (adds support for multi-bank "ROM" `.syx` cart dumps —
stock schwung-dx7 only understands one 4104-byte bank per file), and builds via
`mpc-vst-plugins/tools/build_port.sh`. Output in `build/`: `dx7_dexed.so`, the skin folder, and
`pluginlist-entry.xml`.

## Bank/patch carts

The plugin's `MODULE_DIR` is baked in as `/sdcard/vst/dx7_carts` on the device — drop `.syx` files
there (single 4104-byte banks or multi-bank ROM dumps, any size that's an exact multiple of 4104
bytes) and they show up via the bank/patch stepper on the GLOBAL tab.

## Status

Builds clean for armhf, real in-process audio confirmed (no IPC/shared-memory bridge — a plain
`plugin_api_v2` DSP callback), bank/patch loading and live text readouts working, passed
`tools/bench.sh` on real Force hardware with comfortable headroom. See the extracted git history
(this repo split out of `mpc-vst-plugins`' `force-dx7/vst-schwung/`) for the full trail of bugs
found and fixed along the way.
