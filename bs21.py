#!/usr/bin/python3
#
# MIT License
#
# Copyright (c) 2018-2021 heckie75
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
import logging
import os
import re
import socket
import subprocess
import sys
import time

_USAGE = "usage"
_DESCR = "descr"
_PARAMS = "params"

COMMANDS = {
    "aliases": {
        _USAGE: "--aliases",
        _DESCR: "print known aliases from .known_bs21 file",
        _PARAMS: []
    },
    "devices": {
        _USAGE: "--devices",
        _DESCR: "print devices that are paired with this system",
        _PARAMS: []
    },
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

    def __init__(self, message) -> None:
        self.message = message


class Alias():

    _KNOWN_SOCKETS_FILE = ".known_bs21"

    address = ""
    pin = ""
    alias = ""

    def __init__(self, address: str, pin: str, alias: str) -> None:
        self.address = address
        self.pin = pin
        self.alias = alias

    @staticmethod
    def validate_pin(pin: str) -> bool:

        try:
            return int(pin) >= 0 and int(pin) <= 9999

        except:
            return False

    @staticmethod
    def get_aliases() -> list:

        try:
            filename = os.path.join(os.environ['USERPROFILE'] if os.name == "nt" else os.environ['HOME']
                                    if "HOME" in os.environ else "~", Alias._KNOWN_SOCKETS_FILE)

            aliases = list()

            if os.path.isfile(filename):
                with open(filename, "r") as ins:
                    for line in ins:
                        _m = re.match(
                            "([0-9A-Fa-f:]+) +([0-9]{4}) +(.*)$", line)
                        if _m:
                            aliases.append(Alias(address=_m.groups()[
                                           0], pin=_m.groups()[1], alias=_m.groups()[2]))

        except:
            pass

        return aliases

    @staticmethod
    def get_address_n_alias(s: str):

        aliases = Alias.get_aliases()
        for alias in aliases:
            if s == alias.address or s in alias.alias:
                return alias.address, alias

        if re.match(Device.MAC_PATTERN, s):
            return s, None
        else:
            return None, None

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,
                          sort_keys=True, indent=2)


class Device(Alias):

    MAC_PATTERN = "5C:B6:CC:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}"

    PORT_BLUETOOTH = "Bluetooth"
    PORT_SERIAL = "Serial"

    port = ""
    controller = ""
    mac = ""
    name = ""

    def __init__(self, address="", pin="", alias="", port="", controller="", mac="", name="") -> None:
        super().__init__(address=address, pin=pin, alias=alias)
        self.port = port
        self.controller = controller
        self.mac = mac
        self.name = name

    @staticmethod
    def get_devices() -> list:

        _devices = Device.get_devices_for_windows(
        ) if os.name == "nt" else Device.get_devices_for_linux()
        _aliases = Alias.get_aliases()

        if len(_aliases) > 0:
            for _d in _devices:
                _a = next(filter(lambda _a: _a.address == _d.address, _aliases))
                if _a:
                    _d.alias = _a.alias
                    _d.pin = _a.pin

        return _devices

    @staticmethod
    def get_devices_for_linux() -> list:

        def _exec_bluetoothctl(commands=list()) -> str:

            command_str = "\n".join(commands)

            p1 = subprocess.Popen(["echo", "-e", "%s\nquit\n\n" % command_str],
                                  stdout=subprocess.PIPE)
            p2 = subprocess.Popen(["bluetoothctl"],
                                  stdin=p1.stdout,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            p1.stdout.close()
            out, err = p2.communicate()
            return out.decode("utf8")

        output = _exec_bluetoothctl()

        controllers = list()
        for match in re.finditer("Controller ([0-9A-F:]+) (.+)", output):
            controllers.append(match.group(1))

        _devices = list()
        for controller in controllers:
            time.sleep(.25)
            output = _exec_bluetoothctl(["select %s" % controller, "devices"])
            for match in re.finditer("Device (%s) (.+)" % Device.MAC_PATTERN, output):

                _devices.append(Device(
                    port=Device.PORT_BLUETOOTH,
                    address=match.group(1),
                    controller=controller,
                    mac=match.group(1),
                    name=match.group(2)
                ))

        return _devices

    @staticmethod
    def get_devices_for_windows() -> list:

        import serial.tools.list_ports
        _devices = list()
        for p in list(serial.tools.list_ports.comports()):
            if p.hwid.startswith("BTHENUM"):
                _mac = "".join(["%s%s" % (s, ":" if i % 2 else "") for i, s in enumerate(
                    p.hwid.split("\\")[-1].split("&")[-1][:12])])[:-1]
                if re.match(Device.MAC_PATTERN, _mac):

                    _d = Device(
                        port=Device.PORT_SERIAL,
                        address=_mac if "BTPROTO_RFCOMM" in dir(
                            socket) else p.device,
                        mac=_mac,
                        controller=None,
                        name=p.description
                    )
                    _devices.append(_d)

        return _devices


class State(Device):

    _NAME_PATTERN = "(BS-21)-([0-9]+)-([01])-(.)"
    #                |     |        |       + Error Code, e.g. "A" is ASCII 65
    #                |     |        + 0=off, 1=on
    #                |     + Serial no., e.g. "004593"
    #                + Model, always "BS-21"

    _STATUS_PATTERN = "\$(BS-21)-([0-9]+)-([01])-(.) (V[0-9]+.[0-9]+) ([0-9]{2}) ([0-9]{2}) ([0-9]{2}) ([0-9]{2})"
    #                   ||       |        |      |   |                |          |          |          |         | Newline "\r\n"
    #                   ||       |        |      |   |                |          |          |          | Clock seconds, e.g. "59"
    #                   ||       |        |      |   |                |          |          | Clock minutes, e.g. "41"
    #                   ||       |        |      |   |                |          | Clock hours, e.g. "05"
    #                   ||       |        |      |   |                + Clock day of week, e.g. "02" for Tuesday
    #                   ||       |        |      |   + Firmware Version, e.g. "V1.18"
    #                   ||       |        |      + Error Code, e.g. "A" is ASCII 65
    #                   ||       |        + 0=off, 1=on
    #                   ||       + Serial no., e.g. "004593"
    #                   |+ Model, always "BS-21"
    #                   + Sign for begin response

    _WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    RANDOM_SCHEDULER = 41
    COUNTDOWN_SCHEDULER = 43

    serial = ""
    model = ""
    firmware = ""
    is_on = False
    is_overtemp = False
    is_power = False
    is_random = False
    is_countdown = False
    time = dict()
    schedulers = list()
    random = dict()
    countdown = dict()

    def get_printable_status(self) -> str:

        s = "\n"
        s += " MAC-Address:      %s\n" % self.mac
        s += " PIN:              %s\n" % self.pin
        s += " Alias:            %s\n" % ("" if not self.alias else self.alias)
        s += "\n"
        s += " Model:            %s\n" % self.model
        s += " Serial no.:       %s\n" % self.serial
        s += " Firmware:         %s\n" % self.firmware
        s += "\n"
        s += " Relais:           %s\n" % ("on" if self.is_on else "off")
        s += " Random mode:      %s\n" % ("on" if self.is_random else "off")
        s += " Countdown:        %s\n" % ("on" if self.is_countdown else "off")
        s += " Power:            %s\n" % ("yes" if self.is_power else "no")
        s += " Over temperature: %s\n" % ("yes" if self.is_overtemp else "no")
        s += "\n"
        s += " Time:             %s, %s" % (
            self.time["weekday"][0], self.time["time"])
        s += "\n"
        return s

    def get_printable_schedulers(self) -> str:

        s = ""

        if len(self.random["schedule"]["weekday"]) > 0:
            s += " Random:           %s on %s for %s hours, %s\n" % (
                self.random["schedule"]["time"],
                ", ".join(self.random["schedule"]["weekday"]),
                self.random["duration"][:-3],
                "active" if self.random["active"] else "inactive"
            )

        if self.countdown["active"]:
            s += " Countdown:        %s, switch %s in %s\n" % (
                "Running" if self.countdown["active"] else "Stopped",
                self.countdown["type"],
                self.countdown["remaining"]
            )

        for scheduler in sorted(self.schedulers, key=lambda s: s["slot"] % 20):
            if len(scheduler["schedule"]["weekday"]) > 0:
                s += " Scheduler %02d %s:\tSwitch %s at %s on %s\n" % (
                    scheduler["slot"] % 20,
                    scheduler["type"],
                    scheduler["type"],
                    scheduler["schedule"]["time"][:-3],
                    ", ".join(scheduler["schedule"]["weekday"])
                )

        return s

    def __init__(self, address="", pin="", alias="", port="", controller="", mac="", name="") -> None:

        super().__init__(address=address, pin=pin, alias=alias,
                         port=port, controller=controller, mac=mac, name=name)

    def set_state_from_name(self, name: str) -> None:

        matcher = re.search(State._NAME_PATTERN, name)
        if matcher == None:
            raise BS21Exception("ERROR: Unexpected device name!")

        self.model = matcher.group(1)
        self.serial = matcher.group(2)
        self.is_power = matcher.group(3) == "1"
        self.is_overtemp = (ord(matcher.group(4)) & 2) > 0
        self.is_power = (ord(matcher.group(4)) & 4) > 0
        self.is_random = (ord(matcher.group(4)) & 8) > 0
        self.is_countdown = (ord(matcher.group(4)) & 16) > 0

    def set_state_from_response(self, response: str) -> None:

        if response.startswith("$ERR"):
            raise BS21Exception(
                "ERROR: Device has explicitly responded with error! Do you want to double-check PIN?")

        matcher = re.search(State._STATUS_PATTERN, response)
        if matcher == None:
            raise BS21Exception("ERROR: Unexpected response from device!")

        self.model = matcher.group(1)
        self.serial = matcher.group(2)
        self.firmware = matcher.group(5)
        self.is_on = matcher.group(3) == "1"
        self.is_overtemp = (ord(matcher.group(4)) & 2) > 0
        self.is_power = (ord(matcher.group(4)) & 4) > 0
        self.is_random = (ord(matcher.group(4)) & 8) > 0
        self.is_countdown = (ord(matcher.group(4)) & 16) > 0

        # day_in_hex = hex(int(matcher.group(6))).replace("x", "0")
        day_in_hex = matcher.group(6)
        _time = State.build_weekdays_and_time(
            day_in_hex, matcher.group(7), matcher.group(8), matcher.group(9))

        self.time = _time

    def set_timers_from_response(self, response: str) -> None:

        if not response.startswith("$OK"):
            raise BS21Exception(
                "ERROR: Device has explicitly responded with error! Do you want to double-check PIN?")

        if len(response) != 442:
            raise BS21Exception("ERROR: Unexpected response from device!")

        # parse schedulers
        raw = response[14:372].split(" ")
        self.schedulers = list()
        for i in range(40):
            self.schedulers.append({
                "slot": i + 1,
                "type": "on" if i <= 19 else "off",
                "schedule": State.build_weekdays_and_time(raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2])
            })

        # parse random mode
        raw = response[374:414].split(" ")
        self.random = {
            "slot": State.RANDOM_SCHEDULER,
            "active": True if raw[5] != "00" else False,
            "schedule": State.build_weekdays_and_time(raw[0], raw[1], raw[2]),
            "duration": State.build_time(raw[3], raw[4])
        }

        # parse countdown
        raw = response[416:439].split(" ")
        original = datetime.datetime(
            2000, 1, 1, int(raw[5]), int(raw[6]), int(raw[7]))

        _remaining_secs = int(raw[7]) if raw[3].startswith(
            "I") else int(raw[3])
        remaining = datetime.timedelta(
            hours=int(raw[1]), minutes=int(raw[2]), seconds=_remaining_secs)
        self.countdown = {
            "slot": State.COUNTDOWN_SCHEDULER,
            "active": True if raw[4] != "00" else False,
            "type": "on" if raw[0] != "00" else "off",
            "remaining": State.build_time(raw[1], raw[2], _remaining_secs),
            "elapsed": (original - remaining).strftime("%H:%M:%S"),
            "original": State.build_time(raw[5], raw[6], raw[7])
        }

    @staticmethod
    def init_state_from_device(device):

        _s = State()

        _s.address = device.address
        _s.pin = device.pin
        _s.alias = device.alias
        _s.port = device.port
        _s.controller = device.controller
        _s.mac = device.mac
        _s.name = device.name

        return _s

    @staticmethod
    def init_state_by_address(address):

        _d = next(filter(lambda _d: _d.address ==
                  address, Device.get_devices()))
        if _d:
            return State.init_state_from_device(_d)

        else:
            return State(address=address)

    @staticmethod
    def build_weekdays_and_time(day, hour, minute, second=0):

        _hour = int(hour) % 24
        _minute = int(minute) % 60
        _second = int(second) % 60

        weekdays = []
        i = 1
        for weekday in State._WEEKDAYS:
            if i & int(day, 16) > 0:
                weekdays += [weekday]
            i *= 2

        time = {
            "weekday": weekdays,
            "time": State.build_time(_hour, _minute, _second)
        }

        return time

    @staticmethod
    def build_time(hour, minute, second=0):

        _hour = int(hour) % 24
        _minute = int(minute) % 60
        _second = int(second) % 60

        _time = "%02d:%02d:%02d" % (_hour, _minute, _second)

        return _time


class BS21():

    LOGGER = logging.getLogger("BS21")

    _client_socket = None
    _serial = None

    _state = None

    _PAYLOAD = {
        "on": "REL1",                                     # no parameters
        "off": "REL0",                                    # no parameters
        "status": "RELX",                                 # no parameters
        # % (0=off/1=on, dur_hh, dur_mm, dur_ss)
        "countdown": "SET43 %02d %02d %02d %02d 01",
        "countdown-clear": "CLEAR43",                     # no parameters
        # % (id[1-20]->on / id[21-40]->off, daymask, hh, mm)
        "scheduler": "SET%02d %s %02d %02d %02d 01",
        "scheduler-clear": "CLEAR%02d",                   # no parameters
        # % (id, daymask, start_hh, start_mm, dur_hh, dur_mm)
        "random": "SET%02d %s %02d %02d %02d %02d 01 00",
        "random-clear": "CLEAR41",                        # no parameters
        "clear-all": "CLEAR00",                           # no parameters
        "pin": "NEWC #%s ",                               # % (newpin)
        "visible": "VISB",                                # no parameters
        # % (weekday, hh, mm, ss)
        "sync": "TIME %s %02d %02d %02d",
        "schedulers": "INFO"                              # no parameters
    }

    def __init__(self, address, pin=None) -> None:

        self._state = State.init_state_by_address(address)
        if pin:
            self._state.pin = pin

    def connect(self) -> bool:

        try:
            if re.match(Device.MAC_PATTERN, self._state.address):
                BS21.LOGGER.debug("Connnect via Bluetooth to %s" %
                                  self._state.address)
                self._client_socket = socket.socket(
                    socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
                self._client_socket.connect((self._state.address, 1))
                self._client_socket.settimeout(2)

            else:
                raise BS21Exception("Invalid mac address.")

        except:
            BS21.LOGGER.error(
                "Connection failed! Check mac address and device.\n")

            return None

        BS21.LOGGER.debug("Connnected to %s" % self._state.address)
        self.sync_time()

        return self._state

    def disconnect(self) -> None:

        BS21.LOGGER.debug("disconnect")
        try:
            if self._client_socket:
                self._client_socket.close()

            if self._serial:
                self._serial.close()

        except:
            pass

        BS21.LOGGER.debug("disconnected")

    def _send(self, payload: str) -> str:

        data = "%s#%s\r\n" % (payload, self._state.pin)
        BS21.LOGGER.debug(" >>> %s" % data)

        try:
            if self._serial:
                self._serial.write(data.encode("utf-8"))
                self._serial.flush()

            elif self._client_socket:
                self._client_socket.send(data.encode("utf-8"))

        except:
            raise BS21Exception("ERROR: Failed to send command to device!")

        try:
            _str = ""
            while True:
                if self._serial:
                    _bytes = list(self._serial.read(1))

                elif self._client_socket:
                    _bytes = self._client_socket.recv(1024)

                if not _bytes:
                    break
                _str = _str + _bytes.decode("utf-8")

                # we have reach end of message
                if _str.find("\r\n") != -1:
                    break

        except:
            raise BS21Exception(
                "ERROR: No response from device! Do you want to double-check PIN?")

        BS21.LOGGER.debug(" <<< %s" % _str)

        return _str

    def _is_response_ok(self, response):

        return response.startswith("$OK")

    def request_state(self) -> State:

        BS21.LOGGER.debug(" SEND: request state")

        response = self._send(BS21._PAYLOAD["status"])
        self._state.set_state_from_response(response)

        BS21.LOGGER.debug(" SUCCESS: state received")

        return self._state

    def get_state(self) -> State:

        return self._state

    def sync_time(self) -> State:

        BS21.LOGGER.debug(" SEND: synchronize time")

        now = datetime.datetime.now()
        weekday = hex(pow(2, now.weekday())).replace("x", "0")[-2:]

        payload = BS21._PAYLOAD["sync"] % (
            weekday, now.hour, now.minute, now.second)
        response = self._send(payload)
        self._state.set_state_from_response(response)

        BS21.LOGGER.debug(" SUCCESS: time synchronized")

        return self._state

    def request_schedulers(self) -> State:

        BS21.LOGGER.debug(" SEND: request schedulers")

        response = self._send(BS21._PAYLOAD["schedulers"])
        self._state.set_timers_from_response(response)

        BS21.LOGGER.debug(" SUCCESS: schedulers received")

        return self._state

    def turn_on(self) -> State:

        BS21.LOGGER.debug(" SEND: turn on")

        response = self._send(BS21._PAYLOAD["on"])
        self._state.set_state_from_response(response)

        BS21.LOGGER.debug(" SUCCESS: turned on")

        return self._state

    def turn_off(self) -> State:

        BS21.LOGGER.debug(" SEND: turn off")

        response = self._send(BS21._PAYLOAD["off"])
        self._state.set_state_from_response(response)

        BS21.LOGGER.debug(" SUCCESS: turned off")

        return self._state

    def toggle(self):

        if self._state.is_on:
            self.turn_off()

        else:
            self.turn_on()

    @staticmethod
    def _build_daymask(mon=None, tue=None, wed=None, thu=None, fri=None, sat=None, sun=None) -> str:

        b = 0
        b += 1 if mon else 0
        b += 2 if tue else 0
        b += 4 if wed else 0
        b += 8 if thu else 0
        b += 16 if fri else 0
        b += 32 if sat else 0
        b += 64 if sun else 0

        return hex(b).replace("x", "0")[-2:].upper()

    def _get_or_create_and_add_scheduler(self, id):

        scheduler = next(
            filter(lambda _s: _s["slot"] == id, self._state.schedulers))
        if not scheduler:
            scheduler = {
                "slot": id
            }
            self._state.schedulers.append(scheduler)

        return scheduler

    def set_scheduler(self, id, type, hours, minutes, mon, tue, wed, thu, fri, sat, sun) -> State:

        BS21.LOGGER.debug(" SEND: set scheduler")

        _id = int(id) % 20
        _id = _id if type == "on" else _id + 20
        _d = BS21._build_daymask(mon, tue, wed, thu, fri, sat, sun)
        _h = int(hours) % 24
        _m = int(minutes) % 60
        _s = 0

        payload = BS21._PAYLOAD["scheduler"] % (_id, _d, _h, _m, _s)
        response = self._send(payload)

        if not self._is_response_ok(response):
            raise BS21Exception("ERROR: Device returned error!")

        # update internal state

        scheduler = self._get_or_create_and_add_scheduler(_id)
        scheduler["type"] = "on" if _id <= 20 else "off"
        scheduler["schedule"] = State.build_weekdays_and_time(_d, _h, _m)

        BS21.LOGGER.debug(" SUCCESS: scheduler set")

        return self._state

    def reset_scheduler(self, id, type) -> State:

        BS21.LOGGER.debug(" SEND: clear scheduler")

        _id = int(id) % 20
        _id = _id if type == "on" else _id + 20

        payload = BS21._PAYLOAD["scheduler-clear"] % _id
        response = self._send(payload)

        if not self._is_response_ok(response):
            raise BS21Exception("ERROR: Device returned error!")

        # update internal state
        scheduler = self._get_or_create_and_add_scheduler(_id)
        scheduler["type"] = "on" if _id <= 20 else "off"
        scheduler["schedule"] = State.build_weekdays_and_time(
            BS21._build_daymask(), 0, 0)

        BS21.LOGGER.debug(" SUCCESS: scheduler cleared")

        return self._state

    def set_random(self, hours, minutes, dur_hours, dur_minutes, mon, tue, wed, thu, fri, sat, sun) -> State:

        BS21.LOGGER.debug(" SEND: set random")

        _d = BS21._build_daymask(mon, tue, wed, thu, fri, sat, sun)
        _h = int(hours) % 24
        _m = int(minutes) % 60
        _dh = int(dur_hours) % 24
        _dm = int(dur_minutes) % 60

        payload = BS21._PAYLOAD["random"] % (
            State.RANDOM_SCHEDULER, _d, _h, _m, _dh, _dm)
        response = self._send(payload)

        if not self._is_response_ok(response):
            raise BS21Exception("ERROR: Device returned error!")

        # update internal state
        self._state.is_random = True
        scheduler = self._get_or_create_and_add_scheduler(
            State.RANDOM_SCHEDULER)
        scheduler["active"] = True
        scheduler["schedule"] = State.build_weekdays_and_time(_d, _h, _m)
        scheduler["duration"] = State.build_time(_dh, _dm)

        BS21.LOGGER.debug(" SUCCESS: Random set")

        return self._state

    def reset_random(self) -> State:

        BS21.LOGGER.debug(" SEND: clear random mode")

        response = self._send(BS21._PAYLOAD["random-clear"])

        if not self._is_response_ok(response):
            raise BS21Exception("ERROR: Device returned error!")

        # update internal state
        self._state.is_random = False
        scheduler = self._get_or_create_and_add_scheduler(
            State.RANDOM_SCHEDULER)
        scheduler["active"] = False
        scheduler["schedule"] = State.build_weekdays_and_time(
            self._build_daymask(), 0, 0)
        scheduler["duration"] = State.build_time(0, 0)

        BS21.LOGGER.debug(" SUCCESS: Random mode cleared")

        return True

    def set_countdown(self, hours, minutes, seconds, type) -> State:

        BS21.LOGGER.debug(" SEND: set countdown")

        _t = 1 if type == "on" else 0
        _h = int(hours) % 24
        _m = int(minutes) % 60
        _s = int(seconds) % 60

        payload = BS21._PAYLOAD["countdown"] % (_t, _h, _m, _s)
        response = self._send(payload)

        if not self._is_response_ok(response):
            raise BS21Exception("ERROR: Device returned error!")

        # todo update state
        self._state.is_countdown = True
        original = datetime.datetime(2000, 1, 1, _h, _m, _s)
        remaining_secs = (datetime.datetime.today() - original).seconds
        self._state.countdown = {
            "slot": State.COUNTDOWN_SCHEDULER,
            "active": True,
            "type": type,
            "remaining": State.build_time(remaining_secs // 3600, (remaining_secs % 3600) // 60, remaining_secs % 60),
            "elapsed": "00:00:00",
            "original": State.build_time(_h, _m, _s)
        }

        BS21.LOGGER.debug(" SUCCESS: countdown set")

        return self._state

    def set_countdown_until(self, hour, minute, type) -> State:

        now = datetime.datetime.now()
        then = datetime.datetime(1900, 1, 1, int(hour) %
                                 24, int(minute) % 60, 0)

        duration = (then - now)
        _h = duration.seconds // 3600
        _m = duration.seconds % 3600 // 60
        _s = duration.seconds % 60

        return self.set_countdown(_h, _m, _s, type)

    def reset_countdown(self) -> State:

        BS21.LOGGER.debug(" SEND: clear countdown")

        response = self._send(BS21._PAYLOAD["countdown-clear"])

        if not self._is_response_ok(response):
            raise BS21Exception("ERROR: Device returned error!")

        # todo update state
        self._state.is_countdown = False
        self._state.countdown = {
            "slot": State.COUNTDOWN_SCHEDULER,
            "active": False,
            "type": "off",
            "remaining": "00:00:00",
            "elapsed": "00:00:00",
            "original": "00:00:00"
        }

        BS21.LOGGER.debug(" SUCCESS: countdown cleared")

        return self._state

    def reset_all(self) -> State:

        BS21.LOGGER.debug(" SEND: clear all schedulers")

        response = self._send(BS21._PAYLOAD["clear-all"])

        if not self._is_response_ok(response):
            raise BS21Exception("ERROR: Device returned error")

        self._state.schedulers = list()
        self._state.is_schedulers = False

        self._state.random = None
        self._state.is_random = False

        self._state.countdown = None
        self._state.is_countdown = False

        BS21.LOGGER.debug(" SUCCESS: all schedulers cleared")

        return self._state

    def change_pin(self, newpin) -> State:

        BS21.LOGGER.debug(" SEND: change pin")

        if not Alias.validate_pin(newpin):
            raise BS21Exception("ERROR: Pin must be 4-digit numeric")

        payload = BS21._PAYLOAD["pin"] % self._state.pin
        self._state.pin = newpin
        self._send(payload)

        BS21.LOGGER.debug(" SUCCESS: pin changed")

        return self._state

    def set_visible(self) -> State:

        BS21.LOGGER.debug(" SEND: set visible for next 2 minutes")

        self._send(BS21._PAYLOAD["visible"])

        BS21.LOGGER.debug(" SUCCESS: visible for next 2 minutes")

        return self._state

    def disconnect(self):

        try:
            if self._client_socket:
                self._client_socket.close()

            if self._serial:
                self._serial.close()

        except:
            pass


def _build_help(cmd, header=False, msg="") -> None:

    s = ""

    if header == True:
        s = """ Renkforce BS-21 bluetooth power switch command line interface \
 for Linux / Raspberry Pi / Windows

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


def _help() -> None:

    s = ""
    i = 0
    for cmd in sorted(COMMANDS):
        s += _build_help(cmd, i == 0)
        i += 1

    return s


def _translate_for_scheduler_call(id: str, type: str, weekdays: list[str], hours: str, minutes: str) -> list[str]:

    params = [id, type, hours, minutes]
    for i in range(len(weekdays)):
        params.append(weekdays[i].isupper() and weekdays[i] != "_")

    return params


def _translate_for_random_call(weekdays: list[str], hours: str, minutes: str, dur_hours: str, dur_minutes: str) -> list[str]:

    params = [hours, minutes, dur_hours, dur_minutes]
    for i in range(len(weekdays)):
        params.append(weekdays[i].isupper())

    return params


def do_commands(target, pin, commands):

    address, alias = Alias.get_address_n_alias(target)

    if address == None:
        raise BS21Exception(_build_help(
            None, True, "No alias found. Please check mac address!"))

    if pin == None and not alias:
        raise BS21Exception(_build_help(None, True, "No pin given?!"))

    bs21 = BS21(address, pin)
    bs21.connect()

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
                bs21.request_state()
                bs21.request_schedulers()
                print(bs21.get_state().get_printable_status())

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
                state = bs21.request_schedulers()
                print(state.get_printable_schedulers())

            elif func == "json":
                bs21.request_state()
                state = bs21.request_schedulers()
                print(state.toJSON())

            elif func == "sleep":
                time.sleep(int(call[0]))

            elif func == "debug":
                logging.basicConfig(level=logging.DEBUG)

            else:
                raise BS21Exception(_help()
                                    + "\n\n ERROR: Invalid command "
                                    + "<" + func + ">\n")

    except BS21Exception as ex:
        raise BS21Exception(_build_help(None, False, ex.message))

    finally:
        if bs21:
            bs21.disconnect()


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
            commands.append(command)

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

        # print devices
        elif len(commands) == 0 or commands[0] == "--devices":
            print("address\tpin\talias\tport\tcontroller\tmac\tname")
            for _d in Device.get_devices():
                print("%s\t%s\t%s\t%s\t%s\t%s\t%s" % (_d.address, _d.pin,
                      _d.alias, _d.port, _d.controller, _d.mac, _d.name))
            exit(0)

        # print aliases
        elif len(commands) == 0 or commands[0] == "--aliases":
            print("address\tpin\talias")
            for _a in Alias.get_aliases():
                print("%s\t%s\t%s" % (_a.address, _a.pin, _a.alias))
            exit(0)

        # do commands
        else:
            target, pin, commands = parse_args(commands)
            do_commands(target, pin, commands)

    except BS21Exception as e:
        print(e.message)
        exit(1)
