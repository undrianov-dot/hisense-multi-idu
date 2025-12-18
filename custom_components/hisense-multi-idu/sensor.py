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
            "model": "Multi-IDU AC"
        }

    @property
    def available(self):
        """Return True if sensor data is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data is not None)

    @property
    def native_value(self):
        """Return the current power consumption value."""
        # The coordinator data holds the latest power value
        return self.coordinator.data

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Hisense power meter sensor from config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator_sensor"]
    ip = entry.data.get("host")
    sensor = HisensePowerMeter(coordinator, ip)
    async_add_entities([sensor], update_before_add=False)
