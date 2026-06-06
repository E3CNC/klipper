# 01 — MCU halt primitive

Status: implemented-pending-deploy

## Parent

[PRD: CNC Motion Controls](..\PRD.md)

## What to build

Add a new MCU command (`config_cnc_button`) that monitors a GPIO pin via Klipper's existing trsync mechanism and halts all stepper step generation when the pin fires.

On the MCU side: when the button pin is detected (debounced, same sampling pattern as `config_endstop`), a `halt_all_steppers` flag is set inside the trsync signal callback — interrupt-safe. Each stepper's step timer checks this flag on every invocation and returns `SF_DONE` instead of scheduling its next step. The trigger clock time is sent back to the host via the existing trsync `sendf` path.

Two companion MCU commands control the arming state: `cnc_button_arm` enables the halt behaviour, `cnc_button_disarm` suppresses it (flag silently ignored). The host sends `cnc_button_disarm` before every homing and probing operation and `cnc_button_arm` after.

On the host side: a `cnc_controls.py` plugin skeleton configures the MCU object, registers for the trsync trigger response, and exposes an internal `_on_halt(trigger_time)` callback (wired up fully in issue 02). The plugin reads its `feed_hold_pin` from `[cnc_controls]` config.

Reference implementation: `src/endstop.c` (GPIO monitoring + trsync wiring) and `klippy/extras/homing.py` (host-side trsync arming pattern).

**Requires MCU reflash** of the STM32F103 on the Creality V4.2.2 board. A free GPIO pin must be identified before flashing — check `SNAPSHOT.md` for currently allocated pins and cross-reference the V4.2.2 schematic for available breakout points.

## Acceptance criteria

- [ ] A `[cnc_controls]` config section with `feed_hold_pin` is accepted by Klipper without error
- [ ] During a long `G1` move, pressing the wired button causes axis motion to stop mid-travel; the machine does not continue to the move endpoint
- [ ] Spindle output is unaffected by the halt
- [ ] Pressing the button during `G28` has no effect — homing completes normally
- [ ] Pressing the button during a touch probe operation has no effect — probe completes normally
- [ ] The trigger clock time is received by the host `_on_halt` callback

## Blocked by

None — can start immediately.
