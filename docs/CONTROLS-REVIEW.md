# Controls review against JV-880 PR #22 (2026-11-13)

Lessons from sd88me/mpc-vst-jv880 PR #22 (patch/bank controls), checked against this port. Not yet fixed or tested on hardware.

Background, measured on an MPC One+: a Q-Link tick moves the host value by 1/128 of the range. While the host keeps moving a param the worker holds its read-back for 300 ms, so the host value can run ahead of the engine. After a read-back the Q-Link sometimes carries on from its own old value (about 30% of the time).

## Findings (src/DexedPlugin.cpp)

1. **Bank Q-Link can step the wrong way: FIXED on branch bank-qlink-direction** (Live III, data wheel 8 up then 3 down one click at a time: +5 carts). `bankValue()` steps one cart toward the host value (`v > cur ? +1 : -1`). During a turn `syncFromEngine(true)` skips params moved in the last 300 ms, so the host value runs ahead of the engine. Turn up fast and then back: the host value is still above the engine's, so the first ticks down still step up until the host value crosses back. JV-880's fix: judge the direction from the host's last position while it is ahead (`ahead_`, `lastPos_`), not from the engine.
2. **Every set of `syx_bank_index` is a one-cart step.** An automation point, a reset or a recalled value moves one cart instead of going to that cart. Check whether the param is automatable; if so make it NoAuto or tell a set from a tick as JV-880 does.
3. **Q-Link carrying on from its own value:** same exposure as 1. Re-test on device with a long, paused turn.
4. Not affected: PATCH (0..31, absolute, and the steppers use `preset_next`/`preset_prev` verbs). The tiles use momentary verbs that fire on every press (no held flag), so the JV-880 stuck-tile bug does not apply.
5. **New, seen on the Live III: fast clicks are merged.** 8 wheel clicks up then 3 down sent in one go moved +2 carts, not +5. \`parameterChanged\` only marks the param dirty, and the audio thread reads it once per block, so several host moves inside one block become one step. Fix idea: count host moves (or their direction) in parameterChanged and apply each as a step. Not fixed.
