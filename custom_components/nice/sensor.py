from __future__ import annotations

from typing import Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfLength
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify
from homeassistant.util.unit_conversion import DistanceConverter
from nicett6.ciw_helper import CIWHelper
from nicett6.cover import Cover

from homeassistant.util.unit_system import METRIC_SYSTEM

from . import EntityUpdater, NiceData, make_device_info
from .const import DOMAIN


def to_target_length_unit(value, from_length_unit, to_length_unit):
    if value is None:
        return None
    else:
        return DistanceConverter.convert(value, from_length_unit, to_length_unit)


class EntityBuilder:
    def __init__(self, data: NiceData) -> None:
        self.data = data
        self.entities: list[NiceCIWSensor | NiceCoverSensor] = []

    def add_ciw_sensors(
        self,
        name: str,
        icon: str | None,
        native_unit_of_measurement: str | None,
        getter: Callable[[CIWHelper], StateType],
        device_class: SensorDeviceClass | None,
    ):
        self.entities.extend(
            [
                NiceCIWSensor(
                    slugify(f"{id}_{name}"),
                    item["ciw_manager"].get_helper(),
                    f"{item['name']} {name}",
                    icon,
                    native_unit_of_measurement,
                    getter,
                    device_class,
                )
                for id, item in self.data.ciw_mgrs.items()
            ]
        )

    def add_cover_sensors(
        self,
        name: str,
        icon: str | None,
        native_unit_of_measurement: str | None,
        getter: Callable[[Cover], StateType],
        device_class: SensorDeviceClass | None,
    ):
        self.entities.extend(
            [
                NiceCoverSensor(
                    slugify(f"{id}_{name}"),
                    item["tt6_cover"].cover,
                    item["controller_id"],
                    f"{item['tt6_cover'].cover.name} {name}",
                    icon,
                    native_unit_of_measurement,
                    getter,
                    device_class,
                )
                for id, item in self.data.tt6_covers.items()
            ]
        )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the entities."""
    data: NiceData = hass.data[DOMAIN][config_entry.entry_id]
    builder: EntityBuilder = EntityBuilder(data)

    native_length_unit = (
        UnitOfLength.METERS
        if hass.config.units is METRIC_SYSTEM
        else UnitOfLength.INCHES
    )

    builder.add_ciw_sensors(
        "Image Height",
        "mdi:arrow-expand-vertical",
        native_length_unit,
        lambda ciw_helper: ciw_helper.image_height,
        SensorDeviceClass.DISTANCE,
    )
    builder.add_ciw_sensors(
        "Image Width",
        "mdi:arrow-expand-horizontal",
        native_length_unit,
        lambda ciw_helper: ciw_helper.image_width,
        SensorDeviceClass.DISTANCE,
    )
    # Diagonal unit can be set to inches from the Entity Configuration
    builder.add_ciw_sensors(
        "Image Diagonal",
        "mdi:arrow-top-left-bottom-right",
        native_length_unit,
        lambda ciw_helper: ciw_helper.image_diagonal,
        SensorDeviceClass.DISTANCE,
    )
    builder.add_ciw_sensors(
        "Aspect Ratio",
        "mdi:aspect-ratio",
        ":1",
        lambda ciw_helper: ciw_helper.aspect_ratio,
        None,
    )
    builder.add_cover_sensors(
        "Drop",
        "mdi:arrow-collapse-down",
        native_length_unit,
        lambda cover: cover.drop,
        SensorDeviceClass.DISTANCE,
    )
    async_add_entities(builder.entities)


class NiceCIWSensor(SensorEntity):
    """Nice TT6 CIW Sensor."""

    def __init__(
        self,
        unique_id,
        helper: CIWHelper,
        name: str,
        icon: str | None,
        native_unit_of_measurement: str | None,
        getter: Callable[[CIWHelper], StateType],
        device_class: SensorDeviceClass | None,
    ) -> None:
        """A Sensor for a CIWManager property."""
        self._attr_unique_id = unique_id
        self._helper: CIWHelper = helper
        self._attr_name = name
        self._attr_icon = icon
        self._attr_should_poll = False
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._getter = getter
        self._attr_device_class = device_class
        self._updater = EntityUpdater(self.handle_update)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._helper.screen.attach(self._updater)
        self._helper.mask.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._helper.screen.detach(self._updater)
        self._helper.mask.detach(self._updater)

    async def handle_update(self):
        self._attr_native_value = self._getter(self._helper)
        self.async_write_ha_state()


class NiceCoverSensor(SensorEntity):
    """Nice TT6 Cover Sensor."""

    def __init__(
        self,
        unique_id,
        cover: Cover,
        controller_id,
        name: str,
        icon: str | None,
        native_unit_of_measurement: str | None,
        getter: Callable[[Cover], StateType],
        device_class: SensorDeviceClass | None,
    ) -> None:
        """A Sensor for a Cover property."""
        self._attr_unique_id = unique_id
        self._cover: Cover = cover
        self._attr_name = name
        self._attr_icon = icon
        self._attr_should_poll = False
        self._attr_device_info = make_device_info(controller_id)
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._getter = getter
        self._attr_device_class = device_class
        self._updater = EntityUpdater(self.handle_update)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._cover.detach(self._updater)

    async def handle_update(self):
        self._attr_native_value = self._getter(self._cover)
        self.async_write_ha_state()
