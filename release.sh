#!/usr/bin/env bash
# Build and package DX7 (Dexed) as one shareable zip: dist/DX7-Dexed-<version>-mpc-armv7.zip,
# containing the built .so, skin, install.sh/uninstall.sh and a generated INSTALL.md.
#   ./release.sh <version>            e.g. ./release.sh 1.0.0
#   ./release.sh <version> <bench-ip> also runs tools/bench.sh on a real device first and embeds
#                                      the CPU result in INSTALL.md
# Needs a sibling mpc-vst-plugins checkout (see build.sh); MPC_VST overrides its location.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MPC_VST="${MPC_VST:-$here/../mpc-vst-plugins}"
[ -f "$MPC_VST/tools/release.py" ] || { echo "need an mpc-vst-plugins checkout (MPC_VST)" >&2; exit 1; }
VERSION="${1:?usage: release.sh <version> [bench-device-ip]}"
BENCH_IP="${2:-}"

echo "== build ==" >&2
bash "$here/build.sh"

echo "== skin preview ==" >&2
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$MPC_VST":/mv:ro -v "$here":/w -w /w python:3.11-slim sh -c \
  'pip install --quiet --user Pillow && python3 /mv/tools/studio.py preview "build/skin/sd88me - VST - DX7 (Dexed)/Plugin Skins" -o build/preview_%d.png'
echo "wrote $here/build/preview_*.png -- look at them before shipping" >&2

BENCH_ARGS=()
if [ -n "$BENCH_IP" ]; then
  echo "== bench (device: $BENCH_IP) ==" >&2
  "$MPC_VST/tools/bench.sh" "$here/build/dx7_dexed.so" "$BENCH_IP" -j | tee "$here/build/bench.json"
  BENCH_ARGS=(--bench "$here/build/bench.json")
else
  echo "== bench skipped (no device IP given) -- run \`./release.sh $VERSION <ip>\` before a real release ==" >&2
fi

echo "== package ==" >&2
python3 "$MPC_VST/tools/release.py" \
  --so "$here/build/dx7_dexed.so" \
  --skin "$here/build/skin/sd88me - VST - DX7 (Dexed)" \
  --entry "$here/build/pluginlist-entry.xml" \
  --version "$VERSION" \
  --extra "$here/banks:vst/dx7_carts" \
  --about "6-operator FM synthesis (Dexed/MSFA via schwung-dx7), with the DX7-editor LCD touchscreen skin ported from force-dx7." \
  "${BENCH_ARGS[@]}" \
  -o "$here/dist"

echo "== done: $here/dist ==" >&2
