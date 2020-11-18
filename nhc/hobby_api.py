import os
import paho.mqtt.client as mqtt
from nhc.discover import discoverNHC
import threading
import json
import logging
import struct
from prettytable import PrettyTable
from uuid import UUID
import yaml


TOPIC_DEVICES_CMD = "hobby/control/devices/cmd"
TOPIC_DEVICES_RSP = "hobby/control/devices/rsp"
TOPIC_DEVICES_ERR = "hobby/control/devices/err"
TOPIC_DEVICES_EVT = "hobby/control/devices/evt"

TOPIC_LOCATIONS_CMD = "hobby/control/locations/cmd"
TOPIC_LOCATIONS_RSP = "hobby/control/locations/rsp"
TOPIC_LOCATION_ERR = "hobby/control/location/err"

TOPIC_SYSTEM_CMD = "hobby/system/cmd"
TOPIC_SYSTEM_RSP = "hobby/system/rsp"
TOPIC_SYSTEM_ERR = "hobby/system/err"
TOPIC_SYSTEM_EVT = "hobby/system/evt"
TOPIC_SYSTEM_TIME_RSP = "hobby/control/time/rsp"

TOPIC_NOTIFICATION_CMD = "hobby/notification/cmd"
TOPIC_NOTIFICATION_RSP = "hobby/notification/rsp"
TOPIC_NOTIFICATION_ERR = "hobby/notification/err"
TOPIC_NOTIFICATION_EVT = "hobby/notification/evt"

class NHC_MODELS():
    ALL = 0
    RELAY = 1
    DIMMER = 2
    MOTOR = 3
    MOOD = 4


class controlNHC(object):
    def __init__(self, hobby):
        self.hobby = hobby

    def mood(self, device):
        if self.hobby.search_uuid_action(device, NHC_MODELS.MOOD) is None:
            return
        self.hobby.devices_control(device, "BasicState", "Triggered")

    def relay(self, device, status):
        if self.hobby.search_uuid_action(device, NHC_MODELS.RELAY) is None:
            return
        self.hobby.devices_control(device, "Status", status)

    def dimmer(self, device, status, brightness):
        if self.hobby.search_uuid_action(device, NHC_MODELS.DIMMER) is None:
            return
        self.hobby.devices_control(device, "Status", status, "Brightness", str(brightness))

    def motor(self, device, action, position):
        if self.hobby.search_uuid_action(device, NHC_MODELS.MOTOR) is None:
            return
        self.hobby.devices_control(
            device, "Action", action, "Position", str(position))


class hobbyAPI(object):
    def __init__(self, logger, configfile=None):
        self.logger = logger
        self.configfile = configfile
        self.discover = discoverNHC(self.logger)
        self.host = self.discover.discover()
        self.port = 8884
        self.connect_timeout = 60
        self.connected = False
        self.client = None
        self.systeminfo = None
        self.devices = None
        self.locations = None
        self.device_update_callback = None
        self.device_remove_callback = None
        self.device_add_callback = None
        self.nhc_models = ["relay", "dimmer", "motor", "mood"]
        self.relay_models = ["light", "socket", "switched-fan", "switched-generic"]
        self.dimmer_models = ["dimmer"]
        self.motor_models = ["rolldownshutter", "sunblind", "gate", "venetianblind"]
        self.mood_models = ["comfort", "alloff", "generic"]
        self.read_config()


    def read_config(self):
        if self.configfile is None:
            self.logger.fatal("No configfile specified")
            return
        if not os.path.exists(self.configfile):
            self.logger.fatal("config file does not exist")
            return
        with open(self.configfile, mode='r') as fp:
            try:
                self.config = yaml.load(fp, Loader=yaml.FullLoader)
            except yaml.YAMLError:
                self.logger.fatal("config file not readable")
                return
            pass

    def set_callbacks(self, device_update_callback, device_remove_callback, device_add_callback):
        self.device_update_callback = device_update_callback
        self.device_remove_callback = device_remove_callback
        self.device_add_callback = device_add_callback

    def _connect_timeout_handler(self):
        if self.connected:
            return
        self.logger.info("Cannot connect to NHC broker")
        self.connected = False
        self.client.disconnect()

    def is_connected(self):
        return self.connected

    def start(self):
        try:
            self.password = self.config["password"]
        except:
            self.logger.error("no password in config")
            return
        try:
            self.username = self.config["username"]
        except:
            self.logger.error("no username in config")
            return
        try:
            self.ca_cert_file = self.config["ca_cert_hobby"]
        except:
            self.logger.error("no ca_cert in config")
            return
        if self.host is None:
            self.logger.error("no COCO found")
            return
        if not os.path.exists(self.ca_cert_file):
            self.logger.error("Cannot find ca_cert file")
            return

        self.client = mqtt.Client()
        self.client.username_pw_set(self.username, self.password)
        self.client.tls_set(ca_certs=self.ca_cert_file)
        self.client.tls_insecure_set(True)
        self.client.on_message = self._message
        self.client.on_connect = self._connect
        self.client.on_disconnect = self.disconnect
        self.client.connect_async(self.host, self.port)
        self.connect_timer = threading.Timer(self.connect_timeout, self._connect_timeout_handler)
        self.connect_timer.start()
        self.client.loop_start()

    def stop(self):
        self.connected = False
        self.client.disconnect()

    def _message(self, client, obj, msg):
        #self.logger.info("Hobby mqtt message topic:%s\n%s", msg.topic, json.loads(msg.payload))
        if msg.topic == TOPIC_DEVICES_RSP:
            self._message_devices_response(client, msg)
        elif msg.topic == TOPIC_DEVICES_ERR:
            self._message_devices_error(client, msg)
        elif msg.topic == TOPIC_DEVICES_EVT:
            self._message_devices_event(client, msg)
        elif msg.topic == TOPIC_LOCATIONS_RSP:
            self._message_locations_response(client, msg)
        elif msg.topic == TOPIC_LOCATION_ERR:
            self._message_location_error(client, msg)
        elif msg.topic == TOPIC_SYSTEM_EVT:
            self._message_system_event(client, msg)
        elif msg.topic == TOPIC_SYSTEM_RSP:
            self._message_system_response(client, msg)
        elif msg.topic == TOPIC_SYSTEM_TIME_RSP:
            self._message_system_time_response(client, msg)
        elif msg.topic == TOPIC_NOTIFICATION_RSP:
            self._message_notification_event(client, msg)
        elif msg.topic == TOPIC_NOTIFICATION_ERR:
            self._message_notification_error(client, msg)
        elif msg.topic == TOPIC_NOTIFICATION_EVT:
            self._message_notification_event(client, msg)
        else:
            self.logger.info("Hobby mqtt message '%s' on topic: %s", msg.payload, msg.topic)

    def _connect(self, client, obj, flags, rc):
        self.connected = True
        self.connect_timer.cancel()
        self.logger.info("Connected to HobbyAPI. rc:%d", rc)
        self.client.subscribe(TOPIC_DEVICES_RSP, 0)
        self.client.subscribe(TOPIC_DEVICES_ERR, 0)
        self.client.subscribe(TOPIC_DEVICES_EVT, 0)
        self.client.subscribe(TOPIC_LOCATIONS_RSP, 0)
        self.client.subscribe(TOPIC_LOCATION_ERR, 0)
        self.client.subscribe(TOPIC_SYSTEM_EVT, 0)
        self.client.subscribe(TOPIC_SYSTEM_RSP, 0)
        self.client.subscribe(TOPIC_SYSTEM_ERR, 0)
        self.client.subscribe(TOPIC_SYSTEM_TIME_RSP, 0)
        self.client.subscribe(TOPIC_NOTIFICATION_RSP, 0)
        self.client.subscribe(TOPIC_NOTIFICATION_ERR, 0)
        self.client.subscribe(TOPIC_NOTIFICATION_EVT, 0)
        self.systeminfo_get()
        self.devices_list_get()
        self.locations_list_get()
        #self.notifications_list_get() --> do not ask for a list of past notifications

    def disconnect(self, client, userdata, rc):
        self.logger.warning("Disconnected from HobbyAPI")
        self.connected = False
        self.connect_timer.cancel()

    def devices_list_get(self):
        if not self.connected:
            return False
        frame = {"Method": "devices.list"}
        self.client.publish(TOPIC_DEVICES_CMD, json.dumps(frame))

    def get_device(self, uuid):
        i = 0
        while i < len(self.devices):
            if self.devices[i]["Uuid"] == uuid:
                return self.devices[i]
            i += 1
        return None

    def devices_control(self, uuid, property1, value1, property2=None, value2=None):
        if not self.connected:
            return False
        frame = {}
        frame["Method"] = "devices.control"
        frame_device = {}
        frame_property1 = {property1: value1}
        if property2 is not None and value2 is not None:
            frame_property2 = {property2: value2}
            frame_device["Properties"] = [frame_property1, frame_property2]
        else:
            frame_device["Properties"] = [frame_property1]
        frame_device["Uuid"] = uuid
        frame_devices = {}
        frame_devices["Devices"] = [frame_device]
        frame["Params"] = [frame_devices]
        self.client.publish(TOPIC_DEVICES_CMD, json.dumps(frame))

    def _extra_traits_in_name(self, index):
        name = self.devices[index]["Name"]
        namesplit = name.split("#")
        self.devices[index]["Name"] = namesplit[0]
        if len(namesplit) == 1:
            return
        i = 1
        while i < len(namesplit):
            key = "Option" + str(i-1)
            newtrait = {key:namesplit[i]}
            self.devices[index]["Traits"].append(newtrait)
            i += 1

    def _message_devices_response(self, client, msg):
        frame = json.loads(msg.payload)
        self.devices = frame["Params"][0]["Devices"]
        self.logger.info("initial devices list created")
        i = 0
        # search for additional configuration in the Name property
        while i < len(self.devices):
            self._extra_traits_in_name(i)
            i += 1

    def _message_devices_error(self, client, msg):
        frame = json.loads(msg.payload)
        message = frame["ErrMessage"]
        code = frame["ErrCode"]
        _ = frame["Method"]
        self.logger.info("%s (code:%s)", message, code)

    def _device_status_update(self, device_index, frame):
        call_callback = True
        name = self.devices[device_index]["Name"]
        try:
            self.devices[device_index]["Online"] = frame["Online"]
            call_callback = False
        except:
            pass
        if 'Properties' not in self.devices[device_index]:
            self.devices[device_index]["Properties"] = frame["Properties"]
            return
        i = 0
        while i < len(frame["Properties"]):
            _property_new = list(frame["Properties"][i].keys())[0]
            _value_new = list(frame["Properties"][i].values())[0]
            j = 0
            while j < len(self.devices[device_index]["Properties"]):
                _property_device = list(self.devices[device_index]["Properties"][j].keys())[0]
                _value_device = list(self.devices[device_index]["Properties"][j].values())[0]
                if _property_new == _property_device:
                    self.devices[device_index]["Properties"][j][_property_device] = _value_new
                j += 1
            i += 1

        self.logger.info("device '%s' status changed: %s", name, frame)
        
        if self.device_update_callback is not None and call_callback:
            self.device_update_callback(self.devices[device_index], frame)


    def _message_devices_event(self, client, msg):
        frame = json.loads(msg.payload)
        method = frame["Method"]
        devices_in = frame["Params"][0]["Devices"]
        if method == "devices.added":
            for dev_index in range(len(devices_in)):
                i = 0
                _new = True
                _name = devices_in[dev_index]["Name"]
                _model = devices_in[dev_index]["Model"]
                _type = devices_in[dev_index]["Type"]
                while i < len(self.devices):
                    uuid = devices_in[dev_index]["Uuid"]
                    if self.devices[i]["Uuid"] == uuid:
                        # update existing entry
                        self.devices[i] = devices_in[dev_index]
                        self._extra_traits_in_name(i)
                        self.logger.info("device '%s' (%s/%s) updated", _name, _model, _type)
                        _new = False
                        break
                    i += 1
                if _new:
                    self.devices.append(devices_in[dev_index])
                    self._extra_traits_in_name(dev_index)
                    if self.device_add_callback is not None:
                        self.device_add_callback(devices_in[dev_index])
                    self.logger.info("device '%s' (%s/%s) added", _name, _model, _type)
            return
        # handle the rest of the methods
        found = False
        # incoming message can have multiple devices
        for dev_index in range(len(devices_in)):
            i = 0
            # walk through the devices list in memory
            while i < len(self.devices):
                uuid = devices_in[dev_index]["Uuid"]
                if self.devices[i]["Uuid"] == uuid:
                    # we have a match
                    found = True
                    _name = self.devices[i]["Name"]
                    _model = self.devices[i]["Model"]
                    _type = self.devices[i]["Type"]
                    if method == "devices.removed":
                        self.logger.info("device '%s' (%s/%s) removed", _name, _model, _type)
                        if self.device_remove_callback is not None:
                            self.device_remove_callback(uuid, _model)
                        del self.devices[i]
                    elif method == "devices.displayname_changed":
                        new_name = devices_in[dev_index]["DisplayName"]
                        self.devices[i]["Name"] = new_name
                        self._extra_traits_in_name(i)
                        self.logger.info("device '%s' (%s/%s) name changed to '%s'", _name,  _model, _type, new_name)
                    elif method == "devices.changed":
                        self.devices[i]["PropertyDefinitions"] = devices_in[dev_index]["PropertyDefinitions"]
                        self.logger.info("device '%s' (%s/%s) property definitions changed", _name, _model, _type)
                    elif method == "devices.param_changed":
                        self.devices[i]["Parameters"] = devices_in[dev_index]["Parameters"]
                        self.logger.info("device '%s' (%s/%s) parameters changed", _name, _model, _type)
                    elif method == "devices.status":
                        self._device_status_update(i, devices_in[dev_index])
                    else:
                        # normally we don't come here
                        self.logger.info("unknown device method: %s", method)
                    break                                                                         
                i += 1
        if not found:
            self.logger.info("no device (uuid:%s) found for action '%s'", uuid, method)  


    def print_devices(self, filtermodel=None, filtertype=None, fulltable=False, sortby="Name"):
        if self.devices is None:
            self.logger.warn("no NHC devices found")
            return

        t = PrettyTable()
        if fulltable:
            t.field_names = ["Name", "Location", "Model", "Type", "UUID", "MAC", "Channel", "Online"]
        else:
            t.field_names = ["Name", "Location", "Model", "Type", "UUID"]
        t.align = "l"
        i = 0
        while i < len(self.devices):
            _device = self.devices[i]
            _name = _device["Name"]
            _model = _device["Model"]
            _type = _device["Type"]
            _uuid = _device["Uuid"]
            _mac = ""
            _channel = ""
            _location = ""
            try:
                _online = _device["Online"]
            except:
                _online = "?"
            j = 0
            while j < len(_device["Parameters"]):
                parameter = _device["Parameters"][j]
                for key, value in parameter.items(): 
                    if key == "LocationName":
                        _location = value
                    elif key == "LocationIcon":
                        _location_icon = value
                j += 1
            j = 0
            while j < len(_device["Traits"]):
                trait = _device["Traits"][j]
                for key, value in trait.items(): 
                    if key == "MacAddress":
                        _mac = value
                    elif key == "Channel":
                        _channel = value
                j += 1

            if filtermodel is None:
                _print_model = True
            elif _model in filtermodel:
                _print_model = True
            else:
                _print_model = False

            if filtertype is None:
                _print_type = True
            elif filtertype == _type:
                _print_type = True
            else:
                _print_type = False

            if _print_model and _print_type:
                if fulltable:
                    t.add_row([_name, _location, _model, _type, _uuid, _mac, _channel, _online])
                else:
                    t.add_row([_name, _location, _model, _type, _uuid])
            i += 1
        return str(t.get_string(sortby=sortby))

    def print_mood_action(self):
        return self.print_devices(filtermodel=self.mood_models, filtertype="action")

    def print_relay_action(self):
        return self.print_devices(filtermodel=self.relay_models, filtertype="action")

    def print_dimmer_action(self):
        return self.print_devices(filtermodel=self.dimmer_models, filtertype="action")

    def print_motor_action(self):
        return self.print_devices(filtermodel=self.motor_models, filtertype="action")

    def print_properties(self, uuid):
        try:
            UUID(uuid)
        except ValueError:
            return None
        _uuid = None
        i = 0
        while i < len(self.devices):
            _device = self.devices[i]
            _name = _device["Name"]
            _model = _device["Model"]
            _type = _device["Type"]
            _uuid = _device["Uuid"]
            if uuid == _uuid:
                break
            i += 1

        if _uuid is None:
            self.logger.warning("uuid not found")
            return

        t = PrettyTable()
        t.field_names = ["Property", "Value"]
        t.align = "l"
        i = 0
        while i < len(_device["Properties"]):
            _properties = _device["Properties"][i]
            for key, value in _properties.items():
                t.add_row([key, value])
            i += 1
        return str(t.get_string(sortby="Property"))


    def nhc_info(self):
        frame = {"ip": self.discover.gateway["ip"]}
        i = 0
        while i < len(self.devices):
            if self.devices[i]["Model"] == "nhc" and self.devices[i]["Type"] == "home_automation":
                frame["gateway_name"] = self.devices[i]["Name"]
            if self.devices[i]["Name"] == "gatewayfw":
                frame["hubtype"] = self.devices[i]["Traits"][0]["HubType"]
                j = 0
                while j < len(self.devices[i]["Properties"]):
                    _property = self.devices[i]["Properties"][j]
                    for key, value in _property.items():
                        if key == "CurrentFWInfo":
                            frame["firmware"] = value
                    j += 1
            i += 1
        return frame


    def search_uuid_action(self, uuid, nhcmodel):
        try:
            UUID(uuid)
        except ValueError:
            return None
        if nhcmodel == NHC_MODELS.MOOD:
            models = self.mood_models
        elif nhcmodel == NHC_MODELS.RELAY:
            models = self.relay_models
        elif nhcmodel == NHC_MODELS.DIMMER:
            models = self.dimmer_models
        elif nhcmodel == NHC_MODELS.MOTOR:
            models = self.motor_models
        else:
            models = self.relay_models + self.dimmer_models + self.motor_models + self.mood_models
        i = 0
        while i < len(self.devices):
            _device = self.devices[i]
            _name = _device["Name"]
            _model = _device["Model"]
            _type = _device["Type"]
            _uuid = _device["Uuid"]
            if _type == "action":
                for model in models:
                    if uuid == _uuid and model == _model:
                        return _device
            i += 1
        self.logger.warning("uuid not found")
        return None
        

    def list_uuid_action(self):
        _list = []
        models = self.relay_models + self.dimmer_models + self.motor_models + self.mood_models
        i = 0
        while i < len(self.devices):
            _device = self.devices[i]
            _model = _device["Model"]
            _type = _device["Type"]
            _uuid = _device["Uuid"]
            if _type == "action" and _model in models:
                _list.append(_uuid)
            i += 1
        return _list


    def locations_list_get(self):
        if not self.connected:
            return False
        frame = {"Method": "locations.list"}
        self.client.publish(TOPIC_LOCATIONS_CMD, json.dumps(frame))

    def locations_listitems(self, uuid):
        if not self.connected:
            return False
        frame = {}
        frame["Method"] = "devices.listitems"
        frame_uuid = {"Uuid":uuid}
        frame_locations = {"Locations": [frame_uuid]}
        frame["Params"] = [frame_locations]
        self.client.publish(TOPIC_LOCATIONS_CMD, json.dumps(frame))

    def _message_locations_response(self, client, msg):
        frame = json.loads(msg.payload)
        method = frame["Method"]
        if method == "locations.list":
            self.locations = frame["Params"][0]["Locations"]
            self.logger.info("list of locations updated")
        else:
            self.logger.info("unknown method: %s", method)

    def _message_location_error(self, client, msg):
        frame = json.loads(msg.payload)
        message = frame["ErrMessage"]
        code = frame["ErrCode"]
        method = frame["Method"]
        self.logger.info("%s (code:%s)", message, code)

    def _update_systeminfo(self, frame):
        self.systeminfo = frame
        self.logger.info("systeminfo updated")

    def _message_system_event(self, client, msg):
        frame = json.loads(msg.payload)
        method = frame["Method"]
        if method == "time.published":
            params = frame["Params"]
            offset = params[0]["TimeInfo"][0]["GMTOffset"]
            timezone = params[0]["TimeInfo"][0]["Timezone"]
            time = params[0]["TimeInfo"][0]["UTCTime"]
            #self.logger.debug("time info: %s (offset:%s, timezone:%s)", time, offset, timezone)
        elif method == "systeminfo.published":
            self._update_systeminfo(frame["Params"][0]["SystemInfo"][0])
        else:
            self.logger.info("unknown method: %s", method)

    def _message_system_response(self, client, msg):
        frame = json.loads(msg.payload)
        self._update_systeminfo(frame["Params"][0]["SystemInfo"][0])

    def systeminfo_get(self):
        if not self.connected:
            return False
        frame = {"Method": "systeminfo.publish"}
        self.client.publish(TOPIC_SYSTEM_CMD, json.dumps(frame))

    def _message_system_time_response(self, client, msg):
        frame = json.loads(msg.payload)
        pass

    def notifications_list_get(self):
        if not self.connected:
            return False
        frame = {"Method": "notifications.list"}
        self.client.publish(TOPIC_NOTIFICATION_CMD, json.dumps(frame))

    def notifications_update(self, uuid, status="read"):
        if not self.connected:
            return False
        frame = {}
        frame["Method"] = "notifications.update"
        frame_notifications = {}
        frame_notifications["Uuid"] = uuid
        frame_notifications["Status"] = status
        frame["Params"] = [frame_notifications]
        self.client.publish(TOPIC_NOTIFICATION_CMD, json.dumps(frame))

    def _message_notification_error(self, client, msg):
        frame = json.loads(msg.payload)
        self.logger.info(frame)

    def _message_notification_event(self, client, msg):
        frame = json.loads(msg.payload)
        j = 0
        while j < len(frame["Params"]):
            parameter = frame["Params"][j]
            i = 0
            while i < len(parameter['Notifications']):
                notification = parameter['Notifications'][i]
                for key, value in notification.items(): 
                    if key == "Type":
                        _type = value
                    elif key == "Text":
                        _text = value
                    elif key == "Status":
                        _status = value
                self.logger.info("notification type:'%s' status:'%s', text:'%s'", _type, _status, _text)
                #if _status == 'new':
                    # TODO callback
                i += 1
            j += 1
