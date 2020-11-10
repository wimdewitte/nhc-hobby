import json

class HassSwitch(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, name):
        uuid = device["Uuid"]
        main_topic = "homeassistant/switch/" + uuid
        config_topic = main_topic + "/config"
        payload = {}
        payload["name"] = name
        payload["unique_id"] = uuid
        payload["command_topic"] = main_topic + "/set"
        payload["state_topic"] = main_topic + "/state"
        self.hass.publish(config_topic, json.dumps(payload))
        self.update(uuid, device["Properties"])

    def update(self, uuid, properties):
        status = properties[0]["Status"].upper()
        topic = "homeassistant/switch/" + uuid + "/state"
        self.hass.publish(topic, status)

    def set(self, uuid, payload):
        state = payload.decode('ascii').capitalize()
        self.hobby.devices_control(uuid, "Status", state)
