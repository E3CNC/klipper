# ADR-0001: WCS resets to G54 after homing and Klipper connect

## Status
Accepted

## Context
After a machine home (`G28`) or a Klipper reconnect, the WCS plugin must decide which coordinate system to activate. The alternatives are:

- **Auto-restore**: re-apply whichever WCS was active before the event
- **Clean slate**: always activate G54

## Decision
Always activate G54 after homing or Klipper connect, regardless of which WCS was previously active.

Stored offsets for G54–G59 are loaded from disk and remain available — the operator simply has to issue `G55` (etc.) explicitly to re-enter a non-G54 system.

## Reasons
- Homing is a deliberate re-reference of the machine. After a crash-and-home the operator should be in a known, predictable state — not silently back in whatever WCS was active before the crash.
- Auto-restore would hide a potentially dangerous state change: a crash mid-G55-job that triggers a home would put the machine back in G55 without any visible confirmation.
- This matches the feel of the existing Futtawuh macro workflow (single origin, always explicit), making the transition familiar.

## Consequences
- Operators switching between G54 and G55 mid-job must re-issue the WCS command after any home.
- `active_wcs` is not persisted to disk — only the offset values are saved.
