"""Sensor platform for Hisense Multi-IDU (power meter)."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class HisensePowerMeter(CoordinatorEntity, SensorEntity):
    """Representation of the Hisense power meter sensor."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
_attr_suggested_display_precision = 3  # 3 знака после запятой

@property
def native_value(self):
    data = self.coordinator.data
    if data is None:
        return "Недоступно"
    try:
        # Конвертируем ватты в киловатты
        return round(float(data) / 1000, 3)
    except (ValueError, TypeError):
        return data
    # Добавляем предложение для единицы измерения (опционально)
    _attr_suggested_unit_of_measurement = UnitOfPower.KILO_WATT

    def __init__(self, coordinator, ip: str):
        """Initialize the power meter sensor entity."""
        super().__init__(coordinator)
        self._ip = ip
        ip_slug = ip.replace('.', '_')
        self._attr_unique_id = f"{DOMAIN}_power_meter_{ip_slug}"
        self._attr_name = "Электросчётчик"
        
        # Device info to link with climate devices
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ip)},
            "name": f"Hisense Multi-IDU Hub ({ip})",
            "manufacturer": "Hisense",
            "model": "Multi-IDU Hub",
            "configuration_url": f"http://{ip}"
        }
        
        _LOGGER.debug("Power meter sensor created for IP: %s", ip)

    @property
    def available(self):
        """Return True if sensor data is available."""
        available = bool(self.coordinator.last_update_success and self.coordinator.data is not None)
        _LOGGER.debug("Power meter available: %s", available)
        return available

    @property
    def native_value(self):
        """Return the current power consumption value in watts."""
        data = self.coordinator.data
        
        # Если данные недоступны
        if data is None:
            _LOGGER.debug("Power meter data is None")
            return "Недоступно"
        
        # Если число, возвращаем как float (в ваттах)
        try:
            value = float(data)
            _LOGGER.debug("Power meter value: %s W", value)
            return value
        except (ValueError, TypeError) as e:
            _LOGGER.debug("Power meter data is not float: %s (error: %s)", data, e)
            return data

    @property
    def suggested_display_precision(self):
        """Return suggested display precision."""
        return 0  # Показывать целые числа

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        data = self.coordinator.data
        attrs = {
            "data_source": "Hisense Multi-IDU Power Meter",
            "status": "online" if data is not None else "offline",
            "ip_address": self._ip,
            "last_update_success": self.coordinator.last_update_success
        }
        
        # Если есть данные, добавляем в киловаттах для удобства
        if data is not None and isinstance(data, (int, float)):
            attrs["power_kw"] = round(data / 1000, 3)  # В киловаттах
        
        return attrs

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Hisense power meter sensor from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_sensor"]
    ip = data["host"]
    
    _LOGGER.info("Setting up power meter sensor for IP: %s", ip)
    
    sensor = HisensePowerMeter(coordinator, ip)
    async_add_entities([sensor], update_before_add=False)

