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

SERVICE_CURRTIME = 'currtime_command'

CONF_CURRENT = 'current'  # Current value in mA. Possible values: 0; 6000 - 63000
CONF_TIME    = 'time'     # Timeout in seconds before the current will be applied. Possible values: 0; 1 - 860400

# Validation of the user's configuration
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, default='keba_kecontact'): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
    })
}, extra=vol.ALLOW_EXTRA)

SCHEMA_SERVICE_CURRTIME = vol.Schema({
    vol.Required(CONF_CURRENT): vol.Coerce(int),
    vol.Required(CONF_TIME): vol.Coerce(int),
})


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
        try:
            hass.data[DOMAIN].update()
        except Exception as ex:
            _LOGGER.error(ex)

    track_time_interval(hass, refresh, SCAN_INTERVAL)

    def handle_currtime_commnd(call):
        """Send currtime command to Keba KeContact"""
        current = call.data.get(CONF_CURRENT)
        time = call.data.get(CONF_TIME)

        _LOGGER.debug("Send currtime command...")
        try:
            command = 'currtime {!r} {!r} '.format(current, time)
            hass.data[DOMAIN].command(command)
        except Exception as ex:
            _LOGGER.error(ex)

    hass.services.register(
        DOMAIN, SERVICE_CURRTIME, handle_currtime_commnd,
        schema=SCHEMA_SERVICE_CURRTIME)

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
            self._sock.settimeout(0.01)
            data, server = self._sock.recvfrom(1024)
            _LOGGER.error('unexpected data received {!r} from {!r}'.format(data, server))

        except:
            _LOGGER.debug('Receive buffer was empty')


        try:
            # set timeout
            self._sock.settimeout(timeout)

            # Send data
            if message is not None:
                _LOGGER.debug('sending {!r}'.format(message))
                sent = self._sock.sendto(message.encode(), self._server_address)

                time.sleep(0.1)

            # Receive response
            _LOGGER.debug('waiting to receive')
            data, server = self._sock.recvfrom(1024)
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
