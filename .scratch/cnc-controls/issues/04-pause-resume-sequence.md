# 04 — Pause / Resume sequence

Status: implemented-pending-deploy

## Parent

[PRD: CNC Motion Controls](..\PRD.md)

## What to build

Implement the `CNC_PAUSE` and `CNC_RESUME` G-code commands and wire them into Mainsail's existing Pause/Resume buttons via macro delegation.

**`CNC_PAUSE`:**
1. Fire the MCU halt (same path as issue 01/02) — Hold Position and Resume Target are stored.
2. Issue `G1 Z{retract_height}` to retract to the configured Retract Height. The retract height is clamped to `position_max` at runtime regardless of the configured value.
3. Issue `M5` (spindle off via existing macro).
4. Enter PAUSED state. Jogging is permitted; no further automated action until `CNC_RESUME`.

**`CNC_RESUME`:**
1. Issue `M3` (spindle on via existing macro).
2. Issue `G4 P{spindle_dwell}` — dwell until spindle reaches RPM.
3. Issue `G1 X{halt_pos.x} Y{halt_pos.y}` at a safe rapid rate to return to Hold Position XY (machine is still at Retract Height).
4. Issue `G1 Z{halt_pos.z}` to lower to Hold Position Z.
5. Issue `G1` to Resume Target at the original feed rate.
6. Signal `virtual_sdcard` to continue the file from its current position.
7. Return to RUNNING state.

**Config parameters added to `[cnc_controls]`:**
- `pause_retract_height` — absolute machine-space Z in mm; clamped to `position_max`; default: `position_max`
- `spindle_dwell` — seconds; default: `5.0`

**Macro integration:** Rewrite the `PAUSE` and `RESUME` G-code macros in `macros.cfg` to delegate to `CNC_PAUSE` and `CNC_RESUME` respectively. Mainsail's Pause/Resume buttons POST to the existing webhook endpoints that call these macros — no Mainsail changes required.

Reference: existing `PAUSE`/`RESUME` macros in `macros.cfg`; `pause_resume.py` for the existing webhook endpoint registration pattern.

## Acceptance criteria

- [ ] Clicking Pause in Mainsail mid-job: motion stops, Z retracts to Retract Height, spindle turns off
- [ ] `pause_retract_height: 60` with `position_max: 52` results in a retract to Z=52, not Z=60
- [ ] After Pause, jogging in X/Y/Z works normally
- [ ] Clicking Resume: spindle turns on, machine dwells for `spindle_dwell` seconds, moves XY to Hold Position at Retract Height, lowers Z to Hold Position Z, continues to Resume Target, job continues correctly
- [ ] If operator jogged away during Pause, Resume still returns to Hold Position (not current jog position)
- [ ] Configuring `spindle_dwell: 3.0` results in a 3-second dwell, not the 5-second default
- [ ] `CNC_PAUSE` called while already PAUSED has no effect (idempotent)
- [ ] `CNC_RESUME` called while RUNNING has no effect (idempotent)

## Blocked by

- [02 — Position reconciliation](02-position-reconciliation.md)
