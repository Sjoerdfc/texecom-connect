# Texecom Connect Protocol Python

## Introduction

This is a python module that implements decoding of the Texecom Connect protocol. 

Original work was done by Joseph Heenan, Charly Anderson, davidMbrooke, mpredfearn and lodesmets. I added small stuff to make it work how I want it with my Texecom Premier Elite 24 (fw V6.05.03LS1) and Home Assistant.

I changed the Night Arm in Home Assistant to Part Arm 1, and Home Arm to Part Arm 2. Part Arm 3 seems to have the same status byte as 2, so that doesn't work yet.

## Requirements

This module connects over TCP to the alarm panel, so a ComIP or SmartCom is needed.

The ComIP/SmartCom only allow one TCP connection to be made to them, so you will need to dedicate one to this purpose. Whilst this program is running, the SmartCom/ComIP will not be able to send out events to notification centers or to the texecom applications - I believe except for when an alarm occurs, in which case the connection to this program will be forcibly dropped by the panel. 

Your alarm panel must be a Premier Elite panel running firmware version 4.0 or higher.

You need to set a UDL password for your panel. If you don't have a UDL password and do not have the engineer code you will not be able to use this code.

## Using it

Install python and run alarm-monitor.py manually. The configuration options are in this file.

Or use this docker-compose file:

```yaml
services:
  texecom-connect:
    container_name: texecom-connect
    image: sjoerdfc/texecom-connect
    restart: unless-stopped
    environment:
      - TEXHOST=10.0.0.20
      - TEXTPORT=10001
      - UDLPASSWORD=1234
      - BROKER_URL=10.0.0.10
      - BROKER_USER=user
      - BROKER_PASS=pass
      - MQTT_ROOT_TOPIC=homeassistant
      - MQTT_AREAS=all,ground_floor,upstairs,outside,shed
      - MQTT_AREAMAPS=0F000000000000,01000000000000,02000000000000,04000000000000,08000000000000
      # What state Part Arm 1/2/3 should have in Home Assistant. Available states:
      # ARM_HOME, ARM_NIGHT, ARM_VACATION, ARM_CUSTOM_BYPASS. (ARM_AWAY is used for Full Arm)
      - PART_ARM_1=ARM_NIGHT
      - PART_ARM_2=ARM_HOME
      - PART_ARM_3=ARM_VACATION
      # Set the device class in Home Assistant of all the zones
      - ZONE_1_CLASS=door
      - ZONE_2_CLASS=door
      - ZONE_3_CLASS=motion
      # etc..
```

## License

Copyright (C) 2018 Joseph Heenan

Licensed under the Apache License, Version 2.0;
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
documentation.

