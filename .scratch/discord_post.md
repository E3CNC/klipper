# Work Coordinate Systems for E3CNC Klipper — drop-in plugin

> **Files attached:** `work_coordinate_systems.py` · `wcs_macros.cfg`
> No extra hardware. No touch probe required. Pure drop-in.

---

## The problem

The default E3CNC Klipper config zeros the machine with `ZERO_X / Y / Z` — macros that use `SET_KINEMATIC_POSITION` under the hood. It works, until Klipper restarts mid-job or you home at the wrong moment. When that happens your zero is silently gone and the machine has no idea where your part is. That's how crashes happen.

## What this adds

**Work Coordinate Systems** (G54–G59) are how real CNC machines handle this. Instead of telling Klipper "pretend X=0 right now," you define a named, saved zero point — and the machine always knows where your part is, even after a restart.

**What you get:**
- `WCS_1` → `WCS_6` — dashboard buttons to switch between coordinate systems
- `ZERO_X` / `ZERO_Y` / `ZERO_Z` / `ZERO_ALL` — zero the active coordinate system
- `MACHINE_COORDS` — temporarily switch to raw machine coordinates
- `WCS_STATUS` — print all six systems and their saved origins to the console
- Offsets survive Klipper restarts automatically

This is a **Klipper plugin** — a Python file that drops into Klipper's extras folder. Klipper supports this natively; most people just don't know it's possible.

---
<!-- ✂ SPLIT — paste below as a reply -->
---

## Install — 4 steps

**1.** Drop `work_coordinate_systems.py` into Klipper's extras folder:
```
~/klipper/klippy/extras/
```

**2.** Add to `printer.cfg`:
```ini
[work_coordinate_systems]
```

**3.** Drop `wcs_macros.cfg` into your config folder and include it:
```ini
[include macros/wcs_macros.cfg]
```
*(adjust path to match where you put it)*

**4.** If you have `ZERO_X / Y / Z / ALL` in your existing `macros.cfg`, comment them out — the new ones in `wcs_macros.cfg` replace them.

Restart Klipper. Done.

---

## Basic workflow

```
1. Home  (G28)
2. Click WCS_1 on the dashboard
3. Jog to your part zero
4. Click ZERO_ALL
5. Run your job
```

Zero reloads automatically if Klipper restarts. Got two setups on the table? Zero them into WCS_1 and WCS_2 and switch between them with the dashboard buttons.

---

## What's next

Next up is a **tool setter** plugin — a fixed touch pad at the back of the machine. Change tools, tap the setter, and all coordinate systems update their Z offset automatically. No re-zeroing after a tool change.

Also thinking about a proper E3CNC Klipper + Mainsail setup that gives people a clean starting point without fighting the config from scratch — curious if there's interest.

Drop questions below.
