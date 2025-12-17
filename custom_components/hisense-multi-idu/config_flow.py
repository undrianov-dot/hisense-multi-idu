import asyncio
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class HisenseMultiIDUConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow для интеграции Hisense Multi-IDU (настройка через UI)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Обработка шага конфигурации, запрашивающего IP контроллера."""
        errors = {}
        if user_input is not None:
            # Проверяем, не настроена ли уже интеграция с этим же хостом
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            session = aiohttp_client.async_get_clientsession(self.hass)
            try:
                # Пробуем получить данные с контроллера для проверки доступности
                from . import HisenseClient
                client = HisenseClient(user_input[CONF_HOST], session)
                await client.get_idu_data()
            except Exception as err:
                _LOGGER.error("Error connecting to Hisense controller %s: %s", user_input[CONF_HOST], err)
                errors["base"] = "cannot_connect"
            else:
                # Подключение успешно – создаем запись конфигурации
                return self.async_create_entry(
                    title=f"Hisense Multi-IDU ({user_input[CONF_HOST]})",
                    data=user_input
                )

        # Форма ввода IP-адреса
        data_schema = vol.Schema({
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST) if user_input else ""): str
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
