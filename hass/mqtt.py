import paho.mqtt.client as mqtt
import threading
import json
import logging
import socket
from nhc.hobby_api import NHC_MODELS
from hass.light import HassLight
from hass.switch import HassSwitch
from hass.cover import HassCover
from hass.fan import HassFan
from hass.binary_sensor import HassBinarySensor

TOPIC_HA_SET = "homeassistant/+/+/set"
TOPIC_HA_STATUS = "homeassistant/status"


class Hass(object):
    def __init__(self, logger, hobby=None, host=None, port=1883, connect_timeout=60):
        self.logger = logger
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.hobby = hobby
        self.connected = False
        self.client = None
        self.hass_online = True # assume online because no method to poll
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
        self.logger.info("HASS mqtt message topic:%s\n%s", msg.topic, json.loads(msg.payload))
        if msg.topic == TOPIC_HA_STATUS:
            self.hass_status(msg.payload)
        elif msg.topic.endswith("set"):
            self.hass_set(client, msg)
        else:
            self.logger.info("mesh mqtt message '%s' on topic: %s", msg.payload, msg.topic)


    def connect(self, client, obj, flags, rc):
        self.connected = True
        self.connect_timer.cancel()
        self.logger.info("Connected to mesh broker. rc:%d", rc)
        self.light = HassLight(self.logger, self.client, self.hobby)
        self.switch = HassSwitch(self.logger, self.client, self.hobby)
        self.cover = HassCover(self.logger, self.client, self.hobby)
        self.fan = HassFan(self.logger, self.client, self.hobby)
        self.binary_sensor = HassBinarySensor(self.logger, self.client, self.hobby)
        self.client.subscribe(TOPIC_HA_SET, 0)
        self.client.subscribe(TOPIC_HA_STATUS, 0)


    def disconnect(self, client, userdata, rc):
        self.logger.warning("Disconnected from mesh broker")
        self.connected = False
        self.connect_timer.cancel()


    def hass_status(self, payload):
        if payload == "online":
            self.hass_online = True
            self.logger.warning("Home Assistant online")
            # pass all nhc states towards hass
        elif payload == "offline":
            self.logger.warning("Home Assistant offline")
            self.hass_online = False
        pass


    def hass_set(self, client, msg):
        topic_split = msg.topic.split("/")
        hass_type = topic_split[1]
        uuid = topic_split[2]
        if hass_type == "light":
            self.light.set(uuid, msg.payload)
        elif hass_type == "switch":
            self.switch.set(uuid, msg.payload)
        elif hass_type == "cover":
            self.cover.set(uuid, msg.payload)
        elif hass_type == "fan":
            self.fan.set(uuid, msg.payload)
        elif hass_type == "binary_sensor":
            self.binary_sensor.set(uuid, msg.payload)


    def nhc_to_hass_model(self, nhc_model):
        if nhc_model in ["light", "dimmer"]:
            return "light"
        elif nhc_model in ["rolldownshutter", "sunblind", "gate", "venetianblind"]:
            return "cover"
        elif nhc_model == "switched-fan":
            return "fan"
        elif nhc_model in ["socket", "switched-generic"]:
            return "switch"
        elif nhc_model in ["comfort", "alloff", "generic"]:
            return "binary_sensor"
        elif nhc_model in ["pir", "alarms", "condition", "timeschedule"]:
            self.logger.info("NHC model '%s' not supported in Hass", nhc_model)
            return None


    def discover(self, uuid, remove=False):
        exist = self.hobby.search_uuid_action(uuid, NHC_MODELS.ALL)
        if exist is None:
            self.logger.info("uuid not found")
            return False
        device = self.hobby.get_device(uuid)
        if remove:
            self.nhc_remove_device(uuid, device["Model"])
        else:
            self.nhc_add_device(device)


    def nhc_status_update(self, device, frame):
        hass_model = self.nhc_to_hass_model(device["Model"])
        if hass_model is None:
            return
        uuid = device["Uuid"]
        if hass_model == "light":
            self.light.update(uuid, frame["Properties"])
        elif hass_model == "switch":
            self.switch.update(uuid, frame["Properties"])
        elif hass_model == "cover":
            self.cover.update(uuid, frame["Properties"])
        elif hass_model == "fan":
            self.fan.update(uuid, frame["Properties"])


    def nhc_remove_device(self, uuid, model):
        hass_model = self.nhc_to_hass_model(model)
        topic = "homeassistant/" + hass_model + "/" + uuid + "/config"
        self.client.publish(topic, '')


    def discover_frame(self, device):
        location = device["Parameters"][0]["LocationName"]
        _hass_name = device["Name"]
        if _hass_name.find(location) == -1:
            _hass_name = _hass_name + " " + location
        _gateway_info = self.hobby.nhc_info()
        frame_device = {}
        frame_device["name"] = "NHC"
        frame_device["identifiers"] = [_gateway_info["gateway_name"]]
        frame_device["manufacturer"] = "Niko"
        frame_device["model"] = _gateway_info["hubtype"]
        frame_device["sw_version"] = _gateway_info["firmware"]
        frame = {}
        frame["name"] = _hass_name
        frame["unique_id"] = device["Uuid"]
        frame["retain"] = True
        frame["device"] = frame_device
        frame["command_topic"] = "~/set"
        frame["state_topic"] = "~/state"
        return frame


    def nhc_add_device(self, device):
        hass_model = self.nhc_to_hass_model(device["Model"])
        if hass_model is None:
            return False
        _base_frame = self.discover_frame(device)
        if hass_model == "light":
            self.light.discover(device, _base_frame)
        elif hass_model == "switch":
            self.switch.discover(device, _base_frame)
        elif hass_model == "cover":
            self.cover.discover(device, _base_frame)
        elif hass_model == "fan":
            self.fan.discover(device, _base_frame)
        elif hass_model == "binary_sensor":
            self.binary_sensor.discover(device, _base_frame)
