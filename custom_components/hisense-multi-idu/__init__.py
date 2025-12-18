"""Hisense Multi-IDU integration."""
import asyncio
import logging
from datetime import timedelta
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, DEFAULT_SCAN_INTERVAL_CLIMATE, DEFAULT_SCAN_INTERVAL_SENSOR,
    MODE_MAP, FAN_MAP
)

# Импортируем новый модуль
from .power_meter import fetch_power_data

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor"]

class HisenseClient:
    """Клиент для взаимодействия с устройством Hisense Multi-IDU."""
    
    def __init__(self, host: str, session: aiohttp.ClientSession):
        self._host = host
        self._session = session
        self._miscdata_cache = None
        self._miscdata_timestamp = 0
    
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
    
    async def get_idu_data(self):
        """Получает данные всех внутренних блоков."""
        try:
            # Получаем топологию
            miscdata = await self.get_miscdata()
            topo = miscdata.get("topo", [])
            
            # Фильтруем только IDU (внутренние блоки)
            idu_list = [item for item in topo if item.get("type") == "IDU"]
            
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
                    
                    # Преобразуем коды в строки
                    if result[key]["mode_code"] in MODE_MAP:
                        result[key]["mode"] = MODE_MAP[result[key]["mode_code"]]
                    else:
                        result[key]["mode"] = "cool"
                    
                    if result[key]["fan_code"] in FAN_MAP:
                        result[key]["fan"] = FAN_MAP[result[key]["fan_code"]]
                    else:
                        # Если скорость не стандартная, преобразуем в ближайшую стандартную
                        fan_code = result[key]["fan_code"]
                        if fan_code in [16, 32, 64]:  # Дополнительные скорости
                            result[key]["fan"] = "high"
                        else:
                            result[key]["fan"] = "medium"
                    
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
        """Получает данные электросчетчика через отдельную функцию."""
        try:
            power = await fetch_power_data(self._host)
            return power
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
        _LOGGER.debug("Power data update result: %s", data)
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
        _LOGGER.info("Climate coordinator initialized successfully")
    except Exception as e:
        _LOGGER.error("Failed to refresh climate data: %s", e)
        return False
    
    try:
        await coordinator_sensor.async_config_entry_first_refresh()
        _LOGGER.info("Sensor coordinator initialized. Data: %s", coordinator_sensor.data)
    except Exception as e:
        _LOGGER.warning("Failed to refresh sensor data: %s", e)
    
    # Сохраняем ссылки
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator_climate": coordinator_climate,
        "coordinator_sensor": coordinator_sensor,
        "host": host
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
