#!/usr/bin/env bash
# Regenerate the skin, rebuild the beta and copy only Plugin Skins/ to the Force. Usage: tools/push_skin.sh [restart]
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"; HOST="${FORCE:-root@192.168.1.187}"
python3 "$here/tools/make_tui.py" >/dev/null
"$here/build-sdk.sh" beta 2>&1 | grep -E "errors" || true
D="/sdcard/Synths/sd88me - VST - Dexed 2 Beta"
cd "$here/build/beta-project/build/sd88me - VST - Dexed 2 Beta"
ssh "$HOST" "rm -rf '$D/.skins.tmp'"
scp -rq "Plugin Skins" "$HOST:$D/.skins.tmp"
ssh "$HOST" "rm -rf '$D/Plugin Skins' && mv '$D/.skins.tmp' '$D/Plugin Skins'"
if [ "${1:-}" = restart ] || [ "${2:-}" = so ]; then   # also replace the plugin binary (MPC must restart to load it)
  scp -q VST/dexed2beta-arm32.so "$HOST:$D/VST/.dexed2beta-arm32.so.tmp"
  ssh "$HOST" "mv '$D/VST/.dexed2beta-arm32.so.tmp' '$D/VST/dexed2beta-arm32.so'"
fi
[ "${1:-}" = restart ] && ssh "$HOST" "systemctl restart acvs; sleep 25; systemctl is-active acvs"
echo pushed
