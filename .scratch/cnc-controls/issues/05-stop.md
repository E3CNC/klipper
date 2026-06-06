# 05 — Stop (immediate job cancel)

Status: implemented-pending-deploy

## Parent

[PRD: CNC Motion Controls](..\PRD.md)

## What to build

Implement the `CNC_STOP` G-code command and wire it into Mainsail's Cancel button via macro delegation.

**`CNC_STOP`:**
1. Fire the MCU halt (same path as issue 01/02) if a job is running or the machine is in PAUSED state. If already idle, no-op.
2. Issue `M5` (spindle off via existing macro).
3. Call `virtual_sdcard.do_cancel()` to close the file and reset the file position — job cannot be resumed.
4. Clear Hold Position and Resume Target.
5. Enter IDLE state.

**Macro integration:** Rewrite the `CANCEL_PRINT` G-code macro in `macros.cfg` to delegate to `CNC_STOP`. Mainsail's Cancel button POSTs to the existing webhook endpoint that calls `CANCEL_PRINT` — no Mainsail changes required.

Note: `CNC_STOP` does not perform a Z retract. The assumption is that Stop is an intentional cancellation, not a safety pause — the operator can jog to clear the tool manually. If this proves inconvenient in practice, a retract can be added as a follow-on.

Reference: `pause_resume.py` `cmd_CANCEL_PRINT` and `virtual_sdcard.do_cancel()`.

## Acceptance criteria

- [ ] Clicking Cancel in Mainsail mid-job: motion stops, spindle turns off, job is cancelled
- [ ] After Stop, `RESUME` has no effect — job cannot be continued
- [ ] After Stop, starting a new job from Mainsail works normally
- [ ] `CNC_STOP` from PAUSED state also cancels correctly (spindle was already off — no double-off error)
- [ ] `CNC_STOP` when idle is a no-op (no error)

## Blocked by

- [02 — Position reconciliation](02-position-reconciliation.md)
