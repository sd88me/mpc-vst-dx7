#!/usr/bin/env bash
# The release zips, from the release build (build/sd88me - VST - Dexed (DX7), made by ./build-sdk.sh):
#   dist/Dexed-DX7-<ver>-mpc-armv7.zip, -mpc-aarch64.zip   install.sh / uninstall.sh per build (tools/release.py of mpc-vst-plugins); the .so
#                                      keeps its 1.x name dx7_dexed.so and the carts stay in dx7_carts, so an install upgrades in place
#   dist/Dexed-DX7-<ver>-mpc-sdk.zip   the one plugin folder for "VST2 Plugins" (tools/sdk_zip.py)
#   dist/Dexed-DX7-<ver>-SHA256SUMS.txt
# MPC_VST: mpc-vst-plugins with tools/release.py, catalog_check.py and sdk_zip.py.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
MPC_VST="${MPC_VST:-$HOME/mpc-vst-plugins}"
[ -f "$MPC_VST/tools/release.py" ] && [ -f "$MPC_VST/tools/sdk_zip.py" ] || { echo "need mpc-vst-plugins with tools/sdk_zip.py (MPC_VST)" >&2; exit 1; }
DIR="sd88me - VST - Dexed (DX7)"; SRC="$here/build/$DIR"
[ -f "$SRC/VST/dexed-dx7-arm64.so" ] || { echo "missing $SRC: run ./build-sdk.sh first" >&2; exit 1; }
VER=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$SRC/plugin.json")
python3 -c 'import json,sys; m=json.load(open(sys.argv[1])); sys.exit(0 if m["uid"]=="FDX2" and "Beta" not in m["name"] else "not the release identity")' "$SRC/plugin.json"
out="$here/dist"; mkdir -p "$out"
for pair in "arm32:armv7:file32" "arm64:aarch64:file64"; do
  IFS=: read -r so arch key <<<"$pair"
  st="$here/build/catalog/$arch"; rm -rf "$st"; mkdir -p "$st/$DIR" "$st/extra"
  cp -r "$SRC/Plugin Skins" "$SRC/version.xml" "$st/$DIR/"
  python3 - "$SRC/plugin.json" "$st/$DIR/plugin.json" "$key" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
m.pop("file32", None); m.pop("file64", None)
m[sys.argv[3]] = "dx7_dexed.so"
json.dump(m, open(sys.argv[2], "w"), indent=2)
PY
  cp "$SRC/VST/dexed-dx7-$so.so" "$st/dx7_dexed.so"
  cp -r "$SRC/Content/carts" "$st/extra/dx7_carts"
  python3 "$MPC_VST/tools/release.py" --so "$st/dx7_dexed.so" --skin "$st/$DIR" --entry "$here/build/pluginlist-entry.xml" --version "$VER" \
    --extra "$st/extra/dx7_carts:dx7_carts" --user-data dx7_carts --user-data favourites.dat --user-files "$here/userfiles.json" \
    --repo sd88me/mpc-vst-dx7 --license GPL-3.0-only --id dexed-dx7 \
    --requires "MPC OS standalone (Force/Live/One/X/Key) with root SSH access; 44.1 kHz" \
    --about "6-operator FM synthesis (Dexed/MSFA via schwung-dx7), with the DX7-editor LCD touchscreen skin ported from force-dx7." \
    -o "$st/dist"
  cp "$(ls "$st/dist"/*.zip)" "$out/Dexed-DX7-$VER-mpc-$arch.zip"
done
python3 "$MPC_VST/tools/catalog_check.py" "$out/Dexed-DX7-$VER-mpc-aarch64.zip" --catalog --require-portable --expect-id dexed-dx7 --expect-repo sd88me/mpc-vst-dx7
python3 "$MPC_VST/tools/sdk_zip.py" "$out/Dexed-DX7-$VER-mpc-sdk.zip" "$out/Dexed-DX7-$VER-mpc-armv7.zip" "$out/Dexed-DX7-$VER-mpc-aarch64.zip"
(cd "$out" && sha256sum "Dexed-DX7-$VER-mpc-armv7.zip" "Dexed-DX7-$VER-mpc-aarch64.zip" "Dexed-DX7-$VER-mpc-sdk.zip" > "Dexed-DX7-$VER-SHA256SUMS.txt")
ls -la "$out"/Dexed-DX7-"$VER"-*
