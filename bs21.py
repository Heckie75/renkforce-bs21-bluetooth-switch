#!/usr/bin/python3
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

import bluetooth

TIMEOUT = 10

_USAGE = "usage"
_DESCR = "descr"
_PARAMS = "params"

COMMANDS = {
    "on": {
        _USAGE: "--on",
        _DESCR: "power switch on",
        _PARAMS: []
    },
    "off": {
        _USAGE: "--off",
        _DESCR: "power switch off",
        _PARAMS: []
    },
    "toggle": {
        _USAGE: "--toggle",
        _DESCR: "toggles switch",
        _PARAMS: []
    },
    "status": {
        _USAGE: "--status",
        _DESCR: "just read and print the basic information of the bluetooth switch",
        _PARAMS: []
    },
    "countdown-until": {
        _USAGE: "--countdown-until <hh:mm> <on|off>",
        _DESCR: "starts countdown with action (turn on / turn off) and specific endtime",
        _PARAMS: [
            r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$",
            r"^(on|off)$"
        ]
    },
    "countdown": {
        _USAGE: "--countdown <hh:mm:ss> <on|off>",
        _DESCR: "starts countdown with action (turn on / turn off) and duration",
        _PARAMS: [
            r"^([01]?[0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])$",
            r"^(on|off)$"
        ]
    },
    "countdown-clear": {
        _USAGE: "--countdown-clear",
        _DESCR: "resets countdown",
        _PARAMS: []
    },
    "scheduler": {
        _USAGE: "--scheduler <n:1-20> <on|off> <mtwtfss> <hh:mm>",
        _DESCR: "sets specific scheduler (1-20) with action (turn on / turn off), daymask, e.g. MTWTFss for Monday to Friday, starttime",
        _PARAMS: [
            r"^([0-9]{1}|1[0-9]{1}|20)$",
            r"^(on|off)$",
            r"^([Mm_][Tt_][Ww_][Tt_][Ff_][Ss_][Ss_])$",
            r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$"
        ]
    },
    "scheduler-clear": {
        _USAGE: "--scheduler-clear <n:1-20> <on|off>",
        _DESCR: "resets specific scheduler",
        _PARAMS: [
            r"^([0-9]{1}|1[0-9]{1}|20)$",
            r"^(on|off)$"
        ]
    },
    "random": {
        _USAGE: "--random <mtwtfss> <hh:mm> <hh:mm>",
        _DESCR: "activated random mode with daymask, e.g. MTWTFss for Monday to Friday, starttime und duration",
        _PARAMS: [
            r"^([Mm_][Tt_][Ww_][Tt_][Ff_][Ss_][Ss_])$",
            r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$",
            r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$"
        ]
    },
    "random-clear": {
        _USAGE: "--random-clear",
        _DESCR: "stops random mode",
        _PARAMS: []
    },
    "clear-all": {
        _USAGE: "--clear-all",
        _DESCR: "clears alls schedulers, random mode and countdown",
        _PARAMS: []
    },
    "pin": {
        _USAGE: "--pin <nnnn>",
        _DESCR: "set new pin with 4-digits",
        _PARAMS: [
            r"^([0-9]{4})$"
        ]
    },
    "visible": {
        _USAGE: "--visible",
        _DESCR: "make bluetooth switch visible for a while so that it can be discovered by bluetooth services",
        _PARAMS: []
    },
    "sync": {
        _USAGE: "--sync",
        _DESCR: "synchronizes current time with your computer",
        _PARAMS: []
    },
    "schedulers": {
        _USAGE: "--schedulers",
        _DESCR: "prints all scheduler information",
        _PARAMS: []
    },
    "json": {
        _USAGE: "--json",
        _DESCR: "prints information in json format",
        _PARAMS: []
    },
    "sleep": {
        _USAGE: "--sleep <nnn>",
        _DESCR: "script sleeps for n seconds and stays connected. Helpful for queueing commands",
        _PARAMS: [
            r"^([0-9_-]{1,3})$"
        ]
    },
    "debug": {
        _USAGE: "--debug",
        _DESCR: "prints raw data sent and received",
        _PARAMS: []
    }
}



class BS21Exception(Exception):
    def __init__(self, message):
        self.message = message


class BS21():

    _debug = False
    _client_socket = None
    _device = {
        "device": {
            "mac": "",
            "pin": "",
            "alias": ""
        },
        "status": None,
        "time": None,
        "schedulers": [],
        "random": None,
        "countdown": None
    }

    _PAYLOAD = {
        "on": "REL1",                                     # no parameters
        "off": "REL0",                                    # no parameters
        "status": "RELX",                                 # no parameters
        # % (0=off/1=on, dur_hh, dur_mm, dur_ss)
        "countdown": "SET43 %02d %02d %02d %02d 01",
        "countdown-clear": "CLEAR43",                      # no parameters
        # % (id[1-20]->on / id[21-40]->off, daymask, hh, mm)
        "scheduler": "SET%02d %s %02d %02d %02d 01",
        "scheduler-clear": "CLEAR%02d",                       # no parameters
        # % (id, daymask, start_hh, start_mm, dur_hh, dur_mm)
        "random": "SET%02d %s %02d %02d %02d %02d 01 00",
        "random-clear": "CLEAR41",                        # no parameters
        "clear-all": "CLEAR00",                           # no parameters
        "pin": "NEWC #%s ",                               # % (newpin)
        "visible": "VISB",                                # no parameters
        # % (weekday, hh, mm, ss)
        "sync": "TIME %s %02d %02d %02d",
        "schedulers": "INFO"                                  # no parameters
    }

    MAC_PATTERN = "5C:B6:CC:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}"
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

    _WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, mac, pin="1234", alias=None, timeout=20):

        if not self._validate_mac(mac):
            raise BS21Exception("ERROR: MAC address < %s > is invalid!" % mac)

        if not self._validate_pin(pin):
            raise BS21Exception("ERROR: Pin must be 4-digit numeric")

        self._device["device"]["mac"] = mac
        self._device["device"]["pin"] = pin
        self._device["device"]["alias"] = alias

        self._connect(timeout)

    def _validate_mac(self, mac):

        matcher = re.search(self.MAC_PATTERN, mac)
        return matcher != None

    def _validate_pin(self, pin):

        return pin >= "0000" and pin <= "9999"

    def set_debug(self, b):

        self._debug = b


    def _connect(self, timeout):

        try:
            client_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            client_socket.connect((self._device["device"]["mac"], 1))
            client_socket.settimeout(timeout)
            self._client_socket = client_socket

        except bluetooth.btcommon.BluetoothError as error:
            raise BS21Exception("Connection failed, %s" % error)

    def _send(self, payload):

        if self._debug:
            print(" > %s#%s" % (payload, self._device["device"]["pin"]))

        try:
            self._client_socket.send("%s#%s\r\n" % (
                payload, self._device["device"]["pin"]))
        except:
            raise BS21Exception("ERROR: Failed to send command to device!")

        try:
            _str = ""
            while True:
                _bytes = self._client_socket.recv(1024)
                if not _bytes:
                    break
                _str = _str + _list_to_string(_bytes)

                # we have reach end of message
                if _str.find("\r\n") != -1:
                    break
        except:
            raise BS21Exception(
                "ERROR: No response from device! Do you want to double-check PIN?")

        if self._debug:
            print(" < %s" % _str)

        return _str

    def _parse_status(self, response):

        if response.startswith("$ERR"):
            raise BS21Exception(
                "ERROR: Device has explicitly responded with error! Do you want to double-check PIN?")

        matcher = re.search(self._STATUS_PATTERN, response)
        if matcher == None:
            raise BS21Exception("ERROR: Unexpected response from device!")

        _state = {
            "model": matcher.group(1),
            "serial": matcher.group(2),
            "firmware": matcher.group(5),
            "on": matcher.group(3) == "1",
            "overtemp":  (ord(matcher.group(4)) & 2) > 0,
            "power":     (ord(matcher.group(4)) & 4) > 0,
            "random":    (ord(matcher.group(4)) & 8) > 0,
            "countdown": (ord(matcher.group(4)) & 16) > 0
        }

        # day_in_hex = hex(int(matcher.group(6))).replace("x", "0")
        day_in_hex = matcher.group(6)
        _time = self._build_weekdays_and_time(
            day_in_hex, matcher.group(7), matcher.group(8), matcher.group(9))

        return _state, _time

    def _parse_info(self, response):

        if not response.startswith("$OK"):
            raise BS21Exception(
                "ERROR: Device has explicitly responded with error! Do you want to double-check PIN?")

        if len(response) != 442:
            raise BS21Exception("ERROR: Unexpected response from device!")

        raw = response[14:372].split(" ")
        _schedulers = []
        for i in range(40):
            _schedulers.append({
                "slot": i + 1,
                "type": "on" if i <= 19 else "off",
                "schedule": self._build_weekdays_and_time(raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2])
            })

        raw = response[374:414].split(" ")
        _random = {
            "slot": 41,
            "active": True if raw[5] != "00" else False,
            "schedule": self._build_weekdays_and_time(raw[0], raw[1], raw[2]),
            "duration": self._build_time(raw[3], raw[4])
        }

        raw = response[416:439].split(" ")

        original = datetime.datetime(
            2000, 1, 1, int(raw[5]), int(raw[6]), int(raw[7]))
        remaining = datetime.timedelta(
            hours=int(raw[1]), minutes=int(raw[2]), seconds=int(raw[3]))
        _countdown = {
            "slot": 43,
            "active": True if raw[4] != "00" else False,
            "type": "on" if raw[0] != "00" else "off",
            "remaining": self._build_time(raw[1], raw[2], raw[3]),
            "elapsed": (original - remaining).strftime("%H:%M:%S"),
            "original": self._build_time(raw[5], raw[6], raw[7])
        }

        return _schedulers, _random, _countdown
    def _build_weekdays_and_time(self, day, hour, minute, second=0):

        _hour = int(hour) % 24
        _minute = int(minute) % 60
        _second = int(second) % 60

        weekdays = []
        i = 1
        for weekday in self._WEEKDAYS:
            if i & int(day, 16) > 0:
                weekdays += [weekday]
            i *= 2

        time = {
            "weekday": weekdays,
            "time": self._build_time(_hour, _minute, _second)
        }

        return time
    def _build_time(self, hour, minute, second=0):

        _hour = int(hour) % 24
        _minute = int(minute) % 60
        _second = int(second) % 60

        _time = "%02d:%02d:%02d" % (_hour, _minute, _second)

        return _time

    def _parse_response(self, response):

        return response.startswith("$OK")


    def get_status(self):

        if self._debug:
            print(" SEND: get status")

        response = self._send(self._PAYLOAD["status"])
        _status, _time = self._parse_status(response)
        self._device["time"] = _time
        self._device["status"] = _status

        if self._debug:
            print(" SUCCESS: status received")

        return True, _time, _status

    def get_device(self):

        return self._device


    def sync_time(self):

        if self._debug:
            print(" SEND: synchronize time")

        now = datetime.datetime.now()
        weekday = hex(pow(2, now.weekday())).replace("x", "0")[-2:]

        payload = self._PAYLOAD["sync"] % (
            weekday, now.hour, now.minute, now.second)
        response = self._send(payload)

        _status, _time = self._parse_status(response)
        self._device["time"] = _time
        self._device["status"] = _status

        if self._debug:
            print(" SUCCESS: time synchronized")

        return True, _time, _status

    def get_schedulers(self):

        if self._debug:
            print(" SEND: get schedulers")

        response = self._send(self._PAYLOAD["schedulers"])
        _schedulers, _random, _countdown = self._parse_info(response)

        self._device["schedulers"] = _schedulers
        self._device["random"] = _random
        self._device["countdown"] = _countdown

        if self._debug:
            print(" SUCCESS: schedulers received")

        return True, _schedulers, _random, _countdown


    def turn_on(self):

        if self._debug:
            print(" SEND: turn on")

        response = self._send(self._PAYLOAD["on"])
        _status, _time = self._parse_status(response)
        self._device["time"] = _time
        self._device["status"] = _status

        if self._debug:
            print(" SUCCESS: turned on")

        return True, _time, _status

    def turn_off(self):

        if self._debug:
            print(" SEND: turn off")

        response = self._send(self._PAYLOAD["off"])
        _status, _time = self._parse_status(response)
        self._device["time"] = _time
        self._device["status"] = _status

        if self._debug:
            print(" SUCCESS: turned off")

        return True, _time, _status

    def is_on(self):

        b, _time, _status = self.get_status()
        return True == _status["on"]


    def toggle(self):

        if self.is_on():
            self.turn_off()
        else:
            self.turn_on()


    def _build_daymask(self, mon, tue, wed, thu, fri, sat, sun):

        b = 0
        b += 1 if mon else 0
        b += 2 if tue else 0
        b += 4 if wed else 0
        b += 8 if thu else 0
        b += 16 if fri else 0
        b += 32 if sat else 0
        b += 64 if sun else 0

        return hex(b).replace("x", "0")[-2:].upper()

    def set_scheduler(self, id, type, hours, minutes, mon, tue, wed, thu, fri, sat, sun):

        if self._debug:
            print(" SEND: set scheduler")

        _id = int(id) % 20
        _id = _id if type == "on" else _id + 20
        _d = self._build_daymask(mon, tue, wed, thu, fri, sat, sun)
        _h = int(hours) % 24
        _m = int(minutes) % 60
        _s = 0

        payload = self._PAYLOAD["scheduler"] % (_id, _d, _h, _m, _s)
        response = self._send(payload)

        if not self._parse_response(response):
            raise BS21Exception("ERROR: Device returned error!")

        if self._debug:
            print(" SUCCESS: scheduler set")

        return True

    def reset_scheduler(self, id, type):

        if self._debug:
            print(" SEND: clear scheduler")

        _id = int(id) % 20
        _id = _id if type == "on" else _id + 20

        payload = self._PAYLOAD["scheduler-clear"] % _id
        response = self._send(payload)

        if not self._parse_response(response):
            raise BS21Exception("ERROR: Device returned error!")

        if self._debug:
            print(" SUCCESS: scheduler cleared")

        return True


    def set_random(self, hours, minutes, dur_hours, dur_minutes, mon, tue, wed, thu, fri, sat, sun):

        if self._debug:
            print(" SEND: set random")

        id = 41

        _d = self._build_daymask(mon, tue, wed, thu, fri, sat, sun)
        _h = int(hours) % 24
        _m = int(minutes) % 60
        _dh = int(dur_hours) % 24
        _dm = int(dur_minutes) % 60

        payload = self._PAYLOAD["random"] % (id, _d, _h, _m, _dh, _dm)
        response = self._send(payload)

        if not self._parse_response(response):
            raise BS21Exception("ERROR: Device returned error!")

        if self._debug:
            print(" SUCCESS: Random set")

        return True

    def reset_random(self):

        if self._debug:
            print(" SEND: clear random mode")

        response = self._send(self._PAYLOAD["random-clear"])

        if not self._parse_response(response):
            raise BS21Exception("ERROR: Device returned error!")

        self._device["random"] = None

        if self._debug:
            print(" SUCCESS: Random mode cleared")

        return True


    def set_countdown(self, hours, minutes, seconds, type):

        if self._debug:
            print(" SEND: set countdown")

        _t = 1 if type == "on" else 0
        _h = int(hours) % 24
        _m = int(minutes) % 60
        _s = int(seconds) % 60

        payload = self._PAYLOAD["countdown"] % (_t, _h, _m, _s)
        response = self._send(payload)

        if not self._parse_response(response):
            raise BS21Exception("ERROR: Device returned error!")

        if self._debug:
            print(" SUCCESS: countdown set")

        return True

    def set_countdown_until(self, hour, minute, type):

        now = datetime.datetime.now()
        then = datetime.datetime(1900, 1, 1, int(hour) %
                                 24, int(minute) % 60, 0)

        duration = (then - now)
        _h = duration.seconds // 3600
        _m = duration.seconds % 3600 // 60
        _s = duration.seconds % 60

        self.set_countdown(_h, _m, _s, type)

    def reset_countdown(self):

        if self._debug:
            print(" SEND: clear countdown")

        response = self._send(self._PAYLOAD["countdown-clear"])

        if not self._parse_response(response):
            raise BS21Exception("ERROR: Device returned error!")

        self._device["countdown"] = None

        if self._debug:
            print(" SUCCESS: countdown cleared")

        return True


    def reset_all(self):

        if self._debug:
            print(" SEND: clear all schedulers")

        response = self._send(self._PAYLOAD["clear-all"])

        if not self._parse_response(response):
            raise BS21Exception("ERROR: Device returned error")

        self._device["schedulers"] = []
        self._device["random"] = None
        self._device["countdown"] = None

        if self._debug:
            print(" SUCCESS: all schedulers cleared")

        return True

    def change_pin(self, newpin):

        if self._debug:
            print(" SEND: change pin")

        if not self._validate_pin(newpin):
            raise BS21Exception("ERROR: Pin must be 4-digit numeric")

        payload = self._PAYLOAD["pin"] % self._device["device"]["pin"]
        self._device["device"]["pin"] = newpin
        self._send(payload)

        if self._debug:
            print(" SUCCESS: pin changed")

        return True, newpin

    def set_visible(self):

        if self._debug:
            print(" SEND: set visible for next 2 minutes")

        self._send(self._PAYLOAD["visible"])

        if self._debug:
            print(" SUCCESS: visible for next 2 minutes")

        return True


    def disconnect(self):

        if self._client_socket is not None:
            self._client_socket.close()

def _build_help(cmd, header=False, msg=""):

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
        s += "\n " + \
            COMMANDS[cmd][_USAGE].ljust(32) + "\t" + COMMANDS[cmd][_DESCR]

    if msg != "":
        s += "\n"

    return s



def _help():

    s = ""
    i = 0
    for cmd in sorted(COMMANDS):
        s += _build_help(cmd, i == 0)
        i += 1

    return s


def _read_aliases(target, pin):

    is_mac = re.search(BS21.MAC_PATTERN, target)
    if is_mac:
        pattern = "(%s)[ \t]+([0-9]{4})[ \t]+(.+)" % target
    else:
        pattern = "(%s)[ \t]+([0-9]{4})[ \t]+(.*%s.*)" % (
            BS21.MAC_PATTERN, target)

    filename = os.path.join(os.environ['HOME'], ".known_bs21")
    if os.path.isfile(filename):
        with open(filename, "r") as ins:
            for line in ins:
                matcher = re.search(pattern, line)
                if matcher is not None and len(matcher.groups()) == 3:
                    _mac = matcher.group(1)
                    _pin = matcher.group(2) if pin is None else pin
                    _alias = matcher.group(3)

                    return _mac, _pin, _alias

    if is_mac:
        return target, pin, None
    else:
        return None, pin, target


def _translate_for_scheduler_call(id, type, weekdays, hours, minutes):

    params = [id, type, hours, minutes]
    for i in range(len(weekdays)):
        params.append(weekdays[i].isupper() and weekdays[i] != "_")

    return params


def _translate_for_random_call(weekdays, hours, minutes, dur_hours, dur_minutes):

    params = [hours, minutes, dur_hours, dur_minutes]
    for i in range(len(weekdays)):
        params.append(weekdays[i].isupper())

    return params



def printable_status(mac, pin, alias, time, status):

    s = "\n"
    s += " MAC-Address:      %s\n" % mac
    s += " PIN:              %s\n" % pin
    s += " Alias:            %s\n" % ("n/a" if alias == "" else alias)
    s += "\n"
    s += " Model:            %s\n" % status["model"]
    s += " Serial no.:       %s\n" % status["serial"]
    s += " Firmware:         %s\n" % status["firmware"]
    s += "\n"
    s += " Relais:           %s\n" % ("on" if status["on"] else "off")
    s += " Random mode:      %s\n" % ("on" if status["random"] else "off")
    s += " Countdown:        %s\n" % ("on" if status["countdown"] else "off")
    s += " Power:            %s\n" % ("yes" if status["power"] else "no")
    s += " Over temperature: %s\n" % ("yes" if status["overtemp"] else "no")
    s += "\n"
    s += " Time:             %s, %s" % (time["weekday"][0], time["time"])
    s += "\n"
    return s


def printable_schedulers(schedulers, random, countdown):

    s = ""

    if len(random["schedule"]["weekday"]) > 0:
        s += " Random:           %s on %s for %s hours, %s\n" % (
            random["schedule"]["time"],
            ", ".join(random["schedule"]["weekday"]),
            random["duration"][:-3],
            "active" if random["active"] else "inactive"
        )

    if countdown["active"]:
        s += " Countdown:        %s, switch %s in %s\n" % (
            "Running" if countdown["active"] else "Stopped",
            countdown["type"],
            countdown["remaining"]
        )

    for scheduler in schedulers:
        if len(scheduler["schedule"]["weekday"]) > 0:
            s += " Scheduler %02d:         Switch %s at %s on %s\n" % (
                scheduler["slot"] % 20,
                scheduler["type"],
                scheduler["schedule"]["time"][:-3],
                ", ".join(scheduler["schedule"]["weekday"])
            )

    return s


def do_commands(target, pin, commands):

    mac, pin, alias = _read_aliases(target, pin)

    if mac == None:
        raise BS21Exception(_build_help(
            None, True, "No alias found. Please check mac address!"))

    if pin == None:
        raise BS21Exception(_build_help(None, True, "No pin given?!"))

    try:
        bs21 = BS21(mac, pin, alias, TIMEOUT)

    except BS21Exception as ex:
        raise BS21Exception(_build_help(None, True, ex.message))

    try:
        for command in commands:
            func = command["func"]
            call = tuple(command["call"])

            if func == "on":
                bs21.turn_on()

            elif func == "off":
                bs21.turn_off()

            elif func == "toggle":
                bs21.toggle()

            elif func == "status":
                b, time, status = bs21.get_status()
                print(printable_status(mac, pin, alias, time, status))

            elif func == "countdown":
                bs21.set_countdown(*call)

            elif func == "countdown-until":
                bs21.set_countdown_until(*call)

            elif func == "countdown-clear":
                bs21.reset_countdown()

            elif func == "random":
                params = _translate_for_random_call(*call)
                bs21.set_random(*tuple(params))

            elif func == "random-clear":
                bs21.reset_random()

            elif func == "scheduler":
                params = _translate_for_scheduler_call(*call)
                bs21.set_scheduler(*tuple(params))

            elif func == "scheduler-clear":
                bs21.reset_scheduler(*call)

            elif func == "clear-all":
                bs21.reset_all()

            elif func == "pin":
                b, pin = bs21.change_pin(*call)

            elif func == "visible":
                bs21.set_visible()

            elif func == "sync":
                bs21.sync_time()

            elif func == "schedulers":
                b, schedulers, random, countdown = bs21.get_schedulers()
                print(printable_schedulers(schedulers, random, countdown))

            elif func == "json":
                bs21.get_status()
                bs21.get_schedulers()
                device = bs21.get_device()
                print(json.dumps(device, indent=2, sort_keys=False))

            elif func == "sleep":
                time.sleep(int(call[0]))

            elif func == "debug":
                bs21.set_debug(True)

            else:
                raise BS21Exception(_help()
                                    + "\n\n ERROR: Invalid command "
                                    + "<" + func + ">\n")

    except BS21Exception as ex:
        raise BS21Exception(_build_help(None, False, ex.message))

    finally:
        if bs21 is not None:
            bs21.disconnect()


def _list_to_string(l):

    s = ""
    for c in l:
        s += chr(c) if c != 0 else ""

    return s



def _translate_commands(commands):

    errors = []

    for command in commands:

        func = command["func"]
        if func not in COMMANDS:
            errors.append("ERROR: Unknown command <%s>" % func)
            continue

        cmd_def = COMMANDS[func]

        params = command["params"]
        if len(cmd_def[_PARAMS]) != len(params):
            errors.append(
                _build_help(func, False,
                            "ERROR: Please check parameters of command\n")
            )
            continue

        call = []
        for i in range(len(params)):
            m = re.search(cmd_def[_PARAMS][i], params[i])
            if m is None:
                errors.append(
                    _build_help(func, False,
                                "ERROR: Please check parameters of command, especially parameter %i\n" % (i + 1))
                )
                break

            for group in m.groups():
                call.append(str(group))

            command["call"] = call

    if len(commands) == 0:
        errors.append(
            _help() + "\n\n ERROR: No commands given. What can I do for you?\n")

    if len(errors) > 0:
        raise BS21Exception("\n".join(errors))

    return commands



def parse_args(args):

    target = None
    pin = None
    commands = []

    # get target
    if len(args) > 0 and not args[0].startswith("--"):
        target = args.pop(0)

    # get optional pin
    if len(args) > 0 and not args[0].startswith("--"):
        pin = args.pop(0)

    # collect commands
    command = None
    while (len(args) > 0):
        arg = args.pop(0)

        # command starts
        if arg.startswith("--"):
            arg = arg[2:]
            if arg not in COMMANDS:
                raise BS21Exception(_help()
                                    + "\n\n ERROR: Invalid command "
                                    + "--" + arg + "\n")
            command = {
                "func": arg,
                "params": [],
                "call": []
            }
            commands += [command]

        # collect parameters of current command
        elif command != None:
            command["params"] += [arg]

    commands = _translate_commands(commands)

    return target, pin, commands



if __name__ == "__main__":
    try:
        commands = sys.argv[1:]

        # help for specific command
        if len(commands) == 2 and commands[0] == "--help" and commands[1] in COMMANDS:
            print(_build_help(commands[1]))
            exit(0)

        # general help
        elif len(commands) == 0 or commands[0] == "--help":
            print(_help())
            exit(0)

        # do commands
        else:
            target, pin, commands = parse_args(commands)
            do_commands(target, pin, commands)

    except BS21Exception as e:
        print(e.message)
        exit(1)
