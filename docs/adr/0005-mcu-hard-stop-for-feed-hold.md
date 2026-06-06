# ADR-0005: MCU-level hard stop for Feed Hold, Pause, and Stop

## Status
Accepted

## Context
The CNC feed hold feature requires stopping axis motion as fast as possible when
the operator presses the hold button mid-move. Three approaches were evaluated:

1. **Buffer drain (host-only):** Reduce `buffer_time_high` to ~0.1s and stop
   the G-code work loop. Fast between short moves, but a single long move (e.g.
   `G1 X200`) queues its entire step sequence to the MCU at dispatch time —
   buffer tuning has no effect on that in-flight sequence.

2. **Drip-move adaptation (host-only):** Run all job moves through Klipper's
   `drip_move` path, which feeds steps to the MCU in 50ms slices and checks a
   completion flag between each. Achieves ~1.5mm worst-case overshoot at max
   speed (30 mm/s). No MCU changes needed, but degrades motion quality
   (eliminates lookahead across slice boundaries) and cannot achieve sub-0.1mm
   stopping precision.

3. **MCU GPIO interrupt + hard stop (MCU firmware change):** Wire the feed hold
   button to a MCU GPIO. The MCU detects the pin change via the existing trsync
   mechanism, halts step generation immediately, and reports the exact step count
   at halt time. The host calculates the Hold Position from that step count using
   the same position-reconciliation logic already used by homing.

## Decision
Use approach 3: MCU GPIO interrupt + hard stop.

## Reasons
- **Precision:** A hard stop resolves to within 2–3 MCU interrupt cycles =
  0.003–0.005mm of position uncertainty. This is 10× inside the machine's
  0.05mm part tolerance.
- **Latency:** The GPIO interrupt fires at the MCU level — no host roundtrip.
  Response time is sub-5ms, giving <0.1mm overshoot at max cutting speed
  (20 mm/s).
- **Hard stop is mechanically safe at these speeds:** Max rapids are 1800 mm/min
  (30 mm/s) with 300 mm/s² acceleration. NEMA23 motors with DM556 external
  drivers have sufficient holding torque to hard-stop without skipping steps at
  this speed. Deceleration ramp logic is not required.
- **Architecturally correct:** This matches how GRBL and FluidNC implement feed
  hold — halt step execution at the MCU level when a pin fires, record position,
  reconcile on the host. It is the right design for a CNC-focused Klipper fork.
- **Reuses existing infrastructure:** Klipper's trsync mechanism and
  `stepper.get_past_mcu_position(trigger_time)` already handle the
  pin-fire → position-reconciliation path (used by homing). The feed hold
  plugin extends this rather than inventing a new mechanism.

## Consequences
- Requires a MCU firmware change (new `config_cnc_feed_hold` MCU command or
  adaptation of the endstop/trsync path) and a reflash of the STM32F103 on the
  Creality V4.2.2 board.
- The feed hold button must be wired directly to a MCU GPIO — not to a
  Raspberry Pi GPIO — to achieve the required latency.
- Mainsail UI Pause/Stop buttons go through the network + host path (~100ms
  additional latency) before reaching the MCU. This is acceptable because
  UI-triggered pauses are intentional operator actions, not emergency stops.
- All three stop types (Feed Hold, Pause, Stop) share the same MCU halt path.
  The difference is what the host does after the stop: Feed Hold resumes on
  button release; Pause retracts Z and waits for operator; Stop cancels the job.
