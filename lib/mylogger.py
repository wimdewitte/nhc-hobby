import sys
import logging
import logging.handlers
from cmd2 import style, ansi

LOG_FORMAT = "%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s"

class mylogger(object):
    def __init__(self, name, loglevel):
        self.logger = logging.getLogger(name)
        self.set_loglevel(['i'])


    def set_loglevel(self, args):
        if len(args) != 1:
            self.cli_info("Current loglevel: {}".format(logging.getLevelName(self._loglevel)))
            return
        if args[0][0] == 'd':
            self._loglevel = logging.DEBUG
        elif args[0][0] == 'i':
            self._loglevel = logging.INFO
        elif args[0][0] == 'w':
            self._loglevel = logging.WARNING
        elif args[0][0] == 'e':
            self._loglevel = logging.ERROR
        else:
            self.cli_error("arg1: d(ebug), i(nfo), w(arning), e(rror)")
            return

        self.logger.setLevel(self._loglevel)
        self.cli_info("loglevel {}".format(logging._levelToName[self._loglevel]))


    def set_logger_stream(self):
        stream_formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt='%H:%M:%S')
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(stream_formatter)
        stream_handler.set_name("stream")
        self.logger.addHandler(stream_handler)


    def set_logger_syslog(self):
        syslog_formatter = logging.Formatter('%(name)s[%(process)d]: %(message)s')
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
        syslog_handler.setFormatter(syslog_formatter)
        syslog_handler.set_name("syslog")
        self.logger.addHandler(syslog_handler)


    def get_syslog_fileno(self):
        i = 0
        while i < len(self.logger.handlers):
            if self.logger.handlers[i].name == "syslog":
                return self.logger.handlers[i].socket.fileno()
            i += 1
        return -1


    def get_logger(self):
        return self.logger

    def _cli_print(self, level, color, msg):
        colored_str = ansi.style(msg, fg=color)
        print(colored_str)
        if len(msg) == 0:
            return
        if level == logging.INFO:
            self.logger.info(msg)
        elif level == logging.WARNING:
            self.logger.warning(msg)
        elif level == logging.ERROR:
            self.logger.error(msg)

    def cli_neutral(self, msg):
        self._cli_print(logging.DEBUG, "reset", msg)

    def cli_info(self, msg):
        self._cli_print(logging.INFO, "green", msg)

    def cli_warning(self, msg):
        self._cli_print(logging.WARNING, "yellow", msg)

    def cli_error(self, msg):
        self._cli_print(logging.ERROR, "red", msg)
