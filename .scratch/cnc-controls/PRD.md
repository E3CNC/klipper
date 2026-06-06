# PRD: CNC Motion Controls — Feed Hold, Pause, Stop

Status: ready-for-agent

---

## Problem Statement

CNC machining requires the ability to interrupt axis motion at any moment — mid-move — and either resume from the exact hold position or cancel the job cleanly. Klipper's existing PAUSE mechanism stops the G-code work loop between lines. A single long move (e.g. `G1 X200`) queues its entire step sequence to the MCU before the work loop can check a pause flag, so "pause" may complete 50–200 mm into a travel move. For a machine targeting 0.05 mm part tolerance, this is not a pause — it is a potential crash or ruined part.

GRBL and FluidNC solve this by halting step generation at the MCU level the moment a hardware signal fires. Klipper exposes no such capability outside of homing moves.

---

## Solution

A new `cnc_controls` plugin adds four motion control states familiar to any CNC operator:

- **Feed Hold** — hardware button wired to MCU GPIO; sub-5ms halt; spindle stays on; machine holds at the exact Hold Position; motion resumes immediately on button release.
- **Pause** — Mainsail UI button; same MCU halt; Z retracts to configured Retract Height; spindle off; operator can jog; Resume sequence returns to exact Hold Position.
- **Stop** — Mainsail UI button; same MCU halt; job cancelled, no resume.
- **Emergency Stop** — existing M112 path, unchanged.

All three stop variants share the same MCU-level halt: a GPIO interrupt routes through Klipper's existing trsync infrastructure to halt step generation within 1–2 MCU interrupt cycles, then reports the exact step count. The host reconciles the actual stop position using `stepper.get_past_mcu_position(trigger_time)` — the same path used by homing — and continues from the Hold Position to the Resume Target on resume.

---

## User Stories

1. As a CNC operator, I want pressing the feed hold button to stop axis motion within 2 mm at most, so that I can react to a problem before the tool causes damage.
2. As a CNC operator, I want the spindle to stay running during a Feed Hold, so that the tool does not stall in the material and cause a regrind mark or broken cutter on resume.
3. As a CNC operator, I want to release the feed hold button and have motion continue immediately to the original move endpoint, so that I do not have to restart the job.
4. As a CNC operator, I want the machine to remember exactly where it stopped (the Hold Position) and what the original move target was (the Resume Target), so that the resume path is geometrically correct.
5. As a CNC operator, I want clicking Pause in Mainsail to stop the machine as fast as possible — not merely between G-code lines — so that a UI pause is as useful as a hardware button pause.
6. As a CNC operator, I want the machine to retract Z to a configured safe height after a Pause, so that I can jog around the workpiece and fixturing without crashing the tool.
7. As a CNC operator, I want the spindle to turn off after a Pause, so that the spindle is not running unattended while I inspect the workpiece.
8. As a CNC operator, I want Pause to allow jogging, so that I can inspect the part and measure without moving the machine back to start.
9. As a CNC operator, I want the Resume sequence to turn the spindle on and wait a configurable dwell before re-engaging, so that the spindle is at operating RPM before it touches the workpiece.
10. As a CNC operator, I want the Resume sequence to move XY back to the Hold Position at the Retract Height before lowering Z, so that the tool re-enters the material at exactly the right location.
11. As a CNC operator, I want the machine to lower Z from the Retract Height to the Hold Position Z before resuming the interrupted move, so that the tool is at the correct cutting depth when motion restarts.
12. As a CNC operator, I want clicking Stop in Mainsail to instantly halt motion and cancel the job, so that I can abort a bad run without waiting for the current move to finish.
13. As a CNC operator, I want the spindle to turn off automatically after a Stop, so that it does not run unattended after a job is cancelled.
14. As a CNC operator, I want the feed hold button to have no effect during homing, so that an accidental press during G28 does not corrupt the machine's position reference.
15. As a CNC operator, I want the feed hold button to have no effect during touch probing or tool setter probing, so that an accidental press does not corrupt a probe result.
16. As a CNC operator, I want a configurable Retract Height (capped at position_max) so that I can set a safe clearance for my current fixturing without traversing to the absolute Z maximum every time.
17. As a CNC operator, I want a configurable Spindle Spin-up Dwell (default 5.0 s) so that the resume sequence works correctly with both the current 500 W and the future 1.5 kW spindle.
18. As a machine builder, I want the feed hold button wired directly to a MCU GPIO, so that halt latency is governed by the MCU interrupt rather than the host/network round-trip.
19. As a machine builder, I want the existing Mainsail Pause/Resume/Cancel buttons to transparently invoke the new CNC logic, so that the UI works correctly without custom Mainsail modifications.
20. As a machine builder, I want to configure the feature with a single `[cnc_controls]` section in printer.cfg, so that setup is self-contained.

---

## Implementation Decisions

### MCU firmware addition
A new MCU command (`config_cnc_button`) wraps a GPIO pin with the existing trsync mechanism, mirroring how `config_endstop` works. When the button pin fires, a `halt_all_steppers` flag is set via a trsync signal callback (interrupt-safe). Each stepper's step timer checks this flag and returns `SF_DONE` instead of scheduling its next step — halting motion within 1–2 interrupt cycles. The trigger clock time is reported to the host via the existing trsync `sendf` path, enabling exact position reconciliation.

The flag is armed and disarmed from the host via `cnc_button_arm` / `cnc_button_disarm` MCU commands. It must be disarmed during all homing and probing operations.

The target MCU is the STM32F103RET6 on the Creality V4.2.2 board (512 KB flash — ample headroom). A reflash is required.

### Position reconciliation
On halt:
1. Host calls `stepper.get_past_mcu_position(trigger_time)` for each axis — the same mechanism used by homing after an endstop triggers.
2. Host calls `toolhead.set_position(halt_pos)` to correct the Cartesian position model.
3. `resume_target` = `toolhead.commanded_pos` at halt time — the endpoint of the last dispatched move, covering all in-flight moves across lookahead.

Position error after hard stop: 0.003–0.005 mm (1–2 stepper interrupt cycles on a ballscrew). This is 10× inside the machine's 0.05 mm part tolerance. A deceleration ramp is not required. See ADR-0005.

### State machine

```
IDLE ──────────────────────────────── (no job)

RUNNING ─[feed hold button pressed]──► FEED_HOLD
FEED_HOLD ─[button released]──────────► (move halt_pos → resume_target → continue file)

RUNNING ─[CNC_PAUSE]──────────────────► halt → Z retract → spindle off → PAUSED
PAUSED ──[CNC_RESUME]─────────────────► spindle on → dwell → XY to halt_pos →
                                          Z to halt_pos_z → move to resume_target →
                                          continue file → RUNNING

RUNNING ─[CNC_STOP]───────────────────► halt → spindle off → cancel job → IDLE
PAUSED ──[CNC_STOP]───────────────────► spindle off → cancel job → IDLE
```

### Mutual exclusion with homing and probing
The plugin hooks `homing:homing_move_begin` and `homing:homing_move_end` to disarm and rearm the MCU button. These events fire for all `HomingMove`-based operations — G28, touch probe, tool setter probing. The feed hold button is silently ignored when disarmed. See ADR-0006.

The spindle must never be running during homing or probing. This is a hard operational precondition documented in CONTEXT.md under Motion Control Exclusion.

### Macro integration
The existing `PAUSE`, `RESUME`, and `CANCEL_PRINT` macros in macros.cfg are rewritten to delegate to `CNC_PAUSE`, `CNC_RESUME`, and `CNC_STOP` respectively. Mainsail's UI buttons POST to the webhook endpoints that call these macros — no Mainsail changes are required.

### Spindle integration
Spindle on/off is driven via the existing M3/M5 G-code macros already present in macros.cfg. The plugin calls these via `gcode.run_script()`.

### Configuration
```
[cnc_controls]
feed_hold_pin: <pin>           # required; MCU GPIO, normally-open button to GND
pause_retract_height: <mm>     # optional; absolute machine-space Z;
                               #   clamped to position_max at runtime;
                               #   default: position_max
spindle_dwell: <seconds>       # optional; default: 5.0
```

---

## Testing Decisions

### What makes a good test
Test observable external behaviour at the highest seam available — G-code command sequences and resulting machine state (position, pause state, file position). Do not test internal plugin state or MCU command wire formats directly. Tests should be runnable in Klipper's simulation mode (`-d` / `debuginput`) without the physical MCU where possible.

### Modules to test

**Position reconciliation (unit):** Given a known step count at a trigger time, verify that the plugin computes the correct Cartesian Hold Position. Mock a stepper with a fixed step history. Prior art: `StepperPosition.note_home_end` / `get_past_mcu_position` in `homing.py`.

**State machine transitions (integration):** Issue a long `G1` move; fire a simulated `CNC_PAUSE`; verify:
- `toolhead.get_position()` equals the expected halt_pos within one step
- `is_paused` is set
- `resume_target` equals the original move endpoint
- A subsequent `CNC_RESUME` moves to `resume_target` before continuing the file

**Mutual exclusion (integration):** Begin a homing sequence; fire a simulated feed hold signal; verify the home completes without corruption and no feed hold state is entered.

**Resume sequence ordering (integration):** After a Pause, verify the resume emits commands in order: (1) spindle on, (2) dwell, (3) XY move to halt_pos, (4) Z move to halt_pos Z, (5) move to resume_target. No steps skipped or reordered.

**Retract height clamping (unit):** Configure `pause_retract_height` above `position_max`; verify the actual retract move targets `position_max`.

### Prior art
`homing.py` (`StepperPosition`, `HomingMove`) and `pause_resume.py` are the closest existing patterns. `virtual_sdcard.py`'s work handler is prior art for file position tracking across pause.

---

## Out of Scope

- **Deceleration ramp at halt.** Hard stop is mechanically safe at this machine's speeds (max 1800 mm/min, NEMA23 + DM556) and achieves 0.003–0.005 mm position uncertainty — 10× inside tolerance. See ADR-0005.
- **Jogging during Feed Hold.** Machine is frozen at Hold Position while the button is held. Jogging is only permitted during Pause.
- **Mainsail UI changes.** Existing webhook endpoints are reused; no Mainsail fork needed for this feature.
- **Spindle RPM feedback.** The machine has no tachometer. Spin-up wait is a configurable dwell only.
- **Feed Hold during probing or homing.** These are mutually exclusive with job execution. See ADR-0006.
- **Hardware Pause/Stop buttons.** Only Feed Hold has a MCU-wired hardware button. Pause and Stop are Mainsail UI only. Emergency Stop uses the existing M112 / hardware kill path.
- **Replaying the interrupted path's intermediate waypoints on resume.** Resume moves directly from Hold Position to Resume Target.

---

## Further Notes

- A free MCU GPIO pin must be identified on the V4.2.2 board for the feed hold button. Currently allocated pins are documented in SNAPSHOT.md.
- Mainsail Pause will have higher latency than the hardware button (~100–200 ms network + host round-trip vs. sub-5ms MCU interrupt). At maximum cutting speed (1200 mm/min), this is ~2–4 mm of additional travel before the MCU halt fires. Acceptable for a deliberate UI-triggered pause.
- The 1.5 kW spindle upgrade is planned. The `spindle_dwell` parameter covers both; update the config value when the spindle is swapped.
- Domain vocabulary for all terms used in this PRD (Feed Hold, Hold Position, Resume Target, Retract Height, Spindle Spin-up Dwell, Motion Control Exclusion) is defined in `CONTEXT.md`.
- Architectural decisions underpinning this PRD: ADR-0005 (MCU hard stop), ADR-0006 (mutual exclusion with homing/probing).
