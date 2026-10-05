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
# The skin is written in the MPC OS 2.x shape (the Force and MPC OS 3.x read it too), so the catalog can label the release
# "MPC OS 2.x + 3.x". SHADOW_SKIN_MPC_OS=3 in the environment writes the 3.x shape instead.
export SHADOW_SKIN_MPC_OS="${SHADOW_SKIN_MPC_OS:-2}"
exec "$MPC_VST/tools/build_port.sh" "$here/vst.json"
