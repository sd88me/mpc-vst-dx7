#!/usr/bin/env bash
# The +FAV naming keyboard, offline: needs build/native/dexed--dx7-.so (./build-sdk.sh) and MPC_SDK.
set -euo pipefail
cd "$(dirname "$0")/.."
SDK="${MPC_SDK:-$HOME/mpc-plugin-builder-sdk}"
T=build/test; mkdir -p "$T"
g++ -std=c++17 -O1 -pthread -I"$SDK/framework" -o "$T/kb_test" tests/kb_test.cpp -ldl
scratch="$(mktemp -d)"; ln -s "$PWD/Content" "$scratch/Content"; trap 'rm -rf "$scratch"' EXIT
MPC_PLUGIN_FOLDER="$scratch" "$T/kb_test" "$PWD/build/native/dexed--dx7-.so"
