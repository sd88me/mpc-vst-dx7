#!/usr/bin/env bash
# Build the DX7 (Dexed/MSFA) port as an MPC OS VST2 instrument via mpc-vst-plugins'
# generic port builder (vst.json). DSP source (schwung-dx7's plugin_api_v2 build of
# Dexed/MSFA): a checkout of https://github.com/charlesvestal/schwung-dx7 at
# ../../.scratch/schwung-dx7 (gitignored, not vendored into this repo -- see vst.json's build.root).
#   vst-schwung/build/dx7_dexed.so        -> /sdcard/vst/ on the device
#   vst-schwung/build/skin/<folder>/      -> /sdcard/Synths/ on the device
#   vst-schwung/build/pluginlist-entry.xml
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MPC_VST="${MPC_VST:-$here/../..}"
[ -x "$MPC_VST/tools/build_port.sh" ] || { echo "need an mpc-vst-plugins checkout (MPC_VST)" >&2; exit 1; }
[ -f "$here/../../.scratch/schwung-dx7/src/dsp/dx7_plugin.cpp" ] || {
  echo "need a schwung-dx7 checkout at $here/../../.scratch/schwung-dx7" >&2
  echo "  git clone https://github.com/charlesvestal/schwung-dx7 $here/../../.scratch/schwung-dx7" >&2
  exit 1
}
exec "$MPC_VST/tools/build_port.sh" "$here/vst.json"
