import voluptuous as vol
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import get_device_class
from homeassistant.util import slugify
from nicett6.cover import TT6Cover

from . import EntityUpdater, NiceData, make_device_info
from .const import DOMAIN, SERVICE_SET_DROP_PERCENT


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the cover(s)"""
    data: NiceData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        NiceCover(
            slugify(id),
            item["tt6_cover"],
            item["controller_id"],
        )
        for id, item in data.tt6_covers.items()
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


class NiceCover(CoverEntity):
    """Representation of a cover"""

    def __init__(self, unique_id, tt6_cover: TT6Cover, controller_id) -> None:
        """Create HA entity representing a cover"""
        self._attr_unique_id = unique_id
        self._tt6_cover: TT6Cover = tt6_cover
        self._attr_name = str(self._tt6_cover.cover.name)
        self._attr_is_closed = None  # Not initialised by CoverEntity
        self._attr_should_poll = False
        self._attr_device_class = CoverDeviceClass.SHADE
        self._attr_device_info = make_device_info(controller_id)
        self._updater = EntityUpdater(self.handle_update)
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        if get_device_class(self.hass, self.entity_id) == "screen":
            await self._tt6_cover.send_open_command()
        else:
            await self._tt6_cover.send_close_command()

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover"""
        if get_device_class(self.hass, self.entity_id) == "screen":
            await self._tt6_cover.send_close_command()
        else:
            await self._tt6_cover.send_open_command()

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover"""
        await self._tt6_cover.send_stop_command()

    async def async_set_cover_position(self, **kwargs) -> None:
        """Set the cover to an int position"""
        await self.async_set_drop_percent(kwargs[ATTR_POSITION])

    async def async_set_drop_percent(self, drop_percent: float) -> None:
        """Set the cover to a float position (thousandths accuracy)"""
        if get_device_class(self.hass, self.entity_id) == "screen":
            await self._tt6_cover.send_drop_pct_command(1.0 - drop_percent / 100.0)
        else:
            await self._tt6_cover.send_drop_pct_command(drop_percent / 100.0)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._tt6_cover.cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._tt6_cover.cover.detach(self._updater)

    async def handle_update(self):
        if get_device_class(self.hass, self.entity_id) == "screen":
            drop_percent = 100.0 - self._tt6_cover.cover.drop_pct * 100.0
            self._attr_is_opening = self._tt6_cover.cover.is_opening
            self._attr_is_closing = self._tt6_cover.cover.is_closing
            self._attr_is_closed = self._tt6_cover.cover.is_closed
        else:
            drop_percent = self._tt6_cover.cover.drop_pct * 100.0
            self._attr_is_opening = self._tt6_cover.cover.is_closing
            self._attr_is_closing = self._tt6_cover.cover.is_opening
            self._attr_is_closed = not self._tt6_cover.cover.is_closed
        self._attr_current_cover_position = round(drop_percent)
        self._attr_extra_state_attributes = {"drop_percent": drop_percent}
        self.async_write_ha_state()
