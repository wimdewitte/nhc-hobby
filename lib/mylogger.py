import sys
import logging
import logging.handlers
from cmd2 import style, ansi

LOG_FORMAT = "%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s"

class mylogger(object):
    def __init__(self, name, loglevel):
        self.logger = logging.getLogger(name)
        self.set_loglevel(loglevel)


    def set_loglevel(self, level):
        if level == 'd':
            self._loglevel = logging.DEBUG
        elif level == 'i':
            self._loglevel = logging.INFO
        elif level == 'w':
            self._loglevel = logging.WARNING
        else:
            self._loglevel = logging.ERROR
        self.logger.setLevel(self._loglevel)


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

    def cli_neutral(self, msg):
        print(ansi.style(msg, fg="reset"))

    def cli_info(self, msg):
        print(ansi.style(msg, fg="green"))

    def cli_warning(self, msg):
        print(ansi.style(msg, fg="yellow"))

    def cli_error(self, msg):
        print(ansi.style(msg, fg="red"))
