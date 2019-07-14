"""Support for Keba KeContact P30 charging station"""
import logging

from datetime import timedelta

import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

DOMAIN = 'keba_kecontact'

SERVICE_CURRTIME = 'currtime_command'

CONF_CURRENT = 'current'  # Current value in mA. Possible values: 0; 6000 - 63000
CONF_TIME    = 'time'     # Timeout in seconds before the current will be applied. Possible values: 0; 1 - 860400

# Validation of the user's configuration

DEVICE_CONFIG = vol.Schema({
    vol.Optional(CONF_NAME, default='keba_kecontact'): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [DEVICE_CONFIG]),
    })
}, extra=vol.ALLOW_EXTRA)

SCHEMA_SERVICE_CURRTIME = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_CURRENT): vol.Coerce(int),
    vol.Required(CONF_TIME): vol.Coerce(int),
})


def setup(hass, config):
    """Set up the Keba KeContact integration."""

    hass.data.setdefault(DOMAIN, {})

    for device_config in config[DOMAIN][CONF_DEVICES]:
        name = device_config.get(CONF_NAME)
        host = device_config.get(CONF_HOST)
        port = device_config.get(CONF_PORT)

        try:
            gateway = KeContactGateway(host, port, name)
            hass.data[DOMAIN][name] = gateway
        except Exception as ex:
            _LOGGER.error(ex)

    def refresh(event_time):
        """Refresh"""
        _LOGGER.debug("Updating...")
        try:
            for gateway in hass.data[DOMAIN].values():
                gateway.update()
        except Exception as ex:
            _LOGGER.error(ex)

    track_time_interval(hass, refresh, SCAN_INTERVAL)

    def handle_currtime_commnd(call):
        """Send currtime command to Keba KeContact"""
        name = call.data.get(CONF_NAME)
        current = call.data.get(CONF_CURRENT)
        time = call.data.get(CONF_TIME)

        _LOGGER.debug("Send currtime command...")
        try:
            command = 'currtime {!r} {!r} '.format(current, time)
            hass.data[DOMAIN][name].command(command)
        except Exception as ex:
            _LOGGER.error(ex)

    hass.services.register(
        DOMAIN, SERVICE_CURRTIME, handle_currtime_commnd,
        schema=SCHEMA_SERVICE_CURRTIME)

    return True


class KeContactGateway():

    sock = None

    def __init__(self, host, port, name):

        self._name = name
        self._host = host
        self._port = port
        self._server_address = (self._host, self._port)
        self._energy_consumption = None
        self._is_valid = None
        self._report = {}

        if KeContactGateway.sock is None:
            KeContactGateway.sock = self.UDP_create_socket()

        if KeContactGateway.sock:
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

        _LOGGER.debug("Trying to create UDP socket")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

        sock.bind(('', self._port))
        if not sock:
            _LOGGER.error("ERROR Binding socket - " + str(self._port))
        elif sock:
            _LOGGER.debug("Bound to socket: " + str(self._port))
        return sock

    def update(self):
        import json

        for i in range(3):

            report_no = str(i+1)

            message = 'report ' + report_no

            try:
                data, server = self.UDP_send_receive(message)
            except:
                self._is_valid = False
                self._report[report_no] = None
                raise Exception('UDP error')
            try:
                self._report[report_no] = json.loads(data)
            except:
                _LOGGER.warning("Data received is no JSON: {!r}".format(data))
                self._is_valid = False
                self._report[report_no] = None
                raise Exception('JSON error')

        self._is_valid = True

    def handshake(self):

            try:
                data, server = self.UDP_send_receive('i')
            except:
                _LOGGER.error("Handshake failed")
                raise Exception('Handshake error')

            if data is None:
                _LOGGER.error("Handshake failed")
                raise Exception('Handshake error')

    def command(self, message):

            try:
                self.handshake()
                data, server = self.UDP_send_receive(message)
            except:
                raise Exception('UDP error')

            if data.decode() != 'TCH-OK :done\n':
                _LOGGER.error("Command failed: {!r}".format(message))

    def UDP_send_receive(self, message, timeout=2):
        import time

        try:
            # empty receive buffer
            KeContactGateway.sock.settimeout(0.01)
            data, server = KeContactGateway.sock.recvfrom(1024)
            _LOGGER.error('unexpected data received {!r} from {!r}'.format(data, server))

        except:
            _LOGGER.debug('Receive buffer was empty')


        try:
            # set timeout
            KeContactGateway.sock.settimeout(timeout)

            # Send data
            if message is not None:
                _LOGGER.debug('sending {!r}'.format(message))
                sent = KeContactGateway.sock.sendto(message.encode(), self._server_address)

                time.sleep(0.1)

            # Receive response
            _LOGGER.debug('waiting to receive')
            data, server = KeContactGateway.sock.recvfrom(1024)
            _LOGGER.debug('received {!r} from {!r}'.format(data, server))

            return data, server

        except:
            raise

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
