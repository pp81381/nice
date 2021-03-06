from __future__ import annotations

from typing import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONF_UNIT_SYSTEM_METRIC,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_METERS,
)
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify
from homeassistant.util.distance import convert as convert_length_units
from nicett6.ciw_helper import CIWHelper
from nicett6.cover import Cover

from . import EntityUpdater, NiceData, make_device_info
from .const import DOMAIN


def to_target_length_unit(value, from_length_unit, to_length_unit):
    if value is None:
        return None
    else:
        return convert_length_units(value, from_length_unit, to_length_unit)


def to_target_area_unit(value, from_length_unit, to_length_unit):
    if value is None:
        return None
    else:
        return convert_length_units(value, from_length_unit, to_length_unit) ** 2


class EntityBuilder:
    def __init__(self, data: NiceData) -> None:
        self.data = data
        self.entities: list[NiceCIWSensor | NiceCoverSensor] = []

    def add_ciw_sensors(
        self,
        name: str,
        icon: str | None,
        native_unit_of_measurement: str | None,
        decimal_places: int | None,
        getter: Callable[[CIWHelper], StateType],
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
                    decimal_places,
                )
                for id, item in self.data.ciw_mgrs.items()
            ]
        )

    def add_cover_sensors(
        self,
        name: str,
        icon: str | None,
        native_unit_of_measurement: str | None,
        decimal_places: int | None,
        getter: Callable[[CIWHelper], StateType],
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
                    decimal_places,
                )
                for id, item in self.data.tt6_covers.items()
            ]
        )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the entities."""
    data: NiceData = hass.data[DOMAIN][config_entry.entry_id]
    builder: EntityBuilder = EntityBuilder(data)

    config_length_unit = (
        LENGTH_METERS
        if data.config_unit_system == CONF_UNIT_SYSTEM_METRIC
        else LENGTH_INCHES
    )

    if data.sensor_unit_system == CONF_UNIT_SYSTEM_METRIC:
        sensor_length_unit = LENGTH_METERS
        sensor_diagonal_length_unit = (
            LENGTH_INCHES if data.force_imperial_diagonal else LENGTH_METERS
        )
        sensor_area_length_unit = LENGTH_METERS
        sensor_area_unit = AREA_SQUARE_METERS
    else:
        sensor_length_unit = LENGTH_INCHES
        sensor_diagonal_length_unit = LENGTH_INCHES
        sensor_area_length_unit = LENGTH_FEET
        sensor_area_unit = "ft??"

    builder.add_ciw_sensors(
        "Image Height",
        "mdi:arrow-expand-vertical",
        sensor_length_unit,
        data.dimensions_decimal_places,
        lambda ciw_helper: to_target_length_unit(
            ciw_helper.image_height,
            config_length_unit,
            sensor_length_unit,
        ),
    )
    builder.add_ciw_sensors(
        "Image Width",
        "mdi:arrow-expand-horizontal",
        sensor_length_unit,
        data.dimensions_decimal_places,
        lambda ciw_helper: to_target_length_unit(
            ciw_helper.image_width,
            config_length_unit,
            sensor_length_unit,
        ),
    )
    builder.add_ciw_sensors(
        "Image Diagonal",
        "mdi:arrow-top-left-bottom-right",
        sensor_diagonal_length_unit,
        data.diagonal_decimal_places,
        lambda ciw_helper: to_target_length_unit(
            ciw_helper.image_diagonal,
            config_length_unit,
            sensor_diagonal_length_unit,
        ),
    )
    builder.add_ciw_sensors(
        "Image Area",
        "mdi:arrow-expand-all",
        sensor_area_unit,
        data.area_decimal_places,
        lambda ciw_helper: to_target_area_unit(
            ciw_helper.image_area,
            config_length_unit,
            sensor_area_length_unit,
        ),
    )
    builder.add_ciw_sensors(
        "Aspect Ratio",
        "mdi:aspect-ratio",
        ":1",
        data.ratio_decimal_places,
        lambda ciw_helper: ciw_helper.aspect_ratio,
    )
    builder.add_cover_sensors(
        "Drop",
        "mdi:arrow-collapse-down",
        sensor_length_unit,
        data.dimensions_decimal_places,
        lambda cover: to_target_length_unit(
            cover.drop,
            config_length_unit,
            sensor_length_unit,
        ),
    )
    async_add_entities(builder.entities)


class NiceCIWSensor(SensorEntity):
    """Nice TT6 CIW Sensor."""

    def __init__(
        self,
        unique_id,
        helper: CIWHelper,
        name: str,
        icon: str,
        native_unit_of_measurement: str | None,
        getter: Callable[[CIWHelper], StateType],
        decimal_places: float | None,
    ) -> None:
        """A Sensor for a CIWManager property."""
        self._attr_unique_id = unique_id
        self._helper: CIWHelper = helper
        self._attr_name = name
        self._attr_icon = icon
        self._attr_should_poll = False
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._getter = getter
        self._decimal_places = decimal_places
        self._updater = EntityUpdater(self.handle_update)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._helper.screen.attach(self._updater)
        self._helper.mask.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._helper.screen.detach(self._updater)
        self._helper.mask.detach(self._updater)

    async def handle_update(self):
        full_precision_value = self._getter(self._helper)
        if full_precision_value is None or self._decimal_places is None:
            self._attr_native_value = full_precision_value
        else:
            self._attr_native_value = round(full_precision_value, self._decimal_places)
        self._attr_extra_state_attributes = {
            "full_precision_value": full_precision_value,
        }
        self.async_write_ha_state()


class NiceCoverSensor(SensorEntity):
    """Nice TT6 Cover Sensor."""

    def __init__(
        self,
        unique_id,
        cover: Cover,
        controller_id,
        name: str,
        icon: str,
        native_unit_of_measurement: str,
        getter: Callable[[Cover], StateType],
        decimal_places: float | None,
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
        self._decimal_places = decimal_places
        self._updater = EntityUpdater(self.handle_update)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._cover.detach(self._updater)

    async def handle_update(self):
        full_precision_value = self._getter(self._cover)
        if full_precision_value is None or self._decimal_places is None:
            self._attr_native_value = full_precision_value
        else:
            self._attr_native_value = round(full_precision_value, self._decimal_places)
        self._attr_extra_state_attributes = {
            "full_precision_value": full_precision_value,
        }
        self.async_write_ha_state()
