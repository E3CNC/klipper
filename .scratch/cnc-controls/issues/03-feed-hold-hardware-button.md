# 03 — Feed Hold (hardware button, full cycle)

Status: implemented-pending-deploy

## Parent

[PRD: CNC Motion Controls](..\PRD.md)

## What to build

Wire the MCU halt (issue 01) and position reconciliation (issue 02) into the complete RUNNING ↔ FEED_HOLD state cycle driven by the physical hardware button.

**On button press:** halt fires → Hold Position and Resume Target are computed and stored → plugin enters FEED_HOLD state. Spindle is not touched.

**On button release:** plugin detects the GPIO returning to its idle state (monitored via the existing `buttons` / `gcode_button` polling infrastructure, or a second trsync on the release edge) → issues `G1` to Resume Target at the feed rate that was in effect at halt → re-arms the MCU halt flag → returns to RUNNING state and signals `virtual_sdcard` to continue the file.

**Homing and probing exclusion:** the plugin hooks `homing:homing_move_begin` to disarm the MCU button (`cnc_button_disarm`) and `homing:homing_move_end` to rearm it (`cnc_button_arm`). These same events fire for all `HomingMove`-based operations — G28, touch probe, tool setter — so a single pair of hooks covers all cases. See ADR-0006.

**Feed rate preservation:** the feed rate active at halt must be restored when issuing the resume move. Capture it from `gcode_move.speed` at halt time.

## Acceptance criteria

- [ ] Mid `G1 X200` from X=0, pressing and holding the button stops motion at (say) X=73; releasing causes the machine to continue to X=200 and the job completes normally
- [ ] Spindle state is unchanged by press or release
- [ ] The resume move uses the same feed rate as the interrupted move
- [ ] Pressing the button during G28 (homing) does nothing — home completes normally
- [ ] Pressing the button during `FIND_CENTER_X` or any other touch probe command does nothing — probe completes normally
- [ ] Multiple press/release cycles in a single job all behave correctly

## Blocked by

- [01 — MCU halt primitive](01-mcu-halt-primitive.md)
- [02 — Position reconciliation](02-position-reconciliation.md)
