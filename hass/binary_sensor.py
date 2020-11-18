import json

class HassBinarySensor(object):
    def __init__(self, logger, hass, hobby):
        self.logger = logger
        self.hass = hass
        self.hobby = hobby

    def discover(self, device, payload):
        uuid = device["Uuid"]
        main_topic = "homeassistant/binary_sensor/" + uuid
        config_topic = main_topic + "/config"
        payload["~"] = main_topic
        payload["off_delay"] = 10
        del(payload["command_topic"]) # a binary_sensor doesn't have a command topic
        self.hass.publish(config_topic, json.dumps(payload))
        self.availability(uuid)

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
        topic = "homeassistant/binary_sensor/" + uuid + "/state"
        self.hass.publish(topic, status)

    def set(self, uuid, payload):
        pass # a binary_sensor doesn't have a command topic

    def availability(self, uuid, mode="online"):
        topic = "homeassistant/binary_sensor/" + uuid + "/available"
        self.hass.publish(topic, mode, retain=True)
