#!/usr/bin/env python
#
# Decoder for Texecom Connect API/Protocol
#
# Copyright (C) 2018 Joseph Heenan
# Updates Jul 2020 Charly Anderson
# Updates 2025 Sjoerd
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

    if os.getenv("DEBUG") == "TRUE":
        debug_mode = True
    else:
        debug_mode = False

    log_mqtt_traffic = debug_mode

    @staticmethod
    def on_connect(client, userdata, flags, reason_code, properties):
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
        if paho.topic_matches_sub(topic_root + "/alarm_control_panel/+/command/#", topic):
            topic = topic.split('/')
            areanumber = topic[2]
            if os.getenv("AREA_" + areanumber + "_ENABLED", False) == "TRUE":
                areamap = topic_areamaps[int(areanumber)]
                area_bitmap = bytes.fromhex(areamap)
                if message.payload.decode("utf-8") == "ARM_AWAY": # The Home Assistant command payload text
                    tc.requestArmAreas(area_bitmap)
                elif message.payload.decode("utf-8") == os.getenv("PART_ARM_1", "ARM_NIGHT"): # part arm 1, default = ARM_NIGHT
                    tc.requestPartArm1Areas(area_bitmap)
                elif message.payload.decode("utf-8") == os.getenv("PART_ARM_2", "ARM_HOME"): # part arm 2, default = ARM_HOME
                    tc.requestPartArm2Areas(area_bitmap)
                elif message.payload.decode("utf-8") == os.getenv("PART_ARM_3", "ARM_VACATION"): # part arm 3, default = ARM_VACATION
                    tc.requestPartArm3Areas(area_bitmap)
                elif message.payload.decode("utf-8") == "DISARM":
                    tc.requestDisArmAreas(area_bitmap)
                elif message.payload.decode("utf-8") == "reset":
                    tc.requestResetAreas(area_bitmap)

    @staticmethod
    def zone_details_callback(zone, panelType, numberOfZones):
        HAZoneType =  os.getenv("ZONE_" + str(zone.number) + "_CLASS" , "motion")

        name = str.lower((zone.text).replace(" ", "_"))
        topicbase = topic_root + "/binary_sensor/" + name
        configtopic = topicbase + "/config"
        statetopic = topicbase + "/state"
        message = {
            "name": zone.text,
            "device_class": HAZoneType,
            "state_topic": statetopic,
            "availability_topic": topic_root + "/alarm_control_panel/availability",
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
        if os.getenv("AREA_" + str(area.number) + "_ENABLED", False) == "TRUE":
            number = str(area.number)
            name = str.lower((area.text).replace(" ", "_"))
            topicbase = topic_root + "/alarm_control_panel/" + number
            configtopic = topicbase + "/config"
            statetopic = topicbase + "/state"
            commandtopic = topicbase + "/command"
            message = {
                "name": area.text,
                "state_topic": statetopic,
                "availability_topic": topic_root + "/alarm_control_panel/availability",
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
        if os.getenv("AREA_" + str(area.number) + "_ENABLED", False) == "TRUE":
            area_state_str = [
                "disarmed", # the Home Assistant states for a MQTT Alarm control panel. These must match (in order) the actual states in area.py
                "arming", # in exit
                "disarming", # in entry
                "armed_away",
                "arming", # part arming
                "triggered",
                os.getenv("PART_ARM_1", "ARM_NIGHT"), # part armed 1
                os.getenv("PART_ARM_2", "ARM_HOME"), # part armed 2
                os.getenv("PART_ARM_3", "ARM_VACATION") # part armed 3
            ][area.state]

            #replace the syntax for the part arm stings from the config with the correct syntax home assistant expects for the states
            for old, new in (("ARM_NIGHT", "armed_night"), ("ARM_HOME", "armed_home"), ("ARM_VACATION", "armed_vacation"), ("ARM_CUSTOM_BYPASS", "armed_custom_bypass")):
                area_state_str = area_state_str.replace(old, new)

            topic = (
                topic_root
                + "/alarm_control_panel/"
                + str(area.number)
                + "/state"
            )
            if TexecomMqtt.log_mqtt_traffic:
                print("MQTT Update %s: %s" % (topic, area_state_str))
            client.publish(topic, area_state_str, retain=True)

    @staticmethod
    def login_event():
        available = "online"
        topic = topic_root + "/alarm_control_panel/availability"
        if TexecomMqtt.log_mqtt_traffic:
            print("MQTT Update %s: %s" % (topic, available))
        client.publish(topic, available, retain=True)

    @staticmethod
    def disconnect_event():
        available = "offline"
        topic = topic_root + "/alarm_control_panel/availability"
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

    # the first one is all areas, not used anymore
    topic_areamaps = ["0F000000000000","01000000000000","02000000000000","04000000000000","08000000000000"]

    sys.stdout = Unbuffered(sys.stdout)

    client = paho.Client(paho.CallbackAPIVersion.VERSION2)
    client.username_pw_set(broker_user, broker_pass)
    client.on_message = TexecomMqtt.on_message
    client.on_connect = TexecomMqtt.on_connect
    client.will_set(topic_root + "/alarm_control_panel/availability", "offline")
    print("connecting to broker ", broker_url)
    client.connect(broker_url, broker_port)
    client.loop_start()

    tc = TexecomConnect(texhost, texport, udlpassword, TexecomMqtt.debug_mode)
    tc.enable_output_events(False)
    #tc.on_alive_event(TexecomMqtt.alive_event)
    tc.on_login_event(TexecomMqtt.login_event)
    tc.on_disconnect_event(TexecomMqtt.disconnect_event)
    tc.on_area_event(TexecomMqtt.area_status_event)
    tc.on_zone_event(TexecomMqtt.zone_status_event)
    tc.on_area_details(TexecomMqtt.area_details_callback)
    tc.on_zone_details(TexecomMqtt.zone_details_callback)
    tc.on_log_event(TexecomMqtt.log_event)

    atexit.register(TexecomMqtt.exiting)

    tc.event_loop()
