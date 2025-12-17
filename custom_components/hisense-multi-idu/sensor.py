import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class HisenseEnergySensor(CoordinatorEntity, SensorEntity):
    """Датчик для учета электроэнергии (электросчётчик Hisense)."""

    def __init__(self, coordinator, client):
        """Инициализация датчика энергопотребления."""
        super().__init__(coordinator)
        self._client = client
        self._attr_name = "Hisense электросчётчик"
        self._attr_unique_id = "hisense_meter_energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        """Текущее значение энергии (кВт·ч)."""
        return self.coordinator.data

    @property
    def device_info(self):
        """Информация об устройстве контроллера (для Device Registry)."""
        return {
            "identifiers": {(DOMAIN, self._client.host)},
            "name": f"Hisense Multi-IDU Controller {self._client.host}",
            "manufacturer": "Hisense",
            "model": "Hisense Multi-IDU Controller"
        }

async def async_setup_entry(hass, entry, async_add_entities):
    """Настройка датчика энергии при добавлении интеграции."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator_energy"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    sensor = HisenseEnergySensor(coordinator, client)
    async_add_entities([sensor])
