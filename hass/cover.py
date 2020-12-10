import json
import time

class HassCover(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, payload):
        uuid = device["Uuid"]
        if device["Model"] == "sunblind":
            _device_class = "awning"
        elif device["Model"] == "gate":
            _device_class = "gate"
        elif device["Model"] == "venetianblind":
            _device_class = "blind"
        else:
            _device_class = "shutter"
        main_topic = "homeassistant/cover/" + uuid
        config_topic = main_topic + "/config"
        payload["~"] = main_topic
        payload["device_class"] = _device_class
        payload["state_open"] = "OPEN"
        payload["state_opening"] = "OPENING"
        payload["state_closed"] = "CLOSE"
        payload["state_closing"] = "CLOSING"
        self.hass.publish(config_topic, json.dumps(payload))
        time.sleep(0.1)
        self.update(device)
        time.sleep(0.1)
        self.availability(uuid)

    def update(self, device):
        uuid = device["Uuid"]
        properties = device["Properties"]
        state = ""
        moving = ""
        position = ""
        i = 0
        while i < len(properties):
            _property = list(properties[i].keys())[0]
            _value = list(properties[i].values())[0]
            if _property == "Action":
                state = _value.upper()
            elif _property == "Moving":
                moving = _value.upper()
            elif _property == "Position":
                position = _value.upper()
            i += 1
        if moving == "TRUE":
            if state == "OPEN" or position == "100":
                state = "CLOSING"
            elif state == "CLOSE" or position == "0":
                state = "OPENING"
        elif moving == "FALSE":
            if position == "0":
                state = "CLOSE"
            elif position == "100":
                state = "OPEN"

        if state == "":
            return
        topic = "homeassistant/cover/" + uuid + "/state"
        self.hass.publish(topic, state)

    def set(self, uuid, payload):
        state = payload.decode('ascii').capitalize()
        self.hobby.devices_control(uuid, "Action", state)

    def availability(self, uuid, mode="online"):
        topic = "homeassistant/cover/" + uuid + "/available"
        self.hass.publish(topic, mode, retain=True)
