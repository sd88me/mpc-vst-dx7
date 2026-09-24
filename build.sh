#!/usr/bin/env bash
# Build the DX7 (Dexed/MSFA) port as an MPC OS VST2 instrument via mpc-vst-plugins'
# generic port builder (vst.json). DSP source (schwung-dx7's plugin_api_v2 build of
# Dexed/MSFA): a checkout of https://github.com/charlesvestal/schwung-dx7 at
# .scratch/schwung-dx7 (gitignored, not vendored into this repo -- see vst.json's build.root).
# Needs a sibling checkout of https://github.com/sd88me/mpc-vst-plugins (the shared wrapper,
# build_port.sh, shadow_skin.py, etc.) -- set MPC_VST if it's not at ../mpc-vst-plugins.
#   build/dx7_dexed.so        -> /sdcard/vst/ on the device
#   build/skin/<folder>/      -> /sdcard/Synths/ on the device
#   build/pluginlist-entry.xml
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MPC_VST="${MPC_VST:-$here/../mpc-vst-plugins}"
SCHWUNG="$here/.scratch/schwung-dx7"
[ -x "$MPC_VST/tools/build_port.sh" ] || { echo "need an mpc-vst-plugins checkout (MPC_VST)" >&2; exit 1; }
if [ ! -f "$SCHWUNG/src/dsp/dx7_plugin.cpp" ]; then
  echo "cloning schwung-dx7 into $SCHWUNG ..." >&2
  git clone https://github.com/charlesvestal/schwung-dx7 "$SCHWUNG"
fi
# patches/schwung-dx7-multibank-syx.patch: schwung-dx7's stock scan_syx_banks()/v2_load_syx()
# only understand one 4104-byte DX7 bank per .syx file. We need multi-bank "ROM" cart dumps
# (N*4104 bytes, banks concatenated back-to-back) to work too -- see docs/NOTES.md's "First
# real interactive device test" entry. .scratch/ is gitignored (not vendored), so a fresh clone
# here won't have this fix; apply it once, idempotently (git apply --check first).
if [ -d "$SCHWUNG/.git" ] && ! git -C "$SCHWUNG" diff --quiet -- src/dsp/dx7_plugin.cpp 2>/dev/null; then
  : # already patched (local changes present) -- don't try to apply again
elif [ -f "$here/patches/schwung-dx7-multibank-syx.patch" ]; then
  if git -C "$SCHWUNG" apply --check "$here/patches/schwung-dx7-multibank-syx.patch" 2>/dev/null; then
    echo "applying schwung-dx7-multibank-syx.patch ..." >&2
    git -C "$SCHWUNG" apply "$here/patches/schwung-dx7-multibank-syx.patch"
  fi
fi
exec "$MPC_VST/tools/build_port.sh" "$here/vst.json"
