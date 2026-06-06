# ADR-0007: Tag-and-freeze upstream tracking for E3CNC forks

## Status
Accepted

## Context
E3CNC maintains forks of two actively-developed upstream projects:

- **Klipper** (`klipper3d/klipper`) — the firmware host. Klipper releases frequently,
  and its internal APIs (trsync, sched, MCU command protocol) change without a
  stable ABI guarantee. E3CNC's `cnc_control.c` calls directly into `trsync.h`,
  `sched.h`, and `basecmd.h`. `cnc_controls.py` uses internal MCU command strings
  (`trsync_start`, `stepper_stop_on_trigger`, `trsync_trigger`) that have changed
  across Klipper releases before.

- **Mainsail** (`mainsail-crew/mainsail`) — the web UI. Vue 3 frontend; active
  development; E3CNC will add a WCS panel, branding changes, and mm/min display.

Three tracking strategies were considered:

1. **Continuous tracking:** Regularly pull upstream into the fork. Merge conflicts
   are frequent; C API changes break `cnc_control.c` without warning; every
   upstream commit is a potential regression.

2. **Tag-and-freeze:** Pin each fork to a specific upstream commit. Upgrade
   deliberately — pull upstream, audit diffs for breaking changes to touched
   APIs, test, then re-tag. Users know exactly which upstream version they run.

3. **Full divergence:** Never pull upstream again. Simplest operationally, but
   users miss all upstream bug fixes, security patches, and hardware support
   additions indefinitely.

## Decision
Use tag-and-freeze for both the Klipper and Mainsail forks.

Each fork is created from a specific upstream commit and tagged
`upstream-freeze-YYYY-MM-DD`. Upstream pulls are explicit events:
pull → audit API diffs → fix any breakage → test on hardware → tag the
new freeze point and publish a release.

## Reasons
- **C code stability:** `cnc_control.c` touches Klipper internals. A surprise
  upstream API change breaks the MCU firmware build. Deliberate upgrade windows
  with explicit diff audits eliminate this class of surprise.
- **User predictability:** Users installing a tagged E3CNC release get a known,
  tested combination of Klipper + Moonraker + Mainsail. They are never
  silently running a partially-compatible mix.
- **Maintenance pace:** E3CNC is a solo/small-team project. Continuous tracking
  imposes a maintenance tax on every upstream commit — unsustainable at this
  scale. Periodic deliberate upgrades amortise the cost.
- **Precedent:** This is the model used by RatOS, Danger-Klipper, and other
  serious Klipper forks. It is the standard approach for this class of project.

## Consequences
- Each fork's README must clearly document which upstream commit it is based on,
  so users and contributors can orient themselves.
- Upstream security fixes that affect E3CNC users require a deliberate upgrade
  cycle — they are not pulled automatically. The maintainer is responsible for
  monitoring Klipper and Mainsail release notes.
- The `install.sh` installer pins its clone to the tagged freeze commit, not
  to `HEAD` of the upstream project. Users get the tested version, not whatever
  upstream shipped yesterday.
- Moonraker is not forked and is installed from upstream at the version
  recommended by the pinned Klipper release.
