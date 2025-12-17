# custom_components/hisense_multi_idu/climate.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# --- Маппинги (если у тебя в панели другие коды — поправь здесь) ---
MODE_MAP: dict[str, int] = {
    "cool": 2,
    "dry": 4,
    "fan_only": 8,
    "heat": 1,
}
MODE_REVERSE_MAP: dict[int, str] = {v: k for k, v in MODE_MAP.items()}

FAN_MAP: dict[str, int] = {
    "high": 2,
    "medium": 4,
    "low": 8,
}
FAN_REVERSE_MAP: dict[int, str] = {v: k for k, v in FAN_MAP.items()}


@dataclass(frozen=True)
class HiDomUnitKey:
    sys: int
    addr: int


class HisenseMultiIduCoordinator(DataUpdateCoordinator[dict[HiDomUnitKey, list[int]]]):
    def __init__(self, hass: HomeAssistant, host: str, scan_interval: float):
        self.hass = hass
        self.host = host
        self.session = async_get_clientsession(hass)

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Hisense Multi-IDU",
            update_interval=None,  # interval зададим через async_request_refresh + throttling внутри HA
        )

        # В DataUpdateCoordinator в HA interval обычно задают через timedelta,
        # но чтобы не тянуть datetime — используем built-in periodic через hass.helpers.event.
        # Проще: будем опираться на coordinator.async_request_refresh() из HA,
        # а частоту зададим в __init__.py (рекомендовано).
        self._scan_interval = scan_interval

    async def _async_update_data(self) -> dict[HiDomUnitKey, list[int]]:
        url = f"http://{self.host}/cgi/get_idu_data.shtml"

        # сразу все 16
        devs = [{"sys": s, "addr": a} for s in (1, 2) for a in range(1, 9)]
        payload = {"devs": devs, "ip": self.host}

        try:
            async with self.session.post(url, json=payload, timeout=6) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status} on get_idu_data")

                # Контроллер часто отвечает без Content-Type → отключаем проверку
                try:
                    result = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    try:
                        result = json.loads(text)
                    except Exception as e:
                        raise UpdateFailed(f"Response is not JSON. First 200 chars: {text[:200]!r}") from e

            dats = result.get("dats") or []
            out: dict[HiDomUnitKey, list[int]] = {}

            # ожидаем, что порядок dats соответствует order devs
            for i, item in enumerate(dats):
                data = item.get("data")
                if not isinstance(data, list):
                    continue
                if i >= len(devs):
                    break
                key = HiDomUnitKey(sys=devs[i]["sys"], addr=devs[i]["addr"])
                out[key] = data

            if not out:
                raise UpdateFailed("Empty dats/data from controller")

            return out

        except Exception as e:
            raise UpdateFailed(str(e)) from e


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Hisense Multi-IDU climates from a config entry."""
    host = entry.data.get("host") or entry.options.get("host")
    if not host:
        # именно это убирает твою ошибку:
        # "ConfigEntryError in forwarded platform climate; Instead raise ConfigEntryError before calling async_forward_entry_setups"
        # → тут мы просто не продолжаем сетап, а логируем понятную причину.
        _LOGGER.error("hisense_multi_idu: missing 'host' in config entry")
        return

    scan_interval = float(entry.options.get("scan_interval", entry.data.get("scan_interval", 10)))

    coordinator = HisenseMultiIduCoordinator(hass, host=host, scan_interval=scan_interval)

    # первый опрос перед созданием сущностей
    await coordinator.async_config_entry_first_refresh()

    entities: list[HisenseAC] = []
    for sys in (1, 2):
        for addr in range(1, 9):
            name = f"IDU S{sys}-{addr}"
            unique_id = f"idu_s{sys}_{addr}"
            entities.append(HisenseAC(coordinator, unique_id, name, sys, addr))

    async_add_entities(entities)


class HisenseAC(ClimateEntity, RestoreEntity):
    """Hisense indoor unit controlled via HiDom HTTP API."""

    _attr_temperature_unit = "°C"
    _attr_min_temp = 16
    _attr_max_temp = 30
    _attr_target_temperature_step = 1.0

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    _attr_hvac_modes = [HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT, HVACMode.OFF]
    _attr_fan_modes = ["high", "medium", "low"]

    def __init__(self, coordinator: HisenseMultiIduCoordinator, unique_id: str, name: str, sys: int, addr: int):
        self.coordinator = coordinator
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._sys = sys
        self._addr = addr

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 25
        self._attr_fan_mode = "medium"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            # не трогаем HVAC из restore — реальный статус приходит по опросу
            t = state.attributes.get("temperature")
            if t is not None:
                try:
                    self._attr_target_temperature = float(t)
                except Exception:
                    pass
            fm = state.attributes.get("fan_mode")
            if fm in self._attr_fan_modes:
                self._attr_fan_mode = fm

    def _hvac_to_model(self) -> int:
        if self._attr_hvac_mode == HVACMode.COOL:
            return MODE_MAP["cool"]
        if self._attr_hvac_mode == HVACMode.DRY:
            return MODE_MAP["dry"]
        if self._attr_hvac_mode == HVACMode.FAN_ONLY:
            return MODE_MAP["fan_only"]
        if self._attr_hvac_mode == HVACMode.HEAT:
            return MODE_MAP["heat"]
        return MODE_MAP["cool"]  # OFF → оставляем cool как "дефолт"

    async def _send_command(self) -> None:
        status = 0 if self._attr_hvac_mode == HVACMode.OFF else 1
        model = self._hvac_to_model()
        wind = FAN_MAP.get(self._attr_fan_mode, FAN_MAP["medium"])
        temp = int(round(float(self._attr_target_temperature)))

        cmd_list = [
            {"seq": 1, "sys": self._sys, "iduAddr": self._addr, "regAddr": 72, "regVal": [2, 0, 0, 0, 0, 0]},
            {"seq": 2, "sys": self._sys, "iduAddr": self._addr, "regAddr": 78, "regVal": [status, model, wind, temp, 0]},
            {"seq": 3, "sys": self._sys, "iduAddr": self._addr, "regAddr": 72, "regVal": [2, 0, 0, 0, 0, 0]},
        ]

        body = json.dumps({"ip": "127.0.0.1", "cmdList": cmd_list})
        url = f"http://{self.coordinator.host}/cgi/set_idu.shtml"

        try:
            async with self.coordinator.session.post(
                url,
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                timeout=6,
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("Hisense set failed: %s %s", resp.status, await resp.text())
        except Exception as e:
            _LOGGER.exception("Hisense set exception: %s", e)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._attr_target_temperature = float(temp)
        await self._send_command()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._attr_hvac_mode = hvac_mode
        await self._send_command()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._attr_fan_mode = fan_mode
        await self._send_command()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        if self._attr_hvac_mode == HVACMode.OFF:
            self._attr_hvac_mode = HVACMode.COOL
        await self._send_command()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        self._attr_hvac_mode = HVACMode.OFF
        await self._send_command()
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        # Обновления берём из coordinator (1 запрос на все 16)
        key = HiDomUnitKey(sys=self._sys, addr=self._addr)
        data = (self.coordinator.data or {}).get(key)

        if not data or len(data) < 32:
            return

        try:
            status = int(data[28])
            model = int(data[29])
            wind = int(data[30])
            temp = int(data[31])

            self._attr_target_temperature = temp
            self._attr_fan_mode = FAN_REVERSE_MAP.get(wind, "medium")

            if status == 0:
                self._attr_hvac_mode = HVACMode.OFF
            else:
                mode_str = MODE_REVERSE_MAP.get(model, "cool")
                self._attr_hvac_mode = {
                    "cool": HVACMode.COOL,
                    "dry": HVACMode.DRY,
                    "fan_only": HVACMode.FAN_ONLY,
                    "heat": HVACMode.HEAT,
                }.get(mode_str, HVACMode.COOL)

        except Exception:
            # не валим сущность из-за кривого массива
            _LOGGER.debug("Bad data array for sys=%s addr=%s: %r", self._sys, self._addr, data)
            return
