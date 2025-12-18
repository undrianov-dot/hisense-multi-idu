"""Sensor platform for Hisense Multi-IDU (power meter)."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

class HisensePowerMeter(CoordinatorEntity, SensorEntity):
    """Representation of the Hisense power meter sensor."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, ip: str):
        """Initialize the power meter sensor entity."""
        super().__init__(coordinator)
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"{ip_slug}_power_meter"
        self._attr_name = "Электросчётчик"
        # Device info to link with climate devices
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU",
            "configuration_url": f"http://{ip}"
        }

    @property
    def available(self):
        """Return True if sensor data is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data is not None)

    @property
    def native_value(self):
        """Return the current power consumption value."""
        data = self.coordinator.data
        
        # Если данные недоступны
        if data is None:
            return "Недоступно"
        
        # Если число, возвращаем как float
        try:
            return float(data)
        except (ValueError, TypeError):
            # Если не число, возвращаем как есть
            return data

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return {
            "data_source": "Hisense Multi-IDU Power Meter",
            "status": "online" if self.coordinator.data is not None else "offline"
        }

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Hisense power meter sensor from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_sensor"]
    ip = data["host"]
    
    sensor = HisensePowerMeter(coordinator, ip)
    async_add_entities([sensor], update_before_add=False)
