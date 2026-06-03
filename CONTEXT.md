# E3CNC Klipper — Domain Glossary

## Machine Space

Coordinates measured from the machine's homed position. X=0 is the left rail endstop, Z=0 is bed level (but Z homes high — see Z home). All kinematic soft limits (`position_min` / `position_max`) are enforced in machine space, after any WCS transform has been applied. A negative G-code coordinate does not violate a `position_min: 0` limit if the resolved machine-space position is within range.

## Work Coordinate System (WCS)

One of six named coordinate frames (G54–G59) that each define a **WCS origin** — a point in machine space that reads as X=0, Y=0, Z=0 in that frame. Only one WCS is active at a time (the **active WCS**). All G-code move coordinates are interpreted relative to the active WCS origin.

## WCS Origin

The machine-space position of a WCS's zero point. Stored as [X, Y, Z] in machine-space absolute coordinates. Set with `G10 L20 P<n>` (from current tool position) or `G10 L2 P<n>` (explicit machine coords).

## Zeroing

The act of defining a WCS origin at the current tool position. `G10 L20 P1 X0 Y0 Z0` sets the G54 origin so the current position reads as X=0, Y=0, Z=0. Moving 50 mm in the positive X direction from the origin reads as X=50.

## Active WCS

The WCS currently in effect. All G-code moves are interpreted in the active WCS until a different one is explicitly selected. After every home (`G28`) or Klipper connect, the active WCS resets to G54 — stored offsets for G55–G59 are preserved on disk but must be re-selected explicitly. See ADR-0001.

## Machine Mode (G53)

A temporary override that suspends the active WCS and interprets move coordinates in raw machine space. Active until the next `G54`–`G59` command or a machine home.

## Tool Setter

A fixed touch pad at the back of the machine used to measure tool length differences after tool changes. Lives at a stable but arbitrary machine-space Z position — its absolute height is never measured or stored. Works purely on deltas: reference tool touches the setter after manual Z zero, subsequent tools touch it after each change, the Z difference is applied to every WCS simultaneously. Implemented as a separate plugin (`tool_setter.py`) — not part of the WCS plugin. Requires its own dedicated input pin.

## Tool Length Delta

The difference in Z touch position between the current tool and the reference tool at the tool setter. Applied to all WCS Z offsets simultaneously, because a longer or shorter tool affects every setup by the same amount.

## Reference Touch

The machine-space Z position recorded when the reference tool (the tool used for the initial manual Z zero) contacts the tool setter. Stored persistently. Only needs to be re-recorded when Klipper restarts or the setter is physically moved.

## Soft Limits

Klipper's kinematic travel bounds (`position_min` / `position_max`). Always checked in machine space. WCS does not expand or bypass them — a move that resolves to a machine-space position outside the bounds is rejected before any motion occurs.
