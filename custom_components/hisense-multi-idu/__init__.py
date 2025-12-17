"""Hisense Multi-IDU integration initialization."""
import asyncio
import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL_CLIMATE, DEFAULT_SCAN_INTERVAL_SENSOR, API_METER_PATH, API_UNIT_STATUS_PATH, MODE_MAP, FAN_MAP

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "sensor"]

class HisenseClient:
    """Client to interact with the Hisense Multi-IDU device."""
    def __init__(self, host: str, session: aiohttp.ClientSession):
        """Initialize the client with device IP and aiohttp session."""
        self._host = host
        self._session = session
    
    async def fetch_unit_status(self, s: int, address: int):
        """Fetch status of a single indoor unit (S1/S2 and address). Returns dict or None on failure."""
        url = f"http://{self._host}{API_UNIT_STATUS_PATH}?S={s}&ID={address}"
        try:
            async with self._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    _LOGGER.warning(f"Non-200 response from {url}: {resp.status}")
                    return None
                text = await resp.text()
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Timeout fetching data from unit S{s} address {address}")
            return None
        except aiohttp.ClientError as err:
            _LOGGER.warning(f"Client error fetching data from unit S{s} address {address}: {err}")
            return None
        
        # Parse the response text for unit status
        # Expected format (example guess): "<power>,<mode>,<set_temp>,<room_temp>,<fan>"
        data = {}
        if text:
            # Remove any whitespace or HTML tags that might be present
            content = text.strip().strip('\r\n')
            # If content includes any HTML structure, attempt to extract numeric values
            # For simplicity, try comma-separated parsing
            parts = [p.strip() for p in content.split(',')]
            if len(parts) >= 5:
                # Parse power (on/off)
                power_raw = parts[0].lower()
                if power_raw in ('1', 'on', 'true'):
                    power_on = True
                else:
                    power_on = False
                # Parse mode
                mode_raw = parts[1].lower()
                mode_str = None
                if mode_raw.isdigit():
                    mode_code = int(mode_raw)
                    mode_str = MODE_MAP.get(mode_code)
                else:
                    # assume text like "cool", "heat", etc.
                    mode_str = mode_raw
                # Parse temperatures
                try:
                    set_temp = float(parts[2])
                except ValueError:
                    set_temp = None
                try:
                    room_temp = float(parts[3])
                except ValueError:
                    room_temp = None
                # Parse fan mode
                fan_raw = parts[4].lower()
                fan_str = None
                if fan_raw.isdigit():
                    fan_code = int(fan_raw)
                    fan_str = FAN_MAP.get(fan_code)
                else:
                    fan_str = fan_raw
                if mode_str:
                    data = {
                        "power": power_on,
                        "mode": "off" if not power_on else mode_str,
                        "target_temp": set_temp,
                        "current_temp": room_temp,
                        "fan": fan_str
                    }
        return data if data else None

    async def fetch_all_units(self):
        """Fetch status for all indoor units (S1 & S2, addresses 1-8). Returns dict of data per unit."""
        results = {}
        tasks = []
        keys = []
        # Create tasks for all combinations of S and address
        for s in [1, 2]:
            for address in range(1, 9):
                keys.append(f"S{s}_{address}")
                tasks.append(self.fetch_unit_status(s, address))
        # Gather results concurrently
        fetch_results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, result in enumerate(fetch_results):
            key = keys[idx]
            if isinstance(result, Exception):
                # If any unhandled exception occurred, log and mark as None
                _LOGGER.error(f"Error fetching data for {key}: {result}")
                results[key] = None
            else:
                results[key] = result
        return results

    async def fetch_power_meter(self):
        """Fetch power meter reading from the device. Returns float (power) or None on error."""
        url = f"http://{self._host}{API_METER_PATH}"
        try:
            async with self._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    _LOGGER.warning(f"Non-200 response from power meter endpoint: {resp.status}")
                    raise UpdateFailed(f"Failed to fetch power meter data: HTTP {resp.status}")
                text = await resp.text()
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout fetching power meter data")
            raise UpdateFailed("Timeout fetching power meter data")
        except aiohttp.ClientError as err:
            _LOGGER.warning(f"Client error fetching power meter: {err}")
            raise UpdateFailed(f"Power meter fetch error: {err}")
        # Parse the power value from text
        value = None
        content = text.strip()
        if content:
            # Try to extract a number (float or int)
            # Remove any non-numeric characters except dot and minus
            import re
            match = re.search(r"(-?\d+\.?\d*)", content)
            if match:
                num_str = match.group(1)
                try:
                    if '.' in num_str:
                        value = float(num_str)
                    else:
                        value = int(num_str)
                except ValueError:
                    value = None
        return value

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up integration via YAML is not supported."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Hisense Multi-IDU from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data.get("host")
    session = aiohttp_client.async_get_clientsession(hass)
    client = HisenseClient(host, session)
    # Create coordinators for climate and sensor
    coordinator_climate = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_climate",
        update_method=client.fetch_all_units,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_CLIMATE),
    )
    coordinator_sensor = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_sensor",
        update_method=client.fetch_power_meter,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SENSOR),
    )
    # Fetch initial data
    await coordinator_climate.async_config_entry_first_refresh()
    await coordinator_sensor.async_config_entry_first_refresh()
    # Store references
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator_climate": coordinator_climate,
        "coordinator_sensor": coordinator_sensor,
    }
    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Remove entry from hass.data
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
