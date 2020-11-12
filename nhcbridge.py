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


class AppFailed(Exception):
    def __init__(self, message):
        super(Exception, self).__init__(message)


def configure_options():
    parser = ArgumentParser(description="NHC Hass bridge")
    parser.add_argument('-l', '--loglevel', help='Loglevel: d(ebug), i(nfo), w(arning), e(rror)', default="e", required=False)
    parser.add_argument('-c', '--config', help='Config file location', required=True, default="./nhc.yaml")
    parser.add_argument('-f', '--foreground', help='Run in foreground', default=False, action='store_true')
    parser.add_argument('-a', '--action', help='Action (start,stop,pid)', default="start", required=False)
    return parser.parse_args()


def overall_status(logger, hobby, hass):
    status_hobby = hobby.is_connected()
    status_hass = hass.is_connected()
    if status_hobby and status_hass:
        return True
    else:
        logger.error("Fault status: hobby:%d, hass:%d", status_hobby, status_hass)
        return False


class Daemon():
    def __init__(self, options, clilogger):
        self.options = options
        self.clilogger = clilogger
        self.logger = clilogger.get_logger()
        self.hobby = None
        self.hass = None
        self.running = False

    def run(self, foreground=False):
        while True:
            try:
                self.logger.info("NHC Bridge started")
                self.hobby = hobbyAPI(self.logger, self.options.config)
                self.nhccontrol = controlNHC(self.hobby)
                self.hass = Hass(self.logger, hobby=self.hobby)
                self.hobby.start()
                self.hass.start()
                self.hobby.set_callbacks(self.hass.nhc_status_update)

                # give some time to connect
                time.sleep(3)
                self.running = overall_status(self.logger, self.hobby, self.hass)

                # start infinite while loop
                if foreground:
                    app = prompt(self.clilogger, self.nhccontrol, self.hass)
                    sys.exit(app.cmdloop())
                else:
                    while self.running:
                        self.running = overall_status(self.logger, self.hobby, self.hass)
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


class CreateApp(object):
    def __init__(self, options):
        self.options = options
        self._pidfile = None

    def run_app(self):
        self.clilogger = mylogger("nhcbridge", self.options.loglevel)
        if self.options.foreground:
            self.clilogger.set_logger_stream()
        else:
            self.clilogger.set_logger_syslog()
        self.logger = self.clilogger.get_logger()
        try:
            self.start_app(self.options, self.clilogger)
        except AppFailed as e:
            self.logger.error("Failed ({0})".format(str(e)))

    def start_app(self, options, clilogger):
        _action = self.options.action
        if _action != "start" and _action != "stop" and _action != "status" and _action != "restart":
            raise AppFailed("Invalid action specified")

        if os.access("/var/run/", os.W_OK):
            self._pidfile = "/var/run/nhcbridge.pid"
        else:
            self._pidfile = "/var/tmp/nhcbridge.pid"

        pid_file = PIDLockFile(self._pidfile)

        if _action == "stop":
            if pid_file.is_locked():
                self.logger.info("Stopping service with pid %d", pid_file.read_pid())
                os.kill(pid_file.read_pid(), signal.SIGTERM)
            return 0

        elif _action == "status":
            if pid_file.is_locked():
                self.logger.info("Service running with pid %d", pid_file.read_pid())
                return 0
            self.logger.info("Service not running")
            return 1

        elif _action == "start":
            if pid_file.is_locked():
                self.logger.info("Service already running with pid %d", pid_file.read_pid())
                return 1

        if pid_file.is_locked():
            pid_file.break_lock()

        daemon = Daemon(options, clilogger)
        context = DaemonContext()
        context.pidfile = pid_file
        context.stdout = sys.stdout
        context.stderr = sys.stderr
        _fileno = self.clilogger.get_syslog_fileno()
        if _fileno != -1:
            context.files_preserve = [_fileno]

        context.signal_map = {signal.SIGTERM: daemon.shutdown, signal.SIGINT: daemon.shutdown}

        if self.options.foreground:
            self.logger.info("Starting service in foreground")
            try:
                daemon.run(self.options.foreground)
            except (SystemExit, KeyboardInterrupt):
                daemon.shutdown(2, None)
        else:
            with context:
                self.logger.info(
                    "Starting service with pid %d", pid_file.read_pid())
                try:
                    daemon.run(foreground=False)
                except SystemExit:
                    daemon.shutdown(2, None)


def main(options):
    app = CreateApp(options=options)
    app.run_app()


if __name__ == '__main__':
    main(configure_options())
