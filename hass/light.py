import json

class HassLight(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, name):
        uuid = device["Uuid"]
        main_topic = "homeassistant/light/" + uuid
        config_topic = main_topic + "/config"
        payload = {}
        payload["name"] = name
        payload["unique_id"] = uuid
        payload["command_topic"] = main_topic + "/set"
        payload["state_topic"] = main_topic + "/state"
        payload["schema"] = "json"
        if device["Model"] == "dimmer":
            payload["brightness"] = True
        else:
            payload["brightness"] = False
        self.hass.publish(config_topic, json.dumps(payload))
        self.update(uuid, device["Properties"])

    def update(self, uuid, properties):
        status = None
        brightness = None
        i = 0
        while i < len(properties):
            _property = list(properties[i].keys())[0]
            _value = list(properties[i].values())[0]
            if _property == "Status":
                status = _value.upper()
            elif _property == "Brightness":
                brightness = int(_value)
            i += 1
        topic = "homeassistant/light/" + uuid + "/state"
        frame = {}
        frame["state"] = status
        if brightness is not None:
            frame["brightness"] = int(brightness * 2.55)

        self.hass.publish(topic, json.dumps(frame))

    def set(self, uuid, payload):
        frame = json.loads(payload)
        state = frame["state"].capitalize()
        try:
            brightness = frame["brightness"]
            brightness = int(brightness/2.55)
        except:
            brightness = None
        self.hobby.devices_control(uuid, "Status", state, "Brightness", brightness)
