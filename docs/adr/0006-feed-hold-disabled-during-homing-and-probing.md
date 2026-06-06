# ADR-0006: Feed Hold button is silently ignored during homing and probing

## Status
Accepted

## Context
The Feed Hold mechanism arms a trsync on a MCU GPIO pin to halt step generation
mid-move. Klipper's homing and probing operations also use trsync to stop moves
and reconcile position. If a Feed Hold trsync fired concurrently with a homing
or probing trsync, both would attempt to set the toolhead position from
incompatible step counts — corrupting the home or probe result.

Two options were considered:

1. **Silently ignore Feed Hold during homing/probing.** The plugin tracks
   operational state and disarms the feed hold trsync when a home or probe
   begins, rearming it when the operation completes. Emergencies during
   homing/probing are handled by the physical Emergency Stop.

2. **Escalate to Emergency Stop.** If Feed Hold fires during homing/probing,
   trigger M112. This is safe but heavy — a mistaken button press during a
   home destroys the session.

## Decision
Option 1: silently ignore Feed Hold during homing and probing.

## Reasons
- Homing, probing, and job execution are mutually exclusive operations in this
  workflow — they never intentionally overlap.
- The operator's intent when pressing the Feed Hold button during a home is
  almost certainly a mistake, not a deliberate stop request. Escalating to
  E-stop in response to a likely mis-press is disproportionate.
- The spindle is never running during homing or probing (hard operational
  precondition), so the "danger from ignoring" the button is low.
- Emergency Stop (physical button + Mainsail) remains available for genuine
  emergencies during any operation.

## Consequences
- Feed Hold has no effect during `G28` or any operation using `HomingMove`
  (touch probe, tool setter probing).
- The plugin must hook `homing:homing_move_begin` / `homing:homing_move_end`
  events to track when to disarm and rearm the GPIO trsync.
- Operators who press Feed Hold during a home get no response; they must use
  Emergency Stop if they need to abort a home.
