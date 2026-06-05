# ADR-0003: active_p exposed by WCS plugin, not computed in macros

## Status
Accepted

## Context
The ZERO_X/Y/Z/ALL macros need to call `G10 L20 P<n>` targeting the active WCS.
The P number (1–6) is the integer form of the active WCS name (G54=1, G55=2, …).
The canonical mapping already lives in the plugin as `WCS_P_MAP`.

Two options were considered:
- Compute the reverse mapping inline in each macro via a Jinja2 dict literal
- Expose `active_p` (the integer P for the currently active WCS) from `get_status()`

## Decision
Expose `active_p` from `get_status()` in `work_coordinate_systems.py` via a
module-level reverse map `WCS_NAME_TO_P`.

## Reasons
- The WCS→P mapping already lives in the plugin. Duplicating it in every macro
  creates two sources of truth that can silently diverge.
- Macros should express intent (`zero X in the active WCS`), not navigation logic.
- A single fix point: if WCS names or P numbering ever change, only the plugin
  needs updating.

## Consequences
- Macros that target the active WCS depend on
  `printer.work_coordinate_systems.active_p` being available.
- Any future macro or script needing the active P number should read it from the
  plugin, not recompute it.
