import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["climate", "sensor"]

class HisenseClient:
    """Клиент для взаимодействия с контроллером Hisense Multi-IDU по локальному API."""

    def __init__(self, host: str, session):
        """Инициализация клиента с IP-адресом контроллера и сессией aiohttp."""
        self.host = host
        self._session = session

    async def get_idu_data(self):
        """Получить данные всех внутренних блоков (IDU) через API."""
        url = f"http://{self.host}/cgi/get_idu_data.shtml"
        try:
            resp = await self._session.get(url)
            resp.raise_for_status()
        except Exception as err:
            _LOGGER.error("Failed to fetch IDU data: %s", err)
            raise
        try:
            data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.error("Invalid response from IDU data API: %s", err)
            raise

        # Преобразуем ответ в словарь {idu_id: data}
        idu_data = {}
        if isinstance(data, dict):
            if "dats" in data:
                # Ответ содержит список IDU в поле "dats"
                for unit in data["dats"]:
                    unit_id = unit.get("id") or unit.get("uid") or unit.get("name")
                    if unit_id:
                        idu_data[unit_id] = unit
            else:
                # Если данные представлены как словарь {id: значения}
                for key, val in data.items():
                    idu_data[key] = val
        elif isinstance(data, list):
            for unit in data:
                uid = unit.get("id") or unit.get("uid") or unit.get("name")
                if uid:
                    idu_data[uid] = unit
        _LOGGER.debug("Fetched IDU data: %s", idu_data)
        return idu_data

    async def get_meter_data(self):
        """Получить данные электросчётчика (энергия в кВт·ч)."""
        url = f"http://{self.host}/cgi/get_meter_pwr.shtml"
        payload = {"ids": ["1", "2"], "ip": self.host}
        try:
            resp = await self._session.post(url, json=payload)
            resp.raise_for_status()
        except Exception as err:
            _LOGGER.error("Failed to fetch meter data: %s", err)
            raise
        try:
            data = await resp.json(content_type=None)
        except Exception as err:
            _LOGGER.error("Invalid response from meter API: %s", err)
            raise

        if isinstance(data, dict) and "dats" in data and data["dats"]:
            first_entry = data["dats"][0]
            value = None
            if "pwr" in first_entry:
                value = first_entry["pwr"]
            elif "power" in first_entry:
                value = first_entry["power"]
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        _LOGGER.warning("Unexpected meter data format: %s", data)
        return None

    async def set_idu(self, idu_id: str, **kwargs):
        """Отправить команду управлением на внутренний блок (IDU). Поддерживаются ключи: power, mode, set_temp, fan_speed и др."""
        url = f"http://{self.host}/cgi/set_idu_data.shtml"
        payload = {"id": idu_id, "ip": self.host}
        # Включаем в запрос только переданные параметры
        payload.update(kwargs)
        try:
            resp = await self._session.post(url, json=payload)
            resp.raise_for_status()
        except Exception as err:
            _LOGGER.error("Failed to set IDU data for %s: %s", idu_id, err)
            raise
        _LOGGER.debug("Set IDU %s with payload %s", idu_id, payload)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из ConfigEntry (через UI)."""
    hass.data.setdefault(DOMAIN, {})
    session = async_get_clientsession(hass)
    host = entry.data["host"]

    # Инициализируем клиент и координаторы обновления данных
    client = HisenseClient(host, session)
    coordinator_climate = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_climate",
        update_method=client.get_idu_data,
        update_interval=timedelta(seconds=30),
    )
    coordinator_energy = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_energy",
        update_method=client.get_meter_data,
        update_interval=timedelta(seconds=60),
    )

    # Первое обновление данных (блокирующее настройку до успешного чтения)
    await coordinator_climate.async_config_entry_first_refresh()
    await coordinator_energy.async_config_entry_first_refresh()

    # Сохраняем объекты в hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator_climate": coordinator_climate,
        "coordinator_energy": coordinator_energy
    }

    # Инициализируем платформы climate и sensor
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции при удалении ConfigEntry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True
