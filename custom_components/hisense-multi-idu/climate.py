from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FAN_REVERSE_MAP, FAN_MAP, MODE_REVERSE_MAP, MODE_MAP

class HisenseClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.TURN_OFF |
        ClimateEntityFeature.FAN_MODE
    )
    _attr_hvac_modes = [HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.OFF]
    _attr_fan_modes = ["low", "medium", "high", "auto"]

    def __init__(self, coordinator, client, uid, ip):
        super().__init__(coordinator)
        self._client = client
        self._uid = uid
        self._ip = ip
        self._attr_unique_id = f"idu_{uid}"
        self._attr_name = f"IDU {uid}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{ip}-{uid}")},
            "name": f"Hisense Multi-IDU ({ip})",
            "manufacturer": "Hisense",
            "model": "Indoor Unit",
            "configuration_url": f"http://{ip}"
        }

    @property
    def target_temperature(self):
        return self.coordinator.data[self._uid].get("set_temp", 25)

    @property
    def hvac_mode(self):
        status = self.coordinator.data[self._uid].get("power", 0)
        model = self.coordinator.data[self._uid].get("mode", MODE_MAP["cool"])
        if status == 0:
            return HVACMode.OFF
        return MODE_REVERSE_MAP.get(model, HVACMode.COOL)

    @property
    def fan_mode(self):
        wind = self.coordinator.data[self._uid].get("fan_speed", 1)
        return FAN_REVERSE_MAP.get(wind, "medium")

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._client.set_idu(self._uid, set_temp=temp)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self._client.set_idu(self._uid, power=0)
        else:
            await self._client.set_idu(self._uid, power=1, mode=MODE_MAP[hvac_mode])
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode):
        await self._client.set_idu(self._uid, fan_speed=FAN_MAP[fan_mode])
        await self.coordinator.async_request_refresh()

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    ip = data["host"]
    entities = [HisenseClimate(coordinator, client, uid, ip) for uid in coordinator.data]
    async_add_entities(entities, update_before_add=True)
