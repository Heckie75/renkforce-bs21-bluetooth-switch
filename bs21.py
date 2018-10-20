#!/usr/bin/python
#
# MIT License
#
# Copyright (c) 2018 heckie75
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
import datetime
import json
import math
import os
import re
import sys
import time

from bluetooth import *

class BS21Exception(Exception):
    def __init__(self, message):
        self.message = message

TIMEOUT = 20

_MAC_PATTERN    = "5C:B6:CC:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}"
_STATUS_PATTERN = "\$(BS-21)-([0-9]+)-([01])-(.) (V[0-9]+.[0-9]+) ([0-9]{2}) ([0-9]{2}) ([0-9]{2}) ([0-9]{2})"
#                   ||       |        |      |      |                |          |          |          |         | Newline "\r\n"
#                   ||       |        |      |      |                |          |          |          | Clock seconds, e.g. "59"
#                   ||       |        |      |      |                |          |          | Clock minutes, e.g. "41"
#                   ||       |        |      |      |                |          | Clock hours, e.g. "05"
#                   ||       |        |      |      |                + Clock day of week, e.g. "02" for Tuesday
#                   ||       |        |      |      + Firmware Version, e.g. "V1.18"
#                   ||       |        |      + Error Code, e.g. "A" is ASCII 65
#                   ||       |        + 0=off, 1=on
#                   ||       + Serial no., e.g. "004593"
#                   |+ Model, always "BS-21"
#                   + Sign for begin response

_USAGE   = "usage"
_DESCR   = "descr"
_PARAMS  = "params"
_PAYLOAD = "payload"

COMMANDS = {
    "on" : {
        _USAGE : "-on",
        _DESCR : "power switch on",
        _PAYLOAD : "REL1",                                # no parameters
        _PARAMS : []
        },
    "off" : {
        _USAGE : "-off",
        _DESCR : "power switch off",
        _PAYLOAD : "REL0",                                # no parameters
        _PARAMS : []
        },
    "status" : {
        _USAGE : "-status",
        _DESCR : "just read and print the basic information of the bluetooth switch",
        _PAYLOAD : "RELX",                                # no parameters
        _PARAMS : []
        },
    "countdown-until" : {
        _USAGE : "-countdown-until <on|off> <hh:mm>",
        _DESCR : "starts countdown with action (turn on / turn off) and specific endtime",
        _PAYLOAD : "SET43 %02d %02d %02d %02d 01",        # % (0=off/1=on, dur_hh, dur_mm, dur_ss)
        _PARAMS : [
            r"(on|off)",
            r"([01]?[0-9]|2[0-3]):([0-5][0-9])"
            ]
        },
    "countdown-for" : {
        _USAGE : "-countdown-for <on|off> <hh:mm>",
        _DESCR : "starts countdown with action (turn on / turn off) and duration",
        _PAYLOAD : "SET43 %02d %02d %02d %02d 01",        # % (0=off/1=on, dur_hh, dur_mm, dur_ss)
        _PARAMS : [
            r"(on|off)",
            r"([01]?[0-9]|2[0-3]):([0-5][0-9])"
            ]
        },
    "countdown-clear" : {
        _USAGE : "-countdown-clear",
        _DESCR : "resets countdown",
        _PAYLOAD : "CLEAR43",                              # no parameters
        _PARAMS : []
        },
    "timer" : {
        _USAGE : "-timer <n:1-20> <on|off> <mtwtfss> <hh:mm>",
        _DESCR : "sets specific timer (1-20) with action (turn on / turn off), daymask, e.g. MTWTFss for Monday to Friday, starttime",
        _PAYLOAD : "SET%02d %s %02d %02d %02d 01",       # % (id[1-20]->on / id[21-40]->off, daymask, hh, mm)
        _PARAMS : [
            r"([0-9]{1}|1[0-9]{1}|20)",
            r"(on|off)",
            r"([Mm][Tt][Ww][Tt][Ff][Ss][Ss])",
            r"([01]?[0-9]|2[0-3]):([0-5][0-9])"
            ]
        },
    "timer-clear" : {
        _USAGE : "-timer-clear <n:1-20> <on|off>",
        _DESCR : "resets specific timer",
        _PAYLOAD : "CLEAR%02d",                            # no parameters
        _PARAMS : [
            r"([0-9]{1}|1[0-9]{1}|20)",
            r"(on|off)"
        ]
        },
    "random" : {
        _USAGE : "-random <mtwtfss> <hh:mm> <hh:mm>",
        _DESCR : "activated random mode with daymask, e.g. mtwtf__ for Monday to Friday, starttime und duration",
        _PAYLOAD : "SET%02d %s %02d %02d %02d %02d 01 00", # % (id, daymask, start_hh, start_mm, dur_hh, dur_mm)
        _PARAMS : [
            r"([Mm][Tt][Ww][Tt][Ff][Ss][Ss])",
            r"([01]?[0-9]|2[0-3]):([0-5][0-9])",
            r"([01]?[0-9]|2[0-3]):([0-5][0-9])"
            ]
        },
    "random-clear" : {
        _USAGE : "-random-clear",
        _DESCR : "stops random mode",
        _PAYLOAD : "CLEAR41",                              # no parameters
        _PARAMS : []
        },
    "clear-all" : {
        _USAGE : "-clear-all",
        _DESCR : "clears alls timers, random mode and countdown",
        _PAYLOAD : "CLEAR00",                              # no parameters
        _PARAMS : []
        },
    "pin" : {
        _USAGE : "-pin <nnnn>",
        _DESCR : "set new pin with 4-digits",
        _PAYLOAD : "NEWC #%s ",                          # % (newpin)
        _PARAMS : [
            r"([0-9]{4})"
            ]
        },
    "visible" : {
        _USAGE : "-visible",
        _DESCR : "make bluetooth switch visible for a while so that it can be discovered by bluetooth services",
        _PAYLOAD : "VISB",                                  # no parameters
        _PARAMS : []
        },
    "sync" : {
        _USAGE : "-sync",
        _DESCR : "synchronizes current time with your computer",
        _PAYLOAD : "TIME %s %02d %02d %02d",              # % (weekday, hh, mm, ss)
        _PARAMS : []
        },
    "timers" : {
        _USAGE : "-timers",
        _DESCR : "prints all timer information",
        _PAYLOAD : "INFO",                                  # no parameters
        _PARAMS : []
        },
    "json" : {
        _USAGE : "-json",
        _DESCR : "prints information in json format",
        _PARAMS : []
        },
    "sleep" : {
        _USAGE : "-sleep <nnn>",
        _DESCR : "script sleeps for n seconds and stays connected. Helpful for queueing commands",
        _PARAMS : [
            r"([0-9_-]{1,3})"
            ]
        },
    "debug" : {
        _USAGE : "-debug",
        _DESCR : "prints raw data sent and received",
        _PARAMS : []
        },
    "alias" : {
        _USAGE : "-alias <alphanumeric w/o white-characters>",
        _DESCR : "sets an alias for device",
        _PARAMS : [
            r"([A-Za-z0-9_-]+)"
            ]
        }
    }

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

debug = False
aliases = []

device = {
    "device" : {
        "mac" : "",
        "pin" : "",
        "alias" : ""
        },
    "status" : None,
    "time" : None,
    "timers" : [],
    "random" : None,
    "countdown" : None
    }




def _build_help(cmd, header = False, msg = ""):

    s = ""

    if header == True:
        s = """ Renkforce BS-21 bluetooth power switch command line interface \
 for Linux / Raspberry Pi

 USAGE:   bs21.py <mac> <pin> <command1> <params1> <command2> ...
 EXAMPLE: sync time and power on
          $ ./bs21.py 5C:B6:CC:00:1A:AE 1234 -sync -on
        """

    if msg != "":
        s += "\n " + msg

    if cmd is not None and cmd in COMMANDS:
        s += "\n " + COMMANDS[cmd][_USAGE].ljust(32) + "\t" + COMMANDS[cmd][_DESCR]

    if msg != "":
        s += "\n"

    return s




def set_debug(b):

    global debug
    debug = b




def _help():

    s = ""
    i = 0
    for cmd in sorted(COMMANDS):
        s += _build_help(cmd, i == 0)
        i += 1

    return s




def _validate_mac(mac):

    matcher = re.search(_MAC_PATTERN, mac)
    return matcher != None




def _validate_pin(pin):

    try:
        if pin < "0000" or pin > "9999":
            raise Exception()

    except:
        raise BS21Exception(_build_help(None, False,
                "ERROR: Pin must be 4-digit numeric\n"))

    return pin




def _read_aliases(target, pin):

    filename = os.path.join(os.environ['HOME'], ".known_bs21")
    if not os.path.isfile(filename):
        return target, pin, None

    is_mac = _validate_mac(target)
    if is_mac:
        pattern = "(%s)[ \t]+([0-9]{4})[ \t]+(.+)" % target
    else:
        pattern = "(%s)[ \t]+([0-9]{4})[ \t]+(.*%s.*)" % (_MAC_PATTERN, target)

    with open(filename, "r") as ins:
        for line in ins:
            matcher = re.search(pattern, line)
            if matcher is not None and len(matcher.groups()) == 3:
                device["device"]["mac"] = matcher.group(1)
                device["device"]["pin"] = matcher.group(2) if pin is None else pin
                device["device"]["alias"] = matcher.group(3)

                return device["device"]["mac"], device["device"]["pin"], device["device"]["alias"]

    return target, pin, None




def connect(mac):

    valid_mac = _validate_mac(mac)

    if not valid_mac:
        raise BS21Exception(_build_help(None, True,
                        "ERROR: MAC address <"
                        + mac
                        + "> is invalid!"))

    try:
        client_socket = BluetoothSocket(RFCOMM)
        client_socket.connect((mac, 1))
        client_socket.settimeout(TIMEOUT)

    except:
        return None

    device["device"]["mac"] = mac

    return client_socket




def send(client_socket, payload, pin):

    pin = _validate_pin(pin)
    device["device"]["pin"] = pin

    if debug:
        print(" > %s#%s" % (payload, pin))

    try:
        client_socket.send("%s#%s\r\n" % (payload, pin))
    except:
        raise BS21Exception("\n ERROR: Failed to send command to device!\n")

    try:
        raw = ""
        while True:
            r = client_socket.recv(1024)
            if not r:
                break
            raw = raw + r

            # we have reach end of message
            if r.find("\r\n") != -1:
                break
    except:
        raise BS21Exception("\n ERROR: No response from device! Do you want to double-check PIN?\n")

    if debug:
        print(" < %s" % raw.replace("\r\n", ""))

    return raw




def get_status(client_socket, pin):

    if debug:
        print(" SEND: get status")

    payload = COMMANDS["status"][_PAYLOAD]
    response = send(client_socket, payload, pin)
    _status, _time = _parse_status(response)
    device["time"] = _time
    device["status"] = _status

    if debug:
        print(" SUCCESS: status received")

    return True, _time, _status




def sync_time(client_socket, pin):

    if debug:
        print(" SEND: synchronize time")

    now = datetime.datetime.now()
    weekday = hex(pow(2, now.weekday())).replace("x", "0")[-2:]

    payload = COMMANDS["sync"][_PAYLOAD] % (weekday, now.hour, now.minute, now.second)
    response = send(client_socket, payload, pin)

    _status, _time = _parse_status(response)
    device["time"] = _time
    device["status"] = _status

    if debug:
        print(" SUCCESS: time synchronized")

    return True, _time, _status




def get_timers(client_socket, pin):

    if debug:
        print(" SEND: get timers")

    payload = COMMANDS["timers"][_PAYLOAD]
    response = send(client_socket, payload, pin)
    _timers, _random, _countdown = _parse_info(response)

    device["timers"] = _timers
    device["random"] = _random
    device["countdown"] = _countdown

    if debug:
        print(" SUCCESS: timers received")

    return True, _timers, _random, _countdown




def turn_on(client_socket, pin):

    if debug:
        print(" SEND: turn on")

    payload = COMMANDS["on"][_PAYLOAD]
    response = send(client_socket, payload, pin)
    _status, _time = _parse_status(response)
    device["time"] = _time
    device["status"] = _status

    if debug:
        print(" SUCCESS: turned on")

    return True, _time, _status




def turn_off(client_socket, pin):

    if debug:
        print(" SEND: turn off")

    payload = COMMANDS["off"][_PAYLOAD]
    response = send(client_socket, payload, pin)
    _status, _time = _parse_status(response)
    device["time"] = _time
    device["status"] = _status

    if debug:
        print(" SUCCESS: turned off")

    return True, _time, _status




def _translate_for_timer_call(id, type, weekdays, hours, minutes):

    params = [id, type, hours, minutes]
    for i in range(len(weekdays)):
        params.append(weekdays[i].isupper())

    return params



def _build_daymask(mon, tue, wed, thu, fri, sat, sun):

    b = 0
    b += 1 if mon else 0
    b += 2 if tue else 0
    b += 4 if wed else 0
    b += 8 if thu else 0
    b += 16 if fri else 0
    b += 32 if sat else 0
    b += 64 if sun else 0

    return hex(b).replace("x", "0")[-2:].upper()




def set_timer(client_socket, pin, id, type, hours, minutes, mon, tue, wed, thu, fri, sat, sun):

    if debug:
        print(" SEND: set timer")

    id = int(id) % 20
    id = id if type == "on" else id + 20
    _d = _build_daymask(mon, tue, wed, thu, fri, sat, sun)
    _h = int(hours) % 24
    _m = int(minutes) % 60
    _s = 0

    payload = COMMANDS["timer"][_PAYLOAD] % (id, _d, _h, _m, _s)
    response = send(client_socket, payload, pin)

    if not _parse_response(response):
        raise BS21Exception(None, False,
                " ERROR: Device returned error\n" % response)

    if debug:
        print(" SUCCESS: Timer set")

    return True




def reset_timer(client_socket, pin, id, type):

    if debug:
        print(" SEND: clear timer")

    id = int(id) % 20
    id = id if type == "on" else id + 20

    payload = COMMANDS["timer-clear"][_PAYLOAD] % id
    response = send(client_socket, payload, pin)

    if not _parse_response(response):
        raise BS21Exception(None, False,
                " ERROR: Device returned error\n" % response)

    if debug:
        print(" SUCCESS: Timer cleared")

    return True



def _translate_for_random_call(weekdays, hours, minutes, dur_hours, dur_minutes):

    params = [hours, minutes, dur_hours, dur_minutes]
    for i in range(len(weekdays)):
        params.append(weekdays[i].isupper())

    return params




def set_random(client_socket, pin, hours, minutes, dur_hours, dur_minutes, mon, tue, wed, thu, fri, sat, sun):

    if debug:
        print(" SEND: set random")

    id = 41

    _d = _build_daymask(mon, tue, wed, thu, fri, sat, sun)
    _h = int(hours) % 24
    _m = int(minutes) % 60
    _dh = int(dur_hours) % 24
    _dm = int(dur_minutes) % 60

    payload = COMMANDS["random"][_PAYLOAD] % (id, _d, _h, _m, _dh, _dm)
    response = send(client_socket, payload, pin)

    if not _parse_response(response):
        raise BS21Exception(None, False,
                " ERROR: Device returned error\n" % response)

    if debug:
        print(" SUCCESS: Random set")

    return True




def reset_random(client_socket, pin):

    if debug:
        print(" SEND: clear random mode")

    payload = COMMANDS["random-clear"][_PAYLOAD]
    response = send(client_socket, payload, pin)

    if not _parse_response(response):
        raise BS21Exception(None, False,
                " ERROR: Device returned error\n" % response)

    device["random"] = None

    if debug:
        print(" SUCCESS: Random mode cleared")

    return True




def set_countdown_for(client_socket, pin, on, hours, minutes, seconds = 0):

    if debug:
        print(" SEND: set countdown")

    _on = 1 if on == "on" else 0
    _h = int(hours) % 24
    _m = int(minutes) % 60
    _s = int(seconds) % 60

    payload = COMMANDS["countdown-for"][_PAYLOAD] % (_on, _h, _m, _s)
    response = send(client_socket, payload, pin)

    if not _parse_response(response):
        raise BS21Exception(None, False,
                " ERROR: Device returned error\n" % response)

    if debug:
        print(" SUCCESS: countdown set")

    return True




def set_countdown_until(client_socket, pin, on, hour, minute):

    now = datetime.datetime.now()
    then = datetime.datetime(1900, 1, 1, int(hour) % 24, int(minute) % 60, 0)

    duration = (then - now)
    hours = duration.seconds / 3600
    minutes = duration.seconds % 3600 / 60
    seconds = duration.seconds % 60

    set_countdown_for(client_socket, pin, on, hours, minutes, seconds)




def reset_countdown(client_socket, pin):

    if debug:
        print(" SEND: clear countdown")

    payload = COMMANDS["countdown-clear"][_PAYLOAD]
    response = send(client_socket, payload, pin)

    if not _parse_response(response):
        raise BS21Exception(None, False,
                " ERROR: Device returned error\n" % response)

    device["countdown"] = None

    if debug:
        print(" SUCCESS: countdown cleared")

    return True




def reset_all(client_socket, pin):

    if debug:
        print(" SEND: clear all timers")

    payload = COMMANDS["clear-all"][_PAYLOAD]
    response = send(client_socket, payload, pin)

    if not _parse_response(response):
        raise BS21Exception(None, False,
                " ERROR: Device returned error\n" % response)

    device["timers"] = []
    device["random"] = None
    device["countdown"] = None

    if debug:
        print(" SUCCESS: all timers cleared")

    return True




def change_pin(client_socket, pin, newpin):

    if debug:
        print(" SEND: change pin")

    try:
        _validate_pin(newpin)
    except:
        raise BS21Exception(_build_help("pin", False,
                "ERROR: Pin must be 4-digit numeric\n"))

    payload = COMMANDS["pin"][_PAYLOAD] % pin
    response = send(client_socket, payload, newpin)

    device["device"]["pin"] = "%s" % pin

    if debug:
        print(" SUCCESS: pin changed")

    return True, newpin




def set_visible(client_socket, pin):

    if debug:
        print(" SEND: set visible for next 2 minutes")

    payload = COMMANDS["visible"][_PAYLOAD]
    response = send(client_socket, payload, pin)

    if debug:
        print(" SUCCESS: visible for next 2 minutes")

    return True




def disconnect(client_socket):

    client_socket.close()




def _build_weekdays_and_time(day, hour, minute, second = 0):

    _hour = int(hour) % 24
    _minute = int(minute) % 60
    _second = int(second) % 60

    weekdays = []
    i = 1
    for weekday in WEEKDAYS:
        if i & int(day, 16) > 0:
            weekdays += [weekday]
        i *= 2

    time = {
        "weekday" : weekdays,
        "time" : _build_time(_hour, _minute, _second)
        }

    return time




def _build_time(hour, minute, second = 0):

    _hour = int(hour) % 24
    _minute = int(minute) % 60
    _second = int(second) % 60

    _time = "%02d:%02d:%02d" % (_hour, _minute, _second)

    return _time




def _parse_status(response):

    if response.startswith("$ERR"):
        raise BS21Exception("\n\n ERROR: Device has explicitly responded with error! Do you want to double-check PIN?\n")

    matcher = re.search(_STATUS_PATTERN, response)
    if matcher == None:
        raise BS21Exception("\n\n ERROR: Unexpected response: %s\n" % response)

    _state = {
        "model" : matcher.group(1),
        "serial" : matcher.group(2),
        "firmware" : matcher.group(5),
        "on" : matcher.group(3) == "1",
        "overtemp" :  (ord(matcher.group(4)) & 2) > 0,
        "power" :     (ord(matcher.group(4)) & 4) > 0,
        "random" :    (ord(matcher.group(4)) & 8) > 0,
        "countdown" : (ord(matcher.group(4)) & 16) > 0
        }

    # day_in_hex = hex(int(matcher.group(6))).replace("x", "0")
    day_in_hex = matcher.group(6)
    _time = _build_weekdays_and_time(day_in_hex, matcher.group(7), matcher.group(8), matcher.group(9))

    return _state, _time




def _parse_response(response):

    return response.startswith("$OK")




def _parse_info(response):

    if not response.startswith("$OK"):
        raise BS21Exception("\n\n ERROR: Device has explicitly responded with error! Do you want to double-check PIN?\n")

    if len(response) != 442:
        raise BS21Exception("\n\n ERROR: Unexpected response from device!")

    raw = response[14:372].split(" ")
    _timers = []
    for i in range(40):
        _timers.append({
            "slot" : i + 1,
            "type" : "on" if i <=19 else "off",
            "schedule" : _build_weekdays_and_time(raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2])
        })

    raw = response[374:414].split(" ")
    _random = {
        "slot" : 41,
        "active" : True if raw[5] != "00" else False,
        "simultaneously" : True if raw[6] != "00" else False,
        "schedule" : _build_weekdays_and_time(raw[0], raw[1], raw[2]),
        "duration" : _build_time(raw[3], raw[4])
    }

    raw = response[416:439].split(" ")

    original = datetime.datetime(1900, 1, 1, int(raw[5]), int(raw[6]), int(raw[7]))
    remaining = datetime.timedelta(hours = int(raw[1]), minutes = int(raw[2]), seconds = int(raw[3]))
    _countdown = {
        "slot" : 43,
        "active" : True if raw[4] != "00" else False,
        "type" : "on" if raw[0] != "00" else "off",
        "remaining" : _build_time(raw[1], raw[2], raw[3]),
        "elapsed" : (original - remaining).strftime("%H:%M:%S"),
        "original" : _build_time(raw[5], raw[6], raw[7])
        }

    return _timers, _random, _countdown




def printable_status():

    _time = device["time"]
    _status = device["status"]
    _device = device["device"]

    s = "\n"
    s += " MAC-Address:      %s\n" % _device["mac"]
    s += " PIN:              %s\n" % _device["pin"]
    s += " Alias:            %s\n" % ("n/a" if _device["alias"] == "" else _device["alias"])
    s += "\n"
    s += " Model:            %s\n" % _status["model"]
    s += " Serial no.:       %s\n" % _status["serial"]
    s += " Firmware:         %s\n" % _status["firmware"]
    s += "\n"
    s += " Relais:           %s\n" % ("on" if _status["on"] else "off")
    s += " Random mode:      %s\n" % ("on" if _status["random"] else "off")
    s += " Countdown:        %s\n" % ("on" if _status["countdown"] else "off")
    s += " Power:            %s\n" % ("yes" if _status["power"] else "no")
    s += " Over temperature: %s\n" % ("yes" if _status["overtemp"] else "no")
    s += "\n"
    s += " Time:             %s, %s" % (_time["weekday"][0], _time["time"])
    s += "\n"
    return s




def printable_timers():

    s = ""

    rand = device["random"]
    if len(rand["schedule"]["weekday"]) > 0:
        s += " Random:           %s on %s until %s, %s %s\n" % (
                                            rand["schedule"]["time"],
                                            ", ".join(rand["schedule"]["weekday"]),
                                            rand["duration"][:-3],
                                            "active" if rand["active"] else "inactive",
                                            "simultaneously" if rand["simultaneously"] else "",
                                            )

    if device["countdown"]["active"]:
        s += " Countdown:        %s, switch %s in %s\n" % (
                                                "Running" if device["countdown"]["active"] else "Stopped",
                                                device["countdown"]["type"],
                                                device["countdown"]["remaining"]
                                                )

    for timer in device["timers"]:
        if len(timer["schedule"]["weekday"]) > 0:
            s += " Timer %02d:         Switch %s at %s on %s\n" % (
                                                timer["slot"] % 20,
                                                timer["type"],
                                                timer["schedule"]["time"][:-3],
                                                ", ".join(timer["schedule"]["weekday"])
                                                )

    return s




def _do_commands(target, pin, commands):

    mac, pin, alias = _read_aliases(target, pin)

    client_socket = connect(mac)
    if client_socket is None:
        raise BS21Exception("Connection failed")

    try:
        for command in commands:
            func = command["func"]
            call = tuple(command["call"])

            if func == "on":
                turn_on(client_socket, pin)

            elif func == "off":
                turn_off(client_socket, pin)

            elif func == "status":
                get_status(client_socket, pin)
                print(printable_status())

            elif func == "countdown-for":
                set_countdown_for(client_socket, pin, *call)

            elif func == "countdown-until":
                set_countdown_until(client_socket, pin, *call)

            elif func == "countdown-clear":
                reset_countdown(client_socket, pin)

            elif func == "random":
                params = _translate_for_random_call(*call)
                set_random(client_socket, pin, *tuple(params))

            elif func == "random-clear":
                reset_random(client_socket, pin)

            elif func == "timer":
                params = _translate_for_timer_call(*call)
                set_timer(client_socket, pin, *tuple(params))

            elif func == "timer-clear":
                reset_timer(client_socket, pin, *call)

            elif func == "clear-all":
                reset_all(client_socket, pin)

            elif func == "pin":
                b, pin = change_pin(client_socket, pin, *call)

            elif func == "visible":
                set_visible(client_socket, pin)

            elif func == "sync":
                sync_time(client_socket, pin)

            elif func == "timers":
                get_timers(client_socket, pin)
                print(printable_timers())

            elif func == "json":
                get_status(client_socket, pin)
                get_timers(client_socket, pin)
                print(json.dumps(device, indent = 2, sort_keys = False))

            elif func == "alias":
                pass # TODO

            elif func == "sleep":
                time.sleep(int(call[0]))

            elif func == "debug":
                set_debug(True)

            else:
                raise BS21Exception(_help()
                    + "\n\n ERROR: Invalid command "
                    + "<" + func + ">\n")
    finally:
        if client_socket is not None:
            disconnect(client_socket)




def _translate_commands(commands):

    errors = []

    for command in commands:

        func = command["func"]
        if func not in COMMANDS:
            errors.append(" ERROR: Unknown command <%s>" % func)
            continue

        cmd_def = COMMANDS[func]

        params = command["params"]
        if len(cmd_def[_PARAMS]) != len(params):
            errors.append(
                _build_help(func, False,
                    " ERROR: Please check parameters of command\n")
            )
            continue

        call = []
        for i in range(len(params)):
            m = re.search(cmd_def[_PARAMS][i], params[i])
            if m is None:
                errors.append(
                    _build_help(func, False,
                        " ERROR: Please check parameters of command, especially parameter %i\n" % (i + 1))
                )
                break

            for group in m.groups():
                call.append(str(group))

            command["call"] = call

    if len(commands) == 0:
        errors.append(_help() + "\n\n ERROR: No commands given. What can I do for you?\n")

    if len(errors) > 0:
        raise BS21Exception("\n".join(errors))

    return commands




def _parse_args(args):

    target = None
    pin = None
    commands = []

    # get target
    if len(args) > 0 and not args[0].startswith("-"):
        target = args.pop(0)

    # get optional pin
    if len(args) > 0 and not args[0].startswith("-"):
        pin = args.pop(0)

    # collect commands
    command = None
    while (len(args) > 0):
        arg = args.pop(0)

        # command starts
        if arg.startswith("-"):
            arg = arg[1:]
            if arg not in COMMANDS:
                raise BS21Exception(_help()
                        + "\n\n ERROR: Invalid command "
                        + "-" + arg + "\n")
            command = {
                "func" : arg,
                "params" : [],
                "call" : []
                }
            commands += [command]

        # collect parameters of current command
        else:
            command["params"] += [arg]

    commands = _translate_commands(commands)

    return target, pin, commands




if __name__ == "__main__":
    try:
        commands = sys.argv[1:]

        # help for specific command
        if len(commands) == 2 and commands[0] == "-help" and commands[1] in COMMANDS:
            print(_build_help(commands[1]))
            exit(0)

        # general help
        elif len(commands) == 0 or commands[0] == "-help":
            print(_help())
            exit(0)

        # do commands
        else:
            target, pin, commands = _parse_args(commands)
            _do_commands(target, pin, commands)

    except BS21Exception as e:
        print(e.message)
        exit(1)
