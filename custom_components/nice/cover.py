import voluptuous as vol
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.helpers import entity_platform
from homeassistant.util import slugify
from nicett6.command_code import simple_command_code_names
from nicett6.tt6_cover import TT6Cover

from . import EntityUpdater, NiceData
from .const import DOMAIN, SERVICE_SEND_SIMPLE_COMMAND, SERVICE_SET_DROP_PERCENT


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the cover(s)"""
    data: NiceData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        NiceCover(slugify(id), item.tt6_cover) for id, item in data.nice_covers.items()
    ]
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_DROP_PERCENT,
        {
            vol.Required("drop_percent"): vol.All(
                vol.Coerce(float), vol.Range(min=0.0, max=100.0)
            )
        },
        "async_set_drop_percent",
    )

    simple_commands = [cn.lower() for cn in simple_command_code_names()]
    platform.async_register_entity_service(
        SERVICE_SEND_SIMPLE_COMMAND,
        {vol.Required("command"): vol.In(simple_commands)},
        "async_send_simple_command",
    )


class NiceCover(CoverEntity):
    """Representation of a cover"""

    def __init__(self, cover_id: str, tt6_cover: TT6Cover) -> None:
        """Create HA entity representing a cover"""
        self._attr_unique_id = cover_id
        self._tt6_cover: TT6Cover = tt6_cover
        self._attr_has_entity_name = True
        self._attr_name = None
        self._attr_is_closed = None  # Not initialised by CoverEntity
        self._attr_should_poll = False
        self._attr_device_class = CoverDeviceClass.SCREEN
        self._attr_device_info = {"identifiers": {(DOMAIN, cover_id)}}
        self._updater = EntityUpdater(self.handle_update)
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        await self.async_send_simple_command("move_down")

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover"""
        await self.async_send_simple_command("move_up")

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover"""
        await self.async_send_simple_command("stop")

    async def async_set_cover_position(self, **kwargs) -> None:
        """Set the cover to an int position"""
        await self.async_set_drop_percent(kwargs[ATTR_POSITION])

    async def async_set_drop_percent(self, drop_percent: float) -> None:
        """Set the cover to a float position (thousandths accuracy)"""
        await self._tt6_cover.send_drop_pct_command(drop_percent / 100.0)

    async def async_send_simple_command(self, command: str) -> None:
        """Send a simple command to the Cover"""
        await self._tt6_cover.send_simple_command(command.upper())

    async def async_added_to_hass(self):
        """Register device notification."""
        self._tt6_cover.cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._tt6_cover.cover.detach(self._updater)

    async def handle_update(self):
        self._attr_is_opening = self._tt6_cover.cover.is_going_down
        self._attr_is_closing = self._tt6_cover.cover.is_going_up
        self._attr_is_closed = self._tt6_cover.cover.is_fully_up
        drop_percent_scaled = self._tt6_cover.cover.drop_pct * 100.0
        self._attr_current_cover_position = round(drop_percent_scaled)
        self._attr_extra_state_attributes = {"drop_percent": drop_percent_scaled}
        self.async_write_ha_state()
