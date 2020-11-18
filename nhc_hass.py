#!/usr/bin/env python3

import sys
import os
import logging
import signal
import time
from traceback import format_exc
from argparse import ArgumentParser
from daemon import DaemonContext
from lockfile.pidlockfile import PIDLockFile
from nhc.hobby_api import hobbyAPI, controlNHC
from hass.mqtt import Hass
from lib.bridge_prompt import prompt
from lib.mylogger import mylogger
import subprocess
from subprocess import PIPE, run


class Application():
    def __init__(self, configfile, clilogger):
        self.configfile = configfile
        self.clilogger = clilogger
        self.logger = clilogger.get_logger()
        self.hobby = None
        self.hass = None
        self.running = False

    def run(self, foreground=False):
        while True:
            try:
                self.logger.info("NHC Hass Bridge started")
                self.hobby = hobbyAPI(self.logger, self.configfile)
                self.nhccontrol = controlNHC(self.hobby)
                self.hass = Hass(self.logger, hobby=self.hobby)
                self.hobby.start()
                self.hass.start()
                self.hobby.set_callbacks(self.hass.nhc_status_update, self.hass.nhc_remove_device, self.hass.nhc_add_device)

                # give some time to connect
                time.sleep(3)
                self.running = self.overall_status()

                # start infinite while loop
                if foreground:
                    app = prompt(self.clilogger, self.nhccontrol, self.hass)
                    sys.exit(app.cmdloop())
                else:
                    while self.running:
                        self.running = self.overall_status()
                        time.sleep(1)

                return 0
            except Exception as exc:
                self.logger.info("%s", format_exc())
                self.logger.fatal("%s", exc)
                if foreground:
                    return 1
            time.sleep(15)

    def shutdown(self, signum, frame):
        self.logger.info("Shutting down with signal %s", signal.Signals(signum).name)
        if self.hobby is not None:
            self.hobby.stop()
        if self.hass is not None:
            self.hass.stop()

    def overall_status(self):
        status_hobby = self.hobby.is_connected()
        status_hass = self.hass.is_connected()
        if status_hobby and status_hass:
            return True
        else:
            self.logger.error("Fault status: hobby:%d, hass:%d", status_hobby, status_hass)
            return False


class CreateApp(object):
    def __init__(self, options):
        self.clilogger = mylogger("nhchabridge", options.loglevel)
        self.logger = self.clilogger.get_logger()
        self.options = options
        if os.access("/var/run/", os.W_OK):
            _pidfile = "/var/run/nhchabridge.pid"
        else:
            _pidfile = "/var/tmp/nhchabridge.pid"
        self.pid_file = PIDLockFile(_pidfile)

    def stop_daemon(self):
        if self.pid_file.is_locked():
            print("Stopping service with pid", self.pid_file.read_pid())
            os.kill(self.pid_file.read_pid(), signal.SIGTERM)        

    def start_foreground(self):
        self.clilogger.set_logger_stream()
        daemon = Application(self.options.config, self.clilogger)
        try:
            daemon.run(foreground=True)
        except (SystemExit, KeyboardInterrupt):
            daemon.shutdown(2, None)

    def start_daemon(self):
        self.clilogger.set_logger_syslog()
        if self.pid_file.is_locked():
            self.logger.error("Service already running with pid %d", self.pid_file.read_pid())
            return
        daemon = Application(self.options.config, self.clilogger)
        context = DaemonContext()
        context.pidfile = self.pid_file
        context.files_preserve = [self.clilogger.get_syslog_fileno()]
        context.signal_map = {signal.SIGTERM: daemon.shutdown, signal.SIGINT: daemon.shutdown}
        with context:
            self.logger.info("Starting service with pid %d", self.pid_file.read_pid())
            try:
                daemon.run(foreground=False)
            except SystemExit:
                daemon.shutdown(2, None)


def main(options):
    app = CreateApp(options=options)
    if options.kill:
        app.stop_daemon()
        return
    if options.config is None:
        print("Missing config file location in arguments")
        return    
    elif options.foreground:
        app.start_foreground()
    else:
        app.start_daemon()


if __name__ == '__main__':
    parser = ArgumentParser(description="NHC Hass bridge")
    parser.add_argument('-l', '--loglevel', help='Loglevel: d(ebug), i(nfo), w(arning), e(rror)', choices=['d','i','w','e'], default="e")
    parser.add_argument('-c', '--config', help='Config file location', default="./nhc.yaml")
    parser.add_argument('-f', '--foreground', help='Run in foreground', default=False, action='store_true')
    parser.add_argument('-k', '--kill', help='Kill running daemon', default=False, action='store_true')
    main(parser.parse_args())
