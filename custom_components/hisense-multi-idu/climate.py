import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

# Карта HVAC режимов Home Assistant -> коды режимов устройства
MODE_HVAC_MAP = {
    HVACMode.AUTO: 0,
    HVACMode.COOL: 1,
    HVACMode.DRY: 2,
    HVACMode.FAN_ONLY: 3,
    HVACMode.HEAT: 4
}
# Обратная карта: код режима устройства -> HVACMode Home Assistant
HVAC_MAP_INV = {v: k for k, v in MODE_HVAC_MAP.items()}

# Карта режимов вентилятора
FAN_MODE_MAP = {
    "Auto": 0,
    "Low": 1,
    "Medium": 2,
    "High": 3
}
# Обратная карта для получения названия по коду
FAN_MODE_MAP_INV = {v: k for k, v in FAN_MODE_MAP.items()}

_LOGGER = logging.getLogger(__name__)

class HisenseIDUClimate(CoordinatorEntity, ClimateEntity):
    """Класс климатического устройства для внутреннего блока Hisense (IDU)."""

    def __init__(self, coordinator, client, idu_id: str):
        """Инициализация климатической сущности IDU."""
        super().__init__(coordinator)
        self._client = client
        self._id = idu_id
        # Формирование дружественного имени, например "IDU S1 1-2"
        parts = idu_id.split('_')
        if parts[0].startswith('s'):
            system_num = parts[0][1:]
        else:
            system_num = parts[0]
        self._attr_name = f"IDU S{system_num} {parts[1]}-{parts[2]}"
        # Уникальный ID для сущности климата (соответствует идентификатору IDU)
        self._attr_unique_id = idu_id
        # Поддерживаемые возможности: установка температуры и скорость вентилятора
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        # Поддерживаемые режимы HVAC (включая выключение)
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT]
        # Единица температуры – градусы Цельсия
        self._attr_temperature_unit = TEMP_CELSIUS
        # Возможные режимы вентилятора
        self._attr_fan_modes = list(FAN_MODE_MAP.keys())

    @property
    def current_temperature(self):
        """Текущая температура воздуха, сообщаемая внутренним блоком."""
        data = self.coordinator.data.get(self._id, {}) or {}
        # Попытаемся получить значение по одному из возможных ключей
        return data.get("current_temperature") or data.get("current_temp") or data.get("room_temp") or data.get("temp_current")

    @property
    def target_temperature(self):
        """Установленная (целевая) температура кондиционера."""
        data = self.coordinator.data.get(self._id, {}) or {}
        return data.get("set_temperature") or data.get("set_temp") or data.get("target_temp")

    @property
    def hvac_mode(self):
        """Текущий режим работы HVAC (охлаждение, обогрев, и т.д., либо Off)."""
        data = self.coordinator.data.get(self._id, {}) or {}
        power = data.get("power")
        # Если питание выключено (power=0 или "off"), возвращаем OFF
        if power == 0 or (isinstance(power, str) and power.lower() == "off"):
            return HVACMode.OFF
        mode_code = data.get("mode")
        return HVAC_MAP_INV.get(mode_code, HVACMode.OFF)

    @property
    def fan_mode(self):
        """Текущая скорость вентилятора."""
        data = self.coordinator.data.get(self._id, {}) or {}
        fan_code = data.get("fan_speed") or data.get("fan") or data.get("fan_mode")
        return FAN_MODE_MAP_INV.get(fan_code)

    @property
    def min_temp(self):
        """Минимально допустимая температура установки (например, 16°C)."""
        return 16

    @property
    def max_temp(self):
        """Максимально допустимая температура установки (например, 30°C)."""
        return 30

    @property
    def device_info(self):
        """Информация о устройстве (для Device Registry)."""
        return {
            "identifiers": {(DOMAIN, self._id)},
            "name": self.name,
            "manufacturer": "Hisense",
            "model": "Hisense Multi-IDU Indoor Unit",
            "via_device": (DOMAIN, self._client.host)
        }

    async def async_set_hvac_mode(self, hvac_mode: str):
        """Установить новый режим работы (или выключить устройство)."""
        if hvac_mode == HVACMode.OFF:
            # Выключаем питание
            await self._client.set_idu(self._id, power=0)
        else:
            # Включаем питание и устанавливаем требуемый режим
            mode_code = MODE_HVAC_MAP.get(hvac_mode)
            await self._client.set_idu(self._id, power=1, mode=mode_code)
        # После команды сразу запрашиваем обновление данных
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        """Установить новую целевую температуру."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        await self._client.set_idu(self._id, set_temp=temp)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str):
        """Установить новую скорость вентилятора."""
        if fan_mode not in FAN_MODE_MAP:
            _LOGGER.error("Unsupported fan mode: %s", fan_mode)
            return
        fan_code = FAN_MODE_MAP[fan_mode]
        await self._client.set_idu(self._id, fan_speed=fan_code)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        """Выключить кондиционер (питание off)."""
        await self._client.set_idu(self._id, power=0)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self):
        """Включить кондиционер (питание on, режим прежний)."""
        await self._client.set_idu(self._id, power=1)
        await self.coordinator.async_request_refresh()

async def async_setup_entry(hass, entry, async_add_entities):
    """Настройка всех климат-сущностей (IDU) на основе полученных данных."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator_climate"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    entities = []
    # Создаем сущности для всех IDU, имеющихся в данных
    for idu_id in coordinator.data.keys():
        entities.append(HisenseIDUClimate(coordinator, client, idu_id))
    async_add_entities(entities)
