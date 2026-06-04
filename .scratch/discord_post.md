# Work Coordinate Systems for E3CNC Klipper — drop-in plugin

> **Files attached:** `work_coordinate_systems.py` · `wcs_macros.cfg`
> No extra hardware. No touch probe required. Pure drop-in.

---

## The problem it solves

If you've been using the E3CNC Klipper config, you've been zeroing your machine with `ZERO_X`, `ZERO_Y`, `ZERO_Z` — macros that call `SET_KINEMATIC_POSITION` under the hood. That works for a single setup, but it has a nasty edge case: if Klipper restarts mid-job, or you home the machine at the wrong moment, your zero is silently gone. The machine has no idea where your part is anymore. That's how crashes happen.

I'm serial 002, and I've been running this machine long enough to hit that scenario more than once. So I built a fix.

---

## What this adds

**Work Coordinate Systems** (G54–G59) are how professional CNC machines handle this. Instead of telling Klipper "pretend X=0 right now," you define a named coordinate frame — a saved zero point — and the machine always knows where it is relative to your part, even after a restart.

This plugin brings that to Klipper. Six independent coordinate systems (G54–G59), persistent across restarts, with dashboard buttons so you never have to type a G-code command manually.

**What you get:**
- `WCS_1` → `WCS_6` — dashboard buttons to switch between coordinate systems
- `MACHINE_COORDS` — temporarily see raw machine coordinates (useful for diagnostics)
- `ZERO_X` / `ZERO_Y` / `ZERO_Z` / `ZERO_ALL` — zero the active coordinate system, not just "the machine position"
- Offsets survive Klipper restarts automatically — no re-zeroing after a crash
- `WCS_STATUS` — print all six coordinate systems and their saved origins to the console

This is a **Klipper plugin** — a single Python file that drops into Klipper's extras folder. Klipper supports this natively; most people just don't know it's possible.

---

## Install — 4 steps

**1. Drop the plugin file into Klipper's extras folder**
```
~/klipper/klippy/extras/work_coordinate_systems.py
```

**2. Add to `printer.cfg`**
```ini
[work_coordinate_systems]
```

**3. Add the macros file to your config folder and include it**

Drop `wcs_macros.cfg` wherever you keep your config files, then add to `printer.cfg`:
```ini
[include macros/wcs_macros.cfg]
```
*(adjust the path to match where you put it)*

**4. Comment out your old ZERO macros**

If you have `ZERO_X`, `ZERO_Y`, `ZERO_Z`, `ZERO_ALL` in your existing `macros.cfg`, comment them out — the new ones in `wcs_macros.cfg` replace them. Put a `#` in front of the `[gcode_macro ZERO_X]` line and all its contents.

Restart Klipper. Done.

---

---
<!-- ✂ SPLIT HERE if Discord cuts off — paste everything below as a reply -->
---

## Basic workflow

```
1. Home the machine (G28)
2. Click WCS_1 on the dashboard  ← select your coordinate system
3. Jog to your part zero position
4. Click ZERO_ALL                 ← saves X, Y, Z in WCS 1
5. Run your job as normal
```

If Klipper restarts for any reason, your zero is reloaded automatically. Just home, select WCS_1 again, and carry on.

Got two setups on the table at the same time? Zero them into WCS_1 and WCS_2 separately, then switch between them with the dashboard buttons between jobs.

---

## What's coming next

The next plugin in this series is a **tool setter** — a fixed touch pad at the back of the machine. Change tools, tap the setter, and all your coordinate systems update their Z offset automatically. No re-zeroing after a tool change.

I'm also thinking longer term about a proper E3CNC Klipper + Mainsail setup that makes it easier for people to get into CNC on this hardware without fighting the config from scratch. More on that when it's ready.

---

*Running on my E3CNC (serial 002) — tested on real aluminium cuts. Drop questions below.*
