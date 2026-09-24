#!/usr/bin/env bash
# Build the DX7 (Dexed/MSFA) port as an MPC OS VST2 instrument via mpc-vst-plugins'
# generic port builder (vst.json). DSP source is vendored directly in src/dsp/ (see
# src/VENDORED.md for exactly what it is and where it came from) -- no network fetch, fully
# self-contained given a sibling mpc-vst-plugins checkout for the shared wrapper/tools.
# Needs a sibling checkout of https://github.com/sd88me/mpc-vst-plugins -- set MPC_VST if
# it's not at ../mpc-vst-plugins.
#   build/dx7_dexed.so        -> /sdcard/vst/ on the device
#   build/skin/<folder>/      -> /sdcard/Synths/ on the device
#   build/pluginlist-entry.xml
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MPC_VST="${MPC_VST:-$here/../mpc-vst-plugins}"
[ -f "$MPC_VST/tools/build_port.sh" ] || { echo "need an mpc-vst-plugins checkout (MPC_VST)" >&2; exit 1; }
exec "$MPC_VST/tools/build_port.sh" "$here/vst.json"
