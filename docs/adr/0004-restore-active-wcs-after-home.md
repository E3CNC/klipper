# ADR-0004: Restore active WCS after both homing and Klipper restart

## Status
Accepted (supersedes ADR-0001)

## Context
ADR-0001 decided to always reset to G54 after both homing and Klipper connect.
In practice this caused a usability footgun: operators working in G55 who home
mid-session, or whose Klipper restarted due to a crash, silently land in G54
and may start their next job in the wrong coordinate system.

An intermediate version of this ADR (v1.1) split the two events — restoring
WCS after home but still forcing G54 on Klipper restart. Community feedback
confirmed that the restart case is equally problematic: operators expect to
resume where they left off regardless of what caused the restart.

## Decision
Both events restore the previously active WCS:

- **`homing:home_rails_end`** (G28): re-applies `active_wcs` after homing resets
  `base_position`.
- **`klippy:ready`** (Klipper start/restart): loads `active_wcs` from the persist
  file and applies it. Defaults to G54 only when no persist file exists yet
  (first ever run).

`active_wcs` is now written to `wcs_offsets.json` alongside the offset values
so it survives restarts.

## Reasons
- A Klipper restart mid-job (crash, power blip) should not change the operator's
  working context — the offsets are already persisted, the active WCS should be too.
- The original safety argument ("land in a known state after a crash") is better
  served by the operator seeing their actual WCS than by silently switching to G54
  and potentially running the next job in the wrong system.
- G53 (machine coordinates) is available as an explicit safe-mode if the operator
  wants to confirm position before resuming work.

## Consequences
- Operators always resume in the WCS they were last using, regardless of what
  triggered the restart or home.
- `active_wcs` is persisted to disk — `wcs_offsets.json` now contains both
  `active_wcs` and `wcs` keys.
- First-ever run with no persist file defaults to G54.
