# E3CNC Build Log — Standalone Handoff

## Overview

This is a self-contained handoff for the **E3CNC**, a self-built steel-tube-frame, router-style CNC in an attic workshop. It runs **Klipper** on a **Linux Mint** laptop. The target is **0.05 mm tolerance on aluminium parts** (steel cutting is possible but limited by the MDF spoilboard and frame flex).

**Current status:** The machine is **functional and cutting accurate aluminium.** The long-standing XY-skew blocker is **resolved and saved**, validated on real machined parts. The build has moved out of calibration and into producing its own upgrade parts. The active machining thread is NEMA23 motor risers in 8 mm aluminium.

A custom Klipper touch-probe plugin (Python, v13) is part of this build — see the **Touch Probe Plugin** section. The live copy lives in the Klipper extras folder on the Linux Mint laptop. This repo (`feature/cnc-plugins` branch) is the canonical development copy — deploy via SCP when ready.

---

## Plugin Development State

This repo is a local fork of Klipper, intended to become a CNC-focused Klipper fork for hobbyists. All custom plugins live in `klippy/extras/`. Domain documentation is in `CONTEXT.md` and `docs/adr/`.

### Plugins — current

| Plugin | File | Status |
|--------|------|--------|
| Touch probe (XY edge/center/bore finding) | `klippy/extras/touch_probe.py` | **v13 — complete, deployed on machine** |
| Work Coordinate Systems (G54–G59) | `klippy/extras/work_coordinate_systems.py` | **v1 — complete, deployed on machine** |

### Plugins — planned

| Plugin | Notes |
|--------|-------|
| Tool setter (`tool_setter.py`) | Fixed touch pad at back of machine. Z delta approach — no absolute calibration needed. Separate pin from touch probe. Updates all WCS Z offsets simultaneously after tool change. See CONTEXT.md for concept. |

### Pending tasks (next session)

1. ~~**Deploy WCS plugin via SSH**~~ — done.
2. ~~**Update `START_PRINT` macro**~~ — done. WCS_STATUS, WCS-aware ZERO macros, dashboard selectors, Discord release post published (blew up).
3. **Set `position_min: 0`** on X (and verify Y/Z) — old `-300 to +300` workaround no longer needed. User to do manually.
4. **Test WCS workflow end-to-end** — home → select WCS → `ZERO_ALL` → switch G54/G55 → verify DRO. User to do manually.

### Ecosystem — next session priority

The WCS Discord post got strong traction. Next steps toward the E3CNC ecosystem:

1. **Set up a public GitHub repo** — home for the E3CNC Klipper fork and future Mainsail fork.
2. **Fork Klipper** — `feature/cnc-plugins` branch is the starting point; move to a proper public fork.
3. **Fork Mainsail** — assess what CNC-specific UI changes make sense (dashboard layout, WCS display, etc.).
4. **KIAUH-style installer** — investigate how KIAUH works and whether a custom install script can deploy the E3CNC stack (Klipper fork + Mainsail fork + base config) in one shot for new builders.
5. **tool_setter plugin** — next planned plugin after the ecosystem groundwork is laid (or in parallel).

### CAM setup

- **Software:** Fusion 360 with MPCNC-Klipper post processor (Zergie's fork)
- **Post processor path:** `C:\Users\Bogdan\AppData\Roaming\Autodesk\Fusion 360 CAM\Posts\MPCNC.cps`
- **Important:** Post processor outputs pure motion G-code (G0/G1/G2/G3). It never outputs WCS commands (G54/G55/G10). The operator selects the WCS manually in Mainsail before starting a job.
- **END_PRINT** is configured as the end G-code in Fusion's output settings.
- **G38 probing:** Not implemented. Touch probe commands (FIND_CENTER_X etc.) are preferred — more verbose and safer for hobbyist use. G38 deferred to future consideration.

---

## Machine State

### Hardware

- **Z axis** — Full metal. 15 mm 6082 aluminium block, MGN linear rails (4-carriage), leadscrew with dual-nut anti-backlash, thrust bearing, NEMA23 + DM556 driver. Thread-locked and tuned. **Considered complete and locked.** Drilling performance is excellent with this axis — heavy plunges (e.g. 2.5 mm spot @ 600 mm/min) with no complaint.
- **X axis** — SFU1605 ballscrew, steel-tube roller, NEMA23 + DM556. **New 8 mm 6082 right-side roller plate machined and installed** (replaced a warped/off-centre 3 mm plate; axis now noticeably smoother). Bottom X plate uses beer-can shims (~0.25 mm). 2 bolts inaccessible for thread-locking (torqued, accepted). **Ballscrew floating end (BF12) was bowing/misaligning toward X0 — fixed this build** with a lock-nut + nut + washer stack, slowly torqued to dial in alignment; BF12 reinstalled and good.
- **Y axis** — Dual motor (`stepper_y` / `stepper_y1`), independent endstops, homes in the positive direction (toward the back). Onboard TMC2208 drivers. The right-side Y endstop screw is backed out ~1 full turn to mechanically reduce gantry skew (at the physical limit — can't adjust further without skipping).
- **Spindle** — 500 W currently mounted and running. **1.5 kW spindle upgrade pending:** it has been tested and runs; it needs the male-side connector re-soldered (~15–20 min job) and machined aluminium risers before it can be installed.
- **Spoilboard** — MDF, freshly faced (30 mm facing bit, clean, zero shingling). It costs ~18 mm of Z travel, which limits some probe routines and prevents misting/coolant until upgraded.
- **Electronics** — Creality 4.2.2 board running Klipper. DM556 external drivers for X and Z; Y uses the onboard drivers. GX16-4 connectors on both NEMA23 motors, properly strain-relieved. Electronics box on the right side panel. Control via an old laptop (Linux Mint, bare-bones) sitting on top of the enclosure. **Enclosure front door not yet built** (recommended when convenient: polycarbonate, not acrylic, for chip and noise containment — louder with the 1.5 kW spindle coming).

### Known Issues / Accepted Limitations

- **3 mm X-axis roller plates:** flexed under load and were found to be machined **off-centre** (a CAD reference error on the nut, which explained prior X binding). Being replaced with 8 mm 6082 — right side done + installed, left side machined and awaiting install.
- **NEMA23 risers currently ABS-GF printed:** functional but compliant (a source of residual vibration, most visible at the Z motor mount). Metal replacements are the next machining job.
- **Z-axis tilt:** ~0.05–0.06 mm over 15 mm of Z travel, suspected partially from out-of-square parts. Currently inside caliper error on actual parts. Accepted for now (see Calibration → Z tilt for the software-correction route).
- **Frame flex:** ~0.4–0.5 mm front-to-back under hard force (steel-pipe-frame limitation). Noted as a V2 design input.
- **1 stripped/jammed screw** on the bottom carriage plate: torqued down, not thread-locked. Acceptable.
- **2 inaccessible bolts** on the top rail carriages: torqued, not thread-locked. Acceptable.
- **MDF spoilboard:** no misting/coolant possible until a spoilboard upgrade.

---

## Calibration State

### Tram

- Measured with a DTI swept in a ~50–55 mm circle over a shimmed plexiglass reference plane.
- Result: **±0.01–0.015 mm** across the full sweep (front-to-back ~0.02–0.03 mm, left-to-right ~0.02 mm).
- Considered complete. **Re-tram after the 1.5 kW spindle is mounted.**

### Squareness / Skew (XY) — RESOLVED

- **Mechanical:** right-side Y endstop screw backed out ~1 turn (at limit).
- **Software:** Klipper `[skew_correction]` enabled, profile named **`cnc`** saved.
- **Working values:** `SET_SKEW XY=140.76,141.57,99.80`
- **How it was obtained (the method that works):** machine a **100×100 mm square**, measure the **two diagonals + one side**, and feed them as `SET_SKEW XY=AC,BD,AD`.
  - **AC and BD are the two DIAGONALS** of the square/rectangle; **AD is one side.**
  - **Important lesson:** a 3-dot 3-4-5 triangle does **not** provide a true second diagonal (BD). Plugging triangle legs into the BD slot produces nonsense (an instance gave 12.94°). Use a machined square (or at least a 4-point rectangle), not a 3-dot triangle.
- **Verification after applying:** re-measured square diagonals **141.22 vs 141.21** (≈0.01 mm); sides 99.95.
- **Confirmed under real cutting load:** 50×50 mm beech square (2D adaptive rough, 3 mm DOC, 100% WOC, 20 mm/s, + finishing contour) → both diagonals **70.61**, machinist square confirms square, no 0.05 mm feeler-gauge gap.
- **Saved with:** `SKEW_PROFILE SAVE=cnc` then `SAVE_CONFIG`. `GET_CURRENT_SKEW` reflects the saved profile.
- **Macro integration (current):** `SET_SKEW CLEAR=1` **before** homing; `SKEW_PROFILE LOAD=cnc` **after** homing completes; the old `SET_SKEW CLEAR=1` was **removed from `END_PRINT`** so the correction persists across operations until the next home (correct for CNC — many ops per home).

### Z tilt (XZ / YZ skew) — future, low priority

- ~0.05–0.06 mm over 15 mm of Z travel; currently inside caliper error on parts, so not urgent.
- Klipper supports `XZ=` / `YZ=` in `SET_SKEW`. To characterise without machining an awkward vertical test object: DTI-sweep along Z against a reference face **parallel to Y → gives XZ** (roughly measured already) and **parallel to X → gives YZ** (not yet measured). Known travel distance + measured deviation → derive `SET_SKEW` values geometrically.

### Steps/mm / rotation_distance

- X: `rotation_distance 5` (SFU1605 ballscrew)
- Y: `rotation_distance 8`
- Z: `rotation_distance 8` (leadscrew)
- **Caveat (confirmed):** dot-finding with calipers reads side lengths ~0.2 mm short — this is a **measurement artifact, not a calibration error**. Machined part edges came out on-size, confirming the steps/mm are correct. **Do not adjust `rotation_distance` from dot measurements**; validate with machined edges.
- **CAM note:** the endmill diameter is currently set to **5.835 mm** (measured), so parts come out ~0.01–0.02 mm over. Worth re-measuring/recalibrating endmill sizes now the machine is stiffer to land bang-on nominal.

---

## Klipper Config Summary

Config lives on the machine; key sections below. Ask the user to upload `printer.cfg` / `macros.cfg` if a full review is needed.

**printer.cfg**
- MCU: `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`
- Kinematics: cartesian
- `stepper_x`: step PB1, dir PC4, endstop PA5, homes negative, `rotation_distance 5`
- `stepper_y`: step PB8, dir PB7, endstop PA6, homes positive (back), `rotation_distance 8`
- `stepper_y1`: step PB6, dir PB5, endstop PA7
- `stepper_z`: step PC6, dir !PB2, endstop PA4, homes positive (up), `position_max 52`, `rotation_distance 8`
- TMC2208 on Y in **standalone mode** (no UART) — current set via Vref pot, **bumped this build to 1.41 V** on both Y motors (~1.4 A RMS, the ceiling for this actively-cooled board + 4010 fan; motors run bone cold, no more Y skipping).
- Spindle power: PA2 (on/off), PB0 (PWM RPM, scale 12000)
- `[skew_correction]` enabled (profile `cnc`)
- `[touch_probe]` configured on PC5
- `homing_override`: homes Z first, then Y, then X, then loads the skew profile

**macros.cfg**: `START_PRINT` (calls `WCS_STATUS` first), `END_PRINT`, `PAUSE` / `RESUME` / `CANCEL_PRINT`, `M3` / `M5` spindle control, `SPINDLE_POWER_ON` / `SPINDLE_POWER_OFF`, `USE_POSITION_ABSOLUTE` / `USE_POSITION_RELATIVE`. Skew clear removed from `END_PRINT` — see Skew section.

**wcs_macros.cfg** (new): `WCS_1`–`WCS_6` (select G54–G59), `MACHINE_COORDS` (G53), `ZERO_X` / `ZERO_Y` / `ZERO_Z` / `ZERO_ALL` (WCS-aware via `G10 L20 P{active_p}`). Pre-WCS `SET_KINEMATIC_POSITION` macros and `LOAD_OFFSETS` / `CHECK_OFFSET_XYZ` preserved as commented-out deprecated block.

---

## Touch Probe Plugin (Python, v13)

A custom XY touch-probe plugin (endstop-wrapper based, per-axis stepper association, fast-then-slow sampling, tip-radius + trigger-offset compensation). Probe input on PC5.

**Commands**
- Raw probe (now also compute, report, and **save** the tip-compensated edge): `PROBE_X_POS`, `PROBE_X_NEG`, `PROBE_Y_POS`, `PROBE_Y_NEG`
- Edge finding (probe → tip-comp → hop up → move over edge): `FIND_EDGE_X_POS` / `_NEG`, `FIND_EDGE_Y_POS` / `_NEG`
- Auto center finding (hop-over: probe one side, Z-hop up, travel over part, drop, probe other side): `FIND_CENTER_X`, `FIND_CENTER_Y`, `FIND_CENTER_XY`
- Bore probing (4-touch from approximate center): `PROBE_BORE`
- **Manual center finding without Z hop-over (added v13):** `COMPUTE_CENTER`, `SHOW_PROBES`, `CLEAR_PROBES`

**Why the v13 additions exist:** the spoilboard eats ~18 mm of Z, so the hop-over auto routines can't always lift clear of the part to travel over it. The manual flow sidesteps this: probe one side → **jog around the part by hand** → probe the other side → `COMPUTE_CENTER` (reports center + width per completed axis pair; add `GOTO=1` to drive to center, Z untouched). Works for outside (block) and inside (bore/slot) the same way. The raw `PROBE_*` commands save their edges automatically; `SHOW_PROBES` lists them, `CLEAR_PROBES` resets. (In practice 8 mm and likely 15 mm stock leave enough Z hop for the auto routines too, but the manual commands remain useful.)

**Status:** working well as-is. User intends to write proper documentation and release it later — not yet done.

---

## Proven Cutting Parameters

- **Wood (validation square):** 2D adaptive rough, 3 mm DOC, 100% WOC, 20 mm/s; finishing contour.
- **Aluminium (6082, 6 mm 1F carbide):** spot drill 2.5 mm @ 600 mm/min plunge to 1 mm; 3.5 mm peck drill; bore/rough 2D adaptive **1 mm DOC, 1.8 mm WOC, 1200 mm/min**; finishing 2D contour passes. 6 mm holes finished on the drill press. Headroom to push DOC to ~1.5–2 mm later. Cutting is loud but the machine sounds happy; residual vibration is attributed to the ABS-GF Z motor mount.

---

## Immediate Next Steps

1. **NEMA23 motor risers (NEXT machining job).** 36 mm tall. Original ABS-GF design was 10 mm wide (really ~8 mm + a cutout to clear the motor boss). **Plan: 8 mm 6082 solid stock** — the narrower stock removes the need for the boss cutout, leaving two simple rectangular blocks. CNC spot-drills the hole locations, drill press finishes to 5–5.5 mm. **Verify clearances in CAD first** (confirm 8 mm width clears the motor boss with margin). Tube standoffs (8 mm OD / 6 mm ID, steel or alu) were considered and **rejected** — narrow base wobble risk; solid 8 mm wins.
2. **1.5 kW spindle:** re-solder male connector → machine spindle risers (8 or 15 mm 6082) → install → re-tram.
3. **Recalibrate CAM endmill diameters** (currently 5.835 mm).
4. **Left X roller plate:** install at the next X-axis teardown, and **thread-lock the X axis** then (blue Loctite 243 on accessible bolts; clean threads with IPA first).
5. Measure **YZ skew** only if Z tilt ever shows up in finished parts.

---

## Parts Machining Queue

| Priority | Part | Material | Status |
|----------|------|----------|--------|
| 1 | X-axis roller plate, right | 8 mm 6082 | ✅ machined + installed |
| 1 | X-axis roller plate, left | 8 mm 6082 | ✅ machined, install deferred to next X teardown |
| 2 | NEMA23 motor risers (×2) | 8 mm 6082 | **NEXT** — simple rectangular blocks |
| 3 | 1.5 kW spindle risers | 8 or 15 mm 6082 | needs CAD + machining |

---

## Material Stock Available

- **3 mm flatbar** (hardware store, 50 mm wide) — non-structural use
- **3 mm heated-bed aluminium** (Tronxy/Ender 3) — soft, prototype use
- **8 mm 6082 plate** — primary structural stock
- **10 mm** — some on hand
- **15 mm 6082 plate** — heavy structural, use deliberately (user won't face it down to make 10 mm risers — 8 mm solid is the chosen path for the risers)

---

## Tooling

- **Aluminium:** 1F and 2F 6 mm carbide; **ZrN coating for roughing**; **4F explicitly avoided for aluminium** (chip welding); spot drill and chamfer mill in inventory (chamfer mill now worth using on good parts for clean edges).
- **Steel:** 2F / 4F 6 mm carbide.
- **To add:** HSS reamers in common bearing-bore sizes — interpolated CNC bores aren't round enough for press/bearing fits, so interpolate slightly undersize and ream to size. Optionally more 2F/3F ZrN for aluminium roughing with the bigger spindle.

---

## Maintenance

- **Grease:** lithium-complex grease for linear rails and leadscrews. **Use one grease type across the whole machine.** **Moly and generic chassis grease explicitly avoided** (moly acts like grit; chassis grease is too thick).
- **Interval:** every 2–3 months given the aluminium-chip environment (more often if dusty).
- **Method:** brush chips off the rail first, then bead grease along the rail / leadscrew and cycle the axis through full travel ~20–30× to distribute (syringe-on-rail works fine; the block wipers pull it in). Leadscrews were switched from light machine oil to grease this build; everything was freshly greased.

---

## Future / V2 / Side Projects

- **V2 machine:** **UHPC concrete base** (~80–100 kg), engineered square from the start, all-metal. No timeline. (UHPC chosen over epoxy granite on cost; seal against moisture; embed steel inserts for all mounting points during the pour.)
- **Frame-flex mitigation (V1):** bolt a 4–8 mm steel flatbar to the open back face of the X gantry tube (40×40×2 mm, ~580 mm), M5/M6 every ~80–100 mm via 3D-printed drill + captive-nut jigs. Single-face bolting still helps. No welding access in the attic (a 3×4 m hut move is planned, far future).
- **MCU upgrade path:** **BTT Manta M5P** preferred (empty driver slots suit the external DM556s; modular — avoids soldered-driver boards like the BTT Rodent). **48 V PSU** (Meanwell LRS-480-48 class, ~15 A for headroom) if moving to NEMA23 everywhere — the current 24 V chokes NEMA23 high-speed torque. (NEMA23 sizing discussed: 2.2–2.5 Nm is plenty for X; protect Z holding torque if reshuffling motors.)
- **Air assist (aluminium):** 150 W airbrush compressor on hand; could add a blast nozzle. Waiting to see whether the 1.5 kW spindle's fan helps first. Low priority.
- **Drill press (Parkside) — teardown ON HOLD** (still needed for current work). Two issues: ~**2 mm quill play** (manufacturing tolerance on a new unit, not wear) and a flexy ~3 mm steel table. Plans discussed: full teardown to inspect (a careful reassembly might fix it — unseated bearing / circlip / preload); if it's quill-to-casting clearance, an **aluminium sleeve** to take up play (needs a lathe to bore/turn concentric); table **gusset or thick auxiliary table** for flex. Teardown order if attempted: pop chuck (wedge slot) → lower + lock quill → strip external hardware → **mind the return spring (under tension)** → remove feed-pinion circlip → slide quill out → measure clearance.
- **Bench lathe** (~100–150 mm swing) interest — was on hold until V1 done; now mildly relevant for the drill-press sleeve idea.

---

## Appendix — Skew Validation G-code (reference)

The **machined 100×100 square** (measure two diagonals + a side → `SET_SKEW XY=AC,BD,AD`) is the method that worked and the one to use. The dot-pattern version below is kept as a quick reference; remember dot diagonals carry the ~0.2 mm caliper artifact, so treat a machined square/part as the real confirmation.

4-dot rectangle/square pattern (no spindle/dwell, simple moves; assumes Z0 at surface, start at X0 Y0 Z5). For a 100×100 square use the points shown; scale as needed:

```gcode
G90
G1 F1000

; Point 1 - X0 Y0
G1 X0 Y0
G1 Z0
G1 Z5

; Point 2 - X0 Y100
G1 X0 Y100
G1 Z0
G1 Z5

; Point 3 - X100 Y100
G1 X100 Y100
G1 Z0
G1 Z5

; Point 4 - X100 Y0
G1 X100 Y0
G1 Z0
G1 Z5

; Back to start
G1 X0 Y0
```

Measure diagonals AC = P1→P3 and BD = P2→P4, and side AD = P1→P4, then `SET_SKEW XY=AC,BD,AD`.

---

## Suggested Skills for Next Agent

- **file-reading** — use if the user uploads an updated `printer.cfg`, `macros.cfg`, or the `touch_probe.py` plugin for review (read large/binary files from disk rather than pasting).
- **Web search** — useful for Klipper documentation lookups (https://www.klipper3d.org) and component/PSU/driver specs.
- **No document-generation skills needed** (docx/pdf/pptx/xlsx/frontend) unless the user later asks for the touch-probe README/release docs — at which point the markdown can be written directly.

---

*Standalone handoff. Machine is cutting accurate aluminium (validated on the first 8 mm roller plate). XY skew is resolved and saved as profile `cnc`. Active thread: NEMA23 risers in 8 mm 6082. No sensitive data in this document.*