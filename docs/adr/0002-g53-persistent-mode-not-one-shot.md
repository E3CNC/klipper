# ADR-0002: G53 is a persistent mode toggle, not a one-shot command

## Status
Accepted

## Context
In standard CNC G-code (NIST/ISO), `G53` is non-modal: it applies to the current block only. `G53 G0 Z40` moves to machine Z=40, and the next block automatically reverts to the previously active WCS.

Implementing true one-shot G53 in Klipper is difficult because Klipper dispatches one command per line. `G53 G0 Z40` on a single line would only execute G53 (the first recognised command) — the G0 Z40 would be silently ignored or partially parsed.

## Decision
G53 activates a persistent machine-mode state. All subsequent moves use raw machine coordinates until the operator explicitly issues `G54`–`G59` or homes the machine.

## Reasons
- The post processor (Fusion 360 / MPCNC-Klipper) never outputs G53 in CAM-generated files. G53 is only used for manual console commands (tool setter approach, safe positioning).
- For manual console use, the toggle pattern is clearer: issue `G53`, jog to the tool setter, do the measurement, issue `G54` to return. The operator can see the mode in `WCS_STATUS`.
- True one-shot G53 within a single Klipper command line would require intercepting and re-dispatching G0/G1 within the G53 handler — adding significant complexity for a case that never arises from the CAM.

## Consequences
- `G53` alone (no following move) is a valid command — it switches mode and waits.
- Operators must explicitly issue a WCS command (`G54`–`G59`) to exit machine mode. Homing also exits it.
- If a future post processor does output `G53 G0 X...` on one line, it will not work as expected. The motion would execute in whatever mode was previously active, not machine mode.
