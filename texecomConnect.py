#!/usr/bin/env python
#
# Decoder for Texecom Connect API/Protocol
#
# Copyright (C) 2018 Joseph Heenan
# Updates Jul 2020 Charly Anderson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import socket
import time
import os
import sys

import crcmod
import hexdump
import datetime
import re

from area import Area
from user import User
from zone import Zone

from texecomDefines import TexecomDefines


class TexecomConnect(TexecomDefines):
    def __init__(self, host, port, udl_password):
        self.host = host
        self.port = port
        self.udlpassword = udl_password.encode("ascii")
        self.crc8_func = crcmod.mkCrcFun(poly=0x185, rev=False, initCrc=0xFF)
        self.nextseq = 0

        self.print_network_traffic = False
        self.log_verbose = False
        self.alive_heartbeat_secs = 300
        self.time_last_heartbeat = 0
        self.last_command_time = 0
        self.last_received_seq = -1
        self.last_sequence = -1
        self.last_command = None
        self.panelType = None
        self.firmwareVersion = None
        self.alive_event_func = None
        self.area_event_func = None
        self.area_details_func = None
        self.zone_details_func = None
        self.zone_event_func = None
        self.log_event_func = None
        self.numberOfZones = None
        self.highestUsedZone = None
        self.numberOfUsers = None
        self.numberOfAreas = None
        self.areaBitmapSize = None
        self.zoneBitmapSize = None
        self.zoneNumSize = None
        self.zones = {}
        self.users = {}
        self.areas = {}
        self.arm_disarm_reset_queue = []
        self.requestPanelOutputEvents = True
        self.s = None
        # used to record which of our idle commands we last sent to the panel
        self.lastIdleCommand = 0
        # Set to true if the idle loop should reread the site data
        self.siteDataChanged = False

    ## texecom commands
    # in order of their command number

    def login(self):
        """CMD_LOGIN"""
        response = self.sendcommand(self.CMD_LOGIN, self.udlpassword)
        if response is None:
            self.log("sendcommand returned None for login")
            return False
        if response == self.CMD_RESPONSE_NAK:
            self.log("NAK response from panel")
            return False
        elif response != self.CMD_RESPONSE_ACK:
            self.log("unexpected ack payload: " + str(response))
            return False
        return True

    def get_zone_state(self, startZone, numZones):
        """CMD_GETZONESTATE"""
        if numZones > 168:
            numZones = 168
        body = bytes([startZone & 0xFF, numZones & 0xFF])
        details = self.sendcommand(self.CMD_GETZONESTATE, body)
        if details is None:
            return None
        if len(details) == numZones:
            for idx in range(0, numZones):
                newState = details[idx]
                zone = self.get_zone(startZone + idx)
                if zone.zoneType != zone.ZONETYPE_UNUSED:
                    if zone.state != newState:
                        zone.save_state(newState)
                        if self.zone_event_func is not None:
                            self.zone_event_func(zone)
                        self.log(
                            "zoneState: zone {:d} '{}' {}".format(
                                startZone + idx, zone.state_text, zone.text 
                            )
                        )
            return numZones
        else:
            self.log(
                "GETZONESTATE: response wrong length: {:d}/{:d} ".format(
                    len(details), numZones
                )
            )
            self.log("Payload: ")
            hexdump.hexdump(details)
            return None

    def get_zone_details(self, zone_number):
        """CMD_GETZONEDETAILS"""
        body = zone_number.to_bytes(self.zoneNumSize, "little")
        details = self.sendcommand(self.CMD_GETZONEDETAILS, body)
        if details is None:
            return None
        if len(details) == (33 + self.areaBitmapSize):
            zone = self.get_zone(zone_number)
            zone.zoneType = details[0]
            zone.zoneType_text = self.zone_types[zone.zoneType]
            zone.areaBitmap = details[1 : self.areaBitmapSize + 1]
            zone.text = details[(self.areaBitmapSize + 1) :].decode("ascii")
        else:
            self.log("GETZONEDETAILS: response wrong length")
            self.log("Payload: ")
            hexdump.hexdump(details)
            return None
        zonetext = zone.text.replace("\x00", " ")
        zonetext = re.sub(r"\W+", " ", zonetext)
        zonetext = zonetext.strip()
        if len(zonetext) > 0:
            zone.text = zonetext
        if zone.zoneType != zone.ZONETYPE_UNUSED:
            self.log(
                "zone {:d} type {} name '{}'".format(
                    zone.number, zone.zoneType_text, zone.text
                )
            )
            if self.zone_details_func is not None:
                self.zone_details_func(zone, self.panelType, self.numberOfZones)
        return zone

    def arm_disarm_reset_area(self, cmd, arm_type, area_bitmap):
        """CMD_ARMAREAS, CMD_DISARMAREAS, CMD_RESETAREAS"""
        if cmd == self.CMD_ARMAREAS:
            body = arm_type + area_bitmap[0 : self.areaBitmapSize]
        elif cmd == self.CMD_DISARMAREAS or cmd == self.CMD_RESETAREAS:
            body = area_bitmap[0 : self.areaBitmapSize]
        else:
            self.log("unexpected cmd for ARMAREAS: 0x" + cmd.hex())
            return False
        response = self.sendcommand(cmd, body)
        if response is None:
            self.log("sendcommand returned None for ARMAREAS")
            return False
        if response == self.CMD_RESPONSE_NAK:
            self.log("NAK response from panel for ARMAREAS")
            return False
        elif response != self.CMD_RESPONSE_ACK:
            self.log(
                "unexpected ack payload for ARMAREAS: 0x"
                + cmd.hex()
                + " response: "
                + str(response.hex())
            )
            return False
        if cmd == self.CMD_ARMAREAS:
            if arm_type == self.ARMING_TYPE_FULL:
                cmdText = "arm"
            else:
                cmdText = "part arm"
        elif cmd == self.CMD_DISARMAREAS:
            cmdText = "disarm"
        elif cmd == self.CMD_RESETAREAS:
            cmdText = "reset"
        else:
            cmdText = "unknown"
        self.log(
            "cmd {} areas: 0x{}".format(
                cmdText, area_bitmap[0 : self.areaBitmapSize].hex()
            )
        )
        return True

    def get_system_flags(self):
        """CMD_GETSYSTEMFLAGS"""
        details = self.sendcommand(self.CMD_GETSYSTEMFLAGS, None)
        if details is None:
            return None
        if len(details) == 8:
            for idx in range(0, 8):
                sysFlags = details[idx]
                self.log("systemFlags {:d}: {:d}".format(idx, sysFlags))
            return True
        else:
            self.log(
                "GETSYSTEMFLAGS: response wrong length: {:d}/{:d} ".format(
                    len(details), 8
                )
            )
            self.log("Payload: ")
            hexdump.hexdump(details)
            return None

    def get_area_flags(self, startAreaFlag, numAreaFlags):
        """CMD_GETAREAFLAGS"""
        if self.numberOfZones == 640 and numAreaFlags > 31:
            numAreaFlags = 31
        body = bytes([(startAreaFlag & 0xFF), (numAreaFlags & 0xFF)])
        details = self.sendcommand(self.CMD_GETAREAFLAGS, body)
        if details is None:
            return None
        expectedResultSize = self.areaBitmapSize * numAreaFlags
        if len(details) == expectedResultSize:
            outputAreaBitmaps = {}
            for outputArea in range(0, numAreaFlags):
                idx = self.areaBitmapSize * outputArea
                areaBitmap = details[idx : (idx + self.areaBitmapSize + 1)]
                outputAreaBitmaps[startAreaFlag + outputArea] = areaBitmap
                if self.log_verbose:
                    self.log(
                        "GETAREAFLAGS {:d}: 0x{}".format(
                            startAreaFlag + outputArea, areaBitmap.hex()
                        )
                    )
            return outputAreaBitmaps
        else:
            self.log(
                "GETAREAFLAGS: response wrong length: {:d}/{:d} ".format(
                    len(details), expectedResultSize
                )
            )
            self.log("Payload: ")
            hexdump.hexdump(details)
            return None

    def get_lcd_display(self):
        """CMD_GETLCDDISPLAY"""
        lcddisplay = self.sendcommand(self.CMD_GETLCDDISPLAY, None)
        if lcddisplay is None:
            return None
        if len(lcddisplay) != 32:
            self.log("GETLCDDISPLAY: response wrong length")
            self.log("Payload: ")
            hexdump.hexdump(lcddisplay)
            return None
        self.log("Panel LCD display: " + lcddisplay.decode("ascii"))
        return lcddisplay

    def get_log_pointer(self):
        """CMD_GETLOGPOINTER"""
        logpointerresp = self.sendcommand(self.CMD_GETLOGPOINTER, None)
        if logpointerresp is None:
            return None
        if len(logpointerresp) != 2:
            self.log("GETLOGPOINTER: response wrong length")
            self.log("Payload: ")
            hexdump.hexdump(logpointerresp)
            return None
        logpointer = logpointerresp[0] + (logpointerresp[1] << 8)
        self.log("Log pointer: {:d}".format(logpointer))
        return logpointer

    def get_panel_identification(self):
        """CMD_GETPANELIDENTIFICATION"""
        panelid = self.sendcommand(self.CMD_GETPANELIDENTIFICATION, None)
        if panelid is None:
            return None
        if len(panelid) != 32:
            self.log("GETPANELIDENTIFICATION: response wrong length")
            self.log("Payload: ")
            hexdump.hexdump(panelid)
            return None
        panelid = panelid.decode("ascii")
        self.log("Panel identification: " + panelid)
        return panelid

    def get_date_time(self):
        """CMD_GETDATETIME"""
        datetimeresp = self.sendcommand(self.CMD_GETDATETIME, None)
        if datetimeresp is None:
            return None
        if len(datetimeresp) < 6:
            self.log("GETDATETIME: response too short")
            self.log("Payload: ")
            hexdump.hexdump(datetimeresp)
            return None
        datetimeresp = bytearray(datetimeresp)
        datetimestr = "20{2:02d}-{1:02d}-{0:02d} {3:02d}:{4:02d}:{5:02d}".format(
            *datetimeresp
        )
        paneltime = datetime.datetime(
            2000 + datetimeresp[2],
            datetimeresp[1],
            datetimeresp[0],
            datetimeresp[3],
            datetimeresp[4],
            datetimeresp[5]
        )
        seconds = int((paneltime - datetime.datetime.now()).total_seconds())
        if seconds > 0:
            diff = " (panel is ahead by {:d} seconds)".format(seconds)
        else:
            diff = " (panel is behind by {:d} seconds)".format(-seconds)
        self.log("Panel date/time: " + datetimestr + diff)
        return datetimestr

    def get_system_power(self):
        """CMD_GETSYSTEMPOWER"""
        details = self.sendcommand(self.CMD_GETSYSTEMPOWER, None)
        if details is None:
            return None
        if len(details) != 5:
            self.log("GETSYSTEMPOWER: response wrong length")
            self.log("Payload: ")
            hexdump.hexdump(details)
            return None
        ref_v = details[0]
        sys_v = details[1]
        bat_v = details[2]
        sys_i = details[3]
        bat_i = details[4]
        system_voltage = 13.7 + ((sys_v - ref_v) * 0.070)
        battery_voltage = 13.7 + ((bat_v - ref_v) * 0.070)
        system_current = sys_i * 9
        battery_current = bat_i * 9
        self.log(
            "System power: system voltage {:.2f} battery voltage {:.2f} system current {:d} battery current {:d}".format(
                system_voltage, battery_voltage, system_current, battery_current
            )
        )
        return (system_voltage, battery_voltage, system_current, battery_current)

    def get_user(self, usernumber):
        """CMD_GETUSER"""
        body = usernumber.to_bytes(self.zoneNumSize, "little")
        details = self.sendcommand(self.CMD_GETUSER, body)
        if details is None:
            return None
        user = User()
        if len(details) == 23:
            username = details[0:8].decode("ascii")
            username = username.replace("\x00", " ")
            username = re.sub(r"\W+", " ", username)
            username = username.strip()
            user.name = username
            user.passcode = self.bcdDecodeBytes(details[8:11])
            user.areas = details[11]
            user.modifiers = details[12]
            user.locks = details[13]
            user.doors = details[14:17]
            user.tag = self.bcdDecodeBytes(details[17:21])  # last byte always 0xff
            user.config = details[21] + ((details[22]) << 8)
        else:
            # there are other lengths but I have no way to test
            self.log("GETUSER: unexpected response length {:d}".format(len(details)))
            self.log("Payload: ")
            hexdump.hexdump(details)
            return None
        if user.valid():
            self.log("user {:d} name '{}'".format(usernumber, user.name))
        return user

    def get_area_details(self, areaNumber):
        """CMD_GETAREADETAILS"""
        details = self.sendcommand(self.CMD_GETAREADETAILS, bytes([areaNumber]))
        if details is None:
            return None
        area = self.get_area(areaNumber)
        if len(details) == 25:
            # first byte is area number
            areatext = (details[1:17]).decode("ascii")
            areatext = areatext.replace("\x00", " ")
            areatext = re.sub(r"\W+", " ", areatext)
            areatext = areatext.strip()
            if len(areatext) > 0:
                area.text = areatext
            area.exitDelay = details[17] + (details[18] << 8)
            area.entry1Delay = details[19] + (details[20] << 8)
            area.entry2Delay = details[21] + (details[22] << 8)
            area.secondEntry = details[23] + (details[24] << 8)
            self.log(
                "area {:d} text '{}' exitDelay {:d} entry1 {:d} entry2 {:d} secondEntry {:d}".format(
                    areaNumber,
                    area.text,
                    area.exitDelay,
                    area.entry1Delay,
                    area.entry1Delay,
                    area.secondEntry,
                )
            )
            if self.area_details_func is not None:
                self.area_details_func(area, self.panelType, self.numberOfZones)
        return area

    def get_zone_changes(self):
        """CMD_GETZONECHANGES"""
        details = self.sendcommand(self.CMD_GETZONECHANGES, None)
        if details is None:
            return None
        if len(details) == self.zoneBitmapSize:
            changedZonesBitmap = details
            return changedZonesBitmap
        else:
            self.log(
                "GETAREAFLAGS: response wrong length: {:d}/{:d} ".format(
                    len(details), self.zoneBitmapSize
                )
            )
            self.log("Payload: ")
            hexdump.hexdump(details)
            return None

    def set_event_messages(self):
        """CMD_SETEVENTMESSAGES"""
        DEBUG_FLAG = 1
        ZONE_EVENT_FLAG = 1 << 1
        AREA_EVENT_FLAG = 1 << 2
        OUTPUT_EVENT_FLAG = 1 << 3
        USER_EVENT_FLAG = 1 << 4
        LOG_FLAG = 1 << 5
        events = (
            ZONE_EVENT_FLAG
            | AREA_EVENT_FLAG
            | USER_EVENT_FLAG
            | LOG_FLAG
        )
        if self.requestPanelOutputEvents:
            events |= OUTPUT_EVENT_FLAG
        body = events.to_bytes(2, "little")
        response = self.sendcommand(self.CMD_SETEVENTMESSAGES, body)
        if response == self.CMD_RESPONSE_NAK:
            self.log("NAK response from panel")
            return False
        elif response != self.CMD_RESPONSE_ACK:
            self.log("unexpected ack payload: " + str(response))
            return False
        return True

    ### Helpers for processing texecom data

    def get_number_zones(self):
        idstr = self.get_panel_identification()
        if idstr is None:
            return None
        self.panelType, numberOfZones, something, self.firmwareVersion = idstr.split()
        self.numberOfZones = int(numberOfZones)
        zone2NumberOfUsers = {
            12: 8,
            24: 25,
            48: 50,
            64: 50,
            88: 100,
            168: 200,
            640: 1000,
        }
        zone2NumberOfAreas = {12: 2, 24: 2, 48: 4, 64: 4, 88: 8, 168: 16, 640: 64}
        zone2AreaBitmapSize = {12: 1, 24: 1, 48: 1, 64: 1, 88: 1, 168: 2, 640: 8}
        zone2ZoneNumSize = {12: 1, 24: 1, 48: 1, 64: 1, 88: 1, 168: 1, 640: 2}
        self.numberOfUsers = zone2NumberOfUsers[self.numberOfZones]
        self.numberOfAreas = zone2NumberOfAreas[self.numberOfZones]
        self.areaBitmapSize = zone2AreaBitmapSize[self.numberOfZones]
        self.zoneBitmapSize = int(self.numberOfZones / 8)
        self.zoneNumSize = zone2ZoneNumSize[self.numberOfZones]

    def set_zone_state(self, zone, zone_bitmap):
        zone.state = zone_bitmap
        if (zone.state & 0x3) == 1:
            zone.active = True
        else:
            zone.active = False
        zone_str = ["secure", "active", "tamper", "short"][zone.state & 0x3]
        if zone.state & (1 << 2):
            zone_str += ", fault"
        if zone.state & (1 << 3):
            zone_str += ", failed test"
        if zone.state & (1 << 4):
            zone_str += ", alarmed"
            zone.armed = True
        else:
            zone.armed = False
        if zone.state & (1 << 5):
            zone_str += ", manual bypassed"
        if zone.state & (1 << 6):
            zone_str += ", auto bypassed"
        if zone.state & (1 << 7):
            zone_str += ", zone masked"
        zone.state_text = zone_str

    def get_zone(self, zone_number):
        if zone_number not in self.zones:
            self.zones[zone_number] = Zone(zone_number)
        return self.zones[zone_number]

    def get_area(self, areaNumber):
        if areaNumber not in self.areas:
            self.areas[areaNumber] = Area(areaNumber)
        return self.areas[areaNumber]

    def get_all_zones(self):
        for zoneNumber in range(1, self.numberOfZones + 1):
            zone = self.get_zone_details(zoneNumber)
            self.zones[zoneNumber] = zone
            if zone.zoneType != zone.ZONETYPE_UNUSED:
                self.highestUsedZone = zoneNumber
                self.associateZoneWithAreas(zone)

    def get_all_users(self):
        if self.numberOfUsers is not None:
            for usernumber in range(1, self.numberOfUsers):
                user = self.get_user(usernumber)
                if user.valid():
                    self.users[usernumber] = user
            user = User()
            user.name = "Engineer"
            self.users[0] = user

    def get_all_areas(self):
        for areanumber in range(1, self.numberOfAreas + 1):
            area = self.get_area_details(areanumber)
            self.areas[areanumber] = area

    def get_all_zones_state(self):
        numZones = self.get_zone_state(1, self.highestUsedZone)
        if numZones is not None and numZones != self.highestUsedZone:
            self.log(
                "get_all_zones_state request {:d} zones, got {:d}".format(
                    self.highestUsedZone, numZones
                )
            )
        return numZones

    def get_changed_zones_state(self):
        changedZonesBitmap = self.get_zone_changes()
        if changedZonesBitmap is None:
            return None
        flags = int.from_bytes(changedZonesBitmap, "little")
        zoneNum = 1
        while zoneNum <= self.highestUsedZone:
            if (flags & 1) == 0:
                if flags == 0:
                    break
                flags = flags >> 1
                zoneNum += 1
            else:
                startZoneNum = zoneNum
                numZonesInBlock = 0
                while (flags & 1) == 1 and numZonesInBlock < 168:
                    flags = flags >> 1
                    zoneNum += 1
                    numZonesInBlock += 1
                respNumZone = self.get_zone_state(startZoneNum, numZonesInBlock)
                if respNumZone is None:
                    return None
        return True

    def get_armed_area_state(self):
        # we just track armed state (not part arming or part armed etc)
        outputAreaBitmaps = self.get_area_flags(21, 1)
        if outputAreaBitmaps is None:
            return None
        return self.saveAreasCurrentArmedState(
            outputAreaBitmaps[21], self.AREA_STATE_ARMED
        )

    def saveAreasCurrentArmedState(self, areaBitmap, areaStateWhenTrue):
        # if its not alarm flag, assume its disarmed (any interim state should self correct on next event)
        flags = int.from_bytes(areaBitmap, "little")
        for areanumber in range(1, self.numberOfAreas + 1):
            area = self.get_area(areanumber)
            if (flags & 1) == 1:
                newState = areaStateWhenTrue
            else:
                if area.state == None:
                    newState = self.AREA_STATE_DISARMED
                else:
                    newState = area.state
            # If we know that the area is part armed, don't override that with fully armed
            # (since area flags only gives us a binary armed / disarmed and not part armed)
            if area.state != newState and area.state != self.AREA_STATE_PARTARMED and newState != self.AREA_STATE_ARMED:
                area.save_state(newState)
                if self.area_event_func is not None:
                    self.area_event_func(area)
                self.log(
                    "areaState {:d} '{}': {:d} {}".format(
                        areanumber, area.text, area.state, area.state_text
                        )
                )
            flags = flags >> 1
        return True

    def associateZoneWithAreas(self, zone):
        flags = int.from_bytes(zone.areaBitmap, "little")
        for areanumber in range(1, self.numberOfAreas + 1):
            area = self.get_area(areanumber)
            if (flags & 1) == 1:
                zone.areas[areanumber] = area
                area.zones[zone.number] = zone
                self.log(
                    "zone {:d} -> area {:d} ('{}' -> '{}')".format(
                        zone.number, areanumber, zone.text, area.text
                    )
                )
            else:
                if areanumber in zone.areas:
                    del zone.areas[areanumber]
                if zone.number in area.zones:
                    del area.zones[zone.number]
            flags = flags >> 1
        return True

    def alive(self):
        # call any alive callback
        self.time_last_heartbeat = time.time()
        self.log("alive ok")
        if self.alive_event_func is not None:
            self.alive_event_func()
        return True

    def get_site_data(self):
        self.get_all_areas()
        self.get_all_zones()
        self.get_all_users()

    def on_alive_event(self, alive_event_func):
        self.alive_event_func = alive_event_func

    def on_area_event(self, area_event_func):
        self.area_event_func = area_event_func

    def on_zone_event(self, zone_event_func):
        self.zone_event_func = zone_event_func

    def on_area_details(self, area_details_func):
        self.area_details_func = area_details_func

    def on_zone_details(self, zone_details_func):
        self.zone_details_func = zone_details_func

    def on_log_event(self, log_event_func):
        self.log_event_func = log_event_func

    def enable_output_events(self, yes):
        self.requestPanelOutputEvents = (yes == True)

    def requestArmAreas(self, area_bitmap):
        """Queue arm areas request. Request is queued for processing by main thread"""
        self.arm_disarm_reset_queue.append((self.CMD_ARMAREAS, self.ARMING_TYPE_FULL, area_bitmap))

    def requestPartArmAreas(self, area_bitmap):
        """Queue part arm areas request. Request is queued for processing by main thread"""
        self.arm_disarm_reset_queue.append((self.CMD_ARMAREAS, self.ARMING_TYPE_PART1, area_bitmap))

    def requestDisArmAreas(self, area_bitmap):
        """Queue disarm areas request. Request is queued for processing by main thread"""
        self.arm_disarm_reset_queue.append((self.CMD_DISARMAREAS, None, area_bitmap))

    def requestResetAreas(self, area_bitmap):
        """Queue reset areas request. Request is queued for processing by main thread"""
        self.arm_disarm_reset_queue.append((self.CMD_RESETAREAS, None, area_bitmap))

    def set_area_state(self, area, area_state):
        area.state = area_state
        area.state_text = [
            "disarmed",
            "in exit",
            "in entry",
            "armed",
            "part armed",
            "in alarm",
        ][area.state]

    def handle_event_message(self, payload):
        msg_type, payload = payload[0:1], payload[1:]
        if msg_type == self.MSG_DEBUG:
            return "Debug message: " + payload.decode("ascii")
        elif msg_type == self.MSG_ZONEEVENT:
            if len(payload) == 2:
                zone_number = payload[0]
                zone_bitmap = payload[1]
            elif len(payload) == 3:
                zone_number = payload[0] + (payload[1] << 8)
                zone_bitmap = payload[2]
            else:
                return "unknown zone event payload length: {:d}".format(
                    len(payload)
                )
            zone = self.get_zone(zone_number)
            zone.save_state(zone_bitmap)
            if self.zone_event_func is not None:
                self.zone_event_func(zone)
            return "Zone event: zone {:d} '{}' {}".format(
                zone.number, zone.state_text, zone.text
            )
        elif msg_type == self.MSG_AREAEVENT:
            area_number = payload[0]
            area_state = payload[1]
            area = self.get_area(area_number)
            area.save_state(area_state)
            if self.area_event_func is not None:
                self.area_event_func(area)
            return "Area event: area {:d} {} {}".format(
                area.number, area.state_text, area.text
            )
        elif msg_type == self.MSG_OUTPUTEVENT:
            locations = [
                "Panel outputs",
                "Digi outputs",
                "Digi Channel low 8",
                "Digi Channel high 8",
                "Redcare outputs",
                "Custom outputs 1",
                "Custom outputs 2",
                "Custom outputs 3",
                "Custom outputs 4",
                "X-10 outputs",
            ]
            output_location = payload[0]
            output_state = payload[1]
            if output_location < len(locations):
                output_name = locations[output_location]
            elif (output_location & 0xF) == 0:
                output_name = "Network {:d} keypad outputs".format(output_location >> 4)
            else:
                output_name = "Network {:d} expander {:d} outputs".format(
                    output_location >> 4, output_location & 0xF
                )
            return "Output event message: location {:d}['{}'] now {:#04x}".format(
                output_location, output_name, output_state
            )
        elif msg_type == self.MSG_USEREVENT:
            user_number = payload[0]
            user_state = payload[1]
            user_state_str = ["code", "tag", "code+tag"][user_state]
            if user_number in self.users:
                name = self.users[user_number].name
            else:
                name = "unknown"
            return "User event message: logon by user '{}' {:d} {}".format(
                name, user_number, user_state_str
            )
        elif msg_type == self.MSG_LOGEVENT:
            if len(payload) == 8:
                parameter = payload[2]
                areas = payload[3]
                timestamp = payload[4:8]
            elif len(payload) == 9:
                # Premier 168 - longer message as 16 bits of area info
                parameter = payload[2]
                areas = payload[3] + (payload[8] << 8)
                timestamp = payload[4:8]
            elif len(payload) == 16:
                # Premier 640
                # I'm unsure if this is correct and I don't have a panel to test with
                parameter = payload[2] + (payload[3] << 8)
                areas = (
                    payload[4]
                    + (payload[5] << 8)
                    + (payload[6] << 16)
                    + (payload[7] << 24)
                )
                timestamp = payload[8:16]
            else:
                return "unknown log event message payload length"
            event_type = payload[0]
            group_type_msg = payload[1]
            timestamp_int = (
                timestamp[0]
                + (timestamp[1] << 8)
                + (timestamp[2] << 16)
                + (timestamp[3] << 24)
            )
            seconds = timestamp_int & 63
            minutes = (timestamp_int >> 6) & 63
            month = (timestamp_int >> 12) & 15
            hours = (timestamp_int >> 16) & 31
            day = (timestamp_int >> 21) & 31
            year = 2000 + ((timestamp_int >> 26) & 63)
            timestamp_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                year, month, day, hours, minutes, seconds
            )
            if event_type in self.log_event_types:
                event_str = self.log_event_types[event_type]
            else:
                event_str = "Unknown log event type {:d}".format(event_type)
            group_type = group_type_msg & 0b00111111
            comm_delayed = group_type_msg & 0b01000000
            communicated = group_type_msg & 0b10000000

            if group_type in self.log_event_group_type:
                group_type_str = self.log_event_group_type[group_type]
            else:
                group_type_str = "Unknown log event group type {:d}".format(group_type)

            if comm_delayed:
                group_type_str += " [comm delayed]"
            if communicated:
                group_type_str += " [communicated]"

            return "Log event message: {} {}, {} parameter: {:d} areas: {:d}".format(
                timestamp_str, event_str, group_type_str, parameter, areas
            )
        else:
            return "unknown message type " + msg_type.hex() + ": 0x" + payload.hex()

    def message_event(self, payload):
        result = self.handle_event_message(payload)
        self.log(result)
        return None

    ### Main event loop
    def event_loop(self):
        lastConnectedAt = time.time()
        notifiedConnectionLoss = False
        connected = False
        while True:
            if connected:
                lastConnectedAt = time.time()
                connected = False
                notifiedConnectionLoss = False
                self.log("Connection lost")
            connectionLostTime = time.time() - lastConnectedAt
            if connectionLostTime >= 60 and not notifiedConnectionLoss:
                self.log(
                    "Connection lost for over 60 seconds - calling send-message.sh"
                )
                os.system("./send-message.sh 'connection lost'")
                notifiedConnectionLoss = True
            try:
                self.connect()
            except socket.error as e:
                self.log("Connect failed - {}; sleeping for 5 seconds".format(e))
                time.sleep(5)
                continue
            if not self.login():
                self.log(
                    "Login failed - udl password incorrect, pre-v4 panel, or trying to connect too soon: closing socket, try again 5 in seconds"
                )
                time.sleep(5)
                self.closesocket()
                continue
            self.log("login successful")
            if not self.set_event_messages():
                self.log("Set event messages failed, closing socket")
                self.closesocket()
                continue
            connected = True
            if notifiedConnectionLoss:
                self.log("Connection regained - calling send-message.sh")
                os.system("./send-message.sh 'connection regained'")
            self.get_number_zones()
            self.get_date_time()
            self.get_system_power()
            self.get_log_pointer()
            self.get_site_data()
            self.get_all_zones_state()
            self.get_armed_area_state()
            # self.get_system_flags()
            self.log("Got all areas/zones/users; waiting for events")
            while self.s is not None:
                try:
                    for zone in list(self.zones.values()):
                        zone.update()
                    if self.siteDataChanged:
                        self.siteDataChanged = False
                        self.get_site_data()
                    self.recvresponse()
                except socket.timeout:
                    # we didn't send any command, so a timeout is the expected result, continue our loop
                    continue

    ### Comms to texecom panel

    def connect(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(self.CMD_TIMEOUT)
        self.s.connect((self.host, self.port))
        # if we send the login message to fast the panel ignores it; texecom
        # recommend 500ms, see:
        # http://texecom.websitetoolbox.com/post/show_single_post?pid=1303528828&postcount=4&forum=627911
        time.sleep(0.5)

    def closesocket(self):
        if self.s is not None:
            try:
                self.s.shutdown(socket.SHUT_RDWR)
            except socket.error:
                pass
            self.s.close()
            self.s = None

    def recvresponse(self):
        """Receive a response to a command. Automatically handles any messages that arrive first"""
        startTime = time.time()
        while True:
            if time.time() - startTime > self.CMD_TIMEOUT:
                # if we have had multiple event messages, we may get to the timeout time without the recv timing out
                raise socket.timeout
            assert self.last_command_time > 0
            time_since_last_command = time.time() - self.last_command_time
            if self.last_command is None and len(self.arm_disarm_reset_queue) > 0:
                # when no command waiting, drain any arm_disarm_reset queue
                request = self.arm_disarm_reset_queue.pop(0)
                self.arm_disarm_reset_area(request[0], request[1], request[2])
            elif time_since_last_command > 30:
                # get_changed_zones_state and get_armed_area_state to protect against any lost event messages for zone/area status
                # and to reset the panel's 60 second timeout
                # this ends up recursively calling recvresponse; however as our retry * timeout (3 * 2 == 6) is
                # far less than the 30 seconds between idle commands that won't be an issue
                if self.lastIdleCommand == 0:
                    result = self.get_changed_zones_state()
                else:
                    result = self.get_armed_area_state()
                self.lastIdleCommand += 1
                if self.lastIdleCommand == 2:
                    self.lastIdleCommand = 0
                if result is None:
                    self.log("idle command failed; closing socket")
                    self.closesocket()
                    return None
            if time.time() - self.time_last_heartbeat > self.alive_heartbeat_secs:
                self.alive()
            header = self.s.recv(self.LENGTH_HEADER)
            if self.print_network_traffic:
                self.log("Received message header:")
                hexdump.hexdump(header)
            if header == b"+++":
                self.log(
                    "Panel has forcibly dropped connection, possibly due to inactivity"
                )
                self.closesocket()
                return None
            if header == b"+++A":
                self.log("Panel is trying to hangup modem; probably connected too soon")
                self.closesocket()
                return None
            if len(header) == 0:
                self.log("Panel has closed connection")
                self.closesocket()
                return None
            if len(header) < self.LENGTH_HEADER:
                # fix if data isn't in 1 packet
                #header += self.s.recv(self.LENGTH_HEADER - len(header))
                if len(header) < self.LENGTH_HEADER:
                    self.log(
                        "Header received from panel is too short, only {:d} bytes, ignoring - contents:".format(
                            len(header)
                        )
                    )
                    hexdump.hexdump(header)
                    continue
            msg_start, msg_type, msg_length, msg_sequence = (
                header[0:1],
                header[1:2],
                header[-2],
                header[-1],
            )
            if msg_start != b"t":
                self.log("unexpected msg start: 0x" + msg_start.hex())
                hexdump.hexdump(header)
                return None
            expected_len = msg_length - self.LENGTH_HEADER
            #received_len = 0
            #payload = bytearray()
            #while received_len < expected_len:
            #    curr_payload = self.s.recv(expected_len)
            #    if self.print_network_traffic:
            #        self.log("Received message payload:")
            #        hexdump.hexdump(curr_payload)
            #    payload += curr_payload
            #    received_len += len(curr_payload)
            #    if (len(curr_payload) == 0):
            #        self.log("no more data")
            #        break

            payload = self.s.recv(expected_len)
            if self.print_network_traffic:
                self.log("Received message payload:")
                hexdump.hexdump(payload)
            if len(payload) < expected_len:
                self.log(
                    "Ignoring message, payload shorter than expected - got {:d} bytes, expected {:d}".format(
                        len(payload), expected_len
                    )
                )
                print("header:")
                hexdump.hexdump(header)
                print("payload:")
                hexdump.hexdump(payload)
                continue
            payload, msg_crc = payload[:-1], payload[-1]
            expected_crc = self.crc8_func(header + payload)
            if msg_crc != expected_crc:
                self.log(
                    "crc: expected=" + str(expected_crc) + " actual=" + str(msg_crc)
                )
                return None
            if msg_type == self.HEADER_TYPE_RESPONSE:
                if msg_sequence != self.last_sequence:
                    self.log(
                        "incorrect response seq: expected="
                        + str(self.last_sequence)
                        + " actual="
                        + str(msg_sequence)
                    )
                    # recv again - either we receive the correct reply in the next packet, or we'll time out and retry the command
                    continue
            elif msg_type == self.HEADER_TYPE_MESSAGE:
                if self.last_received_seq != -1:
                    next_msg_seq = self.last_received_seq + 1
                    if next_msg_seq == 256:
                        next_msg_seq = 0
                    if msg_sequence == self.last_received_seq:
                        self.log(
                            "ignoring message, sequence number is the same as last message: expected="
                            + str(next_msg_seq)
                            + " actual="
                            + str(msg_sequence)
                        )
                        continue
                    if msg_sequence != next_msg_seq:
                        self.log(
                            "message seq incorrect - processing message anyway: expected="
                            + str(next_msg_seq)
                            + " actual="
                            + str(msg_sequence)
                        )
                        # process message anyway; perhaps we missed one or they arrived out of order
                self.last_received_seq = msg_sequence
            if msg_type == self.HEADER_TYPE_COMMAND:
                self.log("received command unexpectedly")
                return None
            elif msg_type == self.HEADER_TYPE_RESPONSE:
                return payload
            elif msg_type == self.HEADER_TYPE_MESSAGE:
                # FIXME: for "Site Data Changed" we should re-read the zone names etc - need to decode message
                # self.siteDataChanged = True
                self.message_event(payload)

    def sendcommand(self, cmd, body):
        if body is not None:
            body = cmd + body
        else:
            body = cmd
        self.sendcommandbody(body)
        self.last_command_time = time.time()
        retries = self.CMD_RETRIES
        response = None
        while retries > 0:
            retries -= 1
            try:
                response = self.recvresponse()
                break
            except socket.timeout:
                # NB: sequence number will be the same as last attempt
                if self.last_command is None:
                    return None
                self.log("Timeout waiting for response, resending last command")
                self.last_command_time = time.time()
                self.s.send(self.last_command)

        self.last_command = None
        if response is None:
            return None

        commandid, payload = response[0:1], response[1:]
        if commandid != cmd:
            if commandid == self.CMD_LOGIN and payload[0:1] == self.CMD_RESPONSE_NAK:
                self.log(
                    "Received 'Log on NAK' from panel - session has timed out and needs to be restarted"
                )
                return None
            self.log(
                "Got response for wrong command id: Expected 0x"
                + cmd.hex()
                + ", got 0x"
                + commandid.hex()
            )
            self.log("Payload:")
            hexdump.hexdump(payload)
            return None
        return payload

    def sendcommandbody(self, body):
        self.last_sequence = self.getnextseq()
        data = (
            self.HEADER_START
            + self.HEADER_TYPE_COMMAND
            + bytes([len(body) + 5, self.last_sequence])
            + body
        )
        data += bytes([(self.crc8_func(data))])
        if self.print_network_traffic:
            self.log("Sending command: 0x" + data.hex())
        self.s.send(data)
        self.last_command = data

    def getnextseq(self):
        if self.nextseq == 256:
            self.nextseq = 0
        nextseq = self.nextseq
        self.nextseq += 1
        return nextseq

    ### General helpers

    def log(self, string):
        timestamp = time.strftime("%Y-%m-%d %X")
        string = timestamp + ": " + string
        print(string)
        if self.log_event_func is not None:
            self.log_event_func(string)

    @staticmethod
    def bcdDecodeBytes(bcd):
        result = ""
        for char in bcd:
            for val in ((char >> 4), (char & 0xF)):
                if val <= 9:
                    result += str(val)
        return result
