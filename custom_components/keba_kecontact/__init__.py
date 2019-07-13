"""Support for Keba KeContact P30 charging station"""
import logging

from datetime import timedelta

import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

DOMAIN = 'keba_kecontact'

#SERVICE_WRITE_DATA_BY_NAME = 'write_data_by_name'

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, default='keba_kecontact'): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)

# SCHEMA_SERVICE_WRITE_DATA_BY_NAME = vol.Schema({
#     vol.Required(CONF_ADS_TYPE):
#         vol.In([ADSTYPE_INT, ADSTYPE_UINT, ADSTYPE_BYTE, ADSTYPE_BOOL,
#                 ADSTYPE_DINT, ADSTYPE_UDINT]),
#     vol.Required(CONF_ADS_VALUE): vol.Coerce(int),
#     vol.Required(CONF_ADS_VAR): cv.string,
# })


def setup(hass, config):
    """Set up the Keba KeContact integration."""

    conf = config[DOMAIN]

    name = conf.get(CONF_NAME)
    host = conf.get(CONF_HOST)
    port = conf.get(CONF_PORT)

    try:
        hass.data[DOMAIN] = KeContactGateway(host, port, name)
    except Exception as ex:
        _LOGGER.error(ex)
        return False

    def refresh(event_time):
        """Refresh"""
        _LOGGER.debug("Updating...")
        hass.data[DOMAIN].update()

    track_time_interval(hass, refresh, SCAN_INTERVAL)

    # def handle_write_data_by_name(call):
    #     """Write a value to the connected ADS device."""
    #     ads_var = call.data.get(CONF_ADS_VAR)
    #     ads_type = call.data.get(CONF_ADS_TYPE)
    #     value = call.data.get(CONF_ADS_VALUE)
    #
    #     try:
    #         ads.write_by_name(ads_var, value, ads.ADS_TYPEMAP[ads_type])
    #     except pyads.ADSError as err:
    #         _LOGGER.error(err)
    #
    # hass.services.register(
    #     DOMAIN, SERVICE_WRITE_DATA_BY_NAME, handle_write_data_by_name,
    #     schema=SCHEMA_SERVICE_WRITE_DATA_BY_NAME)

    return True


class KeContactGateway():

    def __init__(self, host, port, name):

        self._name = name
        self._host = host
        self._port = port
        self._server_address = (self._host, self._port)
        self._energy_consumption = None
        self._is_valid = None
        self._report = {}

        self._sock = self.UDP_create_socket()

        if self._sock:
            try:
                self.update()
            except:
                raise

    @property
    def is_valid(self):
        return self._is_valid

    @property
    def host(self):
        return self._host

    @property
    def name(self):
        return self._name

    @property
    def energy_consumption(self):
        return self._energy_consumption

    def UDP_create_socket(self):

        import socket

        _LOGGER.debug("Trying to create socket on: " + self._host + ":" + str(self._port))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
        sock.bind(('', self._port))
        if not sock:
            _LOGGER.error("ERROR Binding socket - " + self._host + ":" + str(self._port))
        elif sock:
            _LOGGER.debug("Bound to socket: " + self._host + ":" + str(self._port))
        return sock

    def update(self):
        import time
        import json

        for i in range(3):

            report_no = str(i+1)

            message = b'report ' + report_no.encode()

            try:
                # Send data
                _LOGGER.debug('sending {!r}'.format(message))
                sent = self._sock.sendto(message, self._server_address)

                time.sleep(0.1)

                # Receive response
                _LOGGER.debug('waiting to receive')
                data, server = self._sock.recvfrom(1024)
                _LOGGER.debug('received {!r}'.format(data))

            except:
                self._is_valid = False
                self._report[report_no] = None
                raise Exception('UDP error')

            try:
                self._report[report_no] = json.loads(data)
            except:
                _LOGGER.warning("Data received is no JSON... ---" + str(data))
                self._is_valid = False
                self._report[report_no] = None
                raise Exception('JSON error')

        self._is_valid = True

    def getreportdata(self, name):
        try:
            return self._report["1"][name]
        except KeyError:
            try:
                return self._report["2"][name]
            except KeyError:
                try:
                    return self._report["3"][name]
                except KeyError:
                    return None
