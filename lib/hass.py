import paho.mqtt.client as mqtt
import threading
import json
import logging
import socket
from lib.hobby_api import NHC_MODELS

TOPIC_HA_SUBSCRIBE = "homeassistant/+/+/set"



class Hass(object):
    def __init__(self, logger, hobby=None, host=None, port=1883, connect_timeout=60):
        self.logger = logger
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.hobby = hobby
        self.connected = False
        self.client = None
        if self.hobby is None:
            return
        if self.host is None:
            self.host = "homeassistant.local"
    
    def _connect_timeout_handler(self):
        if self.connected:
            return
        self.logger.info("Cannot connect to mesh broker")
        self.connected = False
        self.client.disconnect()

    def is_connected(self):
        return self.connected

    def start(self):
        if self.host is None:
            return False
        try:
            self.host = socket.gethostbyname(self.host)
        except:
            self.logger.fatal("%s not discovered", self.host)
            return False
        self.logger.info("discovered homeassistant with IP=%s", self.host)

        self.client = mqtt.Client()
        self.client.on_message = self.message
        self.client.on_connect = self.connect
        self.client.on_disconnect = self.disconnect
        self.client.connect_async(self.host, self.port)
        self.connect_timer = threading.Timer(self.connect_timeout, self._connect_timeout_handler)
        self.connect_timer.start()
        self.client.loop_start()

    def stop(self):
        self.connected = False
        self.client.disconnect()
    
    def message(self, client, obj, msg):
        if msg.topic.endswith("set"):
            self.hass_has_set(client, msg)
        else:
            self.logger.info("mesh mqtt message '%s' on topic: %s", msg.payload, msg.topic)

    def connect(self, client, obj, flags, rc):
        self.connected = True
        self.connect_timer.cancel()
        self.logger.info("Connected to mesh broker. rc:%d", rc)
        self.client.subscribe(TOPIC_HA_SUBSCRIBE, 0)

    def disconnect(self, client, userdata, rc):
        self.logger.warning("Disconnected from mesh broker")
        self.connected = False
        self.connect_timer.cancel()

    def hass_has_set(self, client, msg):
        topic_split = msg.topic.split("/")
        hass_type = topic_split[1]
        uuid = topic_split[2]
        if hass_type == "light":
            frame = json.loads(msg.payload)
            state = frame["state"].capitalize()
            try:
                brightness = frame["brightness"]
                brightness = int(brightness/2.55)
            except:
                brightness = None
            self.hobby.devices_control(uuid, "Status", state, "Brightness", brightness)
        elif hass_type == "switch":
            state = msg.payload.decode('ascii').capitalize()
            self.hobby.devices_control(uuid, "Status", state)
        pass

    def nhc_to_hass_model(self, nhc_model):
        if nhc_model in ["light", "dimmer"]:
            return "light"
        elif nhc_model in ["rolldownshutter", "sunblind", "gate", "venetianblind"]:
            return "cover"
        elif nhc_model == "switched-fan":
            return "fan"
        elif nhc_model in ["socket", "switched-generic"]:
            return "switch"
        elif nhc_model in ["pir", "alarms"]:
            return "binary_sensor"
        elif nhc_model in ["comfort", "condition", "alloff", "generic", "timeschedule"]:
            self.logger.info("NHC model '%s' not supported in Hass", nhc_model)
            return None

    def discover_light(self, device, name):
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
        self.client.publish(config_topic, json.dumps(payload))
        self.update_light(uuid, device["Properties"])

    def update_light(self, uuid, properties):
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

        self.client.publish(topic, json.dumps(frame))

    def discover_switch(self, device, name):
        uuid = device["Uuid"]
        main_topic = "homeassistant/switch/" + uuid
        config_topic = main_topic + "/config"
        payload = {}
        payload["name"] = name
        payload["unique_id"] = uuid
        payload["command_topic"] = main_topic + "/set"
        payload["state_topic"] = main_topic + "/state"
        self.client.publish(config_topic, json.dumps(payload))
        self.update_switch(uuid, device["Properties"])

    def update_switch(self, uuid, properties):
        status = properties[0]["Status"].upper()
        topic = "homeassistant/switch/" + uuid + "/state"
        self.client.publish(topic, status)

    def discover(self, uuid, remove=False):
        exist = self.hobby.search_uuid_action(uuid, NHC_MODELS.ALL)
        if exist is None:
            # todo error reason
            return False
        
        device = self.hobby.get_device(uuid)
        location = device["Parameters"][0]["LocationName"]
        hass_name = device["Name"]
        if hass_name.find(location) == -1:
            hass_name = hass_name + " " + location
        hass_model = self.nhc_to_hass_model(device["Model"])
        if hass_model is None:
            return False
        if remove:
            topic = "homeassistant/" + hass_model + "/" + uuid + "/config"
            self.client.publish(topic, '')
            return True

        if hass_model == "light":
            self.discover_light(device, hass_name)
        elif hass_model == "switch":
            self.discover_switch(device, hass_name)

        pass

    def nhc_status_update(self, device, frame):
        hass_model = self.nhc_to_hass_model(device["Model"])
        if hass_model is None:
            return
        uuid = device["Uuid"]
        if hass_model == "light":
            self.update_light(uuid, frame["Properties"])
        if hass_model == "switch":
            self.update_switch(uuid, frame["Properties"])
