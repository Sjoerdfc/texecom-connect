# Texecom Connect for Home Assistant

## Introduction

This is a python module that connects Texecom Alarm systems to Home Assistant with MQTT.

Original work was done by Joseph Heenan, Charly Anderson, davidMbrooke, mpredfearn and lodesmets. I added small stuff to make it work how I want it with my Texecom Premier Elite 24 (fw V6.05.03LS1) and Home Assistant.

- Arming and disarming should work.
- Part Arm 1, 2 and 3 should all work, and it can be configured what state they should be in Home Assistant in the docker compose config.
- The alarm control panel and zones (binary sensors) should now become unavailable in Home Assistant when the software is not running/crashed/disconnected.
- The device classes in Home Assistant can be configured for all zones in the docker compose config.
- Area configuration is easier than before.

## Requirements

You need a MQTT broker to connect to Home Assistant.

This module connects over TCP to the alarm panel, so a ComIP or SmartCom is needed.

The ComIP/SmartCom only allow one TCP connection to be made to them, so you will need to dedicate one to this purpose. Whilst this program is running, the SmartCom/ComIP will not be able to send out events to notification centers or to the texecom applications - I believe except for when an alarm occurs, in which case the connection to this program will be forcibly dropped by the panel. 

Your alarm panel must be a Premier Elite panel running firmware version 4.0 or higher.

You need to set a UDL password for your panel. If you don't have a UDL password and do not have the engineer code you will not be able to use this code.

## Using it

- Install as a Home Assistant addon. In your Home Assistant, open the Add-On Store, and add `https://github.com/Sjoerdfc/texecom-connect` as a repository in the top right.

- Install python and run alarm-monitor.py manually. The configuration options are in this file.

- Or use this docker-compose file:

```yaml
services:
  texecom-connect:
    container_name: texecom-connect
    image: sjoerdfc/texecom-connect
    restart: unless-stopped
    environment:
      - TEXHOST=10.0.0.20
      - TEXPORT=10001
      - UDLPASSWORD=1234
      - BROKER_URL=10.0.0.10
      - BROKER_USER=user
      - BROKER_PASS=pass
      - MQTT_ROOT_TOPIC=homeassistant
      - AREA_1_ENABLED=TRUE
      - AREA_2_ENABLED=FALSE
      - AREA_3_ENABLED=FALSE
      - AREA_4_ENABLED=FALSE
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

