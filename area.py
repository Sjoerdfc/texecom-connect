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


class Area:
    """Information about an area and it's current state"""

    def __init__(self, area_number):
        self.number = area_number
        self.text = "Area{:d}".format(self.number)
        self.state = None
        self.state_text = None
        self.zones = {}

    def save_state(self, area_state):
        """save state and decoded text"""
        self.state = area_state
        self.state_text = [
            "disarmed",
            "in exit",
            "in entry",
            "armed",
            "part arming", # 04, this used to be part armed I think, but in my system it goes from 4 to 6 (partarm1) or 8 (partarm2/3)
            "in alarm", # 05
            "part armed 1", # 06
            "dont know yet", # 07, never seen this state happen yet
            "part armed 2/3", # 08 - when sending ARMING_TYPE_PART2 or ARMING_TYPE_PART3 commands the status byte I receive is 08
        ][self.state]
