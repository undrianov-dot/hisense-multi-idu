from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

class HisenseEnergySensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, ip: str):
        super().__init__(coordinator)
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"{ip_slug}_energy_meter"
        self._attr_name = "Hisense электросчётчик"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU",
            "configuration_url": f"http://{ip}"
        }

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self):
        raw_value = self.coordinator.data
        if isinstance(raw_value, (float, int)):
            return round(raw_value / 1000, 2)
        return None

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_sensor"]
    ip = data["host"]
    async_add_entities([HisenseEnergySensor(coordinator, ip)], update_before_add=False)
