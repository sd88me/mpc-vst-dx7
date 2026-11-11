#!/usr/bin/env bash
# Build Dexed (DX7) 2.0: native test build + arm32 + arm64, into build/sd88me - VST - Dexed (DX7)/.
# Set MPC_SDK to the plugin framework folder (it must contain tools/build.py).
#   ./build-sdk.sh          build
#   ./build-sdk.sh test     build, then run the framework's host simulator test
#   ./build-sdk.sh beta     a "Dexed 2 Beta" (uid FDXB) test build that installs next to the release
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
SDK="${MPC_SDK:?set MPC_SDK to the plugin framework folder}"
[ -f "$SDK/tools/build.py" ] || { echo "MPC_SDK has no tools/build.py" >&2; exit 1; }
python3 "$here/tools/gen_params.py"
python3 "$here/tools/gen_algo_carriers.py" >/dev/null
if [ "${1:-}" = beta ]; then
  # "Dexed 2 Beta" (uid FDXB): a staging project with its own plugin.json, so it installs next to the release.
  stage="$here/build/beta-project"; rm -rf "$stage"; mkdir -p "$stage"
  ln -s "$here/src" "$stage/src"; ln -s "$here/Content" "$stage/Content"; [ -d "$here/skins" ] && ln -s "$here/skins" "$stage/skins"
  python3 - "$here/plugin.json" "$stage/plugin.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
m.update(name="Dexed 2 Beta", uid="FDXB", version=m["version"],
         file32="VST/dexed2beta-arm32.so", file64="VST/dexed2beta-arm64.so")
json.dump(m, open(sys.argv[2], "w"), indent=2)
PY
  python3 "$SDK/tools/build.py" "$stage" --no-ui --define 'DEXED_NAME="Dexed 2 Beta"' --define "DEXED_UID='F','D','X','B'"
  exit
fi
python3 "$SDK/tools/build.py" "$here" --no-ui
if [ "${1:-}" = test ]; then
  # a scratch plugin folder: the test's random parameter sweep presses +FAV, which writes favourites.dat next to the plugin
  scratch="$(mktemp -d)"; ln -s "$here/Content" "$scratch/Content"; trap 'rm -rf "$scratch"' EXIT
  MPC_PLUGIN_FOLDER="$scratch" "$SDK/.sdk-tools/host_sim" "$here/build/native/dexed--dx7-.so" test --notes 60,64,67 --wav "$here/build/test.wav"
fi
