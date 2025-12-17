import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor"]


class HisenseClient:
    def __init__(self, host: str, session):
        self.host = host
        self._session = session

    async def get_idu_data(self):
        url = f"http://{self.host}/cgi/get_idu_data.shtml"
        try:
            resp = await self._session.get(url)
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.error("Failed to fetch IDU data: %s", err)
            raise

        idu_data = {}
        if isinstance(data, dict) and "dats" in data:
            for unit in data["dats"]:
                unit_id = unit.get("id") or unit.get("uid") or unit.get("name")
                if unit_id:
                    idu_data[unit_id] = unit
        elif isinstance(data, list):
            for unit in data:
                unit_id = unit.get("id") or unit.get("uid") or unit.get("name")
                if unit_id:
                    idu_data[unit_id] = unit
        _LOGGER.debug("Fetched IDU data: %s", idu_data)
        return idu_data

    async def get_meter_data(self):
        url = f"http://{self.host}/cgi/get_meter_pwr.shtml"
        payload = {"ids": ["1", "2"], "ip": self.host}
        try:
            resp = await self._session.post(url, json=payload)
            resp.raise_for_status()
            data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.error("Failed to fetch meter data: %s", err)
            raise

        if isinstance(data, dict) and "dats" in data and data["dats"]:
            value = data["dats"][0].get("pwr") or data["dats"][0].get("power")
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        _LOGGER.warning("Unexpected meter data format: %s", data)
        return None

    async def set_idu(self, idu_id: str, **kwargs):
        url = f"http://{self.host}/cgi/set_idu_data.shtml"
        payload = {"id": idu_id, "ip": self.host}
        payload.update(kwargs)
        try:
            resp = await self._session.post(url, json=payload)
            resp.raise_for_status()
            _LOGGER.debug("Set IDU %s with payload %s", idu_id, payload)
        except Exception as err:
            _LOGGER.error("Failed to set IDU data for %s: %s", idu_id, err)
            raise


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    host = entry.data.get("host")

    if not host:
        raise ConfigEntryNotReady("Missing host configuration")

    client = HisenseClient(host, session)

    coordinator_climate = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_climate",
        update_method=client.get_idu_data,
        update_interval=timedelta(seconds=30),
    )

    coordinator_energy = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_energy",
        update_method=client.get_meter_data,
        update_interval=timedelta(seconds=60),
    )

    try:
        await coordinator_climate.async_config_entry_first_refresh()
        await coordinator_energy.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Error connecting to Hisense controller: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator_climate": coordinator_climate,
        "coordinator_energy": coordinator_energy,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True
