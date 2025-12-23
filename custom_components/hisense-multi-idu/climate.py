"""Climate platform for Hisense Multi-IDU."""
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MODE_MAP,
    MODE_REVERSE_MAP,
    FAN_MAP,
    FAN_REVERSE_MAP,
    MODE_COOL,
    MODE_HEAT,
    MODE_DRY,
    MODE_FAN_ONLY,
    STATUS_ON,
    STATUS_OFF,
)

_LOGGER = logging.getLogger(__name__)

class HisenseIDUClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Hisense indoor unit."""
    
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.TURN_OFF |
        ClimateEntityFeature.TURN_ON
    )
    
    # ВСЕ режимы, которые поддерживает интеграция
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    
    _attr_fan_modes = list(FAN_REVERSE_MAP.keys())  # ["auto", "low", "medium", "high"]
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1
    
    def __init__(self, coordinator, client, uid, device_info, entity_name=None):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._client = client
        self._uid = uid
        
        # Извлекаем sys и addr из uid (формат: S1_1)
        if '_' in uid:
            s_part, addr_part = uid.split('_')
            self._sys = int(s_part[1:])  # Убираем 'S' из начала
            self._addr = int(addr_part)
        else:
            self._sys = 1
            self._addr = 1
        
        # Устанавливаем имя сущности
        if entity_name:
            self._attr_name = entity_name
        else:
            self._attr_name = f"IDU {uid}"
            
        self._attr_unique_id = f"{DOMAIN}_{uid}"
        self._attr_device_info = device_info
        
        # Кэш текущих данных
        self._current_data = {}
        
        _LOGGER.debug(f"Initialized climate entity: {self._attr_name} (S{self._sys}_{self._addr})")
    
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
        """Возвращает доступность устройства."""
        self._update_data()
        return bool(self._current_data)
    
    @property
    def target_temperature(self):
        """Возвращает целевую температуру."""
        self._update_data()
        temp = self._current_data.get("set_temp")
        if temp is not None:
            try:
                return float(temp)
            except (ValueError, TypeError):
                pass
        return 24.0
    
    @property
    def current_temperature(self):
        """Возвращает текущую температуру в помещении."""
        self._update_data()
        temp = self._current_data.get("room_temp")
        if temp is not None:
            try:
                return float(temp)
            except (ValueError, TypeError):
                pass
        return None
    
    @property
    def hvac_mode(self):
        """Возвращает текущий режим HVAC."""
        self._update_data()
        
        # Если нет данных, возвращаем OFF
        if not self._current_data:
            _LOGGER.debug(f"No data for {self._uid}, returning OFF")
            return HVACMode.OFF
        
        # Проверяем статус питания
        power = self._current_data.get("power", 0)
        if power == 0:
            _LOGGER.debug(f"Power is OFF for {self._uid}")
            return HVACMode.OFF
        
        # Получаем код режима от устройства
        mode_code = self._current_data.get("mode_code", MODE_COOL)
        
        # Преобразуем код в строку
        mode_str = MODE_MAP.get(mode_code, "cool")
        
        _LOGGER.debug(f"Device {self._uid}: mode_code={mode_code}, mode_str={mode_str}")
        
        # Преобразуем строку в HVACMode
        if mode_str == "cool":
            return HVACMode.COOL
        elif mode_str == "heat":
            return HVACMode.HEAT
        elif mode_str == "dry":
            return HVACMode.DRY
        elif mode_str == "fan_only":
            return HVACMode.FAN_ONLY
        else:
            _LOGGER.warning(f"Unknown mode string: {mode_str} for device {self._uid}")
            return HVACMode.COOL
    
    @property
    def fan_mode(self):
        """Возвращает текущую скорость вентилятора."""
        self._update_data()
        
        if not self._current_data:
            return "auto"
        
        fan_code = self._current_data.get("fan_code", FAN_AUTO)
        fan_str = FAN_MAP.get(fan_code, "auto")
        
        # Если код не найден в маппинге, пробуем определить по значению
        if fan_str == "auto" and fan_code not in FAN_MAP:
            if fan_code >= 32:
                fan_str = "high"
            elif fan_code >= 16:
                fan_str = "medium"
            elif fan_code >= 8:
                fan_str = "low"
        
        return fan_str
    
    @property
    def extra_state_attributes(self):
        """Возвращает дополнительные атрибуты."""
        self._update_data()
        
        attrs = {
            "uid": self._uid,
            "system_id": self._sys,
            "address": self._addr,
            "device_available": bool(self._current_data),
        }
        
        if self._current_data:
            attrs.update({
                "error_code": self._current_data.get("error_code", 0),
                "status": self._current_data.get("status", "unknown"),
                "pipe_temperature": self._current_data.get("pipe_temp"),
                "device_code": self._current_data.get("code", ""),
                "mode_code_raw": self._current_data.get("mode_code", 0),
                "fan_code_raw": self._current_data.get("fan_code", 0),
                "is_locked": self._current_data.get("model1", 0) == 1,
                "tenant_name": self._current_data.get("tenant_name", ""),
                "indoor_name": self._current_data.get("indoor_name", ""),
            })
        
        return attrs
    
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Установить целевую температуру."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            _LOGGER.warning(f"No temperature specified for {self._uid}")
            return
        
        self._update_data()
        if not self._current_data:
            _LOGGER.error(f"Cannot set temperature for {self._uid}: no data")
            return
        
        # Получаем текущие параметры
        onoff = 1 if self._current_data.get("power", 0) == 1 else 0
        mode_code = self._current_data.get("mode_code", MODE_COOL)
        fan_code = self._current_data.get("fan_code", FAN_MID)
        
        # Логируем действие
        _LOGGER.info(f"Setting temperature for {self._uid}: "
                    f"temp={temperature}, mode={mode_code}, fan={fan_code}")
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=onoff,
            mode=mode_code,
            fan=fan_code,
            temp=int(temperature)
        )
        
        if success:
            _LOGGER.debug(f"Temperature set successfully for {self._uid}")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(f"Failed to set temperature for {self._uid}")
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Установить режим HVAC."""
        _LOGGER.info(f"Setting HVAC mode for {self._uid}: {hvac_mode}")
        
        if hvac_mode == HVACMode.OFF:
            # Выключить устройство
            _LOGGER.debug(f"Turning OFF {self._uid}")
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=0,
                mode=MODE_COOL,  # Режим не важен при выключении
                fan=FAN_MID,
                temp=24
            )
        else:
            # Определяем код режима для устройства
            mode_code = None
            
            if hvac_mode == HVACMode.COOL:
                mode_code = MODE_REVERSE_MAP["cool"]
            elif hvac_mode == HVACMode.HEAT:
                mode_code = MODE_REVERSE_MAP["heat"]
            elif hvac_mode == HVACMode.DRY:
                mode_code = MODE_REVERSE_MAP["dry"]
            elif hvac_mode == HVACMode.FAN_ONLY:
                mode_code = MODE_REVERSE_MAP["fan_only"]
            else:
                _LOGGER.error(f"Unsupported HVAC mode: {hvac_mode}")
                return
            
            # Получаем текущие параметры
            self._update_data()
            current_temp = self._current_data.get("set_temp", 24)
            fan_code = self._current_data.get("fan_code", FAN_MID)
            
            _LOGGER.debug(f"Turning ON {self._uid}: mode={mode_code}, temp={current_temp}, fan={fan_code}")
            
            # Включить устройство с нужным режимом
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(current_temp)
            )
        
        if success:
            _LOGGER.debug(f"HVAC mode set successfully for {self._uid}")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(f"Failed to set HVAC mode for {self._uid}")
    
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Установить скорость вентилятора."""
        _LOGGER.info(f"Setting fan mode for {self._uid}: {fan_mode}")
        
        self._update_data()
        if not self._current_data:
            _LOGGER.error(f"Cannot set fan mode for {self._uid}: no data")
            return
        
        # Преобразуем строку в код устройства
        fan_code = FAN_REVERSE_MAP.get(fan_mode, FAN_MID)
        
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
            _LOGGER.debug(f"Fan mode set successfully for {self._uid}")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(f"Failed to set fan mode for {self._uid}")
    
    async def async_turn_on(self) -> None:
        """Включить кондиционер."""
        _LOGGER.info(f"Turning ON {self._uid}")
        
        self._update_data()
        if not self._current_data:
            # Если нет данных, используем значения по умолчанию
            mode_code = MODE_COOL
            fan_code = FAN_MID
            current_temp = 24
        else:
            mode_code = self._current_data.get("mode_code", MODE_COOL)
            fan_code = self._current_data.get("fan_code", FAN_MID)
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
            _LOGGER.debug(f"Device {self._uid} turned ON successfully")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(f"Failed to turn ON {self._uid}")
    
    async def async_turn_off(self) -> None:
        """Выключить кондиционер."""
        _LOGGER.info(f"Turning OFF {self._uid}")
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=0,
            mode=MODE_COOL,
            fan=FAN_MID,
            temp=24
        )
        
        if success:
            _LOGGER.debug(f"Device {self._uid} turned OFF successfully")
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(f"Failed to turn OFF {self._uid}")

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    host = data["host"]
    
    entities = []
    
    # Базовая информация об устройстве
    hub_device_name = f"Hisense Multi-IDU Hub ({host})"
    
    base_device_info = {
        "identifiers": {(DOMAIN, host)},
        "name": hub_device_name,
        "manufacturer": "Hisense",
        "model": "Multi-IDU Hub",
        "configuration_url": f"http://{host}"
    }
    
    # Создаем сущности для каждого кондиционера
    if isinstance(coordinator.data, dict):
        for uid, unit_data in coordinator.data.items():
            if not unit_data:
                continue
            
            # Получаем оригинальное имя
            original_name = unit_data.get("name", f"IDU {uid}")
            
            # Создаем информацию об устройстве для этого блока
            entity_device_info = base_device_info.copy()
            
            # Добавляем дополнительную информацию
            suggested_area = (unit_data.get("pppname") or 
                             unit_data.get("ppname") or 
                             unit_data.get("pname"))
            if suggested_area:
                entity_device_info["suggested_area"] = suggested_area
            
            entity_device_info.update({
                "via_device": (DOMAIN, host),
            })
            
            # Создаем объект
            entity = HisenseIDUClimate(
                coordinator=coordinator,
                client=client,
                uid=uid,
                device_info=entity_device_info,
                entity_name=original_name
            )
            
            entities.append(entity)
            
            _LOGGER.debug(f"Created climate entity: {original_name} ({uid})")
    
    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info(f"Created {len(entities)} climate entities")
    else:
        _LOGGER.warning("No climate entities created. Check device connection.")
