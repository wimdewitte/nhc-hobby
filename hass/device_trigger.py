import json

class HassDeviceTrigger(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, name):
        uuid = device["Uuid"]
        main_topic = "homeassistant/device_automation/" + uuid
        config_topic = main_topic + "/config"
        payload = {}
        payload["name"] = name
        payload["unique_id"] = uuid
        payload["automation_type"] = "trigger"
        payload["payload"] = "Triggered"
        payload["type"] = "button_short_press"
        payload["topic"] = main_topic + "/trigger"
        self.hass.publish(config_topic, json.dumps(payload))

    def set(self, uuid, payload):
        state = payload.decode('ascii').capitalize()
        self.hobby.devices_control(uuid, "BasicState", state)
