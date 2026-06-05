# ADR-0004: Restore active WCS after homing; G54 only on Klipper start

## Status
Accepted (supersedes ADR-0001)

## Context
ADR-0001 decided to always reset to G54 after both homing and Klipper connect.
In practice this caused a usability footgun: operators working in G55 who home
mid-session (tool change, tramming check, etc.) silently land in G54 and may
start their next job in the wrong coordinate system.

The original safety rationale — "after a crash-and-home you should be in a
known state" — actually only applies to the Klipper restart event, not to a
deliberate manual home.

## Decision
Split the two events:

- **`klippy:ready`** (Klipper start or restart after a crash): always activate
  G54. This is the true "unknown state" event — the operator cannot know what
  happened before the restart.
- **`homing:home_rails_end`** (G28 during a running session): restore whichever
  WCS was active before the home. G54 is still the result on a fresh start
  because `klippy:ready` set it there first.

## Reasons
- A manual home mid-session is not a crash. The operator knows which WCS they
  are in and expects to continue working in it.
- The crash-safety argument still holds for `klippy:ready` — a Klipper restart
  always lands in G54 regardless of what was active before.
- Community feedback confirmed the old behaviour caused missed-WCS crashes in
  normal multi-setup workflows.

## Consequences
- Operators who home mid-session stay in their active WCS automatically.
- After any Klipper restart, the active WCS is G54 — operators must re-select
  explicitly if working in G55–G59.
- `active_wcs` is still not persisted to disk; only offset values are saved.
