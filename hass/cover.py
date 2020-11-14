import json

class HassCover(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, name):
        uuid = device["Uuid"]
        if device["Model"] == "sunblind":
            _device_class = "awning"
        elif device["Model"] == "gate":
            _device_class = "gate"
        elif device["Model"] == "venetianblind":
            _device_class = "blind"
        else:
            _device_class = ""
        main_topic = "homeassistant/cover/" + uuid
        config_topic = main_topic + "/config"
        payload = {}
        payload["name"] = name
        payload["unique_id"] = uuid
        payload["device_class"] = _device_class
        payload["command_topic"] = main_topic + "/set"
        payload["state_topic"] = main_topic + "/state"
        payload["state_open"] = "OPEN"
        payload["state_opening"] = "OPENING"
        payload["state_closed"] = "CLOSE"
        payload["state_closing"] = "CLOSING"
        self.hass.publish(config_topic, json.dumps(payload))
        self.update(uuid, device["Properties"])

    def update(self, uuid, properties):
        state = None
        moving = None
        i = 0
        while i < len(properties):
            _property = list(properties[i].keys())[0]
            _value = list(properties[i].values())[0]
            if _property == "Action":
                state = _value.upper()
            elif _property == "Moving":
                moving = _value.upper()
            i += 1
        if moving is not None:
            if state == "OPEN" and moving:
                state = "CLOSING"
            if state == "CLOSE" and moving:
                state = "OPENING"
        if state is None:
            return
        topic = "homeassistant/cover/" + uuid + "/state"
        self.hass.publish(topic, state)

    def set(self, uuid, payload):
        state = payload.decode('ascii').capitalize()
        self.hobby.devices_control(uuid, "Action", state)
