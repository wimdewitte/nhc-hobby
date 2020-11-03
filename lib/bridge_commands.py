class commands(object):
    def __init__(self, logger, clilogger, hobby):
        self.logger = logger
        self.clilogger = clilogger
        self.hobby = hobby

    def do_devices(self, args):
        if len(args) == 0:
            _filter = None
        elif len(args) == 1:
            _filter = args[0]
        else:
            self.help_devices()
            return

        data = self.hobby.print_devices(_filter)
        self.clilogger.cli_info(data)

    def help_devices(self):
        self.clilogger.cli_neutral("Print all NHC devices, arg1 (optional): type filter")

    def do_light(self, args):
        if len(args) != 2:
            self.help_light()
            return
 
        _device = args[0]
        _value = bool(int(args[1]))
        if _value == 0:
            _value = "Off"
        else:
            _value = "On"

        _device = self.hobby.search_device(_device, "light", "action")
        if _device is None:
            self.clilogger.cli_error("device {} not found or not a light action".format(_device))
            return

        self.hobby.devices_control(_device, "Status", _value)
        self.clilogger.cli_info("set light {} successfully".format(_device))

    def help_light(self):
        self.clilogger.cli_neutral("Set light on or off. arg1: device/uuid, arg2: state (0 or 1)")

    def do_dimmer(self, args):
        if len(args) != 2:
            self.help_dimmer()
            return
 
        _device = args[0]
        _value = args[1]
        try:
            _value = int(_value)
            if _value > 100:
                _value = 100
            elif _value < 0:
                _value = 0
        except:
            if _value == "on" or _value == "On":
                _value = "On"
            elif _value == "off" or _value == "Off":
                _value = "Off"
            else:
                self.help_dimmer()
                return

        _device = self.hobby.search_device(_device, "dimmer", "action")
        if _device is None:
            self.clilogger.cli_error("device {} not found or not a dimmer action".format(_device))
            return

        if isinstance(_value, str):
            self.hobby.devices_control(_device, "Status", _value)
        else:
            self.hobby.devices_control(_device, "Brightness", str(_value))
        self.clilogger.cli_info("set dimmer {} successfully".format(_device))

    def help_dimmer(self):
        self.clilogger.cli_neutral("Set dimmer value. arg1: device/uuid, arg2: value 'on', 'off', '0->100')")
