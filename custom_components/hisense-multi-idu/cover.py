"""Cover platform for Hisense Multi-IDU (damper/louver control)."""
import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
    ATTR_POSITION,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DAMPER_MAP, DAMPER_REVERSE_MAP

_LOGGER = logging.getLogger(__name__)


class HisenseDamperCover(CoordinatorEntity, CoverEntity):
    """Representation of a Hisense damper/louver cover."""
    
    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN |
        CoverEntityFeature.CLOSE |
        CoverEntityFeature.STOP |
        CoverEntityFeature.SET_POSITION
    )
    _attr_assumed_state = True
    
    def __init__(self, coordinator, client, uid, device_info, entity_name=None):
        super().__init__(coordinator)
        self._client = client
        self._uid = uid
        
        # Извлекаем sys и addr из uid
        if '_' in uid:
            s_part, addr_part = uid.split('_')
            self._sys = int(s_part[1:])  # Убираем 'S'
            self._addr = int(addr_part)
        else:
            self._sys = 1
            self._addr = 1
        
        # Настройка имени
        if entity_name:
            self._attr_name = f"{entity_name} Жалюзи"
        else:
            self._attr_name = f"IDU {uid} Жалюзи"
        
        self._attr_unique_id = f"{DOMAIN}_{uid}_damper"
        self._attr_device_info = device_info
        
        # Текущее состояние
        self._current_position = 50  # По умолчанию 50%
        self._is_opening = False
        self._is_closing = False
        
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
            
            # Извлекаем положение жалюзи из данных
            # Предполагаем, что данные о жалюзи хранятся в raw_data[40]
            raw_data = unit_data.get("raw_data", [])
            if len(raw_data) > 40:
                damper_code = raw_data[40]
                # Преобразуем код в положение (0-100%)
                if damper_code == 1:  # Закрыто
                    self._current_position = 0
                elif damper_code == 2:  # Открыто
                    self._current_position = 100
                elif damper_code == 6:  # Качание
                    self._current_position = 50  # Среднее положение
                elif 3 <= damper_code <= 5:  # Позиции 1-3
                    # Преобразуем в проценты: 3=25%, 4=50%, 5=75%
                    self._current_position = (damper_code - 2) * 25
    
    @property
    def available(self):
        """Доступно ли устройство."""
        self._update_data()
        return bool(self._current_data)
    
    @property
    def current_cover_position(self):
        """Возвращает текущее положение жалюзи в %."""
        self._update_data()
        return self._current_position
    
    @property
    def is_closed(self):
        """Возвращает True, если жалюзи закрыты."""
        return self.current_cover_position == 0
    
    @property
    def is_opening(self):
        """Возвращает True, если жалюзи открываются."""
        return self._is_opening
    
    @property
    def is_closing(self):
        """Возвращает True, если жалюзи закрываются."""
        return self._is_closing
    
    async def async_open_cover(self, **kwargs):
        """Открыть жалюзи полностью."""
        await self.async_set_cover_position(position=100)
    
    async def async_close_cover(self, **kwargs):
        """Закрыть жалюзи полностью."""
        await self.async_set_cover_position(position=0)
    
    async def async_stop_cover(self, **kwargs):
        """Остановить движение жалюзи."""
        # Отправляем команду остановки (если поддерживается)
        success = await self._client.set_damper(
            sys=self._sys,
            addr=self._addr,
            command="stop"
        )
        
        if success:
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()
    
    async def async_set_cover_position(self, **kwargs):
        """Установить положение жалюзи."""
        position = kwargs.get(ATTR_POSITION)
        if position is None:
            return
        
        # Определяем направление движения
        if position > self._current_position:
            self._is_opening = True
            self._is_closing = False
        elif position < self._current_position:
            self._is_opening = False
            self._is_closing = True
        else:
            return
        
        self.async_write_ha_state()
        
        # Конвертируем процент в код устройства
        damper_code = self._position_to_code(position)
        
        # Отправляем команду
        success = await self._client.set_damper(
            sys=self._sys,
            addr=self._addr,
            command=damper_code
        )
        
        if success:
            self._current_position = position
            self._is_opening = False
            self._is_closing = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
    
    def _position_to_code(self, position):
        """Конвертирует процент положения в код устройства."""
        if position == 0:
            return 1  # Закрыто
        elif position == 100:
            return 2  # Открыто
        elif position <= 25:
            return 3  # Позиция 1
        elif position <= 50:
            return 4  # Позиция 2
        elif position <= 75:
            return 5  # Позиция 3
        else:
            return 6  # Качание


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up damper cover entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    host = data["host"]
    
    entities = []
    
    hub_device_name = f"Hisense Multi-IDU Hub ({host})"
    
    # Базовая информация об устройстве
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
            if unit_data:
                # Получаем оригинальное имя объекта
                original_name = unit_data.get("name", f"IDU {uid}")
                
                # Создаем информацию об устройстве
                entity_device_info = base_device_info.copy()
                entity_device_info["via_device"] = (DOMAIN, host)
                
                # Добавляем дополнительную информацию
                suggested_area = unit_data.get("pppname") or unit_data.get("ppname") or unit_data.get("pname")
                if suggested_area:
                    entity_device_info["suggested_area"] = suggested_area
                
                # Проверяем, поддерживает ли устройство управление жалюзи
                raw_data = unit_data.get("raw_data", [])
                if len(raw_data) > 40:  # Проверяем наличие данных о жалюзи
                    entities.append(HisenseDamperCover(
                        coordinator, client, uid, entity_device_info, 
                        entity_name=original_name
                    ))
                    _LOGGER.debug("Created damper entity for %s", uid)
    
    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info("Created %s damper entities", len(entities))
    else:
        _LOGGER.info("No damper entities created (device might not support dampers)")
