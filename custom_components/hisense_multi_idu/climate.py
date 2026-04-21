"""Climate platform for Hisense Multi-IDU."""
import asyncio
import logging
import time
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, MODE_MAP, MODE_REVERSE_MAP, 
    FAN_MAP, FAN_REVERSE_MAP,
    LOUVER_MAP, LOUVER_REVERSE_MAP,
    MODE_COOL, MODE_HEAT, MODE_DRY, MODE_FAN_ONLY
)

_LOGGER = logging.getLogger(__name__)

# Небольшая дополнительная задержка перед опросом состояния после команды,
# чтобы устройство успело применить изменения и интерфейс не "отпрыгивал".
POST_COMMAND_REFRESH_DELAY = 10.0

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
HA_SWING_MODES = [
    "auto",
    "angle_1",
    "angle_2",
    "angle_3",
    "angle_4",
    "angle_5",
    "angle_6",
    "angle_7",
    "angle_8",
]

class HisenseIDUClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Hisense indoor unit."""
    
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.FAN_MODE |
        ClimateEntityFeature.SWING_MODE |
        ClimateEntityFeature.TURN_OFF |
        ClimateEntityFeature.TURN_ON
    )
    # Убрали HVACMode.AUTO
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY]
    _attr_fan_modes = HA_FAN_MODES
    _attr_swing_modes = HA_SWING_MODES
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
        # Сохраненные настройки (для использования при включении)
        self._refresh_task: asyncio.Task | None = None
        self._saved_settings = {
            "temp": 24,
            "mode": MODE_COOL,
            "fan": 4,
            "louver": 1,
        }
        self._pending_off_temperature = False
        self._optimistic_overrides: dict[str, object] = {}
        self._optimistic_until: float = 0.0

    def _apply_optimistic_update(self, **changes):
        """Apply immediate local state changes until the delayed refresh arrives."""
        if not changes:
            return

        self._optimistic_overrides.update(changes)
        self._optimistic_until = time.monotonic() + POST_COMMAND_REFRESH_DELAY
        self._current_data.update(changes)
        self.async_write_ha_state()

    def _get_effective_mode_code(self):
        """Return the mode code that should be preserved across commands."""
        return self._current_data.get("mode_code", self._saved_settings.get("mode", MODE_COOL))

    def _get_effective_fan_code(self):
        """Return the fan code that should be preserved across commands."""
        return self._current_data.get("fan_code", self._saved_settings.get("fan", 4))

    def _get_effective_temperature(self):
        """Return the temperature that should be preserved across commands."""
        return self._current_data.get("set_temp", self._saved_settings.get("temp", 24))

    def _get_effective_louver_code(self):
        """Return the louver code that should be preserved across commands."""
        return self._current_data.get("louver_code", self._saved_settings.get("louver", 1))
    
    def _update_data(self):
        """Обновляет данные из координатора."""
        data = self.coordinator.data
        if not data:
            self._current_data = {}
            self._optimistic_overrides = {}
            self._optimistic_until = 0.0
            return
        
        unit_data = data.get(self._uid, {})
        if unit_data:
            self._current_data = unit_data.copy()

            if self._optimistic_overrides:
                if time.monotonic() < self._optimistic_until:
                    self._current_data.update(self._optimistic_overrides)
                else:
                    self._optimistic_overrides = {}
                    self._optimistic_until = 0.0
            # Сохраняем последние настройки для использования при включении.
            # Если температуру меняли локально при выключенном блоке,
            # не перезаписываем её «старыми» данными с устройства до включения.
            power = unit_data.get("power", 0)
            if power == 1 or not self._pending_off_temperature:
                self._saved_settings["temp"] = unit_data.get(
                    "set_temp", self._saved_settings.get("temp", 24)
                )
                if power == 1:
                    self._pending_off_temperature = False

            if "mode_code" in unit_data:
                self._saved_settings["mode"] = unit_data.get("mode_code", MODE_COOL)

            if "fan_code" in unit_data:
                self._saved_settings["fan"] = unit_data.get("fan_code", 4)
            if "louver_code" in unit_data:
                self._saved_settings["louver"] = unit_data.get("louver_code", 1)
        else:
            self._current_data = {}
    
    async def async_will_remove_from_hass(self):
        """Cancel pending debounced refresh task on entity removal."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def _request_refresh_debounced(self, delay: float = POST_COMMAND_REFRESH_DELAY):
        """Coalesce sequential service calls into one coordinator refresh."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()

        async def _delayed_refresh():
            try:
                await asyncio.sleep(delay)
                await self.coordinator.async_request_refresh()
            except asyncio.CancelledError:
                return

        self._refresh_task = asyncio.create_task(_delayed_refresh())

    @property
    def available(self):
        """Доступно ли устройство."""
        self._update_data()
        return bool(self._current_data)
    
    @property
    def target_temperature(self):
        self._update_data()
        if self._current_data and self._current_data.get("power", 0) == 1:
            return self._current_data.get("set_temp", 24)
        return self._saved_settings.get("temp", 24)
    
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
        if self._current_data:
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
        return "auto"
    
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
                "uid": self._uid,
                "saved_temp": self._saved_settings.get("temp"),
                "saved_mode": self._saved_settings.get("mode"),
                "saved_fan": self._saved_settings.get("fan"),
                "saved_louver": self._saved_settings.get("louver"),
            })
        
        return attrs

    @property
    def swing_mode(self):
        self._update_data()
        if self._current_data:
            louver = self._current_data.get("louver", "auto")
            if louver in HA_SWING_MODES:
                return louver
        return "auto"
    
    async def async_set_temperature(self, **kwargs):
        """Установить целевую температуру."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Сохраняем температуру в сохраненные настройки
        self._saved_settings["temp"] = int(temperature)
        
        # Обновляем локальный кэш для отображения в интерфейсе
        self._apply_optimistic_update(set_temp=int(temperature))
        
        # Отправляем команду на устройство ТОЛЬКО если оно включено
        if self._current_data.get("power", 0) == 1:
            self._pending_off_temperature = False
            mode_code = self._get_effective_mode_code()
            fan_code = self._get_effective_fan_code()

            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(temperature),
                louver=self._get_effective_louver_code(),
            )
            
            if success:
                _LOGGER.debug("Temperature set successfully for %s to %s°C", self._uid, temperature)
                # Запрашиваем обновление от координатора
                await self._request_refresh_debounced()
            else:
                _LOGGER.error("Failed to set temperature for %s", self._uid)
        else:
            self._pending_off_temperature = True
            # Устройство выключено - только сохраняем настройки
            _LOGGER.debug("Device %s is off, temperature %s°C saved for next start", 
                         self._uid, temperature)
            # Обновляем состояние в HA без запроса к устройству
            self.async_write_ha_state()
    
    async def async_set_hvac_mode(self, hvac_mode):
        """Установить режим HVAC."""
        if hvac_mode == HVACMode.OFF:
            # Выключить устройство, сохраняя текущие настройки
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=0,
                mode=self._saved_settings.get("mode", MODE_COOL),
                fan=self._saved_settings.get("fan", 4),
                temp=self._saved_settings.get("temp", 24),  # Сохраняем последнюю температуру
                louver=self._saved_settings.get("louver", 1),
            )
            if success:
                _LOGGER.debug("Device %s turned off with saved settings", self._uid)
                self._apply_optimistic_update(power=0)
                await self._request_refresh_debounced()
        else:
            # Преобразуем HVACMode в режим устройства
            device_mode = HVAC_TO_DEVICE.get(hvac_mode, "cool")
            mode_code = MODE_REVERSE_MAP.get(device_mode, MODE_COOL)
            
            # Сохраняем режим
            self._saved_settings["mode"] = mode_code

            # Обновляем локальный кэш для корректного отображения
            self._apply_optimistic_update(mode_code=mode_code, mode=device_mode)

            # Если устройство выключено, только сохраняем режим.
            # Включение/выключение должно быть независимым от изменения режима.
            if self._current_data.get("power", 0) != 1:
                _LOGGER.debug(
                    "Device %s is off, hvac mode %s saved for next start",
                    self._uid,
                    hvac_mode,
                )
                self.async_write_ha_state()
                return
            
            # Используем сохраненную температуру
            current_temp = self._get_effective_temperature()
            fan_code = self._get_effective_fan_code()
            
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(current_temp),
                louver=self._get_effective_louver_code(),
            )
            
            if success:
                _LOGGER.debug("Device %s turned on with mode %s, temp %s", 
                            self._uid, hvac_mode, current_temp)
                self._apply_optimistic_update(power=1)
                await self._request_refresh_debounced()
            else:
                _LOGGER.error("Failed to set HVAC mode for %s", self._uid)
    
    async def async_set_fan_mode(self, fan_mode):
        """Установить скорость вентилятора."""
        # Преобразуем строку в код устройства (только основные скорости)
        fan_code = FAN_REVERSE_MAP.get(fan_mode, 4)
        
        # Сохраняем скорость
        self._saved_settings["fan"] = fan_code
        
        # Обновляем локальный кэш
        self._apply_optimistic_update(fan_code=fan_code, fan=fan_mode)
        
        # Отправляем команду на устройство ТОЛЬКО если оно включено
        if self._current_data.get("power", 0) == 1:
            # Используем параметры из текущих данных
            mode_code = self._get_effective_mode_code()
            current_temp = self._get_effective_temperature()
            
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(current_temp),
                louver=self._get_effective_louver_code(),
            )
            
            if success:
                _LOGGER.debug("Fan mode set successfully for %s to %s", self._uid, fan_mode)
                await self._request_refresh_debounced()
            else:
                _LOGGER.error("Failed to set fan mode for %s", self._uid)
        else:
            # Устройство выключено - только сохраняем настройки
            _LOGGER.debug("Device %s is off, fan mode %s saved for next start", 
                         self._uid, fan_mode)
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode):
        """Установить положение вертикальной жалюзи."""
        louver_code = LOUVER_REVERSE_MAP.get(swing_mode)
        if louver_code is None:
            _LOGGER.warning("Unsupported swing mode %s for %s", swing_mode, self._uid)
            return

        self._saved_settings["louver"] = louver_code
        self._apply_optimistic_update(louver_code=louver_code, louver=swing_mode)

        if self._current_data.get("power", 0) == 1:
            mode_code = self._get_effective_mode_code()
            fan_code = self._get_effective_fan_code()
            current_temp = self._get_effective_temperature()
            success = await self._client.set_idu(
                sys=self._sys,
                addr=self._addr,
                onoff=1,
                mode=mode_code,
                fan=fan_code,
                temp=int(current_temp),
                louver=louver_code,
            )

            if success:
                _LOGGER.debug("Swing mode set successfully for %s to %s", self._uid, swing_mode)
                await self._request_refresh_debounced()
            else:
                _LOGGER.error("Failed to set swing mode for %s", self._uid)
        else:
            _LOGGER.debug("Device %s is off, swing mode %s saved for next start", self._uid, swing_mode)
            self.async_write_ha_state()
    
    async def async_turn_on(self):
        """Включить кондиционер с сохраненными настройками."""
        # Используем текущие/сохраненные настройки без сброса на значения по умолчанию
        self._update_data()
        mode_code = self._get_effective_mode_code()
        fan_code = self._get_effective_fan_code()
        current_temp = self._get_effective_temperature()
        
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=1,
            mode=mode_code,
            fan=fan_code,
            temp=int(current_temp),
            louver=self._get_effective_louver_code(),
        )
        
        if success:
            _LOGGER.debug("Device %s turned on with saved settings", self._uid)
            self._apply_optimistic_update(
                power=1,
                mode_code=mode_code,
                mode=MODE_MAP.get(mode_code, "cool"),
                fan_code=fan_code,
                fan=FAN_MAP.get(fan_code, "auto"),
                set_temp=int(current_temp),
                louver_code=self._get_effective_louver_code(),
                louver=LOUVER_MAP.get(self._get_effective_louver_code(), "auto"),
            )
            await self._request_refresh_debounced()
    
    async def async_turn_off(self):
        """Выключить кондиционер, сохраняя настройки."""
        self._update_data()
        success = await self._client.set_idu(
            sys=self._sys,
            addr=self._addr,
            onoff=0,
            mode=self._get_effective_mode_code(),
            fan=self._get_effective_fan_code(),
            temp=self._get_effective_temperature(),
            louver=self._get_effective_louver_code(),
        )
        
        if success:
            _LOGGER.debug("Device %s turned off with saved settings", self._uid)
            self._apply_optimistic_update(power=0)
            await self._request_refresh_debounced()

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    host = data["host"]
    hub_name = data.get("hub_name", "Hi Dom III")
    
    entities = []
    
    # ФИКСИРОВАННОЕ ИМЯ УСТРОЙСТВА (Device) - это изменит название устройства в HA
    hub_device_name = hub_name
    
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
    _LOGGER.info("Setting up climate entities. Coordinator data type: %s", 
                 type(coordinator_data))
    
    if isinstance(coordinator_data, dict) and coordinator_data:
        for uid, unit_data in coordinator_data.items():
            _LOGGER.debug("Processing device UID: %s", uid)
            
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
        _LOGGER.warning("No valid data in coordinator. Type: %s", 
                       type(coordinator_data))
    
    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info("Successfully created %s climate entities. Hub name: %s", 
                    len(entities), hub_device_name)
    else:
        _LOGGER.error("No climate entities created. Check device connection to %s", host)
