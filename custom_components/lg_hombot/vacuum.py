"""
Support for Wi-Fi enabled LG Hombot robot vacuum cleaner.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.lg_hombot/
"""
import asyncio
import urllib.parse
import voluptuous as vol

import aiohttp
import async_timeout

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
    PLATFORM_SCHEMA
)

_STATE_TO_VACUUM_STATE = {
    "STANDBY": STATE_IDLE,
    "WORKING": STATE_CLEANING,
    "BACKMOVING_INIT": STATE_CLEANING,
    "HOMING": STATE_RETURNING,
    "CHARGING": STATE_DOCKED,
    "DOCKING": STATE_RETURNING,
    "ERROR": STATE_ERROR,
    "PAUSE": STATE_PAUSED,
}

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_NAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import LOGGER, DOMAIN

ATTR_STATE = 'JSON_ROBOT_STATE'
ATTR_BATTERY = 'JSON_BATTPERC'
ATTR_MODE = 'JSON_MODE'
ATTR_REPEAT = 'JSON_REPEAT'
ATTR_LAST_CLEAN = 'CLREC_LAST_CLEAN'
ATTR_TURBO = 'JSON_TURBO'
ATTR_NAME = 'JSON_NICKNAME'

DEFAULT_NAME = 'Hombot'

ICON = 'mdi:robot-vacuum'


FAN_SPEED_NORMAL = 'Normal'
FAN_SPEED_TURBO = 'Turbo'
FAN_SPEEDS = [FAN_SPEED_NORMAL, FAN_SPEED_TURBO]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.string,
}, extra=vol.ALLOW_EXTRA)

# Commonly supported features
SUPPORT_HOMBOT = VacuumEntityFeature.BATTERY | VacuumEntityFeature.START| VacuumEntityFeature.PAUSE | \
                 VacuumEntityFeature.RETURN_HOME | VacuumEntityFeature.SEND_COMMAND | VacuumEntityFeature.STATUS | VacuumEntityFeature.STOP | \
                 VacuumEntityFeature.TURN_OFF | VacuumEntityFeature.TURN_ON | VacuumEntityFeature.FAN_SPEED

async def async_setup_entry(hass, entry, async_add_devices):
    entities = []

    for entry_id, homebot_id in hass.data[DOMAIN].items():
        entity = HombotVacuum(hass, entry=entry)
        entities.append(entity)

    async_add_devices(entities, update_before_add=True)


class HombotVacuum(StateVacuumEntity):
    """Representation of a Hombot vacuum cleaner robot."""

    def __init__(self, hass, entry):
        LOGGER.debug("Initialize the Hombot handler %s", entry.title)
        self._entry = entry  # Store the entry object
        self._battery_level = None
        self._fan_speed = None
        self._is_on = False
        self._name = entry.title
        self._state_attrs = {}
        self._state = None
        self._host = entry.title
        self._port = "6260"
        self._entry_id = entry.entry_id
        self.hass = hass

    @property
    def unique_id(self):
        return self._entry_id

    async def async_config_entry_first_refresh(self):
        LOGGER.debug("async_config_entry_first_refresh")
        await self.async_update()

    async def async_added_to_hass(self):
        LOGGER.debug("async_added_to_hass")
        await self.async_update()

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_HOMBOT

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self._fan_speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return FAN_SPEEDS

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self._battery_level

    @property
    def state(self):
        """Return the status of the vacuum cleaner."""
        return self._state

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    async def async_query(self, command):
        LOGGER.debug('In async_query')
        try:
            websession = async_get_clientsession(self.hass)

            async with async_timeout.timeout(10):
                url = 'http://{}:{}/json.cgi?{}'.format(self._host, self._port, urllib.parse.quote(command, safe=':'))
                LOGGER.debug(url)
                webresponse = await websession.get(url)
                response = await webresponse.read()
            return True
        except asyncio.TimeoutError:
            LOGGER.error("LG Hombot timed out")
            return False
        except aiohttp.ClientError as error:
            LOGGER.error("Error getting LG Hombot data: %s", error)
            return False

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        is_on = await self.async_query('{"COMMAND":"CLEAN_START"}')
        if is_on:
            self._is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        await self.async_return_to_base()

    async def async_start(self, **kwargs):
        """Start the vacuum cleaner."""
        await self.async_turn_on()

    async def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        await self.async_pause()

    async def async_pause(self, **kwargs):
        """Pause the cleaning cycle."""
        is_off = await self.async_query('{"COMMAND":"PAUSE"}')
        if is_off:
            self._is_on = False

    async def async_start_pause(self, **kwargs):
        """Pause the cleaning task or resume it."""
        if self.is_on:
            await self.async_pause()
        else:  # vacuum is off or paused
            await self.async_turn_on()

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        is_on = await self.async_query('{"COMMAND":"HOMING"}')
        if is_on:
            self._is_on = False

    async def async_toggle_turbo(self, **kwargs):
        """Toggle between normal and turbo mode."""
        LOGGER.debug('In toggle')
        await self.async_query('turbo')

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if fan_speed.capitalize() in FAN_SPEEDS:
            fan_speed = fan_speed.capitalize()
            LOGGER.debug("Set fan speed to: %s", fan_speed)
            if fan_speed == FAN_SPEED_NORMAL:
                if self._fan_speed == FAN_SPEED_TURBO:
                    await self.async_toggle_turbo()
            elif fan_speed == FAN_SPEED_TURBO:
                if self._fan_speed == FAN_SPEED_NORMAL:
                    await self.async_toggle_turbo()
            self._fan_speed = fan_speed
        else:
            LOGGER.error("No such fan speed available: %s", fan_speed)
            return

    async def async_send_command(self, command, params, **kwargs):
        """Send raw command."""
        LOGGER.debug("async_send_command %s", command)
        await self.query(command)
        return True

    async def async_update(self):
        LOGGER.debug("Fetch state from the device.")
        response = ''
        try:
            websession = async_get_clientsession(self.hass)

            async with async_timeout.timeout(10):
                url = 'http://{}:{}/status.txt'.format(self._host, self._port)
                webresponse = await websession.get(url)
                bytesresponse = await webresponse.read()
                response = bytesresponse.decode('ascii')
                if len(response) == 0:
                    return False
        except asyncio.TimeoutError:
            LOGGER.error("LG Hombot timed out")
            return False
        except aiohttp.ClientError as error:
            LOGGER.error("Error getting LG Hombot data: %s", error)
            return False

        LOGGER.debug(response)
        all_attrs = {}
        for line in response.splitlines():
            name, var = line.partition("=")[::2]
            all_attrs[name] = var.strip('"')

        self._state = _STATE_TO_VACUUM_STATE[all_attrs[ATTR_STATE]]
        LOGGER.debug("Got new state from the vacuum: %s", self._state)

        self._battery_level = int(all_attrs[ATTR_BATTERY])
        self._name = all_attrs[ATTR_NAME]
        self._is_on = all_attrs[ATTR_STATE] in ['WORKING', 'BACKMOVING_INIT']
        self._fan_speed = FAN_SPEED_TURBO if all_attrs[ATTR_TURBO] == 'true' else FAN_SPEED_NORMAL
        self._state_attrs[ATTR_MODE] = all_attrs[ATTR_MODE]
        self._state_attrs[ATTR_REPEAT] = all_attrs[ATTR_REPEAT]
        self._state_attrs[ATTR_LAST_CLEAN] = all_attrs[ATTR_LAST_CLEAN]
