"""Select platform for Hisense Multi-IDU vertical louver angle."""
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Профиль команд по фактическим дампам Hidom:
# angle_1 -> 0, auto -> 1, angle_2 -> 2, angle_3 -> 4.
DAMPER_CODE_TO_OPTION = {
    0: "angle_1",
    1: "auto",
    2: "angle_2",
    4: "angle_3",
}

OPTION_TO_DAMPER_CODE = {value: key for key, value in DAMPER_CODE_TO_OPTION.items()}


class HisenseLouverAngleSelect(CoordinatorEntity, SelectEntity):
    """Select entity for setting vertical louver angle."""

    _attr_options = ["angle_1", "angle_2", "angle_3", "auto"]

    def __init__(self, coordinator, client, uid, device_info, entity_name=None):
        super().__init__(coordinator)
        self._client = client
        self._uid = uid

        if "_" in uid:
            s_part, addr_part = uid.split("_")
            self._sys = int(s_part[1:])
            self._addr = int(addr_part)
        else:
            self._sys = 1
            self._addr = 1

        if entity_name:
            self._attr_name = f"{entity_name} Угол жалюзи"
        else:
            self._attr_name = f"IDU {uid} Угол жалюзи"

        self._attr_unique_id = f"{DOMAIN}_{uid}_louver_angle"
        self._attr_device_info = device_info

        self._current_data = {}
        self._current_option = "auto"

    def _update_data(self):
        """Refresh state from coordinator cache."""
        data = self.coordinator.data
        if not data:
            self._current_data = {}
            return

        unit_data = data.get(self._uid, {})
        if unit_data:
            self._current_data = unit_data
            damper_code = unit_data.get("damper_vertical", 1)
            self._current_option = DAMPER_CODE_TO_OPTION.get(damper_code, "auto")

    @property
    def available(self):
        """Return if entity is available."""
        self._update_data()
        return bool(self._current_data)

    @property
    def current_option(self):
        """Return current selected option."""
        self._update_data()
        return self._current_option

    async def async_select_option(self, option: str):
        """Handle user-selected louver angle option."""
        if option not in OPTION_TO_DAMPER_CODE:
            _LOGGER.warning("Unsupported louver option '%s' for %s", option, self._uid)
            return

        damper_code = OPTION_TO_DAMPER_CODE[option]
        success = await self._client.set_damper(
            sys=self._sys,
            addr=self._addr,
            command=damper_code,
        )

        if success:
            self._current_option = option
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set louver option '%s' for %s", option, self._uid)

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        self._update_data()
        attrs = {
            "sys": self._sys,
            "addr": self._addr,
            "uid": self._uid,
        }
        if self._current_data:
            attrs["damper_vertical"] = self._current_data.get("damper_vertical", 0)
            attrs["damper_horizontal"] = self._current_data.get("damper_horizontal", 0)
        return attrs


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up louver angle select entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator_climate"]
    client = data["client"]
    host = data["host"]

    entities = []

    hub_device_name = f"Hisense Multi-IDU Hub ({host})"

    base_device_info = {
        "identifiers": {(DOMAIN, host)},
        "name": hub_device_name,
        "manufacturer": "Hisense",
        "model": "Multi-IDU Hub",
        "configuration_url": f"http://{host}",
    }

    if isinstance(coordinator.data, dict):
        for uid, unit_data in coordinator.data.items():
            if not unit_data:
                continue

            original_name = unit_data.get("name", f"IDU {uid}")

            entity_device_info = base_device_info.copy()
            entity_device_info["via_device"] = (DOMAIN, host)

            suggested_area = unit_data.get("pppname") or unit_data.get("ppname") or unit_data.get("pname")
            if suggested_area:
                entity_device_info["suggested_area"] = suggested_area

            entities.append(
                HisenseLouverAngleSelect(
                    coordinator,
                    client,
                    uid,
                    entity_device_info,
                    entity_name=original_name,
                )
            )

    if entities:
        async_add_entities(entities, update_before_add=True)
        _LOGGER.info("Created %s louver angle entities", len(entities))
    else:
        _LOGGER.info("No louver angle entities created")
