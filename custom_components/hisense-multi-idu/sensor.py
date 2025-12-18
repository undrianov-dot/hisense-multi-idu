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

    def __init__(self, coordinator, ip: str, hub_info: dict):
        """Initialize the power meter sensor entity."""
        super().__init__(coordinator)
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"{DOMAIN}_power_{ip_slug}"
        self._attr_name = "Электросчётчик"
        self._hub_info = hub_info
        self._ip = ip
        
        # Device info to link with hub device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": hub_info.get("name", f"Hisense Multi-IDU Hub ({ip})"),
            "manufacturer": "Hisense",
            "model": hub_info.get("model", "Multi-IDU Gateway"),
            "configuration_url": f"http://{ip}"
        }

    @property
    def available(self):
        """Return True if sensor data is available."""
        if not self.coordinator.last_update_success:
            return False
        
        data = self.coordinator.data
        # Доступен, если данные есть (даже если None - это означает "недоступен")
        return data is not None

    @property
    def native_value(self):
        """Return the current power consumption value."""
        data = self.coordinator.data
        
        # Если None - счетчик недоступен
        if data is None:
            return "Недоступно"
        
        # Если число, возвращаем как float
        try:
            return float(data)
        except (ValueError, TypeError):
            # Если не число, возвращаем как есть (строка)
            return data

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        attrs = {
            "hub_name": self._hub_info.get("name"),
            "hub_model": self._hub_info.get("model"),
            "ip_address": self._ip
        }
        
        data = self.coordinator.data
        if data is None:
            attrs["status"] = "offline"
        else:
            attrs["status"] = "online"
            
        return attrs

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Hisense power meter sensor from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_sensor"]
    ip = data["host"]
    hub_info = data.get("hub_info", {})
    
    sensor = HisensePowerMeter(coordinator, ip, hub_info)
    async_add_entities([sensor], update_before_add=False)
    _LOGGER.info("Power meter sensor created for hub: %s", hub_info.get("name"))
