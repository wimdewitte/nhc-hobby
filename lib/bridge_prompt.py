import sys
import time
import argparse
import cmd2 as cli
from cmd2 import style, ansi


class prompt(cli.Cmd):
    def __init__(self, clilogger, nhccontrol, hass):
        super().__init__(allow_cli_args=False)
        self.clilogger = clilogger
        self.nhccontrol = nhccontrol
        self.hass = hass
        self.prompt = style('NHC> ', fg='blue', bold=True)
        self.self_in_py = True
        self.default_category = 'cmd2 Built-in Commands'

    loglevel_parser = argparse.ArgumentParser()
    loglevel_parser.add_argument(
        '-l', '--level', help='Loglevel: d-ebug, i-nfo, w-arning, e-rror', choices=['d', 'i', 'w', 'e'], required=True)

    @cli.with_argparser(loglevel_parser)
    @cli.with_category("miscellaneous")
    def do_loglevel(self, args):
        self.clilogger.set_loglevel(args.level)

    devices_parser = argparse.ArgumentParser()
    devices_parser.add_argument('-m', '--model', help='Filter NHC model')
    devices_parser.add_argument('-t', '--type', help='Filter NHC type')
    devices_parser.add_argument('-f', '--full', help='Print full table', action='store_true', default=False)

    @cli.with_argparser(devices_parser)
    @cli.with_category("NHC")
    def do_devices(self, args):
        if args.model is not None:
            args.model = [args.model]
        _table = self.nhccontrol.hobby.print_devices(
            filtermodel=args.model, filtertype=args.type, fulltable=args.full)
        self.clilogger.cli_info(_table)

    mood_parser = argparse.ArgumentParser()
    mood_parser.add_argument('-u', '--uuid', help='NHC UUID device')
    mood_parser.add_argument('-p', '--print', help='Print table with moods', action='store_true')

    @cli.with_argparser(mood_parser)
    @cli.with_category("NHC")
    def do_mood(self, args):
        if args.print:
            _table = self.nhccontrol.hobby.print_mood_action()
            self.clilogger.cli_info(_table)
        if args.uuid is not None:
            self.nhccontrol.mood(args.uuid)

    relay_parser = argparse.ArgumentParser()
    relay_parser.add_argument('-u', '--uuid', help='NHC UUID device')
    relay_parser.add_argument('-v', '--view', help='View table with relays', action='store_true')
    relay_parser.add_argument('-s', '--status', help='Status: On or Off', choices=['On', 'Off'])

    @cli.with_argparser(relay_parser)
    @cli.with_category("NHC")
    def do_relay(self, args):
        if args.view:
            _table = self.nhccontrol.hobby.print_relay_action()
            self.clilogger.cli_info(_table)
        if args.uuid is not None:
            self.nhccontrol.relay(args.uuid, args.status)

    dimmer_parser = argparse.ArgumentParser()
    dimmer_parser.add_argument('-u', '--uuid', help='NHC UUID device')
    dimmer_parser.add_argument('-v', '--view', help='View table with relays', action='store_true')
    dimmer_parser.add_argument('-s', '--status', help='Status: On or Off', choices=['On', 'Off'])
    dimmer_parser.add_argument('-b', '--brightness', help='Brightness 0->100', type=int, choices=range(0, 100+1))

    @cli.with_argparser(dimmer_parser)
    @cli.with_category("NHC")
    def do_dimmer(self, args):
        if args.view:
            _table = self.nhccontrol.hobby.print_dimmer_action()
            self.clilogger.cli_info(_table)
        if args.uuid is not None:
            self.nhccontrol.dimmer(args.uuid, args.status, args.brightness)

    motor_parser = argparse.ArgumentParser()
    motor_parser.add_argument('-u', '--uuid', help='NHC UUID device')
    motor_parser.add_argument('-v', '--view', help='View table with relays', action='store_true')
    motor_parser.add_argument('-a', '--action', help='Action', choices=['Open', 'Close', 'Stop'])
    motor_parser.add_argument('-p', '--position', help='Position', type=int, choices=range(0, 100+1))

    @cli.with_argparser(motor_parser)
    @cli.with_category("NHC")
    def do_motor(self, args):
        if args.view:
            _table = self.nhccontrol.hobby.print_motor_action()
            self.clilogger.cli_info(_table)
        if args.uuid is not None:
            self.nhccontrol.motor(args.uuid, args.action, args.position)

    discover_parser = argparse.ArgumentParser()
    discover_parser.add_argument('-u', '--uuid', help='NHC UUID device')
    discover_parser.add_argument('-v', '--view', help='View table with actions', action='store_true')
    discover_parser.add_argument('-r', '--remove', help='Remove device', action='store_true', default=False)

    @cli.with_argparser(discover_parser)
    @cli.with_category("Hass")
    def do_discover(self, args):
        if args.view:
            _table = self.nhccontrol.hobby.print_devices(filtertype="action")
            self.clilogger.cli_info(_table)
        if args.uuid is not None:
            self.hass.discover(args.uuid, args.remove)
