import logging

import voluptuous as vol

from . import DOMAIN

# Import the device class from the component that you want to support
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

# SCAN_INTERVAL = timedelta(minutes=1)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=''): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the Keba KeContact platform."""

    # Assign configuration variables. The configuration check takes care they are
    # present. 
    name = config.get(CONF_NAME)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    gateway = hass.data.get(DOMAIN)

    # Verify that passed in configuration works
    if not gateway.is_valid:
        _LOGGER.error("No valid data received from Keba KeContact")
        return False

    # Add devices
    add_entities([KebaKeContactSensor(name, unit_of_measurement, gateway)], True)



class KebaKeContactSensor(Entity):

    def __init__(self, name, unit_of_measurement, gateway):
        self._name = gateway.name + '_' + name
        self._unique_id = gateway.host + '_' + name
        self._unit_of_measurement = unit_of_measurement
        self._gateway = gateway
        self._state = None

        self.update()

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return an unique identifier for this entity."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement


    def update(self):
        """Update state of sensor."""
        try:
            if self._gateway.is_valid:
                self._state = self._gateway.getreportdata(self._name)

                if self._name == "E total":
                    self._state = self._state / 10
            else:
                self._state = None
        except Exception as ex:
            _LOGGER.error(ex)
