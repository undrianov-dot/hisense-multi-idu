"""Climate platform for Hisense Multi-IDU."""
import logging
from homeassistant.components.climate import (
    ClimateEntity, 
    ClimateEntityFeature, 
    HVACMode,
    HVACAction
)
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

# Маппинг режимов устройства на HVACAction
DEVICE_TO_HVAC_ACTION = {
    "cool": HVACAction.COOLING,
    "heat": HVACAction.HEATING,
    "dry": HVACAction.DRYING,
    "fan_only": HVACAction.FAN,
    "auto_dry": HVACAction.DRYING,
    "refresh": HVACAction.COOLING,
    "sleep": HVACAction.COOLING,
    "heat_sup": HVACAction.HEATING
}

HVAC_TO_DEVICE = {v: k for k, v in DEVICE_TO_HVAC.items()}

# Доступные скорости вентилятора в Home Assistant (только основные)
HA_FAN_MODES = ["auto", "low", "medium", "high"]

class HisenseIDUClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Hisense indoor unit (as air conditioner)."""
    
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
    # ДОБАВЛЕНО: шаг изменения температуры 1°C
    _attr_target_temperature_step = 1
    
    # Опционально: задать иконку как кондиционер
    _attr_icon = "mdi:air-conditioner"
    
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
    def hvac_action(self):
        """ВОЗВРАЩАЕТ ТЕКУЩЕЕ ДЕЙСТВИЕ КОНДИЦИОНЕРА (очень важно для правильного отображения!)."""
        self._update_data()
        
        if not self._current_data:
            return HVACAction.OFF
        
        power = self._current_data.get("power", 0)
        if power == 0:
            return HVACAction.OFF
        
        mode = self._current_data.get("mode", "cool")
        
        # Определяем, активно ли устройство (охлаждает/греет) или idle
        # Для этого можно использовать разницу температур
        current_temp = self._current_data.get("room_temp")
        target_temp = self._current_data.get("set_temp", 24)
        
        if current_temp is not None:
            if mode == "cool" and current_temp > target_temp:
                return HVACAction.COOLING
            elif mode == "heat" and current_temp < target_temp:
                return HVACAction.HEATING
            elif mode == "dry":
                return HVACAction.DRYING
            elif mode == "fan_only":
                return HVACAction.FAN
            else:
                # Если температура достигла целевой, устройство idle
                return HVACAction.IDLE
        else:
            # Если нет текущей температуры, используем базовый маппинг
            return DEVICE_TO_HVAC_ACTION.get(mode, HVACAction.IDLE)
    
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
        """Возвращает дополнительные атрибуты для кондиционера."""
        self._update_data()
        attrs = {}
        
        if self._current_data:
            # Основные атрибуты
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
                "device_type": "air_conditioner",  # Явно указываем тип устройства
                "hvac_action": self.hvac_action,  # Добавляем текущее действие
            })
            
            # Только для отладки - сырые данные
            if "raw_data" in self._current_data:
                attrs["raw_power_state"] = self._current_data.get("power")
                attrs["raw_mode_code"] = self._current_data.get("mode_code")
                attrs["raw_fan_code"] = self._current_data.get("fan_code")
        
        return attrs
    
    async def async_set_temperature(self, **kwargs):
        """Установить целевую температуру."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Округляем до целого (так как шаг 1°C)
        temperature = round(temperature)
        
        self._update_data()
        if not self._current_data:
            return
        
        # Получаем текущие параметры
        onoff = 1 if self._current_data.get("power", 0) == 1 else 0
        mode_code = self._current_data.get("mode_code", MODE_COOL)
        fan_code = self._current_data.get("fan_code", 4)
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=onoff,
            mode=mode_code,
            fan=fan_code,
            temp=int(temperature)
        )
        
        if success:
            await self.coordinator.async_request_refresh()
    
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
        else:
            # Включить устройство с нужным режимом
            self._update_data()
            
            # Преобразуем HVACMode в режим устройства
            device_mode = HVAC_TO_DEVICE.get(hvac_mode, "cool")
            mode_code = MODE_REVERSE_MAP.get(device_mode, MODE_COOL)
            
            # Используем текущую температуру и скорость вентилятора
            current_temp = self._current_data.get("set_temp", 24)
            fan_code = self._current_data.get("fan_code", 4)
            
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(current_temp)
            )
        
        if success:
            await self.coordinator.async_request_refresh()
    
    async def async_set_fan_mode(self, fan_mode):
        """Установить скорость вентилятора."""
        self._update_data()
        if not self._current_data:
            return
        
        # Преобразуем строку в код устройства (только основные скорости)
        fan_code = FAN_REVERSE_MAP.get(fan_mode, 4)
        
        # Получаем текущие параметры
        onoff = 1 if self._current_data.get("power", 0) == 1 else 0
        mode_code = self._current_data.get("mode_code", MODE_COOL)
        current_temp = self._current_data.get("set_temp", 24)
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=onoff,
            mode=mode_code,
            fan=fan_code,
            temp=int(current_temp)
        )
        
        if success:
            await self.coordinator.async_request_refresh()
    
    async def async_turn_on(self):
        """Включить кондиционер."""
        self._update_data()
        if not self._current_data:
            return
        
        mode_code = self._current_data.get("mode_code", MODE_COOL)
        fan_code = self._current_data.get("fan_code", 4)
        current_temp = self._current_data.get("set_temp", 24)
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=1,
            mode=mode_code,
            fan=fan_code,
            temp=int(current_temp)
        )
        
        if success:
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
        "model": "Multi-IDU Air Conditioner",  # Изменили модель
        "configuration_url": f"http://{host}"
    }
    
    # Создаем сущности для каждого кондиционера
    if isinstance(coordinator.data, dict):
        for uid, unit_data in coordinator.data.items():
            if unit_data:
                # Получаем оригинальное имя объекта (Entity) из данных устройства
                original_name = unit_data.get("name", f"IDU {uid}")
                
                # Преобразуем технические имена в читаемые
                display_name = original_name
                if "one way cassette" in original_name.lower():
                    display_name = original_name.replace("one way cassette", "Кассетный кондиционер")
                elif "two way cassette" in original_name.lower():
                    display_name = original_name.replace("two way cassette", "Двусторонний кассетный кондиционер")
                elif "compact cassette" in original_name.lower():
                    display_name = original_name.replace("compact cassette", "Компактный кондиционер")
                elif "duct" in original_name.lower():
                    display_name = original_name.replace("duct", "Канальный кондиционер")
                elif "fullsize" in original_name.lower():
                    display_name = original_name.replace("fullsize", "Полноразмерный кондиционер")
                
                # Создаем информацию об устройстве для этого блока
                # НЕ МЕНЯЕМ поле "name" в device_info - оно должно остаться как у хаба
                entity_device_info = base_device_info.copy()
                
                # Добавляем дополнительную информацию, НЕ ТРОГАЯ "name"
                suggested_area = unit_data.get("pppname") or unit_data.get("ppname") or unit_data.get("pname")
                if suggested_area:
                    entity_device_info["suggested_area"] = suggested_area
                
                entity_device_info.update({
                    "via_device": (DOMAIN, host),
                    "model": unit_data.get("indoor_name", "Air Conditioner"),  # Модель кондиционера
                })
                
                # Создаем объект с именем кондиционера
                entities.append(HisenseIDUClimate(
                    coordinator, client, uid, entity_device_info, entity_name=display_name
                ))
                _LOGGER.debug("Created air conditioner: %s", display_name)
    
    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info("Created %s air conditioner entities. Hub name: %s", len(entities), hub_device_name)
    else:
        _LOGGER.warning("No air conditioner entities created. Check device connection.")
