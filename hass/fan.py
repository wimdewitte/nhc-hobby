import json

class HassFan(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, payload):
        uuid = device["Uuid"]
        main_topic = "homeassistant/fan/" + uuid
        config_topic = main_topic + "/config"
        payload["~"] = main_topic
        self.hass.publish(config_topic, json.dumps(payload))
        self.update(uuid, device["Properties"])

    def update(self, uuid, properties):
        status = None
        i = 0
        while i < len(properties):
            _property = list(properties[i].keys())[0]
            _value = list(properties[i].values())[0]
            if _property == "Status":
                status = _value.upper()
                break
            i += 1
        if status is None:
            return
        topic = "homeassistant/fan/" + uuid + "/state"
        self.hass.publish(topic, status)

    def set(self, uuid, payload):
        state = payload.decode('ascii').capitalize()
        self.hobby.devices_control(uuid, "Status", state)
