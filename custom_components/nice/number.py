from homeassistant.components.number import NumberEntity
from homeassistant.util import slugify
from nicett6.ciw_manager import CIWManager, CIWAspectRatioMode

from . import EntityUpdater, NiceData
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the entities."""
    api: NiceData = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        NiceAspectRatio(
            slugify(f"{ciw_id}_aspect_ratio"),
            f"{item['name']} Aspect Ratio",
            item["ciw_manager"],
        )
        for ciw_id, item in api.ciw_mgrs.items()
    ]
    async_add_entities(entities)


class NiceAspectRatio(NumberEntity):
    """Image Aspect Ratio."""

    def __init__(self, unique_id, name, ciw: CIWManager) -> None:
        """Create HA entity to represent image aspect ratio."""
        self._unique_id = unique_id
        self._name = name
        self._ciw: CIWManager = ciw
        self._updater = EntityUpdater(self)

    @property
    def unique_id(self) -> str:
        """Unique id."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Name."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No need to poll"""
        return False

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return 1.2

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return 3.0

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return 0.01

    @property
    def value(self) -> float:
        """Return the aspect ratio."""
        return self._ciw.get_helper().aspect_ratio

    async def async_set_value(self, value: float) -> None:
        """Set the aspect ratio."""
        mode: CIWAspectRatioMode = CIWAspectRatioMode.FIXED_TOP
        baseline_drop = self._ciw.default_baseline_drop(mode)
        await self._ciw.send_set_aspect_ratio(value, mode, baseline_drop)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._ciw.screen_tt6_cover.cover.attach(self._updater)
        self._ciw.mask_tt6_cover.cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._ciw.mask_tt6_cover.cover.detach(self._updater)
        self._ciw.screen_tt6_cover.cover.detach(self._updater)
