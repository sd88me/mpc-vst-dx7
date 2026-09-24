# Vendored DSP source

`dsp/` is a vendored copy of [schwung-dx7](https://github.com/charlesvestal/schwung-dx7)'s
`src/dsp/` (a `plugin_api_v2` build of the Dexed/MSFA FM synthesis engine, itself derived from
Google's MSFA and asb2m10's Dexed), committed directly into this repo instead of being fetched at
build time. This mirrors schwung-dx7's own approach — it vendors MSFA rather than fetching Dexed at
build time — applied one level up: we vendor schwung-dx7 rather than fetching it.

- **Vendored from**: https://github.com/charlesvestal/schwung-dx7, commit `86afe0062415b277ddc40611ec22ee804eb5d797` (`main`, v0.5.13)
- **License**: GPL-3.0 (this repo's own `LICENSE`, copied from schwung-dx7's), individual MSFA files
  carry their own Apache-2.0 headers (Copyright Google Inc.) — both preserved as-is, unmodified.
- **Our one local change**: `dsp/dx7_plugin.cpp`'s `scan_syx_banks()`/`v2_load_syx()`, to (a) scan
  `MODULE_DIR` directly instead of `MODULE_DIR/banks/` (this port's convention differs from
  schwung-dx7's stock Move layout — see the main README) and (b) support multi-bank "ROM" `.syx`
  cart dumps (any file size that's an exact multiple of 4104 bytes = N banks, not just one bank per
  file). Everything else in `dsp/` is byte-for-byte upstream.

`../banks/` (repo root, not under `src/`) is schwung-dx7's own bundled factory `.syx` banks
(`Dexed_01.syx` + 32 `SynprezFM_NN.syx`), vendored the same way and from the same commit, shipped in
release zips as the plugin's default `dx7_carts` content (see `release.sh`).

## Updating from upstream

1. Diff `dsp/dx7_plugin.cpp` against a fresh clone of schwung-dx7 to isolate our local change (or
   just recreate it: the "MODULE_DIR directly" edit is in `scan_syx_banks()`'s first `snprintf`; the
   multi-bank support is the same function's file-size/`sub_index` handling — see the class comment
   at the top of `scan_syx_banks()` for the full explanation).
2. Copy the new upstream `dsp/` over this one, reapply that one change.
3. Update the commit hash above.
4. Rebuild, rerun the offline host test, redo a device smoke test before releasing.
