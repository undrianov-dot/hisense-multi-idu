from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

class HisenseClimate(ClimateEntity, CoordinatorEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator, client, uid):
        super().__init__(coordinator)
        self._client = client
        self._uid = uid
        self._attr_name = f"IDU {uid}"
        self._attr_unique_id = f"idu_{uid}"

    @property
    def target_temperature(self):
        return self.coordinator.data[self._uid].get("set_temp", 25)

    @property
    def hvac_mode(self):
        status = self.coordinator.data[self._uid].get("power", 0)
        return HVACMode.OFF if status == 0 else HVACMode.COOL

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp:
            await self._client.set_idu(self._uid, set_temp=temp)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        power = 0 if hvac_mode == HVACMode.OFF else 1
        await self._client.set_idu(self._uid, power=power)
        await self.coordinator.async_request_refresh()

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    entities = [HisenseClimate(coordinator, client, uid) for uid in coordinator.data]
    async_add_entities(entities, update_before_add=True)
