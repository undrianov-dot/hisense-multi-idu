"""Sensor platform for Hisense Multi-IDU (energy meter like in YAML)."""
import logging
from homeassistant.components.sensor import (
    SensorEntity, 
    SensorDeviceClass, 
    SensorStateClass
)
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class HisenseEnergyMeter(CoordinatorEntity, SensorEntity):
    """Representation of the Hisense energy meter (like in YAML config)."""
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2
    
    def __init__(self, coordinator, ip: str):
        """Initialize the energy meter entity."""
        super().__init__(coordinator)
        self._ip = ip
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"hisense_meter_energy_{ip_slug}"  # Как в YAML
        self._attr_name = "Hisense электросчётчик"  # Как в YAML
        
        # Device info to link with hub device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU Hub ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU Hub",
            "configuration_url": f"http://{ip}"
        }
        
        # Для накопления энергии
        self._last_power = None
        self._last_update_time = None
        self._total_energy = 0.0

    @property
    def available(self):
        """Return True if sensor data is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data is not None)

    @property
    def native_value(self):
        """Return the total energy consumption in kWh."""
        import time
        
        data = self.coordinator.data
        
        if data is None:
            return round(self._total_energy, 2)
        
        try:
            current_power = float(data)  # мощность в ваттах
            current_time = time.time()
            
            # Накапливаем энергию
            if self._last_power is not None and self._last_update_time is not None:
                time_diff_hours = (current_time - self._last_update_time) / 3600.0
                avg_power = (self._last_power + current_power) / 2.0
                energy_kwh = (avg_power * time_diff_hours) / 1000.0
                self._total_energy += energy_kwh
            
            # Обновляем значения
            self._last_power = current_power
            self._last_update_time = current_time
            
            return round(self._total_energy, 2)
            
        except (ValueError, TypeError):
            return round(self._total_energy, 2)

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        import time
        
        data = self.coordinator.data
        attrs = {
            "data_source": "Hisense Multi-IDU",
            "status": "online" if data is not None else "offline",
            "ip_address": self._ip,
            "total_energy_kwh": round(self._total_energy, 3),
            "current_power_w": data if data is not None else 0,
        }
        
        return attrs


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Hisense energy meter from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_sensor"]
    ip = data["host"]
    
    _LOGGER.info("Setting up energy meter for IP: %s", ip)
    
    sensor = HisenseEnergyMeter(coordinator, ip)
    async_add_entities([sensor], update_before_add=False)
