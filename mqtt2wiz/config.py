#!/usr/bin/env python
import collections
import os
import sys
from collections import namedtuple
import yaml

from mqtt2wiz import log

CFG_FILENAME = os.path.dirname(os.path.abspath(__file__)) + "/../config/config.yaml"
Info = namedtuple("Info", "mqtt knobs cfg_globals devices raw_cfg")


class Cfg:
    _info = None  # class (or static) variable

    def __init__(self):
        pass

    @property
    def mqtt_host(self):
        attr = self._get_info().mqtt
        if isinstance(attr, collections.abc.Mapping):
            return attr.get("host", "192.168.1.100")
        return "192.168.1.100"

    @property
    def mqtt_client_id(self):
        attr = self._get_info().mqtt
        if isinstance(attr, collections.abc.Mapping):
            return attr.get("client_id", "mqtt2wiz")
        return "mqtt2wiz"

    @property
    def mqtt_username(self):
        attr = self._get_info().mqtt
        if isinstance(attr, collections.abc.Mapping):
            return attr.get("username", None)
        return None

    @property
    def mqtt_password(self):
        attr = self._get_info().mqtt
        if isinstance(attr, collections.abc.Mapping):
            return attr.get("password", None)
        return None

    @property
    def reconnect_interval(self):
        attr = self._get_info().mqtt
        if isinstance(attr, collections.abc.Mapping):
            return attr.get("reconnect_interval", 15)
        return 15

    @property
    def knobs(self):
        return self._get_info().knobs

    def mqtt_topic(self, device_name):
        devices = self._get_info().devices
        if isinstance(devices, collections.abc.Mapping):
            device_attributes = devices.get(device_name, {})
            if device_attributes.get("topic"):
                return device_attributes["topic"].format(device_name)
        cfg_globals = self._get_info().cfg_globals
        topic_format = cfg_globals.get("topic_format")
        if topic_format:
            return topic_format.format(device_name)
        else:
            logger.debug("using default /{}/ topic")
            return "/{}/".format(device_name)

    @property
    def devices(self):
        return self._get_info().devices

    @classmethod
    def _get_config_filename(cls):
        if len(sys.argv) > 1:
            return sys.argv[1]
        return CFG_FILENAME

    @classmethod
    def _get_info(cls):
        if not cls._info:
            config_filename = cls._get_config_filename()
            logger.info("loading yaml config file %s", config_filename)
            with open(config_filename, "r") as ymlfile:
                raw_cfg = yaml.safe_load(ymlfile)
                cls._parse_raw_cfg(raw_cfg)
        return cls._info

    @classmethod
    def _parse_raw_cfg(cls, raw_cfg):
        cfg_globals = raw_cfg.get("globals", {})
        assert isinstance(cfg_globals, dict)
        devices = raw_cfg.get("devices")
        assert isinstance(devices, dict)

        cls._info = Info(
            raw_cfg.get("mqtt"),
            raw_cfg.get("knobs", {}),
            cfg_globals,
            devices,
            raw_cfg
        )


# =============================================================================


logger = log.getLogger()
if __name__ == "__main__":
    log.initLogger()
    c = Cfg()
    logger.info("c.knobs: {}".format(c.knobs))
    logger.info("c.mqtt_host: {}".format(c.mqtt_host))
    logger.info("c.globals: {}".format(c.cfg_globals))
    logger.info("c.locations: {}".format(c.locations))
