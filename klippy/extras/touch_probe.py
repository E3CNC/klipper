# Simple XY touch probe for CNC use (Klipper)
# v13 - adds manual center finding from saved probes (COMPUTE_CENTER), for
#       setups without enough Z travel to use the auto hop-over routines.
#       PROBE_X/Y_POS/NEG now also report AND save the tip-compensated edge.
#       New: COMPUTE_CENTER, SHOW_PROBES, CLEAR_PROBES.

import logging

DIRECTION_MAP = {
    "X+": (0, +1),
    "X-": (0, -1),
    "Y+": (1, +1),
    "Y-": (1, -1),
}


# ── Endstop wrapper ──────────────────────────────────────────────────────────

class ProbeEndstopWrapper:
    def __init__(self, config, axis):
        self.printer = config.get_printer()
        self.axis = axis

        ppins = self.printer.lookup_object('pins')
        pin   = config.get('pin')
        ppins.allow_multi_use_pin(pin.replace('^', '').replace('!', ''))

        pin_params       = ppins.lookup_pin(pin, can_invert=True, can_pullup=True)
        mcu              = pin_params['chip']
        self.mcu_endstop = mcu.setup_pin('endstop', pin_params)

        self.printer.register_event_handler(
            'klippy:mcu_identify', self._handle_mcu_identify
        )

        # Expose required MCU endstop methods
        self.get_mcu       = self.mcu_endstop.get_mcu
        self.add_stepper   = self.mcu_endstop.add_stepper
        self.get_steppers  = self.mcu_endstop.get_steppers
        self.home_start    = self.mcu_endstop.home_start
        self.home_wait     = self.mcu_endstop.home_wait
        self.query_endstop = self.mcu_endstop.query_endstop

    def _handle_mcu_identify(self):
        kin = self.printer.lookup_object('toolhead').get_kinematics()
        for stepper in kin.get_steppers():
            if stepper.is_active_axis(self.axis):
                self.add_stepper(stepper)

    def get_position_endstop(self):
        return 0.0


# ── Main plugin ──────────────────────────────────────────────────────────────

class TouchProbe:
    def __init__(self, config):
        self.printer = config.get_printer()

        # Config parameters (all overridable per-command except tip_diameter)
        self.fast_speed   = config.getfloat("fast_speed",       10.0, above=0.)
        self.slow_speed   = config.getfloat("slow_speed",        1.0, above=0.)
        self.max_distance = config.getfloat("max_distance",     50.0, above=0.)
        self.retract_dist = config.getfloat("retract_distance",  2.0, above=0.)
        self.tip_diameter = config.getfloat("tip_diameter",      1.0, above=0.)
        self.z_hop        = config.getfloat("z_hop",            10.0, above=0.)
        self.z_hop_speed  = config.getfloat("z_hop_speed",      10.0, above=0.)
        self.overshoot      = config.getfloat("overshoot",         5.0, above=0.)
        self.samples        = config.getint( "samples",          1,   minval=1)
        self.trigger_offset = config.getfloat("trigger_offset",  0.0)
        self.travel_speed   = config.getfloat("travel_speed",   50.0, above=0.)

        # One endstop wrapper per axis — critical for correct stepper association
        self.endstop_x = ProbeEndstopWrapper(config, 'x')
        self.endstop_y = ProbeEndstopWrapper(config, 'y')

        self.gcode = self.printer.lookup_object("gcode")

        # In-memory store of the most recent tip-compensated edge for each
        # direction ("X+", "X-", "Y+", "Y-"). Used by COMPUTE_CENTER so center
        # finding works without the Z travel the auto hop-over routines need.
        # Cleared with CLEAR_PROBES; otherwise survives until Klipper restart.
        self.saved_edges = {}

        # Raw probe commands
        self.gcode.register_command("PROBE_X_POS", self.cmd_probe_x_pos)
        self.gcode.register_command("PROBE_X_NEG", self.cmd_probe_x_neg)
        self.gcode.register_command("PROBE_Y_POS", self.cmd_probe_y_pos)
        self.gcode.register_command("PROBE_Y_NEG", self.cmd_probe_y_neg)

        # Edge finding
        self.gcode.register_command("FIND_EDGE_X_POS", self.cmd_find_edge_x_pos)
        self.gcode.register_command("FIND_EDGE_X_NEG", self.cmd_find_edge_x_neg)
        self.gcode.register_command("FIND_EDGE_Y_POS", self.cmd_find_edge_y_pos)
        self.gcode.register_command("FIND_EDGE_Y_NEG", self.cmd_find_edge_y_neg)

        # Center finding
        self.gcode.register_command("FIND_CENTER_X",  self.cmd_find_center_x)
        self.gcode.register_command("FIND_CENTER_Y",  self.cmd_find_center_y)
        self.gcode.register_command("FIND_CENTER_XY", self.cmd_find_center_xy)

        # Bore probing
        self.gcode.register_command("PROBE_BORE", self.cmd_probe_bore)

        # Manual center finding from saved probes (no Z hop-over required)
        self.gcode.register_command("COMPUTE_CENTER", self.cmd_compute_center)
        self.gcode.register_command("SHOW_PROBES",    self.cmd_show_probes)
        self.gcode.register_command("CLEAR_PROBES",   self.cmd_clear_probes)

    # ────────────────────────────────────────────────────────────────────────
    # Core probe: fast pass to locate surface, then N slow samples averaged
    # ────────────────────────────────────────────────────────────────────────

    def _do_probe(self, gcmd, direction):
        """
        Fast pass to locate the surface, retract, then perform SAMPLES slow
        passes and return the averaged trigger position as [x, y, z, e].
        """
        toolhead = self.printer.lookup_object("toolhead")
        homing   = self.printer.lookup_object("homing")

        axis, sense = DIRECTION_MAP[direction]
        endstop     = self.endstop_x if axis == 0 else self.endstop_y

        fast_speed = gcmd.get_float("FAST_SPEED", self.fast_speed, above=0.)
        slow_speed = gcmd.get_float("SLOW_SPEED", self.slow_speed, above=0.)
        samples    = gcmd.get_int(  "SAMPLES",    self.samples,    minval=1)

        curtime    = self.printer.get_reactor().monotonic()
        kin_status = toolhead.get_kinematics().get_status(curtime)
        axis_min   = kin_status["axis_minimum"][axis]
        axis_max   = kin_status["axis_maximum"][axis]

        # ── Fast pass: locate surface ────────────────────────────────────────
        pos    = toolhead.get_position()
        target = list(pos)
        if sense > 0:
            target[axis] = min(pos[axis] + self.max_distance, axis_max)
        else:
            target[axis] = max(pos[axis] - self.max_distance, axis_min)

        logging.info("Touch probe FAST %s -> %s at %.1f mm/s",
                     direction, target, fast_speed)
        try:
            hit = homing.probing_move(endstop, target, fast_speed)
        except self.printer.command_error as e:
            raise gcmd.error(str(e))

        # Retract from fast hit
        retract       = list(hit)
        retract[axis] = hit[axis] - sense * self.retract_dist
        retract[axis] = max(axis_min, min(axis_max, retract[axis]))
        toolhead.manual_move(retract, fast_speed)
        toolhead.wait_moves()

        # ── Slow passes: N samples ───────────────────────────────────────────
        sample_values = []
        last_epos     = None

        for i in range(samples):
            pos    = toolhead.get_position()
            target = list(pos)
            if sense > 0:
                target[axis] = min(pos[axis] + self.retract_dist * 2, axis_max)
            else:
                target[axis] = max(pos[axis] - self.retract_dist * 2, axis_min)

            logging.info("Touch probe SLOW %s sample %d/%d at %.1f mm/s",
                         direction, i + 1, samples, slow_speed)
            try:
                epos = homing.probing_move(endstop, target, slow_speed)
            except self.printer.command_error as e:
                raise gcmd.error(str(e))

            sample_values.append(epos[axis])
            last_epos = epos

            # Retract between samples and after the last one
            retract       = list(epos)
            retract[axis] = epos[axis] - sense * self.retract_dist
            retract[axis] = max(axis_min, min(axis_max, retract[axis]))
            toolhead.manual_move(retract, fast_speed)
            toolhead.wait_moves()

        # ── Average and report if multi-sample ──────────────────────────────
        avg = sum(sample_values) / len(sample_values)

        if samples > 1:
            mn  = min(sample_values)
            mx  = max(sample_values)
            rng = mx - mn
            axis_label = "X" if axis == 0 else "Y"
            gcmd.respond_info(
                "Samples (%d) on %s: %s\n"
                "  min=%.6f  max=%.6f  range=%.6f  avg=%.6f"
                % (
                    samples, axis_label,
                    ", ".join("%.6f" % v for v in sample_values),
                    mn, mx, rng, avg,
                )
            )

        # Return position with averaged axis value
        result       = list(last_epos)
        result[axis] = avg
        return result

    # ────────────────────────────────────────────────────────────────────────
    # Tip compensation
    # ────────────────────────────────────────────────────────────────────────

    def _calc_edge(self, epos, direction):
        """
        Apply tip radius + trigger offset compensation to a raw trigger position.

        Geometry: when probing in the + direction, the probe center has already
        travelled (tip_radius + trigger_offset) past the true surface when it
        fires. So the true surface is BEHIND the trigger point relative to the
        direction of travel:

            true_edge = trigger_pos - sense * (tip_radius + trigger_offset)

        This correctly pushes X+ edges back (lower X) and X- edges forward
        (higher X), widening the measured span to match the true object size.
        """
        axis, sense = DIRECTION_MAP[direction]
        edge = list(epos)
        edge[axis] = epos[axis] + sense * (
            (self.tip_diameter / 2.0) + self.trigger_offset
        )
        return edge

    # ────────────────────────────────────────────────────────────────────────
    # Z hop helpers  (always use full 4-element moves for Klipper compatibility)
    # ────────────────────────────────────────────────────────────────────────

    def _z_hop_up(self, toolhead, z_hop, z_hop_speed):
        pos = toolhead.get_position()
        toolhead.manual_move(
            [pos[0], pos[1], pos[2] + z_hop, pos[3]], z_hop_speed
        )
        toolhead.wait_moves()

    def _z_hop_down(self, toolhead, z_hop, z_hop_speed):
        pos = toolhead.get_position()
        toolhead.manual_move(
            [pos[0], pos[1], pos[2] - z_hop, pos[3]], z_hop_speed
        )
        toolhead.wait_moves()

    # ────────────────────────────────────────────────────────────────────────
    # Raw probe  (no tip compensation, no hop — debug / repeatability use)
    # ────────────────────────────────────────────────────────────────────────

    def _run_probe(self, gcmd, direction):
        epos = self._do_probe(gcmd, direction)
        edge = self._calc_edge(epos, direction)
        axis, _    = DIRECTION_MAP[direction]
        axis_label = "X" if axis == 0 else "Y"

        # Save the tip-compensated edge so COMPUTE_CENTER can use it later.
        # (Center comes out identical whether computed from raw triggers or
        # edges, but saving the edge also makes width/diameter come out right.)
        self.saved_edges[direction] = edge

        gcmd.respond_info(
            "Probe %s triggered at X=%.6f Y=%.6f Z=%.6f\n"
            "  edge (tip-comp): %s=%.6f  [saved as %s]"
            % (direction, epos[0], epos[1], epos[2],
               axis_label, edge[axis], direction)
        )

    # ────────────────────────────────────────────────────────────────────────
    # Edge finding  (tip compensation + hop to edge coordinate)
    # ────────────────────────────────────────────────────────────────────────

    def _find_edge(self, gcmd, direction):
        """
        Probe the surface, apply tip compensation, report the true edge
        coordinate, then hop up and move to that edge XY position so the
        tool is sitting directly above the edge ready for zeroing.
        """
        toolhead     = self.printer.lookup_object("toolhead")
        fast_speed   = gcmd.get_float("FAST_SPEED",   self.fast_speed,   above=0.)
        travel_speed = gcmd.get_float("TRAVEL_SPEED", self.travel_speed, above=0.)
        z_hop        = gcmd.get_float("Z_HOP",        self.z_hop,        above=0.)
        z_hop_speed  = gcmd.get_float("Z_HOP_SPEED",  self.z_hop_speed,  above=0.)

        axis, _    = DIRECTION_MAP[direction]
        axis_label = "X" if axis == 0 else "Y"

        epos = self._do_probe(gcmd, direction)
        edge = self._calc_edge(epos, direction)

        gcmd.respond_info(
            "Edge found — trigger: %s=%.6f  →  edge: %s=%.6f  (tip_diameter=%.3f)"
            % (axis_label, epos[axis], axis_label, edge[axis], self.tip_diameter)
        )

        # Hop up, then move XY to the compensated edge coordinate at travel speed
        self._z_hop_up(toolhead, z_hop, z_hop_speed)
        pos        = toolhead.get_position()
        move       = list(pos)
        move[axis] = edge[axis]
        toolhead.manual_move(move, travel_speed)
        toolhead.wait_moves()

    # ────────────────────────────────────────────────────────────────────────
    # Center finding  (hopover: probe +, hop, travel, probe -, hop, go center)
    # ────────────────────────────────────────────────────────────────────────

    def _find_center_hopover(self, gcmd, axis, distance=None):
        """
        Hopover sequence:
          1. Probe + side
          2. Z hop up
          3. Travel distance + overshoot in + direction
          4. Z hop down
          5. Probe - side
          6. Z hop up
          7. Move to calculated center (still hopped up, safe to zero)

        distance can be passed directly (from FIND_CENTER_XY) or is read
        from the DISTANCE gcmd parameter (from FIND_CENTER_X/Y).
        """
        toolhead     = self.printer.lookup_object("toolhead")
        fast_speed   = gcmd.get_float("FAST_SPEED",   self.fast_speed,   above=0.)
        travel_speed = gcmd.get_float("TRAVEL_SPEED", self.travel_speed, above=0.)
        z_hop        = gcmd.get_float("Z_HOP",        self.z_hop,        above=0.)
        z_hop_speed  = gcmd.get_float("Z_HOP_SPEED",  self.z_hop_speed,  above=0.)
        overshoot    = gcmd.get_float("OVERSHOOT",    self.overshoot,    above=0.)

        if distance is None:
            distance = gcmd.get_float("DISTANCE", above=0.)

        axis_label = "X" if axis == 0 else "Y"
        dir_pos    = "X+" if axis == 0 else "Y+"
        dir_neg    = "X-" if axis == 0 else "Y-"

        curtime    = self.printer.get_reactor().monotonic()
        kin_status = toolhead.get_kinematics().get_status(curtime)
        axis_min   = kin_status["axis_minimum"][axis]
        axis_max   = kin_status["axis_maximum"][axis]

        # Step 1: probe + side
        gcmd.respond_info("Center %s: probing %s side..." % (axis_label, dir_pos))
        epos_pos = self._do_probe(gcmd, dir_pos)
        edge_pos = self._calc_edge(epos_pos, dir_pos)

        # Step 2: hop up
        self._z_hop_up(toolhead, z_hop, z_hop_speed)

        # Step 3: travel over the stock at travel speed
        pos          = toolhead.get_position()
        travel       = list(pos)
        travel[axis] = min(epos_pos[axis] + distance + overshoot, axis_max)
        toolhead.manual_move(travel, travel_speed)
        toolhead.wait_moves()

        # Step 4: hop down
        self._z_hop_down(toolhead, z_hop, z_hop_speed)

        # Step 5: probe - side
        gcmd.respond_info("Center %s: probing %s side..." % (axis_label, dir_neg))
        epos_neg = self._do_probe(gcmd, dir_neg)
        edge_neg = self._calc_edge(epos_neg, dir_neg)

        # Step 6: hop up
        self._z_hop_up(toolhead, z_hop, z_hop_speed)

        # Step 7: calculate center and move to it (hopped up, safe to zero)
        center = (edge_pos[axis] + edge_neg[axis]) / 2.0
        width  = abs(edge_pos[axis] - edge_neg[axis])

        gcmd.respond_info(
            "Center %s found:\n"
            "  edge(+): %s=%.6f\n"
            "  edge(-): %s=%.6f\n"
            "  width:   %.6f mm\n"
            "  center:  %s=%.6f"
            % (
                axis_label,
                axis_label, edge_pos[axis],
                axis_label, edge_neg[axis],
                width,
                axis_label, center,
            )
        )

        pos        = toolhead.get_position()
        move       = list(pos)
        move[axis] = center
        toolhead.manual_move(move, travel_speed)
        toolhead.wait_moves()

        return center

    # ────────────────────────────────────────────────────────────────────────
    # Bore probing  (4-touch: X+, X-, Y+, Y- all from the same start point)
    # ────────────────────────────────────────────────────────────────────────

    def cmd_probe_bore(self, gcmd):
        """
        Probe a circular bore from its approximate center.
        Touches X+, X-, Y+, Y- — returning to start XY between each touch.
        Reports center X/Y and measured diameter on each axis.
        After completion hops up and moves to the calculated center.
        """
        toolhead     = self.printer.lookup_object("toolhead")
        fast_speed   = gcmd.get_float("FAST_SPEED",   self.fast_speed,   above=0.)
        travel_speed = gcmd.get_float("TRAVEL_SPEED", self.travel_speed, above=0.)
        z_hop        = gcmd.get_float("Z_HOP",        self.z_hop,        above=0.)
        z_hop_speed  = gcmd.get_float("Z_HOP_SPEED",  self.z_hop_speed,  above=0.)

        # Capture start — we return to this XY between every touch
        start = toolhead.get_position()

        def probe_and_return(direction):
            epos = self._do_probe(gcmd, direction)
            edge = self._calc_edge(epos, direction)
            # Return to start XY at travel speed
            toolhead.manual_move(
                [start[0], start[1], start[2], start[3]], travel_speed
            )
            toolhead.wait_moves()
            return edge

        gcmd.respond_info("Bore probe: probing X+...")
        edge_xp = probe_and_return("X+")

        gcmd.respond_info("Bore probe: probing X-...")
        edge_xn = probe_and_return("X-")

        gcmd.respond_info("Bore probe: probing Y+...")
        edge_yp = probe_and_return("Y+")

        gcmd.respond_info("Bore probe: probing Y-...")
        edge_yn = probe_and_return("Y-")

        center_x     = (edge_xp[0] + edge_xn[0]) / 2.0
        center_y     = (edge_yp[1] + edge_yn[1]) / 2.0
        diameter_x   = abs(edge_xp[0] - edge_xn[0])
        diameter_y   = abs(edge_yp[1] - edge_yn[1])
        avg_diameter = (diameter_x + diameter_y) / 2.0

        gcmd.respond_info(
            "Bore probe complete:\n"
            "  center:     X=%.6f  Y=%.6f\n"
            "  diameter X: %.6f mm\n"
            "  diameter Y: %.6f mm\n"
            "  avg diam:   %.6f mm"
            % (center_x, center_y, diameter_x, diameter_y, avg_diameter)
        )

        # Hop up and move to bore center at travel speed
        self._z_hop_up(toolhead, z_hop, z_hop_speed)
        pos = toolhead.get_position()
        toolhead.manual_move(
            [center_x, center_y, pos[2], pos[3]], travel_speed
        )
        toolhead.wait_moves()

    # ────────────────────────────────────────────────────────────────────────
    # Manual center finding from saved probes
    #
    # Workflow (no Z hop-over, so it works with limited Z travel):
    #   1. Jog to one side, run PROBE_X_POS         (saves the X+ edge)
    #   2. Jog around the part by hand to the far side, run PROBE_X_NEG
    #   3. (optional) repeat with PROBE_Y_POS / PROBE_Y_NEG
    #   4. COMPUTE_CENTER          -> center (+ width) for each completed pair
    #      COMPUTE_CENTER GOTO=1   -> also moves XY to center (Z untouched)
    # Works for outside (block) and inside (bore/slot) the same way.
    # ────────────────────────────────────────────────────────────────────────

    def cmd_compute_center(self, gcmd):
        have_x = "X+" in self.saved_edges and "X-" in self.saved_edges
        have_y = "Y+" in self.saved_edges and "Y-" in self.saved_edges

        if not have_x and not have_y:
            raise gcmd.error(
                "No complete probe pair saved. Probe X+ and X- "
                "(and/or Y+ and Y-) first, then run COMPUTE_CENTER. "
                "Use SHOW_PROBES to see what is currently saved."
            )

        lines = ["Center from saved probes:"]
        center_x = center_y = None

        if have_x:
            xp = self.saved_edges["X+"][0]
            xn = self.saved_edges["X-"][0]
            center_x = (xp + xn) / 2.0
            lines.append(
                "  X: edge+=%.6f  edge-=%.6f  width=%.6f  center=%.6f"
                % (xp, xn, abs(xp - xn), center_x)
            )
        else:
            lines.append("  X: incomplete (need both X+ and X-)")

        if have_y:
            yp = self.saved_edges["Y+"][1]
            yn = self.saved_edges["Y-"][1]
            center_y = (yp + yn) / 2.0
            lines.append(
                "  Y: edge+=%.6f  edge-=%.6f  width=%.6f  center=%.6f"
                % (yp, yn, abs(yp - yn), center_y)
            )
        else:
            lines.append("  Y: incomplete (need both Y+ and Y-)")

        gcmd.respond_info("\n".join(lines))

        # Optional move to the computed center. XY only — Z is never changed,
        # so the operator is responsible for ensuring the probe is clear.
        if gcmd.get_int("GOTO", 0):
            toolhead     = self.printer.lookup_object("toolhead")
            travel_speed = gcmd.get_float("TRAVEL_SPEED",
                                          self.travel_speed, above=0.)
            pos  = toolhead.get_position()
            move = list(pos)
            if center_x is not None:
                move[0] = center_x
            if center_y is not None:
                move[1] = center_y
            gcmd.respond_info(
                "GOTO=1: moving to X=%.6f Y=%.6f at %.1f mm/s "
                "(Z unchanged — make sure the probe is clear of the part)"
                % (move[0], move[1], travel_speed)
            )
            toolhead.manual_move(move, travel_speed)
            toolhead.wait_moves()

    def cmd_show_probes(self, gcmd):
        if not self.saved_edges:
            gcmd.respond_info(
                "No saved probes. PROBE_X_POS / X_NEG / Y_POS / Y_NEG "
                "save automatically."
            )
            return
        lines = ["Saved probe edges (tip-compensated):"]
        for d in ("X+", "X-", "Y+", "Y-"):
            if d in self.saved_edges:
                axis, _ = DIRECTION_MAP[d]
                lines.append("  %s: %.6f" % (d, self.saved_edges[d][axis]))
        gcmd.respond_info("\n".join(lines))

    def cmd_clear_probes(self, gcmd):
        self.saved_edges = {}
        gcmd.respond_info("Cleared all saved probe results.")

    # ────────────────────────────────────────────────────────────────────────
    # Command dispatch
    # ────────────────────────────────────────────────────────────────────────

    # Raw probe
    def cmd_probe_x_pos(self, gcmd): self._run_probe(gcmd, "X+")
    def cmd_probe_x_neg(self, gcmd): self._run_probe(gcmd, "X-")
    def cmd_probe_y_pos(self, gcmd): self._run_probe(gcmd, "Y+")
    def cmd_probe_y_neg(self, gcmd): self._run_probe(gcmd, "Y-")

    # Edge finding
    def cmd_find_edge_x_pos(self, gcmd): self._find_edge(gcmd, "X+")
    def cmd_find_edge_x_neg(self, gcmd): self._find_edge(gcmd, "X-")
    def cmd_find_edge_y_pos(self, gcmd): self._find_edge(gcmd, "Y+")
    def cmd_find_edge_y_neg(self, gcmd): self._find_edge(gcmd, "Y-")

    # Center finding
    def cmd_find_center_x(self, gcmd):
        self._find_center_hopover(gcmd, axis=0)

    def cmd_find_center_y(self, gcmd):
        self._find_center_hopover(gcmd, axis=1)

    def cmd_find_center_xy(self, gcmd):
        toolhead     = self.printer.lookup_object("toolhead")
        fast_speed   = gcmd.get_float("FAST_SPEED",   self.fast_speed,   above=0.)
        travel_speed = gcmd.get_float("TRAVEL_SPEED", self.travel_speed, above=0.)
        z_hop        = gcmd.get_float("Z_HOP",        self.z_hop,        above=0.)
        z_hop_speed  = gcmd.get_float("Z_HOP_SPEED",  self.z_hop_speed,  above=0.)
        overshoot    = gcmd.get_float("OVERSHOOT",    self.overshoot,    above=0.)
        distance_x   = gcmd.get_float("DISTANCE_X", above=0.)
        distance_y   = gcmd.get_float("DISTANCE_Y", above=0.)

        curtime    = self.printer.get_reactor().monotonic()
        kin_status = toolhead.get_kinematics().get_status(curtime)
        y_min      = kin_status["axis_minimum"][1]

        # Step 1: find X center — ends hopped up, at X center, arbitrary Y
        cx = self._find_center_hopover(gcmd, axis=0, distance=distance_x)

        # Step 2: still hopped up — travel to Y start at travel speed
        pos     = toolhead.get_position()
        y_start = max(y_min, pos[1] - (distance_y / 2.0 + overshoot))
        toolhead.manual_move([pos[0], y_start, pos[2], pos[3]], travel_speed)
        toolhead.wait_moves()

        # Step 3: drop down — now correctly positioned for Y+ first touch
        self._z_hop_down(toolhead, z_hop, z_hop_speed)

        # Step 4: find Y center
        cy = self._find_center_hopover(gcmd, axis=1, distance=distance_y)

        gcmd.respond_info(
            "Center XY complete:\n"
            "  X=%.6f\n"
            "  Y=%.6f"
            % (cx, cy)
        )


def load_config(config):
    return TouchProbe(config)