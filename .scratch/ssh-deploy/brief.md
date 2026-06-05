# Task: Stable IP + SSH deploy to Klipper laptop

## The problem

Linux Mint laptop in the attic runs Klipper for a CNC machine. It has two WiFi adapters:
- Internal board (built-in, sometimes wakes up unexpectedly)
- TP-Link USB adapter (the intended one, works well)

Both occasionally connect simultaneously, which fights with the router's static DHCP
reservation (set by MAC address for the TP-Link). When the internal board connects it
gets a different IP, making SSH unreliable. User has to walk upstairs and send files
manually.

## The goal

1. **Permanently disable the internal WiFi adapter** on Linux Mint so only the TP-Link
   USB adapter is ever active.
2. **Verify the static IP** from the router sticks reliably.
3. **Set up SSH key auth** from the Windows machine (c:\Users\Bogdan) to the laptop so
   no password prompt is needed.
4. **Add a deploy script** to the repo at `c:\Users\Bogdan\Desktop\klipper` so the agent
   can push plugin files to the laptop with a single command.

## What deploy looks like

Target on the laptop: `~/klipper/klippy/extras/` (standard Klipper install path — confirm
with user if different).

Files to deploy now:
- `klippy/extras/work_coordinate_systems.py` (new WCS plugin, not yet on laptop)

After deploy: restart Klipper service (`sudo systemctl restart klipper`) and add
`[work_coordinate_systems]` to `printer.cfg`.

## Repo context

- Path: `c:\Users\Bogdan\Desktop\klipper`
- Branch: `feature/cnc-plugins`
- OS: Windows 10, PowerShell available, Bash available via Git Bash
- Laptop OS: Linux Mint

## Steps to work through

1. On the laptop: identify the internal adapter name (`ip link` or `nmcli device`).
2. Disable it permanently — options in order of preference:
   a. NetworkManager: `nmcli device set <iface> managed no` + persist via udev rule
   b. Blacklist the kernel module (`/etc/modprobe.d/`)
   c. BIOS disable if accessible
3. Confirm TP-Link USB adapter holds the static IP after reboot.
4. On Windows: generate SSH key if not already present (`ssh-keygen`), copy public key
   to laptop (`ssh-copy-id` or manual `~/.ssh/authorized_keys`).
5. Test passwordless SSH: `ssh user@<ip> "echo ok"`.
6. Write `deploy.sh` (or PowerShell equivalent) in the repo root.
