"""Sensor platform for Hisense Multi-IDU (energy meter like in YAML)."""
import logging
from homeassistant.components.sensor import (
    SensorEntity, 
    SensorDeviceClass, 
    SensorStateClass
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class HisenseRawMeter(CoordinatorEntity, SensorEntity):
    """Raw sensor from Hisense (like in YAML)."""
    
    def __init__(self, coordinator, ip: str):
        """Initialize the raw sensor entity."""
        super().__init__(coordinator)
        self._ip = ip
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"hisense_meter_raw_{ip_slug}"
        self._attr_name = "Hisense raw meter"
        self._attr_icon = "mdi:meter-electric"
        
        # Device info to link with hub device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU Hub ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU Hub",
            "configuration_url": f"http://{ip}"
        }

    @property
    def available(self):
        """Return True if sensor data is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data is not None)

    @property
    def native_value(self):
        """Return the raw power value."""
        data = self.coordinator.data
        
        if data is None:
            return None
        
        try:
            # Возвращаем значение как есть (в ватт-часах)
            return float(data)
        except (ValueError, TypeError):
            return data

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        data = self.coordinator.data
        attrs = {
            "data_source": "Hisense Multi-IDU Raw Meter",
            "status": "online" if data is not None else "offline",
            "ip_address": self._ip,
        }
        
        return attrs


class HisenseEnergyMeter(CoordinatorEntity, SensorEntity):
    """Energy meter that converts watt-hours to kilowatt-hours."""
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2
    
    def __init__(self, coordinator, ip: str):
        """Initialize the energy meter entity."""
        super().__init__(coordinator)
        self._ip = ip
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"hisense_meter_energy_{ip_slug}"
        self._attr_name = "Hisense электросчётчик"
        
        # Device info to link with hub device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU Hub ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU Hub",
            "configuration_url": f"http://{ip}"
        }

    @property
    def available(self):
        """Return True if sensor data is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data is not None)

    @property
    def native_value(self):
        """Return the energy value in kWh."""
        data = self.coordinator.data
        
        if data is None:
            return None
        
        try:
            # Конвертируем ватт-часы в киловатт-часы
            # Как в YAML: (pwr / 1000)
            power_wh = float(data)
            power_kwh = power_wh / 1000.0
            return round(power_kwh, 2)
            
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        data = self.coordinator.data
        attrs = {
            "data_source": "Hisense Multi-IDU",
            "status": "online" if data is not None else "offline",
            "ip_address": self._ip,
        }
        
        if data is not None:
            try:
                attrs["raw_value_wh"] = float(data)
                attrs["raw_value_kwh"] = round(float(data) / 1000, 3)
            except (ValueError, TypeError):
                attrs["raw_value"] = data
        
        return attrs


class HisensePowerSensor(CoordinatorEntity, SensorEntity):
    """Power sensor that calculates current power from energy difference."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_suggested_display_precision = 3
    
    def __init__(self, coordinator, ip: str):
        """Initialize the power sensor entity."""
        super().__init__(coordinator)
        self._ip = ip
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"hisense_power_current_{ip_slug}"
        self._attr_name = "Текущая мощность"
        
        # Device info to link with hub device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU Hub ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU Hub",
            "configuration_url": f"http://{ip}"
        }
        
        # Для расчета текущей мощности
        self._last_energy = None
        self._last_update_time = None
        self._current_power = 0.0

    @property
    def available(self):
        """Return True if sensor data is available."""
        return bool(self.coordinator.last_update_success and self.coordinator.data is not None)

    @property
    def native_value(self):
        """Return the current power in kW."""
        import time
        
        data = self.coordinator.data
        
        if data is None:
            return round(self._current_power, 3)
        
        try:
            current_energy = float(data)  # текущая энергия в ватт-часах
            current_time = time.time()
            
            if self._last_energy is not None and self._last_update_time is not None:
                # Вычисляем разницу энергии в ватт-часах
                energy_diff_wh = current_energy - self._last_energy
                
                # Вычисляем разницу времени в часах
                time_diff_hours = (current_time - self._last_update_time) / 3600.0
                
                if time_diff_hours > 0:
                    # Мощность (кВт) = разница энергии (Вт·ч) / разница времени (ч) / 1000
                    power_kw = (energy_diff_wh / time_diff_hours) / 1000.0
                    
                    # Сглаживаем значение (можно убрать, если не нужно)
                    if self._current_power == 0:
                        self._current_power = power_kw
                    else:
                        self._current_power = 0.7 * self._current_power + 0.3 * power_kw
            
            # Обновляем предыдущие значения
            self._last_energy = current_energy
            self._last_update_time = current_time
            
            return round(self._current_power, 3)
            
        except (ValueError, TypeError):
            return round(self._current_power, 3)

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        import time
        
        data = self.coordinator.data
        attrs = {
            "data_source": "Hisense Multi-IDU Power Calculation",
            "status": "online" if data is not None else "offline",
            "ip_address": self._ip,
            "calculated_power_kw": round(self._current_power, 3),
        }
        
        if data is not None:
            try:
                attrs["current_energy_wh"] = float(data)
                attrs["current_energy_kwh"] = round(float(data) / 1000, 3)
            except (ValueError, TypeError):
                attrs["current_energy"] = data
        
        return attrs


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Hisense sensors from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_sensor"]
    ip = data["host"]
    
    _LOGGER.info("Setting up energy and power sensors for IP: %s", ip)
    
    entities = []
    
    # 1. Сырой сенсор (как в YAML)
    entities.append(HisenseRawMeter(coordinator, ip))
    
    # 2. Счетчик энергии в кВт·ч (основной)
    entities.append(HisenseEnergyMeter(coordinator, ip))
    
    # 3. Расчетный датчик текущей мощности (опционально)
    entities.append(HisensePowerSensor(coordinator, ip))
    
    async_add_entities(entities, update_before_add=False)
