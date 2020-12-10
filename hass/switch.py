import json
import time

class HassSwitch(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, payload):
        uuid = device["Uuid"]
        main_topic = "homeassistant/switch/" + uuid
        config_topic = main_topic + "/config"
        payload["~"] = main_topic
        self.hass.publish(config_topic, json.dumps(payload))
        time.sleep(0.1)
        self.update(device)
        time.sleep(0.1)
        self.availability(uuid)

    def update(self, device):
        uuid = device["Uuid"]
        properties = device["Properties"]
        status = None
        i = 0
        while i < len(properties):
            _property = list(properties[i].keys())[0]
            _value = list(properties[i].values())[0]
            if _property == "Status" or _property == "BasicState":
                status = _value.upper()
                break
            i += 1
        if status is None:
            return
        topic = "homeassistant/switch/" + uuid + "/state"
        self.hass.publish(topic, status)

    def set(self, uuid, payload):
        state = payload.decode('ascii').capitalize()
        if state == "Triggered":
            self.hobby.devices_control(uuid, "BasicState", state)
        elif state == "On" or state == "Off":
            self.hobby.devices_control(uuid, "Status", state)

    def availability(self, uuid, mode="online"):
        topic = "homeassistant/switch/" + uuid + "/available"
        self.hass.publish(topic, mode, retain=True)


class HassSwitchMood(HassSwitch):
    def discover(self, device, payload):
        payload["payload_off"] = "NA"
        payload["payload_on"] = "Triggered"
        payload["state_off"] = "OFF"
        payload["state_on"] = "ON"
        if device["Model"] == "comfort":
            # NHC mood/scene
            payload["icon"] = "mdi:home-heart"
        if device["Model"] == "overallcomfort":
            # NHC house status actions
            payload["icon"] = "mdi:home-circle"
        if device["Model"] == "alloff":
            # NHC All-off action and All-off with walkway assistance
            payload["icon"] = "mdi:home-export-outline"
        if device["Model"] == "generic":
            # NHC Free Start stop action
            payload["icon"] = "mdi:home-automation"
        if device["Model"] == "pir":
            # NHC motion detection
            payload["icon"] = "mdi:home-account"
        super().discover(device, payload)

