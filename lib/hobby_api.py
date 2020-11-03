import os
import paho.mqtt.client as mqtt
import threading
import json
import logging
import struct
from prettytable import PrettyTable
from uuid import UUID


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

class hobbyAPI(object):
    def __init__(self, logger, ca_cert_file=None, password=None, username="hobby", port=8884, host=None, connect_timeout=60):
        self.logger = logger
        self.host = host
        self.port = port
        self.ca_cert_file = ca_cert_file
        self.password = password
        self.username = username
        self.connect_timeout = connect_timeout
        self.connected = False
        self.client = None
        self.systeminfo = None
        self.devices = None
        self.locations = None
        self.notifications = None
        self.device_callback = None

    def set_callbacks(self, device_callback):
        self.device_callback = device_callback

    def _connect_timeout_handler(self):
        if self.connected:
            return
        self.logger.info("Cannot connect to NHC broker")
        self.connected = False
        self.client.disconnect()

    def is_connected(self):
        return self.connected

    def start(self):
        if self.host is None or self.password is None or self.ca_cert_file is None:
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
            self._message_notification_response(client, msg)
        elif msg.topic == TOPIC_NOTIFICATION_ERR:
            self._message_notification_response(client, msg)
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
        self.notifications_list_get()

    def disconnect(self, client, userdata, rc):
        self.logger.warning("Disconnected from HobbyAPI")
        self.connected = False
        self.connect_timer.cancel()

    def devices_list_get(self):
        if not self.connected:
            return False
        frame = {"Method": "devices.list"}
        self.client.publish(TOPIC_DEVICES_CMD, json.dumps(frame))

    def get_devices(self):
        return self.devices

    def devices_control(self, uuid, property, value):
        if not self.connected:
            return False
        frame = {}
        frame["Method"] = "devices.control"
        frame_property = {property: value}
        frame_device = {}
        frame_device["Uuid"] = uuid
        frame_device["Properties"] = [frame_property]
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
            if i == 1:
                key = "MeshAddress"
            else:
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
        method = frame["Method"]
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
        
        if self.device_callback is not None and call_callback:
            self.device_callback(device_index, frame["Properties"])


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


    def print_devices(self, filter=None):
        if self.devices is None:
            self.logger.warn("no NHC devices found")
            return

        t = PrettyTable()
        t.field_names = ["", "Name", "Model", "Type", "Location", "UUID", "MAC", "Channel", "Online"]
        t.align["Name"] = "l"
        t.align["Model"] = "l"
        t.align["Type"] = "l"
        t.align["Location"] = "l"
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
            try:
                _location = _device["Parameters"][0]["LocationName"]
            except:
                pass
            j = 0
            while j < len(_device["Traits"]):
                trait = _device["Traits"][j]
                for key, value in trait.items(): 
                    if key == "MacAddress":
                        _mac = value
                    elif key == "Channel":
                        _channel = value
                j += 1

            if filter == _type or filter is None:
                t.add_row([str(i+1), _name, _model, _type, _location, _uuid, _mac, _channel, _online])
            i += 1
        return str(t)

    def search_device(self, device, modeltype, devicetype):
        is_uuid = False
        try:
            UUID(device)
            is_uuid = True
        except ValueError:
            pass

        i = 0
        found = False
        while i < len(self.devices):
            _device = self.devices[i]
            _name = _device["Name"]
            _model = _device["Model"]
            _type = _device["Type"]
            _uuid = _device["Uuid"]
            if _model == modeltype and _type == devicetype:
                if is_uuid:
                    if device == _uuid: 
                        device = _uuid
                        found = True
                        break
                else:
                    if device == _name:
                        device = _uuid
                        found = True
                        break
            i += 1

        if found:
            return device
        else:
            return None


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
            self.logger.debug("time info: %s (offset:%s, timezone:%s)", time, offset, timezone)
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

    def _message_notification_response(self, client, msg):
        frame = json.loads(msg.payload)
        method = frame["Method"]
        if method == "notifications.list":
            self.notifications = frame["Params"][0]["Notifications"]
            pass
        elif method == "notifications.update":
            # TODO
            pass
        else:
            self.logger.info("unknown method: %s", method)

    def _message_notification_error(self, client, msg):
        frame = json.loads(msg.payload)
        self.logger.info(frame)

    def _message_notification_event(self, client, msg):
        frame = json.loads(msg.payload)
        self.logger.info(frame)

