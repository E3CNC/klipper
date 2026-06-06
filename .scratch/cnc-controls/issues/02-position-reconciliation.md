# 02 — Position reconciliation

Status: implemented-pending-deploy

## Parent

[PRD: CNC Motion Controls](..\PRD.md)

## What to build

When the MCU halt fires, the host must compute two values and update Klipper's position model before any further action:

**Hold Position** — the exact Cartesian XYZ coordinates where the machine stopped. Derived by calling `stepper.get_past_mcu_position(trigger_time)` for each axis (the trigger time comes from the trsync callback wired in issue 01). This is the same mechanism homing uses after an endstop triggers (`StepperPosition.note_home_end` / `HomingMove.calc_toolhead_pos` in `homing.py`). Once computed, call `toolhead.set_position(halt_pos)` to correct the Cartesian model — without this, the host still thinks the tool is at the pre-queued endpoint.

**Resume Target** — `toolhead.commanded_pos` captured at halt time. This is the endpoint of the last move dispatched to the toolhead (covering all in-flight moves across the lookahead). On resume, the machine moves from Hold Position to Resume Target before continuing the G-code file.

Both values are stored on the plugin object and cleared when the job is cancelled or completes.

Reference: `homing.py` `StepperPosition`, `calc_toolhead_pos`, `toolhead.set_position`.

## Acceptance criteria

- [ ] After a button-triggered halt mid `G1 X200` starting from X=0, `GET_POSITION` reports the actual X where the machine stopped — not X=200
- [ ] Position error after halt is within one stepper step of the true stop location (≤ 0.005 mm on the X ballscrew at this machine's step resolution)
- [ ] `resume_target` on the plugin object equals the pre-halt `commanded_pos` (X=200 in the example above)
- [ ] A subsequent move to `resume_target` from `halt_pos` brings the machine to the correct endpoint

## Blocked by

- [01 — MCU halt primitive](01-mcu-halt-primitive.md)
