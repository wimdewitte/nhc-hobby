import sys
import time
import cmd2 as cli
from cmd2 import style, ansi
from lib.nhc_control import NHC_RET

class prompt(cli.Cmd):
    def __init__(self, config, clilogger, nhccontrol, hass):
        super().__init__()
        self.config = config
        self.clilogger = clilogger
        self.nhccontrol = nhccontrol
        self.hass = hass
        self.hidden_commands.append('py')
        self.hidden_commands.append('edit')
        self.prompt = style('NHC> ', fg='blue', bold=True)
        self.intro = style('Welcome! Type ? to list commands', fg='blue', bg='white', bold=True)
        self.locals_in_py = True
        self.default_category = 'cmd2 Built-in Commands'

    def precmd(self, line):
        self.clilogger.set_cmd_from_mqtt(False)
        return line

    def postcmd(self, stop: bool, line: str) -> bool:
        # give some time, otherwise logger prints between response
        time.sleep(0.1)
        # make sure prompt is visible after every command
        self.clilogger.cli_neutral("")
        return stop
    
    def validate_nhc_return(self, value, actiontype=""):
        if value == NHC_RET.ARGS:
            self.clilogger.cli_error("wrong arguments for {} action".format(actiontype))
        elif value == NHC_RET.DEVICE:
            self.clilogger.cli_error("device not found or not a {} action".format(actiontype))
        else:
            self.clilogger.cli_info("set {} successfully".format(actiontype))

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_devices(self, args):
        if len(args) == 0:
            _type = None
        elif len(args) == 1:
            _type = args[0]
        else:
            self.help_devices()
            return
        table, _ = self.nhccontrol.hobby.print_devices(filtermodel=None, filtertype=_type, fulltable=True)
        self.clilogger.cli_info(table)

    def help_devices(self):
        self.clilogger.cli_neutral("Print all NHC devices, arg1 (optional): type filter on Type")

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_mood(self, args):
        if len(args) != 1:
            self.help_mood()
            table, _ = self.nhccontrol.hobby.print_mood_action()
            self.clilogger.cli_info(table)
            return
 
        ret = self.nhccontrol.mood(args[0])
        self.validate_nhc_return(ret, "mood")
        
    def help_mood(self):
        self.clilogger.cli_neutral("Set mood. arg1: device/uuid")

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_relay(self, args):
        if len(args) != 2:
            self.help_relay()
            table, _ = self.nhccontrol.hobby.print_relay_action()
            self.clilogger.cli_info(table)
            return
 
        ret = self.nhccontrol.relay(args[0], args[1])
        self.validate_nhc_return(ret, "relay")
        
    def help_relay(self):
        self.clilogger.cli_neutral("Set relay. arg1: device/uuid, arg2: state (0 or 1)")

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_dimmer(self, args):
        if len(args) != 2:
            self.help_dimmer()
            table, _ = self.nhccontrol.hobby.print_dimmer_action()
            self.clilogger.cli_info(table)
            return
 
        ret = self.nhccontrol.dimmer(args[0], args[1])
        self.validate_nhc_return(ret, "dimmer")


    def help_dimmer(self):
        self.clilogger.cli_neutral("Set dimmer. arg1: device/uuid, arg2: value 'on', 'off', '0->100')")

    @cli.with_argument_list
    @cli.with_category("NHC")
    def do_motor(self, args):
        if len(args) != 2:
            self.help_motor()
            table, _ = self.nhccontrol.hobby.print_motor_action()
            self.clilogger.cli_info(table)
            return
 
        ret = self.nhccontrol.motor(args[0], args[1])
        self.validate_nhc_return(ret, "motor")

    def help_motor(self):
        self.clilogger.cli_neutral("Set motor. arg1: device/uuid, arg2: value 'on', 'off', '0->100')")

    @cli.with_argument_list
    @cli.with_category("Hass")
    def do_discover(self, args):
        if len(args) < 1 or len(args) > 2:
            self.help_discover()
            table, _ = self.nhccontrol.hobby.print_devices(filtertype="action")
            self.clilogger.cli_info(table)
            return
        remove = False
        try:
            if args[1] == "remove":
                remove = True
        except:
            pass
        self.hass.discover(args[0], remove)

    def help_discover(self):
        self.clilogger.cli_neutral("Discover. arg1: device/uuid, arg2 (optional): remove")