import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
    FAN_HIGH,
    FAN_MEDIUM,
    FAN_LOW,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


FAN_MAP = {
    "low": FAN_LOW,
    "medium": FAN_MEDIUM,
    "high": FAN_HIGH,
}
FAN_REVERSE_MAP = {v: k for k, v in FAN_MAP.items()}


class HisenseClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_hvac_modes = [HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY, HVACMode.OFF]
    _attr_fan_modes = list(FAN_MAP.values())
    _attr_min_temp = 16
    _attr_max_temp = 30

    def __init__(self, coordinator, client, uid):
        super().__init__(coordinator)
        self._client = client
        self._uid = uid
        self._attr_name = f"IDU {uid}"
        self._attr_unique_id = f"idu_{uid}"

    def _unit_data(self):
        raw = self.coordinator.data.get(self._uid)
        if isinstance(raw, dict):
            return raw
        _LOGGER.warning("No valid data for IDU %s: %s", self._uid, raw)
        return {}

    @property
    def target_temperature(self):
        return self._unit_data().get("set_temp", 25)

    @property
    def current_temperature(self):
        return self._unit_data().get("current_temp")

    @property
    def hvac_mode(self):
        unit = self._unit_data()
        if unit.get("power", 0) == 0:
            return HVACMode.OFF
        return unit.get("mode", HVACMode.COOL)

    @property
    def fan_mode(self):
        fan = self._unit_data().get("fan", "medium")
        return FAN_MAP.get(fan, FAN_MEDIUM)

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp:
            await self._client.set_idu(self._uid, set_temp=temp)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        payload = {}
        if hvac_mode == HVACMode.OFF:
            payload["power"] = 0
        else:
            payload = {"power": 1, "mode": hvac_mode}
        await self._client.set_idu(self._uid, **payload)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode):
        fan_str = FAN_REVERSE_MAP.get(fan_mode, "medium")
        await self._client.set_idu(self._uid, fan=fan_str)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    entities = []

    for uid, unit in coordinator.data.items():
        if isinstance(unit, dict):
            entities.append(HisenseClimate(coordinator, client, uid))
        else:
            _LOGGER.warning("Skipping IDU %s due to invalid data: %s", uid, unit)

    async_add_entities(entities, update_before_add=True)
