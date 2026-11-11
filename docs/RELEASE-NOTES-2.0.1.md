# Dexed (DX7) 2.0.1

**Fixed**: clicks and pops on note release (#18). 2.0's new front end split each audio block at every MIDI event and
asked the engine for the pieces, but the DX7 engine only renders whole 64-sample blocks: given a shorter piece it still
moved every voice on by 64 samples, so the waveform jumped at each note-off (and note-on). The engine now always renders
whole blocks, as in 1.x; notes land on the next 64-sample boundary (under 1.5 ms, finer than 1.x).

Nothing else changed: same skin, parameters and ID. Install over 2.0.0 or 1.x as before (`install.sh`, see `INSTALL.md`).
Zips: `-mpc-armv7` (Force, Live, One, X, Key) and `-mpc-aarch64` (Gen 2 units).

**Checked**: on a Force (MPC OS 3.9.1), staccato notes on a sustaining patch release cleanly.
