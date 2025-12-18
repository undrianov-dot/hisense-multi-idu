"""Hisense Multi-IDU integration."""
import asyncio
import logging
from datetime import timedelta
import aiohttp
import json

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL_CLIMATE, DEFAULT_SCAN_INTERVAL_SENSOR,
    MODE_MAP, FAN_MAP
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor"]

class HisenseClient:
    """Клиент для взаимодействия с устройством Hisense Multi-IDU."""
    
    def __init__(self, host: str, session: aiohttp.ClientSession):
        self._host = host
        self._session = session
        self._miscdata_cache = None
        self._miscdata_timestamp = 0
        self._hub_info = None
    
    async def get_miscdata(self):
        """Получает топологию устройств с кэшированием."""
        import time
        current_time = time.time()
        
        # Кэшируем на 5 минут
        if (self._miscdata_cache is not None and 
            current_time - self._miscdata_timestamp < 300):
            return self._miscdata_cache
            
        url = f"http://{self._host}/cgi/get_miscdata.shtml"
        try:
            async with self._session.post(
                url, 
                json={"ip": "127.0.0.1"},
                timeout=10
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP error: {resp.status}")
                
                data = await resp.json(content_type=None)
                if data.get("status") != "success":
                    raise UpdateFailed("API returned error")
                
                self._miscdata_cache = data.get("miscdata", {})
                self._miscdata_timestamp = current_time
                return self._miscdata_cache
                
        except Exception as e:
            _LOGGER.error("Failed to get miscdata: %s", e)
            raise UpdateFailed(f"Failed to get miscdata: {e}")
    
    async def get_hub_info(self):
        """Получает информацию о хабе (главном устройстве)."""
        if self._hub_info is not None:
            return self._hub_info
            
        try:
            miscdata = await self.get_miscdata()
            topo = miscdata.get("topo", [])
            
            # Логируем все устройства для анализа
            _LOGGER.debug("=== All devices in topology ===")
            for idx, item in enumerate(topo):
                _LOGGER.debug("[%d] %s", idx, item)
            
            # Ищем устройство, которое является хабом
            # По вашему скриншоту, это "one way cassette-100-1-1"
            hub_device = None
            
            for item in topo:
                name = item.get("name", "")
                # Ищем по имени из скриншота
                if "cassette-100" in name or "hidom" in name.lower():
                    hub_device = item
                    break
            
            if hub_device:
                # Формируем читаемое имя для хаба
                hub_name = "Hisense Multi-IDU Hub"
                if hub_device.get("name"):
                    # Пытаемся очистить имя
                    raw_name = hub_device.get("name")
                    if "one way cassette-100-1-1" in raw_name:
                        hub_name = "Hisense Multi-IDU Gateway"
                    else:
                        hub_name = raw_name.replace("-100-1-1", "").title()
                
                self._hub_info = {
                    "name": hub_name,
                    "type": hub_device.get("type", "hidom"),
                    "code": hub_device.get("code", ""),
                    "sys": hub_device.get("sysAdr", 100),
                    "addr": hub_device.get("address", 1),
                    "model": hub_device.get("indoorName", "Multi-IDU Gateway"),
                    "unique_id": f"S{hub_device.get('sysAdr', 100)}_{hub_device.get('address', 1)}",
                    "raw_name": hub_device.get("name", "")
                }
                _LOGGER.info("Found hub device: %s", self._hub_info["name"])
            else:
                # Если не нашли, используем первое устройство или создаем дефолтное
                if topo:
                    first_device = topo[0]
                    self._hub_info = {
                        "name": "Hisense Multi-IDU Hub",
                        "type": first_device.get("type", "hidom"),
                        "code": first_device.get("code", ""),
                        "sys": first_device.get("sysAdr", 100),
                        "addr": first_device.get("address", 1),
                        "model": first_device.get("indoorName", "Multi-IDU Gateway"),
                        "unique_id": f"S{first_device.get('sysAdr', 100)}_{first_device.get('address', 1)}",
                        "raw_name": first_device.get("name", "")
                    }
                else:
                    self._hub_info = {
                        "name": f"Hisense Multi-IDU Hub ({self._host})",
                        "type": "hidom",
                        "code": "",
                        "sys": 100,
                        "addr": 1,
                        "model": "Multi-IDU Gateway",
                        "unique_id": f"S100_1",
                        "raw_name": ""
                    }
                _LOGGER.warning("No specific hub device found, using: %s", self._hub_info["name"])
            
            return self._hub_info
            
        except Exception as e:
            _LOGGER.error("Failed to get hub info: %s", e)
            # Возвращаем дефолтный хаб
            return {
                "name": f"Hisense Multi-IDU Hub ({self._host})",
                "type": "hidom",
                "code": "",
                "sys": 100,
                "addr": 1,
                "model": "Multi-IDU Gateway",
                "unique_id": f"S100_1",
                "raw_name": ""
            }
    
    async def get_idu_data(self):
        """Получает данные всех внутренних блоков (исключая хаб)."""
        try:
            # Получаем информацию о хабе
            hub_info = await self.get_hub_info()
            hub_unique_id = hub_info.get("unique_id", "S100_1")
            
            # Получаем топологию
            miscdata = await self.get_miscdata()
            topo = miscdata.get("topo", [])
            
            # Фильтруем только IDU (внутренние блоки), исключая хаб
            idu_list = []
            for item in topo:
                sys_adr = item.get("sysAdr", 0)
                address = item.get("address", 0)
                unique_id = f"S{sys_adr}_{address}"
                
                # Пропускаем хаб
                if unique_id == hub_unique_id:
                    _LOGGER.debug("Skipping hub device: %s", item.get("name"))
                    continue
                
                # Включаем только внутренние блоки
                dev_type = item.get("type", "").lower()
                if dev_type in ["idu", "cassette", "duct", "compact", "fullsize", "one way", "two way"]:
                    idu_list.append(item)
            
            _LOGGER.info("Found %s IDU devices (excluding hub)", len(idu_list))
            
            if not idu_list:
                _LOGGER.warning("No IDU devices found in topology")
                return {}
            
            # Формируем список устройств для запроса
            devs = [
                {
                    "sys": item.get("sysAdr", 1),
                    "addr": item.get("address", "1")
                } 
                for item in idu_list
            ]
            
            url = f"http://{self._host}/cgi/get_idu_data.shtml"
            async with self._session.post(
                url,
                json={"ip": "127.0.0.1", "devs": devs},
                timeout=15
            ) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP error: {resp.status}")
                
                data = await resp.json(content_type=None)
                if data.get("status") != "success":
                    raise UpdateFailed("API returned error")
                
                # Объединяем данные с топологией
                result = {}
                for item in data.get("dats", []):
                    sys = item.get("sys")
                    addr = item.get("addr")
                    key = f"S{sys}_{addr}"
                    
                    # Находим соответствующую запись в топологии
                    topo_info = next(
                        (t for t in idu_list 
                         if t.get("sysAdr") == sys and str(t.get("address")) == str(addr)),
                        {}
                    )
                    
                    # Парсим данные
                    raw_data = item.get("data", [])
                    result[key] = {
                        "sys": sys,
                        "addr": addr,
                        "raw_data": raw_data,
                        "name": topo_info.get("name", f"IDU S{sys}-{addr}"),
                        "code": topo_info.get("code", ""),
                        "pname": topo_info.get("pname", ""),
                        "ppname": topo_info.get("ppname", ""),
                        "pppname": topo_info.get("pppname", ""),
                        "indoor_name": topo_info.get("indoorName", ""),
                        "tenant_name": topo_info.get("tenantName", ""),
                        
                        # Парсим основные параметры
                        "power": raw_data[28] if len(raw_data) > 28 else 0,
                        "mode_code": raw_data[29] if len(raw_data) > 29 else 2,
                        "fan_code": raw_data[30] if len(raw_data) > 30 else 4,
                        "set_temp": raw_data[31] if len(raw_data) > 31 else 24,
                        "error_code": raw_data[35] if len(raw_data) > 35 else 0,
                        "room_temp": raw_data[38] if len(raw_data) > 38 else None,
                        "pipe_temp": raw_data[39] if len(raw_data) > 39 else None,
                        
                        # Регистры блокировки
                        "model1": raw_data[72] if len(raw_data) > 72 else 0,
                        "model2": raw_data[73] if len(raw_data) > 73 else 0,
                        "model3": raw_data[74] if len(raw_data) > 74 else 0,
                        "model4": raw_data[75] if len(raw_data) > 75 else 0,
                        "model5": raw_data[77] if len(raw_data) > 77 else 0,
                    }
                    
                    # Преобразуем коды в строки (только основные режимы)
                    mode_code = result[key]["mode_code"]
                    if mode_code in MODE_MAP:
                        result[key]["mode"] = MODE_MAP[mode_code]
                    else:
                        # Если режим не входит в основные, преобразуем в "cool"
                        result[key]["mode"] = "cool"
                    
                    fan_code = result[key]["fan_code"]
                    if fan_code in FAN_MAP:
                        result[key]["fan"] = FAN_MAP[fan_code]
                    else:
                        # Если скорость не стандартная, преобразуем в "auto"
                        result[key]["fan"] = "auto"
                    
                    # Определяем статус
                    error = result[key]["error_code"]
                    if error != 0:
                        if error in [60, 61, 64, 65]:
                            result[key]["status"] = "offline"
                        else:
                            result[key]["status"] = "alarm"
                    else:
                        result[key]["status"] = "on" if result[key]["power"] == 1 else "off"
                
                return result
                
        except Exception as e:
            _LOGGER.error("Failed to get IDU data: %s", e)
            raise UpdateFailed(f"Failed to get IDU data: {e}")
    
    async def get_power_data(self):
        """Получает данные электросчетчика."""
        url = f"http://{self._host}/cgi/get_meter_pwr.shtml"
        try:
            async with self._session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Power meter endpoint returned status %s", resp.status)
                    # Возвращаем None, чтобы показать, что счетчик недоступен
                    return None
                
                text = await resp.text()
                _LOGGER.debug("Raw power meter response: %s", text)
                
                # Пытаемся извлечь числовое значение
                # Возможные форматы: просто число, HTML с числом, JSON
                import re
                
                # Удаляем HTML теги, если есть
                text_clean = re.sub(r'<[^>]+>', '', text)
                
                # Ищем число (целое или с плавающей точкой)
                match = re.search(r'([0-9]+(?:\.[0-9]+)?)', text_clean.strip())
                if match:
                    value = float(match.group(1))
                    _LOGGER.info("Parsed power value: %s W", value)
                    return value
                else:
                    _LOGGER.warning("Could not parse power value. Cleaned text: %s", text_clean)
                    return None
                    
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout when accessing power meter endpoint")
            return None
        except Exception as e:
            _LOGGER.error("Failed to get power data: %s", e)
            return None
    
    async def set_idu(self, sys: int, addr: int, **kwargs):
        """Устанавливает параметры внутреннего блока."""
        try:
            cmd_list = []
            
            # Команда для управления блокировками (если нужно)
            if "lock_mode" in kwargs:
                cmd_list.append({
                    "seq": 1,
                    "sys": sys,
                    "iduAddr": addr,
                    "regAddr": 72,
                    "regVal": kwargs.get("lock_mode", [2, 0, 0, 0, 0, 0])
                })
            
            # Основная команда управления
            cmd_list.append({
                "seq": len(cmd_list) + 1,
                "sys": sys,
                "iduAddr": addr,
                "regAddr": 78,
                "regVal": [
                    kwargs.get("onoff", 1),      # Вкл/Выкл
                    kwargs.get("mode", 2),       # Режим
                    kwargs.get("fan", 4),        # Скорость вентилятора
                    kwargs.get("temp", 24),      # Температура
                    0                            # Неизвестный параметр
                ]
            })
            
            url = f"http://{self._host}/cgi/set_idu.shtml"
            async with self._session.post(
                url,
                json={"ip": "127.0.0.1", "cmdList": cmd_list},
                timeout=10
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("HTTP error when setting IDU: %s", resp.status)
                    return False
                
                data = await resp.json(content_type=None)
                return data.get("status") == "success"
                
        except Exception as e:
            _LOGGER.error("Failed to set IDU: %s", e)
            return False

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hisense Multi-IDU from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    host = entry.data["host"]
    session = aiohttp_client.async_get_clientsession(hass)
    client = HisenseClient(host, session)
    
    # Получаем информацию о хабе
    hub_info = await client.get_hub_info()
    _LOGGER.info("Hub setup: %s", hub_info["name"])
    
    # Координатор для климатических устройств
    async def update_climate_data():
        data = await client.get_idu_data()
        if not data:
            raise UpdateFailed("No climate data received")
        return data
    
    coordinator_climate = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_climate",
        update_method=update_climate_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_CLIMATE),
    )
    
    # Координатор для датчика мощности
    async def update_sensor_data():
        data = await client.get_power_data()
        return data
    
    coordinator_sensor = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_sensor",
        update_method=update_sensor_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SENSOR),
    )
    
    # Первоначальное обновление данных
    try:
        await coordinator_climate.async_config_entry_first_refresh()
    except Exception as e:
        _LOGGER.error("Failed to refresh climate data: %s", e)
        return False
    
    try:
        await coordinator_sensor.async_config_entry_first_refresh()
        if coordinator_sensor.data is None:
            _LOGGER.warning("Power meter data is not available")
        else:
            _LOGGER.info("Power meter initialized with value: %s", coordinator_sensor.data)
    except Exception as e:
        _LOGGER.warning("Failed to refresh sensor data: %s", e)
    
    # Сохраняем ссылки
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator_climate": coordinator_climate,
        "coordinator_sensor": coordinator_sensor,
        "host": host,
        "hub_info": hub_info
    }
    
    # Настраиваем платформы
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Настраиваем слушатель для обновлений опций
    entry.async_on_unload(
        entry.add_update_listener(async_update_options)
    )
    
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
