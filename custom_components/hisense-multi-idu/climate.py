"""Climate platform for Hisense Multi-IDU."""
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, MODE_MAP, MODE_REVERSE_MAP, 
    FAN_MAP, FAN_REVERSE_MAP,
    MODE_COOL, MODE_HEAT, MODE_DRY, MODE_FAN_ONLY
)

_LOGGER = logging.getLogger(__name__)

# Маппинг режимов устройства на HVACMode (без AUTO)
DEVICE_TO_HVAC = {
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dry": HVACMode.DRY,
    "fan_only": HVACMode.FAN_ONLY,
    # Дополнительные режимы перенаправляем в основные
    "auto_dry": HVACMode.DRY,
    "refresh": HVACMode.COOL,
    "sleep": HVACMode.COOL,
    "heat_sup": HVACMode.HEAT
}

# Исправленный маппинг HVAC_TO_DEVICE
HVAC_TO_DEVICE = {
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat", 
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "fan_only",
}

# Доступные скорости вентилятора в Home Assistant (только основные)
HA_FAN_MODES = ["auto", "low", "medium", "high"]

class HisenseIDUClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Hisense indoor unit."""
    
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.TURN_OFF |
        ClimateEntityFeature.TURN_ON
    )
    # Убрали HVACMode.AUTO
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY]
    _attr_fan_modes = HA_FAN_MODES
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1
    
    def __init__(self, coordinator, client, uid, device_info, entity_name=None):
        super().__init__(coordinator)
        self._client = client
        self._uid = uid
        self._device_info = device_info
        
        # Извлекаем sys и addr из uid
        if '_' in uid:
            s_part, addr_part = uid.split('_')
            self._sys = int(s_part[1:])  # Убираем 'S'
            self._addr = int(addr_part)
        else:
            self._sys = 1
            self._addr = 1
        
        # Если передано имя объекта, используем его, иначе берем из device_info
        if entity_name:
            self._attr_name = entity_name
        else:
            self._attr_name = device_info.get("name", f"IDU {uid}")
            
        self._attr_unique_id = f"{DOMAIN}_{uid}"
        self._attr_device_info = device_info
        
        # Кэш текущих данных
        self._current_data = {}
        # Кэш последней успешной команды для предотвращения отключения
        self._last_command = {
            "onoff": 1,
            "mode": MODE_COOL,
            "fan": 4,
            "temp": 24
        }
    
    def _update_data(self):
        """Обновляет данные из координатора."""
        data = self.coordinator.data
        if not data:
            self._current_data = {}
            return
        
        unit_data = data.get(self._uid, {})
        if unit_data:
            self._current_data = unit_data
            # Обновляем кэш последней команды актуальными данными
            self._last_command = {
                "onoff": unit_data.get("power", 1),
                "mode": unit_data.get("mode_code", MODE_COOL),
                "fan": unit_data.get("fan_code", 4),
                "temp": unit_data.get("set_temp", 24)
            }
        else:
            self._current_data = {}
    
    @property
    def available(self):
        """Доступно ли устройство."""
        self._update_data()
        return bool(self._current_data)
    
    @property
    def target_temperature(self):
        self._update_data()
        return self._current_data.get("set_temp", 24)
    
    @property
    def current_temperature(self):
        self._update_data()
        return self._current_data.get("room_temp")
    
    @property
    def hvac_mode(self):
        self._update_data()
        if not self._current_data:
            return HVACMode.OFF
        
        power = self._current_data.get("power", 0)
        if power == 0:
            return HVACMode.OFF
        
        mode = self._current_data.get("mode", "cool")
        return DEVICE_TO_HVAC.get(mode, HVACMode.COOL)
    
    @property
    def fan_mode(self):
        self._update_data()
        fan = self._current_data.get("fan", "auto")
        # Преобразуем нестандартные скорости в стандартные
        if fan not in HA_FAN_MODES:
            if "low" in fan:
                return "low"
            elif "medium" in fan or "mid" in fan:
                return "medium"
            elif "high" in fan:
                return "high"
            else:
                return "auto"
        return fan
    
    @property
    def extra_state_attributes(self):
        """Возвращает дополнительные атрибуты."""
        self._update_data()
        attrs = {}
        
        if self._current_data:
            attrs.update({
                "error_code": self._current_data.get("error_code", 0),
                "status": self._current_data.get("status", "unknown"),
                "code": self._current_data.get("code", ""),
                "indoor_name": self._current_data.get("indoor_name", ""),
                "tenant_name": self._current_data.get("tenant_name", ""),
                "pipe_temperature": self._current_data.get("pipe_temp"),
                "is_locked": self._current_data.get("model1", 0) == 1,
                "original_fan": self._current_data.get("fan", ""),
                "original_mode": self._current_data.get("mode", ""),
                "sys": self._sys,
                "addr": self._addr,
                "uid": self._uid
            })
        
        return attrs
    
    async def async_set_temperature(self, **kwargs):
        """Установить целевую температуру."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Используем параметры из последней команды
        onoff = self._last_command.get("onoff", 1)
        mode_code = self._last_command.get("mode", MODE_COOL)
        fan_code = self._last_command.get("fan", 4)
        
        # Всегда включаем устройство при изменении температуры
        if onoff == 0:
            onoff = 1
            _LOGGER.debug("Device was off, turning on for temperature change")
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=onoff,
            mode=mode_code,
            fan=fan_code,
            temp=int(temperature)
        )
        
        if success:
            # Обновляем кэш
            self._last_command.update({
                "onoff": onoff,
                "temp": int(temperature)
            })
            # Обновляем локальный кэш
            self._current_data["set_temp"] = int(temperature)
            self._current_data["power"] = 1
            _LOGGER.debug("Temperature set successfully for %s to %s°C", self._uid, temperature)
            # Запрашиваем обновление от координатора
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set temperature for %s", self._uid)
    
    async def async_set_hvac_mode(self, hvac_mode):
        """Установить режим HVAC."""
        if hvac_mode == HVACMode.OFF:
            # Выключить устройство
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=0,
                mode=MODE_COOL,
                fan=4,
                temp=24
            )
            if success:
                self._last_command["onoff"] = 0
        else:
            # Включить устройство с нужным режимом
            
            # Преобразуем HVACMode в режим устройства
            device_mode = HVAC_TO_DEVICE.get(hvac_mode, "cool")
            mode_code = MODE_REVERSE_MAP.get(device_mode, MODE_COOL)
            
            # Используем текущую температуру
            current_temp = self._current_data.get("set_temp", 24) if self._current_data else 24
            fan_code = self._current_data.get("fan_code", 4) if self._current_data else 4
            
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(current_temp)
            )
            
            if success:
                self._last_command.update({
                    "onoff": 1,
                    "mode": mode_code,
                    "fan": fan_code,
                    "temp": int(current_temp)
                })
        
        if success:
            # Обновляем локальный кэш
            if hvac_mode == HVACMode.OFF:
                self._current_data["power"] = 0
            else:
                self._current_data["power"] = 1
                self._current_data["mode_code"] = mode_code
                self._current_data["mode"] = device_mode
            _LOGGER.debug("HVAC mode set successfully for %s to %s", self._uid, hvac_mode)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set HVAC mode for %s", self._uid)
    
    async def async_set_fan_mode(self, fan_mode):
        """Установить скорость вентилятора."""
        # Преобразуем строку в код устройства (только основные скорости)
        fan_code = FAN_REVERSE_MAP.get(fan_mode, 4)
        
        # Используем параметры из последней команды
        onoff = self._last_command.get("onoff", 1)
        mode_code = self._last_command.get("mode", MODE_COOL)
        current_temp = self._last_command.get("temp", 24)
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=onoff,
            mode=mode_code,
            fan=fan_code,
            temp=int(current_temp)
        )
        
        if success:
            self._last_command["fan"] = fan_code
            self._current_data["fan_code"] = fan_code
            self._current_data["fan"] = fan_mode
            if onoff == 0:  # Если устройство было выключено, включаем его
                self._current_data["power"] = 1
                self._last_command["onoff"] = 1
            _LOGGER.debug("Fan mode set successfully for %s to %s", self._uid, fan_mode)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set fan mode for %s", self._uid)
    
    async def async_turn_on(self):
        """Включить кондиционер."""
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=1,
            mode=self._last_command.get("mode", MODE_COOL),
            fan=self._last_command.get("fan", 4),
            temp=self._last_command.get("temp", 24)
        )
        
        if success:
            self._last_command["onoff"] = 1
            self._current_data["power"] = 1
            _LOGGER.debug("Device %s turned on", self._uid)
            await self.coordinator.async_request_refresh()
    
    async def async_turn_off(self):
        """Выключить кондиционер."""
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=0,
            mode=MODE_COOL,
            fan=4,
            temp=24
        )
        
        if success:
            self._last_command["onoff"] = 0
            self._current_data["power"] = 0
            _LOGGER.debug("Device %s turned off", self._uid)
            await self.coordinator.async_request_refresh()

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    host = data["host"]
    
    entities = []
    
    # ФИКСИРОВАННОЕ ИМЯ УСТРОЙСТВА (Device) - это изменит название устройства в HA
    hub_device_name = f"Hisense Multi-IDU Hub ({host})"
    
    # Базовая информация об устройстве (Device)
    base_device_info = {
        "identifiers": {(DOMAIN, host)},
        "name": hub_device_name,  # ФИКСИРОВАННОЕ имя устройства
        "manufacturer": "Hisense",
        "model": "Multi-IDU Hub",
        "configuration_url": f"http://{host}"
    }
    
    # Создаем сущности для каждого кондиционера
    coordinator_data = coordinator.data
    _LOGGER.info("Setting up climate entities. Coordinator data type: %s, value: %s", 
                 type(coordinator_data), coordinator_data)
    
    if isinstance(coordinator_data, dict) and coordinator_data:
        for uid, unit_data in coordinator_data.items():
            _LOGGER.info("Processing device UID: %s, data: %s", uid, unit_data)
            
            if not unit_data:
                _LOGGER.warning("Empty data for device %s, skipping", uid)
                continue
            
            # Получаем оригинальное имя объекта (Entity) из данных устройства
            original_name = unit_data.get("name", f"IDU {uid}")
            
            # Создаем информацию об устройстве для этого блока
            entity_device_info = base_device_info.copy()
            
            # Добавляем дополнительную информацию, НЕ ТРОГАЯ "name"
            suggested_area = unit_data.get("pppname") or unit_data.get("ppname") or unit_data.get("pname")
            if suggested_area:
                entity_device_info["suggested_area"] = suggested_area
            
            entity_device_info.update({
                "via_device": (DOMAIN, host),
            })
            
            # Создаем объект с оригинальным именем (Entity), но с device_info хаба
            entities.append(HisenseIDUClimate(
                coordinator, client, uid, entity_device_info, entity_name=original_name
            ))
            _LOGGER.info("Created climate entity for %s with name: %s", uid, original_name)
    else:
        _LOGGER.warning("No valid data in coordinator. Type: %s, Data: %s", 
                       type(coordinator_data), coordinator_data)
        # Попробуем получить данные напрямую
        try:
            _LOGGER.info("Trying to get data directly from client")
            direct_data = await client.get_idu_data(force_refresh=True)
            if direct_data and isinstance(direct_data, dict):
                _LOGGER.info("Got data directly: %s devices", len(direct_data))
                for uid, unit_data in direct_data.items():
                    if unit_data:
                        original_name = unit_data.get("name", f"IDU {uid}")
                        
                        entity_device_info = base_device_info.copy()
                        suggested_area = unit_data.get("pppname") or unit_data.get("ppname") or unit_data.get("pname")
                        if suggested_area:
                            entity_device_info["suggested_area"] = suggested_area
                        
                        entity_device_info.update({"via_device": (DOMAIN, host)})
                        
                        entities.append(HisenseIDUClimate(
                            coordinator, client, uid, entity_device_info, entity_name=original_name
                        ))
                        _LOGGER.info("Created climate entity from direct data: %s", uid)
        except Exception as e:
            _LOGGER.error("Failed to get direct data: %s", e)
    
    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info("Successfully created %s climate entities. Hub name: %s", 
                    len(entities), hub_device_name)
    else:
        _LOGGER.error("No climate entities created. Check device connection to %s", host)
        # Создаем хотя бы одну тестовую сущность для отладки
        test_uid = "S1_1"
        entity_device_info = base_device_info.copy()
        entity_device_info.update({"via_device": (DOMAIN, host)})
        
        test_entity = HisenseIDUClimate(
            coordinator, client, test_uid, entity_device_info, entity_name="Test IDU"
        )
        entities.append(test_entity)
        async_add_entities(entities, update_before_add=True)
        _LOGGER.warning("Created test entity for debugging")
