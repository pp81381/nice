from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHADE,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.util import slugify
from nicett6.cover import TT6Cover

from . import EntityUpdater, NiceData, make_device_info
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the cover(s)"""
    api: NiceData = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        NiceCover(
            slugify(id),
            item["tt6_cover"],
            item["controller_id"],
        )
        for id, item in api.tt6_covers.items()
    ]
    async_add_entities(entities)


class NiceCover(CoverEntity):
    """Representation of a cover"""

    def __init__(self, unique_id, tt6_cover: TT6Cover, controller_id) -> None:
        """Create HA entity representing a cover"""
        self._attr_unique_id = unique_id
        self._tt6_cover = tt6_cover
        self._attr_name = str(self._tt6_cover.cover.name)
        self._attr_should_poll = False
        self._attr_device_info = make_device_info(controller_id)
        self._updater = EntityUpdater(self.handle_update)

    @property
    def supported_features(self):
        """Flag supported features"""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION

    @property
    def device_class(self) -> str:
        """Get device class"""
        return DEVICE_CLASS_SHADE

    @property
    def is_closed(self) -> bool:
        """Return True if the cover is closed"""
        return self._tt6_cover.cover.is_closed

    @property
    def is_opening(self) -> bool:
        """Return True if the cover is opening"""
        return self._tt6_cover.cover.is_opening

    @property
    def is_closing(self) -> bool:
        """Return True if the cover is closing"""
        return self._tt6_cover.cover.is_closing

    @property
    def current_cover_position(self) -> int:
        """Return the position of the cover from 0 to 100"""
        return round(100.0 - self._tt6_cover.cover.drop_pct * 100.0)

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        await self._tt6_cover.send_open_command()

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover"""
        await self._tt6_cover.send_close_command()

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover"""
        await self._tt6_cover.send_stop_command()

    async def async_set_cover_position(self, **kwargs) -> None:
        """Set the cover position"""
        position = kwargs[ATTR_POSITION]
        await self._tt6_cover.send_drop_pct_command(1.0 - position / 100.0)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._tt6_cover.cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._tt6_cover.cover.detach(self._updater)

    async def handle_update(self):
        self.async_write_ha_state()
