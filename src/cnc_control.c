// CNC feed hold button — monitors a GPIO and fires a trsync when pressed.
//
// Virtually identical to endstop.c but without the ESF_HOMING flag: the
// armed/disarmed distinction is handled on the host side by calling
// cnc_button_arm / cnc_button_disarm rather than by an in-MCU flag.
// The host registers all axis steppers via stepper_stop_on_trigger before
// arming, so a single trsync_do_trigger halts the whole machine.
//
// Copyright (C) 2026 E3CNC project
// This file may be distributed under the terms of the GNU GPLv3 license.

#include "basecmd.h"    // oid_alloc
#include "board/gpio.h" // gpio_in_setup, gpio_in_read
#include "board/irq.h"  // irq_disable, irq_enable
#include "command.h"    // DECL_COMMAND
#include "sched.h"      // struct timer, sched_add_timer, sched_del_timer
#include "trsync.h"     // trsync_do_trigger

struct cnc_button {
    struct timer time;
    struct gpio_in pin;
    uint32_t rest_time, sample_time, nextwake;
    struct trsync *ts;
    uint8_t flags, sample_count, trigger_count, trigger_reason;
};

// CBF_PIN_HIGH: the pin reads HIGH when the button is NOT pressed.
// Trigger fires when pin transitions to the opposite state.
enum { CBF_PIN_HIGH=1<<0 };

static uint_fast8_t cnc_button_oversample_event(struct timer *t);

// Main poll: check pin state, reschedule or start oversampling.
static uint_fast8_t
cnc_button_event(struct timer *t)
{
    struct cnc_button *b = container_of(t, struct cnc_button, time);
    uint8_t val = gpio_in_read(b->pin);
    uint32_t nextwake = b->time.waketime + b->rest_time;
    if ((val ? ~b->flags : b->flags) & CBF_PIN_HIGH) {
        // Pin is in its idle state — keep polling.
        b->time.waketime = nextwake;
        return SF_RESCHEDULE;
    }
    // Pin may have triggered — switch to oversampling to debounce.
    b->nextwake = nextwake;
    b->time.func = cnc_button_oversample_event;
    return cnc_button_oversample_event(t);
}

// Oversample: confirm the trigger across multiple samples.
static uint_fast8_t
cnc_button_oversample_event(struct timer *t)
{
    struct cnc_button *b = container_of(t, struct cnc_button, time);
    uint8_t val = gpio_in_read(b->pin);
    if ((val ? ~b->flags : b->flags) & CBF_PIN_HIGH) {
        // Pin returned to idle — false alarm, resume normal polling.
        b->time.func = cnc_button_event;
        b->time.waketime = b->nextwake;
        b->trigger_count = b->sample_count;
        return SF_RESCHEDULE;
    }
    uint8_t count = b->trigger_count - 1;
    if (!count) {
        // Confirmed: fire the trsync. This calls stepper_stop for every
        // stepper registered via stepper_stop_on_trigger, halting all axes.
        trsync_do_trigger(b->ts, b->trigger_reason);
        return SF_DONE;
    }
    b->trigger_count = count;
    b->time.waketime += b->sample_time;
    return SF_RESCHEDULE;
}

void
command_config_cnc_button(uint32_t *args)
{
    struct cnc_button *b = oid_alloc(args[0], command_config_cnc_button,
                                     sizeof(*b));
    b->pin = gpio_in_setup(args[1], args[2]);
}
DECL_COMMAND(command_config_cnc_button,
             "config_cnc_button oid=%c pin=%c pull_up=%c");

// Arm: start polling the pin. Before calling this the host must have called
// trsync_start and stepper_stop_on_trigger for all axis steppers.
void
command_cnc_button_arm(uint32_t *args)
{
    struct cnc_button *b = oid_lookup(args[0], command_config_cnc_button);
    sched_del_timer(&b->time);
    b->ts             = trsync_oid_lookup(args[1]);
    b->trigger_reason = args[2];
    b->sample_time    = args[3];
    b->sample_count   = b->trigger_count = args[4];
    b->rest_time      = args[5];
    b->flags          = (args[6] ? CBF_PIN_HIGH : 0);
    b->time.func      = cnc_button_event;
    b->time.waketime  = args[7]; // start_clock
    sched_add_timer(&b->time);
}
DECL_COMMAND(command_cnc_button_arm,
             "cnc_button_arm oid=%c trsync_oid=%c trigger_reason=%c"
             " sample_ticks=%u sample_count=%c rest_ticks=%u"
             " pin_value=%c clock=%u");

// Disarm: stop polling. No trsync is fired.
void
command_cnc_button_disarm(uint32_t *args)
{
    struct cnc_button *b = oid_lookup(args[0], command_config_cnc_button);
    irq_disable();
    sched_del_timer(&b->time);
    b->ts = NULL;
    irq_enable();
}
DECL_COMMAND(command_cnc_button_disarm, "cnc_button_disarm oid=%c");

void
cnc_button_shutdown(void)
{
    uint8_t oid;
    struct cnc_button *b;
    foreach_oid(oid, b, command_config_cnc_button) {
        sched_del_timer(&b->time);
        b->ts = NULL;
    }
}
DECL_SHUTDOWN(cnc_button_shutdown);
