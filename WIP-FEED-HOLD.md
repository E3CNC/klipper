# WIP: Feed Hold / Pause / Stop — UNTESTED DRAFT

**Branch:** `wip/feed-hold` — do **NOT** merge to `master` or the main feature line.

## Status: pre-alpha, never run

This branch carries a first-draft implementation of the CNC motion-control feature
(Feed Hold, Pause, Stop). **None of it has been tested.**

- ❌ Never compiled into firmware
- ❌ Never flashed to a board
- ❌ Never run on hardware or in simulation
- ❌ `src/cnc_control.c` is **not registered in `src/Makefile`** — the firmware build
  does not include it, so the MCU commands it defines (`config_cnc_button`,
  `cnc_button_arm`, `cnc_button_disarm`) do not exist yet. The host plugin
  (`cnc_controls.py`) looks them up at MCU connect and **will fail** until this is wired.

Treat this as design-complete, implementation-draft code.

## Files on this branch
- `klippy/extras/cnc_controls.py` (435 lines) — host plugin: Feed Hold / Pause / Stop
- `src/cnc_control.c` (130 lines) — MCU: GPIO button → trsync halt

## Design references (on the main line)
- `docs/adr/0005-mcu-hard-stop-for-feed-hold.md`
- `docs/adr/0006-feed-hold-disabled-during-homing-and-probing.md`
- `CONTEXT.md` → "Motion Control States"
- `.scratch/cnc-controls/` — PRD (`status: ready-for-agent`) + 5 issue specs

## TODO to make it real (in order)
1. **Wire the MCU build** — add `cnc_control.c` to `src/Makefile` (`src-y += cnc_control.c`,
   or a Kconfig-gated entry). Confirm it compiles for the target MCU.
2. **Build + flash** firmware to a test board (`make menuconfig` → `make` → flash).
3. **Bench-test each state** against the PRD acceptance criteria:
   - Feed Hold: hardware button, sub-5 ms halt, spindle stays on, resume on release
   - Pause: Z retract to Retract Height, spindle off, jog, full resume sequence
   - Stop: job cancel, no resume
4. **Verify position reconciliation** — Hold Position via `get_past_mcu_position(trigger_time)`,
   Resume Target.
5. **Work through** `.scratch/cnc-controls/issues/01-05`.
6. Only after passing tests on hardware: promote toward the main line — and only then
   reference `[cnc_controls]` in the installer's E3CNC Config Layer.
