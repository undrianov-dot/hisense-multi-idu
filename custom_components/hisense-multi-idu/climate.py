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
        self._last_command = {}
    
    def _update_data(self):
        """Обновляет данные из координатора."""
        data = self.coordinator.data
        if not data:
            self._current_data = {}
            return
        
        unit_data = data.get(self._uid, {})
        if unit_data:
            self._current_data = unit_data
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
                "original_mode": self._current_data.get("mode", "")
            })
        
        return attrs
    
    async def async_set_temperature(self, **kwargs):
        """Установить целевую температуру."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        self._update_data()
        if not self._current_data:
            _LOGGER.warning("No data available for %s", self._uid)
            return
        
        # Определяем, включено ли устройство в данный момент
        current_power = self._current_data.get("power", 0)
        current_mode = self._current_data.get("mode", "cool")
        current_fan = self._current_data.get("fan", "auto")
        
        # Если устройство выключено, включаем его с последними параметрами
        if current_power == 0 and self._last_command:
            # Используем параметры из последней успешной команды
            onoff = 1
            mode_code = self._last_command.get("mode", MODE_COOL)
            fan_code = self._last_command.get("fan", 4)
            _LOGGER.debug("Device was off, using last command params: mode=%s, fan=%s", 
                         mode_code, fan_code)
        else:
            # Используем текущие параметры
            onoff = 1 if current_power == 1 else 1  # Всегда включаем при изменении температуры
            mode_code = self._current_data.get("mode_code", MODE_COOL)
            fan_code = self._current_data.get("fan_code", 4)
            _LOGGER.debug("Using current params: power=%s, mode=%s, fan=%s", 
                         current_power, mode_code, fan_code)
        
        # Сохраняем команду в кэш
        self._last_command = {
            "onoff": onoff,
            "mode": mode_code,
            "fan": fan_code,
            "temp": int(temperature)
        }
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=onoff,
            mode=mode_code,
            fan=fan_code,
            temp=int(temperature)
        )
        
        if success:
            _LOGGER.debug("Temperature set successfully for %s to %s°C", self._uid, temperature)
            # Немедленно обновляем локальный кэш для быстрого отклика
            self._current_data["set_temp"] = int(temperature)
            self._current_data["power"] = 1
            # Запрашиваем полное обновление от координатора
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set temperature for %s", self._uid)
    
    async def async_set_hvac_mode(self, hvac_mode):
        """Установить режим HVAC."""
        self._update_data()
        
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
                self._last_command = {"onoff": 0}
        else:
            # Включить устройство с нужным режимом
            
            # Преобразуем HVACMode в режим устройства
            device_mode = HVAC_TO_DEVICE.get(hvac_mode, "cool")
            mode_code = MODE_REVERSE_MAP.get(device_mode, MODE_COOL)
            
            # Используем текущую температуру и скорость вентилятора
            current_temp = self._current_data.get("set_temp", 24) if self._current_data else 24
            fan_code = self._current_data.get("fan_code", 4) if self._current_data else 4
            
            # Сохраняем команду в кэш
            self._last_command = {
                "onoff": 1,
                "mode": mode_code,
                "fan": fan_code,
                "temp": int(current_temp)
            }
            
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(current_temp)
            )
        
        if success:
            _LOGGER.debug("HVAC mode set successfully for %s to %s", self._uid, hvac_mode)
            # Немедленно обновляем локальный кэш
            if hvac_mode == HVACMode.OFF:
                self._current_data["power"] = 0
            else:
                self._current_data["power"] = 1
                self._current_data["mode_code"] = mode_code
                self._current_data["mode"] = device_mode
            # Запрашиваем обновление от координатора
            await self.coordinator.async_request_refresh()
    
    async def async_set_fan_mode(self, fan_mode):
        """Установить скорость вентилятора."""
        self._update_data()
        if not self._current_data:
            return
        
        # Преобразуем строку в код устройства (только основные скорости)
        fan_code = FAN_REVERSE_MAP.get(fan_mode, 4)
        
        # Получаем текущие параметры
        onoff = 1 if self._current_data.get("power", 0) == 1 else 1  # Всегда включаем
        mode_code = self._current_data.get("mode_code", MODE_COOL)
        current_temp = self._current_data.get("set_temp", 24)
        
        # Сохраняем команду в кэш
        self._last_command = {
            "onoff": onoff,
            "mode": mode_code,
            "fan": fan_code,
            "temp": int(current_temp)
        }
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=onoff,
            mode=mode_code,
            fan=fan_code,
            temp=int(current_temp)
        )
        
        if success:
            _LOGGER.debug("Fan mode set successfully for %s to %s", self._uid, fan_mode)
            # Немедленно обновляем локальный кэш
            self._current_data["fan_code"] = fan_code
            self._current_data["fan"] = fan_mode
            self._current_data["power"] = 1
            # Запрашиваем обновление от координатора
            await self.coordinator.async_request_refresh()
    
    async def async_turn_on(self):
        """Включить кондиционер."""
        self._update_data()
        
        # Используем параметры из последней команды или текущие
        if self._last_command and "mode" in self._last_command:
            mode_code = self._last_command.get("mode", MODE_COOL)
            fan_code = self._last_command.get("fan", 4)
            current_temp = self._last_command.get("temp", 24)
        elif self._current_data:
            mode_code = self._current_data.get("mode_code", MODE_COOL)
            fan_code = self._current_data.get("fan_code", 4)
            current_temp = self._current_data.get("set_temp", 24)
        else:
            mode_code = MODE_COOL
            fan_code = 4
            current_temp = 24
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=1,
            mode=mode_code,
            fan=fan_code,
            temp=int(current_temp)
        )
        
        if success:
            _LOGGER.debug("Device %s turned on", self._uid)
            self._current_data["power"] = 1
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
            _LOGGER.debug("Device %s turned off", self._uid)
            self._last_command = {"onoff": 0}
            self._current_data["power"] = 0
            await self.coordinator.async_request_refresh()

# Остальной код без изменений...
