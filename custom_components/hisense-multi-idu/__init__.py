"""Hisense Multi-IDU integration."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor"]

class HisenseClient:
    def __init__(self, host, session):
        self.host = host
        self.session = session

    async def get_idu_data(self):
        url = f"http://{self.host}/cgi/get_idu_data.shtml"
        try:
            resp = await self.session.get(url)
            resp.raise_for_status()
            return await resp.json(content_type=None)
        except Exception as e:
            _LOGGER.error("Failed to fetch IDU data: %s", e)
            raise

    async def get_meter_data(self):
        url = f"http://{self.host}/cgi/get_meter_pwr.shtml"
        payload = {"ids": ["1", "2"], "ip": self.host}
        try:
            resp = await self.session.post(url, json=payload)
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            return float(data["dats"][0]["pwr"])
        except Exception as e:
            _LOGGER.error("Failed to fetch power meter data: %s", e)
            return None

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    host = entry.data["host"]

    client = HisenseClient(host, session)

    climate_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_climate",
        update_method=client.get_idu_data,
        update_interval=timedelta(seconds=entry.options.get("scan_interval", 30)),
    )

    sensor_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_sensor",
        update_method=client.get_meter_data,
        update_interval=timedelta(seconds=entry.options.get("meter_interval", 60)),
    )

    await climate_coordinator.async_config_entry_first_refresh()
    await sensor_coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator_climate": climate_coordinator,
        "coordinator_sensor": sensor_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
