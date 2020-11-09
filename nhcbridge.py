#!/usr/bin/env python3

import sys
import os
import logging
import signal
import time
import distro
from traceback import format_exc
from argparse import ArgumentParser
from daemon import DaemonContext
from lockfile.pidlockfile import PIDLockFile
from settings import CONFIG
from lib.discover import discoverNHC
from lib.hobby_api import hobbyAPI
from lib.hass import Hass
from lib.bridge_prompt import prompt
from lib.nhc_control import NHCcontrol
from lib.mylogger import mylogger
import subprocess
from subprocess import PIPE, run


DAEMONNAME = "hobbyAPI"


class AppFailed(Exception):
    def __init__(self, message):
        super(Exception, self).__init__(message)


def configure_options():
    parser = ArgumentParser(description="NHC Hass bridge")
    parser.add_argument("-l", "--log-level",
                        dest="log_level",
                        type=int,
                        required=False,
                        default=4,
                        help=("Set default logging level: 1=Errors only, 2=Warnings, 3=Info, 4=Debug"))
    parser.add_argument("-f", "--foreground",
                        dest="foreground",
                        action='store_true',
                        required=False,
                        default=False,
                        help=("Run in foreground"))
    parser.add_argument("-a", "--action",
                        dest="action",
                        required=False,
                        default="start",
                        help=("Action (start,stop,pid)"))
    options, unknown_args = parser.parse_known_args()

    # Perform surgery on sys.argv to remove the arguments which have already been processed by argparse
    sys.argv = sys.argv[:1] + unknown_args

    if options.log_level == 1:
        options.log_level = logging.ERROR
    elif options.log_level == 2:
        options.log_level = logging.WARNING
    elif options.log_level == 3:
        options.log_level = logging.INFO
    else:
        options.log_level = logging.DEBUG
    
    options.abspath = os.path.abspath(os.path.dirname(__file__))
    options.appname = DAEMONNAME
    options.ca_cert_hobby = os.path.join(options.abspath, CONFIG.CA_CERT_HOBBY)
    options.password_hobby = CONFIG.PASSWORD_HOBBY

    return options


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
        self.linux_distribution = distro.id()

    def run(self, foreground=False):
        while True:
            try:
                self.logger.info("NHC Bridge started")
                discover = discoverNHC(self.logger)
                self.host = discover.discover()
                if self.host is None:
                    self.logger.fatal("no COCO found")
                    return 1
                self.hobby = hobbyAPI(self.logger, self.options.ca_cert_hobby, self.options.password_hobby, host=self.host)
                self.hass = Hass(self.logger, hobby=self.hobby)
                self.nhccontrol = NHCcontrol(self.logger, self.hobby)
                self.hobby.start()
                self.hass.start()
                self.hobby.set_callbacks(self.hass.nhc_status_update)

                # give some time to connect
                time.sleep(3)
                self.running = overall_status(self.logger, self.hobby, self.hass)

                # start infinite while loop
                if foreground:
                    app = prompt(CONFIG, self.clilogger, self.nhccontrol, self.hass)
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
        self._foreground = options.foreground
        self._action = options.action
        self._pidfile = None

    def run_app(self):
        self.clilogger = mylogger(self.options.appname, self.options.log_level)
        if self._foreground:
            self.clilogger.set_logger_stream()
        else:
            self.clilogger.set_logger_syslog()
        self.logger = self.clilogger.get_logger()
        try:
            self.start_app(self.options, self.clilogger)
        except AppFailed as e:
            self.logger.error("Failed ({0})".format(str(e)))

    def start_app(self, options, clilogger):
        if self._action != "start" and self._action != "stop" and self._action != "status" and self._action != "restart":
            raise AppFailed("Invalid action specified")

        if os.access("/var/run/", os.W_OK):
            self._pidfile = "/var/run/" + self.options.appname + ".pid"
        else:
            self._pidfile = "/var/tmp/" + self.options.appname + ".pid"

        pid_file = PIDLockFile(self._pidfile)

        if self._action == "stop":
            if pid_file.is_locked():
                self.logger.info("Stopping service with pid %d", pid_file.read_pid())
                os.kill(pid_file.read_pid(), signal.SIGTERM)
            return 0

        elif self._action == "status":
            if pid_file.is_locked():
                self.logger.info("Service running with pid %d", pid_file.read_pid())
                return 0
            self.logger.info("Service not running")
            return 1

        elif self._action == "start":
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

        if self._foreground:
            self.logger.info("Starting service in foreground")
            try:
                daemon.run(self._foreground)
            except (SystemExit, KeyboardInterrupt):
                daemon.shutdown(2, None)
        else:
            with context:
                self.logger.info("Starting service with pid %d", pid_file.read_pid())
                try:
                    daemon.run(foreground=False)
                except SystemExit:
                    daemon.shutdown(2, None)


def main(options):
    app = CreateApp(options=options)
    app.run_app()


if __name__ == '__main__':
    main(configure_options())
