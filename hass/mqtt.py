import paho.mqtt.client as mqtt
import threading
import json
import logging
import socket
from lib.hobby_api import NHC_MODELS
from hass.light import HassLight
from hass.switch import HassSwitch

TOPIC_HA_SET = "homeassistant/+/+/set"
TOPIC_HA_START = "homeassistant/start"
TOPIC_HA_STOP = "homeassistant/stop"


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
        if msg.topic == TOPIC_HA_START:
            self.hass_start()
        elif msg.topic == TOPIC_HA_START:
            self.hass_stop()
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
        self.client.subscribe(TOPIC_HA_SET, 0)
        self.client.subscribe(TOPIC_HA_START, 0)
        self.client.subscribe(TOPIC_HA_STOP, 0)


    def disconnect(self, client, userdata, rc):
        self.logger.warning("Disconnected from mesh broker")
        self.connected = False
        self.connect_timer.cancel()


    def hass_start(self):
        self.hass_online = True
        # pass all nhc states towards hass
        pass

    def hass_stop(self):
        self.hass_online = False
        # do nothing
        pass

    def hass_set(self, client, msg):
        topic_split = msg.topic.split("/")
        hass_type = topic_split[1]
        uuid = topic_split[2]
        if hass_type == "light":
            self.light.set(uuid, msg.payload)
        elif hass_type == "switch":
            self.switch.set(uuid, msg.payload)


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


    def discover(self, uuid, remove=False):
        exist = self.hobby.search_uuid_action(uuid, NHC_MODELS.ALL)
        if exist is None:
            self.logger.info("uuid not found")
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
            self.light.discover(device, hass_name)
        elif hass_model == "switch":
            self.switch.discover(device, hass_name)


    def nhc_status_update(self, device, frame):
        hass_model = self.nhc_to_hass_model(device["Model"])
        if hass_model is None:
            return
        uuid = device["Uuid"]
        if hass_model == "light":
            self.light.update(uuid, frame["Properties"])
        if hass_model == "switch":
            self.switch.update(uuid, frame["Properties"])
