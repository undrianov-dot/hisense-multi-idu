"""Config flow for Hisense Multi-IDU integration."""
import aiohttp
import asyncio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

class HisenseMultiIDUConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hisense Multi-IDU."""
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            host = user_input.get("host", "").strip()
            # Проверяем, не сконфигурировано ли уже это устройство
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            
            # Пробуем подключиться к устройству
            try:
                session = aiohttp_client.async_get_clientsession(self.hass)
                # Проверяем доступность основного интерфейса
                async with session.get(f"http://{host}/", timeout=5) as resp:
                    if resp.status != 200:
                        # Пробуем другой endpoint
                        async with session.get(f"http://{host}/cgi/get_miscdata.shtml", timeout=5):
                            pass
            except (asyncio.TimeoutError, aiohttp.ClientError):
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
                
            if not errors:
                # Всё в порядке, создаём запись
                return self.async_create_entry(
                    title=f"Hisense Multi-IDU ({host})",
                    data={"host": host}
                )
        
        # Показываем форму ввода
        data_schema = vol.Schema({
            vol.Required("host", default="10.99.3.100"): str, 
            vol.Optional("hub_name", default="Hisense Multi-IDU Hub"): str,
        })
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
