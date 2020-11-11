from nhc.hobby_api import NHC_MODELS


class NHC_RET():
    OK = 1
    ARGS = 2
    DEVICE = 3

class NHCcontrol(object):
    def __init__(self, logger, hobby):
        self.logger = logger
        self.hobby = hobby
        self.hobby.set_callbacks(self.status_change)

    def status_change(self, model, frame):
        pass

    def mood(self, device):
        device = self.hobby.search_uuid_action(device, NHC_MODELS.MOOD)
        if device is None:
            return NHC_RET.DEVICE

        self.hobby.devices_control(device, "BasicState", "Triggered")
        return NHC_RET.OK

    def relay(self, device, value):
        try:
            value = int(value)
            if value >= 1:
                value = "On"
            else:
                value = "Off"
        except:
            if value == "on" or value == "On":
                value = "On"
            elif value == "off" or value == "Off":
                value = "Off"
            else:
                return NHC_RET.ARGS

        device = self.hobby.search_uuid_action(device, NHC_MODELS.RELAY)
        if device is None:
            return NHC_RET.DEVICE

        self.hobby.devices_control(device, "Status", value)
        return NHC_RET.OK

    def dimmer(self, device, value):
        try:
            value = int(value)
            if value > 100:
                value = 100
            elif value < 0:
                value = 0
        except:
            if value == "on" or value == "On":
                value = "On"
            elif value == "off" or value == "Off":
                value = "Off"
            else:
                return NHC_RET.ARGS

        device = self.hobby.search_uuid_action(device, NHC_MODELS.DIMMER)
        if device is None:
            return NHC_RET.DEVICE

        if isinstance(value, str):
            self.hobby.devices_control(device, "Status", value)
        else:
            self.hobby.devices_control(device, "Brightness", str(value))
        return NHC_RET.OK

    def motor(self, device, value):
        try:
            value = int(value)
            if value > 100:
                value = 100
            elif value < 0:
                value = 0
        except:
            if value == "open" or value == "Open":
                value = "Open"
            elif value == "close" or value == "Close":
                value = "Close"
            elif value == "stop" or value == "Stop":
                value = "Stop"
            else:
                return NHC_RET.ARGS

        device = self.hobby.search_uuid_action(device, NHC_MODELS.MOTOR)
        if device is None:
            return NHC_RET.DEVICE

        if isinstance(value, str):
            self.hobby.devices_control(device, "Action", value)
        else:
            self.hobby.devices_control(device, "Position", str(value))
        return NHC_RET.OK

