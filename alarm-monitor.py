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


import os
import sys
import json
import atexit

from texecomConnect import TexecomConnect

import paho.mqtt.client as paho


class TexecomMqtt:

    log_mqtt_traffic = False

    @staticmethod
    def on_connect(client, userdata, flags, rc):
        if len(topic_subs[0]) > 0:
            client.subscribe(topic_root + "/alarm_control_panel/+/command/#")

    @staticmethod
    def on_message(client, userdata, message):
        # Arm/Disarm/Reset
        # To give a level of security its advisable to limit access to the subscribe topic on the mqtt broker
        topic = message.topic
        if TexecomMqtt.log_mqtt_traffic:
            print(
                "topic: " + topic + " received message =",
                str(message.payload.decode("utf-8")),
            )
        topicbase = topic_root + "/alarm_control_panel/"
        if len(topic) > len(topicbase):
            idx = topic.find("/", len(topicbase))
            if idx >= 0:
                subtopic = topic[len(topicbase) : idx]
                if subtopic in topic_subs:
                    subtopicIdx = topic_subs.index(subtopic)
                    if len(topic_areamaps) >= subtopicIdx:
                        areamap = topic_areamaps[subtopicIdx]
                        area_bitmap = bytes.fromhex(areamap)
                        if message.payload.decode("utf-8") == "ARM_AWAY": # The Home Assistant command payload text
                            tc.requestArmAreas(area_bitmap)
                        elif message.payload.decode("utf-8") == "ARM_NIGHT": # part arm 1 (rearrange the payload texts to change the part arm 1/2/3 types in Home Assistant)
                            tc.requestPartArm1Areas(area_bitmap)
                        elif message.payload.decode("utf-8") == "ARM_HOME": # part arm 2
                            tc.requestPartArm2Areas(area_bitmap)
                        elif message.payload.decode("utf-8") == "ARM_VACATION": # part arm 3
                            tc.requestPartArm3Areas(area_bitmap)
                        elif message.payload.decode("utf-8") == "DISARM":
                            tc.requestDisArmAreas(area_bitmap)
                        elif message.payload.decode("utf-8") == "reset":
                            tc.requestResetAreas(area_bitmap)

    @staticmethod
    def zone_details_callback(zone, panelType, numberOfZones):
        if zone.zoneType == 1:
            HAZoneType = "door"
        elif zone.zoneType == 8:
            HAZoneType = "safety"
        else:
            HAZoneType = "motion"
        name = str.lower((zone.text).replace(" ", "_"))
        topicbase = topic_root + "/binary_sensor/" + name
        configtopic = topicbase + "/config"
        statetopic = topicbase + "/state"
        message = {
            "name": name,
            "device_class": HAZoneType,
            "state_topic": statetopic,
            "payload_on": "True",
            "payload_off": "False",
            "unique_id": ".".join([panelType, name]),
            "device": {
                "name": "Texecom " + panelType + " " + str(numberOfZones),
                "identifiers": "123456789",  # TODO panel serial number?
                "manufacturer": "Texecom",
                "model": panelType + " " + str(numberOfZones)
            }
        }
        if TexecomMqtt.log_mqtt_traffic:
            print("MQTT Update %s: %s" % (configtopic, json.dumps(message)))
        client.publish(configtopic, json.dumps(message), retain=True)
        return zone

    @staticmethod
    def area_details_callback(area, panelType, numberOfZones):
        name = str.lower((area.text).replace(" ", "_"))
        topicbase = topic_root + "/alarm_control_panel/" + name
        configtopic = topicbase + "/config"
        statetopic = topicbase + "/state"
        commandtopic = topicbase + "/command"
        message = {
            "name": name,
            "state_topic": statetopic,
            "command_topic": commandtopic,
            "unique_id": ".".join([panelType, "area", name]),
            "code_arm_required": "false",
            "code_disarm_required ": "false",
            "device": {
                "name": "Texecom " + panelType + " " + str(numberOfZones),
                "identifiers": "123456789",  # TODO panel serial number?
                "manufacturer": "Texecom",
                "model": panelType + " " + str(numberOfZones)
            }
        }
        if TexecomMqtt.log_mqtt_traffic:
            print("MQTT Update %s: %s" % (configtopic, json.dumps(message)))
        client.publish(configtopic, json.dumps(message), retain=True)
        return area

    @staticmethod
    def zone_status_event(zone):
        topic = (
            topic_root
            + "/binary_sensor/"
            + str.lower((zone.text).replace(" ", "_"))
            + "/state"
        )
        if TexecomMqtt.log_mqtt_traffic:
            print("MQTT Update %s: %s" % (topic, zone.active))
        client.publish(topic, zone.active, retain=True)

    @staticmethod
    def area_status_event(area):
        area_state_str = [
            "disarmed", # the Home Assistant states for a MQTT Alarm control panel. These must match (in order) the actual states in area.py
            "arming", # in exit
            "disarming", # in entry
            "armed_away",
            "arming", # part arming
            "triggered",
            "armed_night", # part armed 1
            "pending", # unknown state, see area.py
            "armed_vacation" # part armed 3
        ][area.state]
        topic = (
            topic_root
            + "/alarm_control_panel/"
            + str.lower((area.text).replace(" ", "_"))
            + "/state"
        )
        if TexecomMqtt.log_mqtt_traffic:
            print("MQTT Update %s: %s" % (topic, area_state_str))
        client.publish(topic, area_state_str, retain=True)

    @staticmethod
    def alive_event():
        available = "online"
        topic = topic_root + "/alarm_control_panel/state"
        if TexecomMqtt.log_mqtt_traffic:
            print("MQTT Update %s: %s" % (topic, available))
        client.publish(topic, available, retain=True)

    @staticmethod
    def log_event(message):
        topic = topic_root + "/alarm_control_panel/log"
        if TexecomMqtt.log_mqtt_traffic:
            print("MQTT Update %s: %s" % (topic, message))
        client.publish(topic, message)

    @staticmethod
    def exiting():
        print("exiting")
        TexecomMqtt.log_event("Exiting alarm-monitor.")


# disable buffering to stdout when it's redirected to a file/pipe
# This makes sure any events appear immediately in the file/pipe,
# instead of being queued until there is a full buffer's worth.


class Unbuffered:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()

    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()

    def __getattr__(self, attr):
        return getattr(self.stream, attr)


if __name__ == "__main__":
    # Texecom config
    texhost = os.getenv("TEXHOST", "192.168.1.9")
    texport = os.getenv("TEXPORT", 10001)
    # This is the default UDL password for a factory panel. For any real
    # installation, use wintex to set the UDL password in the panel to a
    # random 16 character alphanumeric string.
    udlpassword = os.getenv("UDLPASSWORD", "1234")
    # MQTT config
    broker_url = os.getenv("BROKER_URL", "192.168.1.1")
    broker_port = os.getenv("BROKER_PORT", 1883)
    broker_user = os.getenv("BROKER_USER", None)
    broker_pass = os.getenv("BROKER_PASS", None)
    topic_root = os.getenv("MQTT_ROOT_TOPIC", "homeassistant")
    # This is the name of your Areas for arm/disarm via mqtt. They are mapped onto the equivlent areamap.
    # example of MQTT_AREAS and MQTT_AREAMAPS below defines (in order) Area1-4 ('all'), Area1('ground_floor'), Area2('upstairs'), Area3('outside'), Area4('shed')
    topic_subs = os.getenv(
        "MQTT_AREAS", "all,ground_floor,upstairs,outside,shed"
    ).split(",")
    topic_areamaps = os.getenv(
        "MQTT_AREAMAPS",
        "0F000000000000,01000000000000,02000000000000,04000000000000,08000000000000",
    ).split(",")

    sys.stdout = Unbuffered(sys.stdout)

    client = paho.Client()
    client.username_pw_set(broker_user, broker_pass)
    client.on_message = TexecomMqtt.on_message
    client.on_connect = TexecomMqtt.on_connect
    client.will_set(topic_root + "/alarm_control_panel/state", "offline")
    print("connecting to broker ", broker_url)
    client.connect(broker_url, broker_port)
    client.loop_start()

    tc = TexecomConnect(texhost, texport, udlpassword)
    tc.enable_output_events(False)
    tc.on_alive_event(TexecomMqtt.alive_event)
    tc.on_area_event(TexecomMqtt.area_status_event)
    tc.on_zone_event(TexecomMqtt.zone_status_event)
    tc.on_area_details(TexecomMqtt.area_details_callback)
    tc.on_zone_details(TexecomMqtt.zone_details_callback)
    tc.on_log_event(TexecomMqtt.log_event)

    atexit.register(TexecomMqtt.exiting)

    tc.event_loop()
