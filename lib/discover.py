import os
import logging
import socket
import struct


class discoverNHC(object):
    def __init__(self, logger, host=None):
        self.logger = logger
        self.host = host

    def _decode_discover(self, data):
        frame = {}
        frame["type"] = data[1]
        if data[1] == 0x3B:
            frame["device"] = "CoCo"
        elif data[1] == 0x3C:
            frame["device"] = "SmartBox+"
        else:
            frame["device"] = ""
        frame["nhcmac"] = "{:02x}:{:02x}:{:02x}:{:02x}".format(data[2], data[3], data[4], data[5])
        frame["ip"] = "{}.{}.{}.{}".format(str(data[6]), str(data[7]), str(data[8]), str(data[9]))
        frame["mask"] = "{}.{}.{}.{}".format(str(data[10]), str(data[11]), str(data[12]), str(data[13]))
        sw_major, sw_minor, sw_bugfix, sw_build = struct.unpack("<HHHH", data[17:25])
        frame["sw"] = "{}.{}.{}.{}".format(str(sw_major), str(sw_minor), str(sw_bugfix), str(sw_build))
        self.logger.info("discovered a %s with IP=%s and SW=%s", frame["device"], frame["ip"], frame["sw"])
        return frame

    def discover(self):
        try:
            socket.gethostbyname(self.host)
            self.logger.info("using predefined gateway %s", self.host)
            return self.host
        except:
            pass
        message = b'D'
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind(('', 10000))
        s.settimeout(2.0)
        s.sendto(message,('<broadcast>', 10000))
        self.gateway = None
        try:
            while True:
                data = s.recv(30)
                if len(data) > 14:
                    self.gateway = self._decode_discover(data)
                    if self.gateway["device"] == "CoCo":
                        break
        except socket.timeout:
            pass
        finally:
            s.close()
        if self.gateway is None:
            self.logger.info("did not discover a gateway")
            return None
        self.host = self.gateway["ip"]
        return self.host
