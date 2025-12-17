"""Climate platform for Hisense Multi-IDU."""
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODE_MAP, FAN_MAP

# Fan mode constants (possible fan modes)
FAN_MODES = ["auto", "low", "medium", "high"]

class HisenseIDUClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Hisense indoor unit (climate)."""
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO]
    _attr_fan_modes = ["auto", "low", "medium", "high"]
    _attr_min_temp = 16
    _attr_max_temp = 30

    def __init__(self, coordinator, ip: str, s: int, address: int):
        """Initialize the climate entity for a specific indoor unit."""
        super().__init__(coordinator)
        self._s = s
        self._addr = address
        self._unit_key = f"S{s}_{address}"
        # Unique ID for this climate entity
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"{ip_slug}_climate_s{s}_{address}"
        # Name set to include S and address for identification (IDU S1 1.2 format)
        prefix_num = s
        self._attr_name = f"IDU S{s} {prefix_num}.{address}"
        # Associate entity with device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU AC"
        }

    @property
    def current_temperature(self):
        """Return current room temperature of the unit."""
        data = self.coordinator.data.get(self._unit_key)
        if data:
            return data.get("current_temp")
        return None

    @property
    def target_temperature(self):
        """Return the target temperature (setpoint) of the unit."""
        data = self.coordinator.data.get(self._unit_key)
        if data:
            return data.get("target_temp")
        return None

    @property
    def hvac_mode(self):
        """Return the current HVAC mode (Heating/Cooling/Off etc)."""
        data = self.coordinator.data.get(self._unit_key)
        if not data:
            return None
        mode = data.get("mode")
        if mode == "off":
            return HVACMode.OFF
        if mode == "cool":
            return HVACMode.COOL
        if mode == "heat":
            return HVACMode.HEAT
        if mode == "dry":
            return HVACMode.DRY
        if mode == "fan":
            # represent fan-only mode
            return HVACMode.FAN_ONLY
        if mode == "fan_only":
            return HVACMode.FAN_ONLY
        if mode == "auto":
            return HVACMode.AUTO
        return None

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        data = self.coordinator.data.get(self._unit_key)
        if data:
            return data.get("fan")
        return None

    @property
    def available(self):
        """Return True if this entity is available (data is valid)."""
        # Mark available if coordinator update succeeded and this unit has data
        return bool(self.coordinator.last_update_success and self.coordinator.data.get(self._unit_key) is not None)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature for the indoor unit."""
        # Temperature to set
        target_temp = kwargs.get('temperature')
        if target_temp is None:
            return
        # Use last known mode and fan
        data = self.coordinator.data.get(self._unit_key) or {}
        current_mode = data.get("mode", "cool")
        current_fan = data.get("fan", "auto")
        # If the unit is off, do not set temperature
        if current_mode == "off":
            return
        # Determine numeric codes for mode and fan from strings
        mode_code = next((code for code, name in MODE_MAP.items() if name == current_mode), None)
        fan_code = next((code for code, name in FAN_MAP.items() if name == current_fan), None)
        if mode_code is None:
            # default to cool mode if unknown
            mode_code = 1
        if fan_code is None:
            fan_code = 0  # default auto
        # Send command to device
        client = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["client"]
        try:
            # Construct set command URL
            url = f"http://{client._host}/cgi/set_unit_status.cgi?S={self._s}&ID={self._addr}&ONOFF=1&MODE={mode_code}&TEMP={int(target_temp)}&FAN={fan_code}"
            async with client._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return
        except Exception:
            return
        # Force refresh of data
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set a new HVAC mode (or turn on/off) for this unit."""
        client = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["client"]
        power = 1
        mode_code = 1  # default to cool
        # Map HVACMode to mode code and power
        if hvac_mode == HVACMode.OFF:
            power = 0
            data = self.coordinator.data.get(self._unit_key) or {}
            last_mode = data.get("mode", "cool")
            mode_code = next((code for code, name in MODE_MAP.items() if name == last_mode), 1)
        elif hvac_mode == HVACMode.COOL:
            mode_code = 1
        elif hvac_mode == HVACMode.HEAT:
            mode_code = 4
        elif hvac_mode == HVACMode.DRY:
            mode_code = 2
        elif hvac_mode == HVACMode.FAN_ONLY:
            mode_code = 3
        elif hvac_mode == HVACMode.AUTO:
            mode_code = 0
        # Use last known setpoint and fan for turning on
        data = self.coordinator.data.get(self._unit_key) or {}
        set_temp = data.get("target_temp", 24)
        fan_mode = data.get("fan", "auto")
        fan_code = next((code for code, name in FAN_MAP.items() if name == fan_mode), 0)
        try:
            url = f"http://{client._host}/cgi/set_unit_status.cgi?S={self._s}&ID={self._addr}&ONOFF={power}&MODE={mode_code}&TEMP={int(set_temp if set_temp else 24)}&FAN={fan_code}"
            async with client._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return
        except Exception:
            return
        # Force refresh
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str):
        """Set a new fan mode for the unit."""
        client = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["client"]
        # Use last known mode and temp
        data = self.coordinator.data.get(self._unit_key) or {}
        current_mode = data.get("mode", "cool")
        current_temp = data.get("target_temp", 24)
        power = 1
        if current_mode == "off":
            # if off, treat as turning on with last mode
            current_mode = data.get("mode", "cool")
        mode_code = next((code for code, name in MODE_MAP.items() if name == current_mode), 1)
        fan_code = next((code for code, name in FAN_MAP.items() if name == fan_mode), 0)
        try:
            url = f"http://{client._host}/cgi/set_unit_status.cgi?S={self._s}&ID={self._addr}&ONOFF={power}&MODE={mode_code}&TEMP={int(current_temp if current_temp else 24)}&FAN={fan_code}"
            async with client._session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return
        except Exception:
            return
        # Refresh data
        await self.coordinator.async_request_refresh()

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entities for each indoor unit (S1 and S2 addresses 1-8)."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator_climate"]
    ip = entry.data.get("host")
    entities = []
    for s in [1, 2]:
        for address in range(1, 9):
            entities.append(HisenseIDUClimate(coordinator, ip, s, address))
    async_add_entities(entities, update_before_add=False)
