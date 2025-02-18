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
 
class TexecomDefines:

    LENGTH_HEADER = 4
    HEADER_START = b't'
    HEADER_TYPE_COMMAND = b'C'
    HEADER_TYPE_RESPONSE = b'R'
    HEADER_TYPE_MESSAGE = b'M'  # unsolicited message

    CMD_LOGIN = bytes([1])
    CMD_GETZONESTATE = bytes([2])
    CMD_GETZONEDETAILS = bytes([3])
    CMD_ARMAREAS = bytes([6])
    CMD_DISARMAREAS = bytes([8])
    CMD_RESETAREAS = bytes([9])
    CMD_GETSYSTEMFLAGS = bytes([10])
    CMD_GETAREAFLAGS = bytes([11])
    CMD_GETLCDDISPLAY = bytes([13])
    CMD_GETLOGPOINTER = bytes([15])
    CMD_GETPANELIDENTIFICATION = bytes([22])
    CMD_GETDATETIME = bytes([23])
    CMD_GETSYSTEMPOWER = bytes([25])
    CMD_GETUSER = bytes([27])
    CMD_GETAREADETAILS = bytes([35])
    CMD_GETZONECHANGES = bytes([36])
    CMD_SETEVENTMESSAGES = bytes([37])

    # 2-3 seconds is mentioned in section 5.5 of protocol specification
    # Increasing this value is not recommended as it will mean if the
    # panel fails to respond to a command (as it sometimes does it it
    # sends an event at the same time we send a command) it will take
    # longer for us to realise and resend the command
    CMD_TIMEOUT = 2
    CMD_RETRIES = 3

    CMD_RESPONSE_ACK = b'\x06'
    CMD_RESPONSE_NAK = b'\x15'

    MSG_DEBUG = bytes([0])
    MSG_ZONEEVENT = bytes([1])
    MSG_AREAEVENT = bytes([2])
    MSG_OUTPUTEVENT = bytes([3])
    MSG_USEREVENT = bytes([4])
    MSG_LOGEVENT = bytes([5])

    ARMING_TYPE_FULL = bytes([0])
    ARMING_TYPE_PART1 = bytes([1])
    ARMING_TYPE_PART2 = bytes([2])
    ARMING_TYPE_PART3 = bytes([3])

    AREA_STATE_DISARMED = 0
    AREA_STATE_INEXIT = 1
    AREA_STATE_INENTRY = 2
    AREA_STATE_ARMED = 3
    AREA_STATE_PARTARMED = 4
    AREA_STATE_INALARM = 5
    AREA_STATE_PARTARMED1 = 6
    AREA_STATE_PARTARMED2 = 8

    zone_types = {}
    zone_types[0] = "Unused"
    zone_types[1] = "Entry/Exit 1"
    zone_types[2] = "Entry/Exit 2"
    zone_types[3] = "Interior"
    zone_types[4] = "Perimeter"
    zone_types[5] = "24hr Audible"
    zone_types[6] = "24hr Silent"
    zone_types[7] = "Audible PA"
    zone_types[8] = "Silent PA"
    zone_types[9] = "Fire Alarm"
    zone_types[10] = "Medical"
    zone_types[11] = "24Hr Gas Alarm"
    zone_types[12] = "Auxiliary Alarm"
    zone_types[13] = "24hr Tamper Alarm"
    zone_types[14] = "Exit Terminator"
    zone_types[15] = "Keyswitch - Momentary"
    zone_types[16] = "Keyswitch - Latching"
    zone_types[17] = "Security Key"
    zone_types[18] = "Omit Key"
    zone_types[19] = "Custom Alarm"
    zone_types[20] = "Confirmed PA Audible"
    zone_types[21] = "Confirmed PA Audible"

    log_event_types = {}
    log_event_types[1] = "Entry/Exit 1"
    log_event_types[2] = "Entry/Exit 2"
    log_event_types[3] = "Interior"
    log_event_types[4] = "Perimeter"
    log_event_types[5] = "24hr Audible"
    log_event_types[6] = "24hr Silent"
    log_event_types[7] = "Audible PA"
    log_event_types[8] = "Silent PA"
    log_event_types[9] = "Fire Alarm"
    log_event_types[10] = "Medical"
    log_event_types[11] = "24Hr Gas Alarm"
    log_event_types[12] = "Auxiliary Alarm"
    log_event_types[13] = "24hr Tamper Alarm"
    log_event_types[14] = "Exit Terminator"
    log_event_types[15] = "Keyswitch - Momentary"
    log_event_types[16] = "Keyswitch - Latching"
    log_event_types[17] = "Security Key"
    log_event_types[18] = "Omit Key"
    log_event_types[19] = "Custom Alarm"
    log_event_types[20] = "Confirmed PA Audible"
    log_event_types[21] = "Confirmed PA Audible"
    log_event_types[22] = "Keypad Medical"
    log_event_types[23] = "Keypad Fire"
    log_event_types[24] = "Keypad Audible PA"
    log_event_types[25] = "Keypad Silent PA"
    log_event_types[26] = "Duress Code Alarm"
    log_event_types[27] = "Alarm Active"
    log_event_types[28] = "Bell Active"
    log_event_types[29] = "Re-arm"
    log_event_types[30] = "Verified Cross Zone Alarm"
    log_event_types[31] = "User Code"
    log_event_types[32] = "Exit Started"
    log_event_types[33] = "Exit Error (Arming Failed)"
    log_event_types[34] = "Entry Started"
    log_event_types[35] = "Part Arm Suite"
    log_event_types[36] = "Armed with Line Fault"
    log_event_types[37] = "Open/Close (Away Armed)"
    log_event_types[38] = "Part Armed"
    log_event_types[39] = "Auto Open/Close"
    log_event_types[40] = "Auto Arm Deferred"
    log_event_types[41] = "Open After Alarm (Alarm Abort)"
    log_event_types[42] = "Remote Open/Close"
    log_event_types[43] = "Quick Arm"
    log_event_types[44] = "Recent Closing"
    log_event_types[45] = "Reset After Alarm"
    log_event_types[46] = "Power O/P Fault"
    log_event_types[47] = "AC Fail"
    log_event_types[48] = "Low Battery"
    log_event_types[49] = "System Power Up"
    log_event_types[50] = "Mains Over Voltage"
    log_event_types[51] = "Telephone Line Fault"
    log_event_types[52] = "Fail to Communicate"
    log_event_types[53] = "Download Start"
    log_event_types[54] = "Download End"
    log_event_types[55] = "Log Capacity Alert (80%)"
    log_event_types[56] = "Date Changed"
    log_event_types[57] = "Time Changed"
    log_event_types[58] = "Installer Programming Start"
    log_event_types[59] = "Installer Programming End"
    log_event_types[60] = "Panel Box Tamper"
    log_event_types[61] = "Bell Tamper"
    log_event_types[62] = "Auxiliary Tamper"
    log_event_types[63] = "Expander Tamper"
    log_event_types[64] = "Keypad Tamper"
    log_event_types[65] = "Expander Trouble (Network error)"
    log_event_types[66] = "Remote Keypad Trouble (Network error)"
    log_event_types[67] = "Fire Zone Tamper"
    log_event_types[68] = "Zone Tamper"
    log_event_types[69] = "Keypad Lockout"
    log_event_types[70] = "Code Tamper Alarm"
    log_event_types[71] = "Soak Test Alarm"
    log_event_types[72] = "Manual Test Transmission"
    log_event_types[73] = "Automatic Test Transmission"
    log_event_types[74] = "User Walk Test Start/End"
    log_event_types[75] = "NVM Defaults Loaded"
    log_event_types[76] = "First Knock"
    log_event_types[77] = "Door Access"
    log_event_types[78] = "Part Arm 1"
    log_event_types[79] = "Part Arm 2"
    log_event_types[80] = "Part Arm 3"
    log_event_types[81] = "Auto Arming Started"
    log_event_types[82] = "Confirmed Alarm"
    log_event_types[83] = "Prox Tag"
    log_event_types[84] = "Access Code Changed/Deleted"
    log_event_types[85] = "Arm Failed"
    log_event_types[86] = "Log Cleared"
    log_event_types[87] = "iD Loop Shorted"
    log_event_types[88] = "Communication Port"
    log_event_types[89] = "TAG System Exit (Batt. OK)"
    log_event_types[90] = "TAG System Exit (Batt. LOW)"
    log_event_types[91] = "TAG System Entry (Batt. OK)"
    log_event_types[92] = "TAG System Entry (Batt. LOW)"
    log_event_types[93] = "Microphone Activated"
    log_event_types[94] = "AV Cleared Down"
    log_event_types[95] = "Monitored Alarm"
    log_event_types[96] = "Expander Low Voltage"
    log_event_types[97] = "Supervision Fault"
    log_event_types[98] = "PA from Remote FOB"
    log_event_types[99] = "RF Device Low Battery"
    log_event_types[100] = "Site Data Changed"
    log_event_types[101] = "Radio Jamming"
    log_event_types[102] = "Test Call Passed"
    log_event_types[103] = "Test Call Failed"
    log_event_types[104] = "Zone Fault"
    log_event_types[105] = "Zone Masked"
    log_event_types[106] = "Faults Overridden"
    log_event_types[107] = "PSU AC Fail"
    log_event_types[108] = "PSU Battery Fail"
    log_event_types[109] = "PSU Low Output Fail"
    log_event_types[110] = "PSU Tamper"
    log_event_types[111] = "Door Access"
    log_event_types[112] = "CIE Reset"
    log_event_types[113] = "Remote Command"
    log_event_types[114] = "User Added"
    log_event_types[115] = "User Deleted"
    log_event_types[116] = "Confirmed PA"
    log_event_types[117] = "User Acknowledged"
    log_event_types[118] = "Power Unit Failure"
    log_event_types[119] = "Battery Charger Fault"
    log_event_types[120] = "Confirmed Intruder"
    log_event_types[121] = "GSM Tamper"
    log_event_types[122] = "Radio Config. Failure"

    log_event_group_type = {}
    log_event_group_type[0] = "Not Reported"
    log_event_group_type[1] = "Priority Alarm"
    log_event_group_type[2] = "Priority Alarm Restore"
    log_event_group_type[3] = "Alarm"
    log_event_group_type[4] = "Restore"
    log_event_group_type[5] = "Open"
    log_event_group_type[6] = "Close"
    log_event_group_type[7] = "Bypassed"
    log_event_group_type[8] = "Unbypassed"
    log_event_group_type[9] = "Maintenance Alarm"
    log_event_group_type[10] = "Maintenance Restore"
    log_event_group_type[11] = "Tamper Alarm"
    log_event_group_type[12] = "Tamper Restore"
    log_event_group_type[13] = "Test Start"
    log_event_group_type[14] = "Test End"
    log_event_group_type[15] = "Disarmed"
    log_event_group_type[16] = "Armed"
    log_event_group_type[17] = "Tested"
    log_event_group_type[18] = "Started"
    log_event_group_type[19] = "Ended"
    log_event_group_type[20] = "Fault"
    log_event_group_type[21] = "Omitted"
    log_event_group_type[22] = "Reinstated"
    log_event_group_type[23] = "Stopped"
    log_event_group_type[24] = "Start"
    log_event_group_type[25] = "Deleted"
    log_event_group_type[26] = "Active"
    log_event_group_type[27] = "Not Used"
    log_event_group_type[28] = "Changed"
    log_event_group_type[29] = "Low Battery"
    log_event_group_type[30] = "Radio"
    log_event_group_type[31] = "Deactivated"
    log_event_group_type[32] = "Added"
    log_event_group_type[33] = "Bad Action"
    log_event_group_type[34] = "PA Timer Reset"
    log_event_group_type[35] = "PA Zone Lockout"
