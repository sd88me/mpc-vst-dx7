# Dexed (DX7) 2.0.0

A big update, same plugin and same ID as 1.x: existing projects keep working, and your own carts in `dx7_carts` stay where they are.

**New skin**: drawn like the DX7 panel, with a DEXED wordmark, red LED patch number and an LCD that shows cart and patch side by side
(both step with the Q-Links and the data wheel). Horizontal sliders with a lit fill, and Q-Link blocks of four on every page.

**New**
- **Favourites** in MPC's own PRESET menu: +FAV saves the current voice with your edits, -FAV removes it.
- **CARTS** page: paged cart tiles with the current cart lit, the 32 patches, RANDOM (random cart and patch).
- **GENERATE** (ALGO page): a random voice with musical rules. STYLE: PLUCK, BELL, PAD, BASS, EP, LEAD, ALL or CHAOS (no rules).
  GENERATE builds a new voice, MUTATE varies the current one by AMOUNT. Carrier ratios stay put, so the key note doesn't move;
  carriers always release to silence.
- **ALGO** page: algorithm diagram, voice controls and an operator mixer.
- **OP** key with six sub-tabs, one per operator, with a live draggable envelope.
- Pitch envelope on VOICE you can drag.

**Install**: unzip, copy the folder to the device and run `install.sh` (see `INSTALL.md`). Zips: `-mpc-armv7` (Force, Live, One, X, Key)
and `-mpc-aarch64` (newer Gen 2 units). Running it over 1.x upgrades in place and keeps your carts and favourites.

**Checked**: installed over 1.x on a Force and loaded. **Not checked**: a project saved with 1.x. Reports welcome.
