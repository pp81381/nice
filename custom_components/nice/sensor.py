from dataclasses import dataclass
from typing import Callable, Union

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import AREA_SQUARE_METERS, LENGTH_METERS
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify
from nicett6.ciw_helper import CIWHelper
from nicett6.ciw_manager import CIWManager
from nicett6.cover import Cover

from . import EntityUpdater, NiceData
from .const import DOMAIN


@dataclass
class NiceSensorDef:
    name: str
    icon: Union[str, None]
    unit_of_measurement: Union[str, None]
    getter: Callable[[CIWHelper], StateType]


CIW_SENSORS = (
    NiceSensorDef(
        "Image Height",
        "mdi:arrow-expand-vertical",
        LENGTH_METERS,
        lambda ciw_helper: ciw_helper.image_height,
    ),
    NiceSensorDef(
        "Image Width",
        "mdi:arrow-expand-horizontal",
        LENGTH_METERS,
        lambda ciw_helper: ciw_helper.image_width,
    ),
    NiceSensorDef(
        "Image Diagonal",
        "mdi:arrow-top-left-bottom-right",
        LENGTH_METERS,
        lambda ciw_helper: ciw_helper.image_diagonal,
    ),
    NiceSensorDef(
        "Image Area",
        "mdi:arrow-expand-all",
        AREA_SQUARE_METERS,
        lambda ciw_helper: ciw_helper.image_area,
    ),
)

COVER_SENSORS = (
    NiceSensorDef(
        "Drop",
        "mdi:arrow-collapse-down",
        LENGTH_METERS,
        lambda cover: cover.drop,
    ),
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the entities."""
    api: NiceData = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for sd in CIW_SENSORS:
        entities.extend(
            [
                NiceCIWSensor(
                    slugify(f"{id}_{sd.name}"),
                    item["ciw_manager"],
                    f"{item['name']} {sd.name}",
                    sd.icon,
                    sd.unit_of_measurement,
                    sd.getter,
                )
                for id, item in api.ciw_mgrs.items()
            ]
        )
    for sd in COVER_SENSORS:
        entities.extend(
            [
                NiceCoverSensor(
                    slugify(f"{id}_{sd.name}"),
                    item["tt6_cover"].cover,
                    item["controller_id"],
                    f"{item['tt6_cover'].cover.name} {sd.name}",
                    sd.icon,
                    sd.unit_of_measurement,
                    sd.getter,
                )
                for id, item in api.tt6_covers.items()
            ]
        )
    async_add_entities(entities)


class NiceCIWSensor(SensorEntity):
    """Nice TT6 CIW Sensor."""

    def __init__(
        self,
        unique_id,
        ciw: CIWManager,
        name: str,
        icon: str,
        unit_of_measurement: str,
        getter: Callable[[CIWHelper], StateType],
    ) -> None:
        """A Sensor for a CIWManager property."""
        self._unique_id = unique_id
        self._ciw: CIWManager = ciw
        self._name = name
        self._icon = icon
        self._unit_of_measurement = unit_of_measurement
        self._getter = getter
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
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._getter(self._ciw.helper)

    @property
    def unit_of_measurement(self) -> Union[str, None]:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self) -> Union[str, None]:
        """Return the icon to use in the frontend, if any."""
        return self._icon

    async def async_added_to_hass(self):
        """Register device notification."""
        self._ciw.screen_tt6_cover.cover.attach(self._updater)
        self._ciw.mask_tt6_cover.cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._ciw.mask_tt6_cover.cover.detach(self._updater)
        self._ciw.screen_tt6_cover.cover.detach(self._updater)


class NiceCoverSensor(SensorEntity):
    """Nice TT6 Cover Sensor."""

    def __init__(
        self,
        unique_id,
        cover: Cover,
        controller_id,
        name: str,
        icon: str,
        unit_of_measurement: str,
        getter: Callable[[Cover], StateType],
    ) -> None:
        """A Sensor for a Cover property."""
        self._unique_id = unique_id
        self._cover: Cover = cover
        self._controller_id = controller_id
        self._name = name
        self._icon = icon
        self._unit_of_measurement = unit_of_measurement
        self._getter = getter
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
    def state(self) -> StateType:
        """Return the state of the entity."""
        return self._getter(self._cover)

    @property
    def unit_of_measurement(self) -> Union[str, None]:
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self) -> Union[str, None]:
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_info(self):
        """Return parent device information."""
        return {
            "identifiers": {(DOMAIN, self._controller_id)},
            "name": f"Nice TT6 ({self._controller_id})",
            "manufacturer": "Nice",
            "model": "TT6 Control Unit",
        }

    async def async_added_to_hass(self):
        """Register device notification."""
        self._cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._cover.detach(self._updater)
