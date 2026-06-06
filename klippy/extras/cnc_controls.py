# CNC motion controls — Feed Hold, Pause, Stop.
#
# Implements four operator control states for CNC job execution:
#   Feed Hold  — hardware button, sub-5ms MCU halt, resumes on release (Issue #03)
#   Pause      — CNC_PAUSE command, Z retract + spindle off, full resume seq (Issue #04)
#   Stop       — CNC_STOP command, job cancelled (Issue #05)
#   Emergency  — existing M112 / Klipper shutdown, unchanged
#
# ADR-0005: MCU hard stop via trsync (not buffer drain or drip_move).
# ADR-0006: Feed Hold button silently ignored during homing and probing.
#
# Config:
#   [cnc_controls]
#   feed_hold_pin: ^PA3          # MCU GPIO, normally-open button to GND
#   pause_retract_height: 45     # optional, absolute machine-space Z mm
#   spindle_dwell: 5.0           # optional seconds (default 5.0)
#   rapid_speed: 50.             # optional mm/s for retract / return moves (default 50)

import logging

BUTTON_SAMPLE_TIME  = 0.000015
BUTTON_SAMPLE_COUNT = 4
BUTTON_REST_TIME    = 0.001

# Trigger reasons — distinguish press / Pause / Stop in _trigger_in_reactor.
REASON_PRESS  = 1
REASON_PAUSE  = 2
REASON_STOP   = 3

STATE_ARMED   = 'armed'    # button polling active, ready for press
STATE_HOLDING = 'holding'  # button held, polling for release
STATE_PAUSED  = 'paused'   # Pause active, Z retracted, spindle off


class CNCControls:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode   = self.printer.lookup_object('gcode')

        # ── Pin ──────────────────────────────────────────────────────────────
        ppins      = self.printer.lookup_object('pins')
        pin_params = ppins.lookup_pin(config.get('feed_hold_pin'),
                                      can_invert=True, can_pullup=True)
        self._mcu    = pin_params['chip']
        self._pin    = pin_params['pin']
        self._pullup = pin_params['pullup']
        self._invert = pin_params['invert']

        # ── Config ───────────────────────────────────────────────────────────
        self._cfg_retract_height = config.getfloat(
            'pause_retract_height', None, minval=0.)
        self.pause_retract_height = None   # clamped at connect time
        self.spindle_dwell  = config.getfloat('spindle_dwell', 5.0, minval=0.)
        self._rapid_speed   = config.getfloat('rapid_speed', 50., above=0.)

        # ── MCU objects ───────────────────────────────────────────────────────
        self._button_oid  = self._mcu.create_oid()
        self._trsync_oid  = self._mcu.create_oid()
        self._cmd_queue   = self._mcu.alloc_command_queue()

        self._arm_cmd          = None
        self._disarm_cmd       = None
        self._trsync_start_cmd = None
        self._stepper_stop_cmd = None
        self._trsync_query_cmd = None   # synchronous trigger+wait

        # ── Runtime state ─────────────────────────────────────────────────────
        self._state         = STATE_ARMED
        self._armed         = False
        self._arm_for_release = False
        self._axis_steppers = []
        self._halt_pos      = None
        self._resume_target = None
        self._resume_speed  = None

        # ── Setup ─────────────────────────────────────────────────────────────
        self._mcu.register_config_callback(self._build_config)
        self.printer.register_event_handler('klippy:connect',
                                            self._handle_connect)
        self.printer.register_event_handler('klippy:ready',
                                            self._handle_ready)
        self.printer.register_event_handler('homing:homing_move_begin',
                                            self._handle_homing_begin)
        self.printer.register_event_handler('homing:homing_move_end',
                                            self._handle_homing_end)
        self.gcode.register_command('CNC_PAUSE',  self.cmd_CNC_PAUSE,
                                    desc="Instant CNC pause with Z retract")
        self.gcode.register_command('CNC_RESUME', self.cmd_CNC_RESUME,
                                    desc="Resume from CNC pause")
        self.gcode.register_command('CNC_STOP',   self.cmd_CNC_STOP,
                                    desc="Instant stop and job cancel")

    # ── MCU config ────────────────────────────────────────────────────────────

    def _build_config(self):
        mcu = self._mcu
        mcu.add_config_cmd(
            "config_cnc_button oid=%d pin=%s pull_up=%d"
            % (self._button_oid, self._pin, self._pullup))
        mcu.add_config_cmd(
            "config_trsync oid=%d" % (self._trsync_oid,))
        mcu.add_config_cmd(
            "cnc_button_disarm oid=%d" % (self._button_oid,),
            on_restart=True)
        mcu.add_config_cmd(
            "trsync_start oid=%d report_clock=0 report_ticks=0 expire_reason=0"
            % (self._trsync_oid,), on_restart=True)
        self._arm_cmd = mcu.lookup_command(
            "cnc_button_arm oid=%c trsync_oid=%c trigger_reason=%c"
            " sample_ticks=%u sample_count=%c rest_ticks=%u"
            " pin_value=%c clock=%u",
            cq=self._cmd_queue)
        self._disarm_cmd = mcu.lookup_command(
            "cnc_button_disarm oid=%c", cq=self._cmd_queue)
        self._trsync_start_cmd = mcu.lookup_command(
            "trsync_start oid=%c report_clock=%u report_ticks=%u expire_reason=%c",
            cq=self._cmd_queue)
        self._stepper_stop_cmd = mcu.lookup_command(
            "stepper_stop_on_trigger oid=%c trsync_oid=%c",
            cq=self._cmd_queue)
        # Synchronous trigger+wait: used by CNC_PAUSE and CNC_STOP.
        self._trsync_query_cmd = mcu.lookup_query_command(
            "trsync_trigger oid=%c reason=%c",
            "trsync_state oid=%c can_trigger=%c trigger_reason=%c clock=%u",
            oid=self._trsync_oid, cq=self._cmd_queue)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _handle_connect(self):
        kin = self.printer.lookup_object('toolhead').get_kinematics()
        self._axis_steppers = [s for s in kin.get_steppers()
                               if s.get_mcu() is self._mcu]
        # Resolve pause_retract_height — clamp to Z position_max.
        z_max = None
        if hasattr(kin, 'rails'):
            for rail in kin.rails:
                for s in rail.get_steppers():
                    if s.get_name() == 'stepper_z':
                        z_max = rail.position_max
                        break
        if self._cfg_retract_height is None:
            self.pause_retract_height = z_max
        elif z_max is not None:
            self.pause_retract_height = min(self._cfg_retract_height, z_max)
        else:
            self.pause_retract_height = self._cfg_retract_height

    def _handle_ready(self):
        self._arm()

    # ── Arm / disarm ──────────────────────────────────────────────────────────

    def _arm(self, for_release=False):
        if self._armed or not self._axis_steppers:
            return
        mcu      = self._mcu
        toolhead = self.printer.lookup_object('toolhead')
        clock    = mcu.print_time_to_clock(toolhead.get_last_move_time())

        # Reset trsync — clears previous stepper_stop signals without firing.
        self._trsync_start_cmd.send([self._trsync_oid, clock, 0, 0])

        if not for_release:
            # Only register stepper stops for press detection.
            for s in self._axis_steppers:
                self._stepper_stop_cmd.send([s.get_oid(), self._trsync_oid])

        mcu.register_response(self._handle_trsync_state,
                              "trsync_state", self._trsync_oid)

        # pin_value: what gpio_in_read returns when button is NOT pressed.
        # Normally-open + pullup → pin HIGH at rest → LOW when pressed.
        # press  trigger: fire on LOW → pin_value = 0 ^ invert
        # release trigger: fire on HIGH → pin_value = 1 ^ invert
        pin_value    = (1 ^ self._invert) if for_release else (0 ^ self._invert)
        sample_ticks = mcu.seconds_to_clock(BUTTON_SAMPLE_TIME)
        rest_ticks   = mcu.seconds_to_clock(BUTTON_REST_TIME)
        self._arm_cmd.send([
            self._button_oid, self._trsync_oid, REASON_PRESS,
            sample_ticks, BUTTON_SAMPLE_COUNT, rest_ticks,
            pin_value, clock,
        ], reqclock=clock)

        self._armed         = True
        self._arm_for_release = for_release
        logging.info("cnc_controls: armed (for_release=%s)", for_release)

    def _disarm(self):
        if not self._armed:
            return
        self._disarm_cmd.send([self._button_oid])
        # Clear trsync signals without firing them.
        self._trsync_start_cmd.send([self._trsync_oid, 0, 0, 0])
        self._mcu.register_response(None, "trsync_state", self._trsync_oid)
        self._armed = False
        logging.info("cnc_controls: disarmed")

    # ── Homing / probing exclusion (ADR-0006) ─────────────────────────────────

    def _handle_homing_begin(self, homing_state):
        self._disarm()

    def _handle_homing_end(self, homing_state):
        if self._state in (STATE_ARMED, STATE_HOLDING):
            self._arm(for_release=(self._state == STATE_HOLDING))

    # ── Position reconciliation (Issue #02) ───────────────────────────────────

    def _reconcile_position(self, trigger_print_time):
        toolhead = self.printer.lookup_object('toolhead')
        # Flush so step history is complete up to trigger_print_time.
        toolhead.flush_step_generation()
        # Capture resume_target BEFORE set_position changes commanded_pos.
        resume_target = list(toolhead.commanded_pos)
        # Build per-stepper commanded positions at trigger time.
        kin = toolhead.get_kinematics()
        kin_spos = {
            s.get_name(): s.mcu_to_commanded_position(
                s.get_past_mcu_position(trigger_print_time))
            for s in kin.get_steppers()
        }
        halt_xyz = kin.calc_position(kin_spos)
        thpos    = toolhead.get_position()
        halt_pos = [
            halt_xyz[i] if halt_xyz[i] is not None else thpos[i]
            for i in range(3)
        ] + [thpos[3]]
        # Update host position model and reset MCU step clocks.
        toolhead.set_position(halt_pos)
        logging.info(
            "cnc_controls: halt=%.3f,%.3f,%.3f  target=%.3f,%.3f,%.3f",
            halt_pos[0], halt_pos[1], halt_pos[2],
            resume_target[0], resume_target[1], resume_target[2])
        return halt_pos, resume_target

    # ── Synchronous MCU halt (used by CNC_PAUSE and CNC_STOP) ────────────────

    def _force_halt_sync(self):
        """Arm trsync with stepper stops, force-trigger it, wait for response.
        Must be called after _disarm() so no async handler conflicts.
        Returns the trigger print_time for position reconciliation."""
        mcu      = self._mcu
        toolhead = self.printer.lookup_object('toolhead')
        clock    = mcu.print_time_to_clock(toolhead.get_last_move_time())
        self._trsync_start_cmd.send([self._trsync_oid, clock, 0, 0])
        for s in self._axis_steppers:
            if s.get_mcu() is mcu:
                self._stepper_stop_cmd.send([s.get_oid(), self._trsync_oid])
        params  = self._trsync_query_cmd.send([self._trsync_oid, REASON_PAUSE])
        clock64 = mcu.clock32_to_clock64(params['clock'])
        return mcu.clock_to_print_time(clock64)

    # ── Async trigger handler (physical button path) ──────────────────────────

    def _handle_trsync_state(self, params):
        """Called from MCU serial reader thread when trsync fires."""
        if params['can_trigger']:
            return   # periodic report, not a trigger
        self._armed = False
        self._mcu.register_response(None, "trsync_state", self._trsync_oid)
        reactor = self.printer.get_reactor()
        if self._arm_for_release:
            reactor.register_async_callback(
                lambda e: self._release_in_reactor(params))
        else:
            reactor.register_async_callback(
                lambda e: self._trigger_in_reactor(params))

    def _trigger_in_reactor(self, params):
        """Button pressed — stop SD loop, reconcile position, enter HOLDING."""
        mcu     = self._mcu
        clock64 = mcu.clock32_to_clock64(params['clock'])
        trigger_time = mcu.clock_to_print_time(clock64)

        v_sd = self.printer.lookup_object('virtual_sdcard', None)
        if v_sd and v_sd.is_active():
            v_sd.do_pause()

        halt_pos, resume_target = self._reconcile_position(trigger_time)

        self._halt_pos      = halt_pos
        self._resume_target = resume_target
        # Capture the current feed rate for later resume.
        gcode_move = self.printer.lookup_object('gcode_move')
        self._resume_speed = gcode_move.get_status().get('speed', 50.)

        self._state = STATE_HOLDING
        # Re-arm to detect button release (no stepper stops on release).
        self._arm(for_release=True)
        logging.info("cnc_controls: HOLDING at %.3f,%.3f,%.3f",
                     halt_pos[0], halt_pos[1], halt_pos[2])

    def _release_in_reactor(self, params):
        """Button released — issue resume move, continue SD loop."""
        toolhead = self.printer.lookup_object('toolhead')

        # Move from halt_pos to resume_target (completes the interrupted move).
        if self._resume_target:
            toolhead.manual_move(
                self._resume_target[:3] + [None],
                self._resume_speed or self._rapid_speed)

        v_sd = self.printer.lookup_object('virtual_sdcard', None)
        if v_sd and not v_sd.is_active():
            v_sd.do_resume()

        self._state = STATE_ARMED
        self._arm(for_release=False)
        logging.info("cnc_controls: RUNNING — resumed to target")

    # ── CNC_PAUSE (Issue #04) ─────────────────────────────────────────────────

    def cmd_CNC_PAUSE(self, gcmd):
        if self._state == STATE_PAUSED:
            gcmd.respond_info("Already paused")
            return
        if self._state == STATE_HOLDING:
            # Button is held — machine already stopped, just escalate to pause.
            self._disarm()
        else:
            self._disarm()
            # Stop SD work loop so no new lines are dispatched.
            v_sd = self.printer.lookup_object('virtual_sdcard', None)
            if v_sd and v_sd.is_active():
                v_sd.do_pause()
            # Synchronous MCU halt.
            trigger_time = self._force_halt_sync()
            halt_pos, resume_target = self._reconcile_position(trigger_time)
            self._halt_pos      = halt_pos
            self._resume_target = resume_target
            gcode_move = self.printer.lookup_object('gcode_move')
            self._resume_speed = gcode_move.get_status().get('speed',
                                                              self._rapid_speed)

        halt_pos = self._halt_pos or self.printer.lookup_object(
            'toolhead').get_position()

        # Retract Z to safe height.
        toolhead = self.printer.lookup_object('toolhead')
        retract_z = (self.pause_retract_height
                     if self.pause_retract_height is not None
                     else halt_pos[2])
        toolhead.manual_move([None, None, retract_z, None], self._rapid_speed)

        # Spindle off.
        self.gcode.run_script_from_command("M5")

        self._state = STATE_PAUSED
        gcmd.respond_info(
            "CNC paused at X=%.3f Y=%.3f Z=%.3f"
            % (halt_pos[0], halt_pos[1], halt_pos[2]))

    # ── CNC_RESUME (Issue #04) ────────────────────────────────────────────────

    def cmd_CNC_RESUME(self, gcmd):
        if self._state != STATE_PAUSED:
            gcmd.respond_info("Not paused")
            return

        toolhead   = self.printer.lookup_object('toolhead')
        halt_pos   = self._halt_pos
        resume_tgt = self._resume_target

        # Spindle on.
        self.gcode.run_script_from_command("M3")

        # Wait for spindle to reach RPM.
        toolhead.dwell(self.spindle_dwell)

        # Return to hold position XY at retract height.
        if halt_pos:
            toolhead.manual_move(
                [halt_pos[0], halt_pos[1], None, None], self._rapid_speed)
            # Lower Z to hold position.
            toolhead.manual_move(
                [None, None, halt_pos[2], None], self._rapid_speed)

        # Complete the interrupted move.
        if resume_tgt:
            toolhead.manual_move(
                resume_tgt[:3] + [None],
                self._resume_speed or self._rapid_speed)

        # Resume SD work loop from current file position.
        v_sd = self.printer.lookup_object('virtual_sdcard', None)
        if v_sd and not v_sd.is_active():
            v_sd.do_resume()

        self._state = STATE_ARMED
        self._arm(for_release=False)
        gcmd.respond_info("CNC resumed")

    # ── CNC_STOP (Issue #05) ──────────────────────────────────────────────────

    def cmd_CNC_STOP(self, gcmd):
        v_sd = self.printer.lookup_object('virtual_sdcard', None)

        if self._state == STATE_PAUSED:
            # Machine is already stopped; spindle is already off.
            pass
        elif self._state == STATE_HOLDING:
            # Button held — machine is stopped; spindle still on.
            self._disarm()
            self.gcode.run_script_from_command("M5")
        else:
            # Machine may be moving — hard stop.
            self._disarm()
            if v_sd and v_sd.is_active():
                v_sd.do_pause()
            self._force_halt_sync()   # stop steppers; ignore position
            self.gcode.run_script_from_command("M5")

        # Cancel the job.
        if v_sd:
            v_sd.do_cancel()

        self._halt_pos = self._resume_target = None
        self._state    = STATE_ARMED
        # Re-arm for the next job.
        self._arm(for_release=False)
        gcmd.respond_info("CNC stopped — job cancelled")

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self, eventtime=None):
        return {
            'state':                self._state,
            'armed':                self._armed,
            'pause_retract_height': self.pause_retract_height,
            'spindle_dwell':        self.spindle_dwell,
        }


def load_config(config):
    return CNCControls(config)
