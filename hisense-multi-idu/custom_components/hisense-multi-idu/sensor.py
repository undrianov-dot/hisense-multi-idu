import logging
import json
import aiohttp
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Deprecated setup; not used with config entry."""
    return


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Hisense meter sensor from config entry."""
    host = hass.data[DOMAIN].get("host")
    if not host:
        _LOGGER.error("Hisense meter: missing 'host' in configuration")
        return

    async def async_update_data():
        payload = {"ids": ["1", "2"], "ip": host}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{host}/cgi/get_meter_pwr.shtml",
                    json=payload,
                    timeout=5
                ) as response:
                    if response.status != 200:
                        raise ValueError(f"Bad response status: {response.status}")
                    text = await response.text()
                    data = json.loads(text)
                    return data
        except Exception as err:
            _LOGGER.warning("Error fetching Hisense meter data: %s", err)
            return None

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Hisense Meter Sensor",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities([HisenseMeterSensor(coordinator)], True)


class HisenseMeterSensor(CoordinatorEntity, SensorEntity):
    """Representation of Hisense power meter."""

    _attr_name = "Hisense электросчётчик"
    _attr_unique_id = "hisense_meter_energy"
    _attr_device_class = "energy"
    _attr_state_class = "total_increasing"
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

    def __init__(self, coordinator: DataUpdateCoordinator):
        super().__init__(coordinator)
        self._state = None

    @property
    def native_value(self):
        try:
            dats = self.coordinator.data.get("dats")
            if dats and len(dats) > 0 and "pwr" in dats[0]:
                return round(float(dats[0]["pwr"]) / 1000, 2)
        except Exception as e:
            _LOGGER.debug("Parsing error: %s", e)
        return None
