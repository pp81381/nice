from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfLength
from homeassistant.util.unit_system import METRIC_SYSTEM
from nicett6.ciw_helper import CIWHelper
from nicett6.cover import Cover

from . import EntityUpdater, NiceData
from .const import DOMAIN


@dataclass
class NiceCIWSensorEntityDescriptionMixIn:
    value_fn: Callable[[CIWHelper], float | None]


@dataclass
class NiceCIWSensorEntityDescription(
    SensorEntityDescription, NiceCIWSensorEntityDescriptionMixIn
):
    """Describes a Nice TT6 CIW Sensor"""


@dataclass
class NiceCoverSensorEntityDescriptionMixIn:
    value_fn: Callable[[Cover], float | None]


@dataclass
class NiceCoverSensorEntityDescription(
    SensorEntityDescription, NiceCoverSensorEntityDescriptionMixIn
):
    """Describes a Nice TT6 Cover"""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the entities."""
    data: NiceData = hass.data[DOMAIN][config_entry.entry_id]

    native_length_unit = (
        UnitOfLength.METERS
        if hass.config.units is METRIC_SYSTEM
        else UnitOfLength.INCHES
    )

    ciw_sensor_descriptions: List[NiceCIWSensorEntityDescription] = [
        NiceCIWSensorEntityDescription(
            key="image_height",
            name="Image Height",
            icon="mdi:arrow-expand-vertical",
            native_unit_of_measurement=native_length_unit,
            device_class=SensorDeviceClass.DISTANCE,
            value_fn=lambda ciw_helper: ciw_helper.image_height,
        ),
        NiceCIWSensorEntityDescription(
            key="image_width",
            name="Image Width",
            icon="mdi:arrow-expand-horizontal",
            native_unit_of_measurement=native_length_unit,
            device_class=SensorDeviceClass.DISTANCE,
            value_fn=lambda ciw_helper: ciw_helper.image_width,
        ),
        NiceCIWSensorEntityDescription(
            key="image_diagonal",
            name="Image Diagonal",
            icon="mdi:arrow-top-left-bottom-right",
            # Diagonal unit can be set to inches from the Entity Configuration
            native_unit_of_measurement=native_length_unit,
            device_class=SensorDeviceClass.DISTANCE,
            value_fn=lambda ciw_helper: ciw_helper.image_diagonal,
        ),
        NiceCIWSensorEntityDescription(
            key="image_aspect_ratio",
            name="Image Aspect Ratio",
            icon="mdi:aspect-ratio",
            native_unit_of_measurement=":1",
            value_fn=lambda ciw_helper: ciw_helper.aspect_ratio,
        ),
    ]

    cover_descriptions: List[NiceCoverSensorEntityDescription] = [
        NiceCoverSensorEntityDescription(
            key="drop",
            name="Drop",
            icon="mdi:arrow-collapse-down",
            native_unit_of_measurement=native_length_unit,
            device_class=SensorDeviceClass.DISTANCE,
            value_fn=lambda cover: cover.drop,
        )
    ]

    async_add_entities(
        [
            NiceCIWSensor(id, entity_description, item)
            for id, item in data.ciw_helpers.items()
            for entity_description in ciw_sensor_descriptions
        ]
    )

    async_add_entities(
        [
            NiceCoverSensor(id, entity_description, item)
            for id, item in data.tt6_covers.items()
            for entity_description in cover_descriptions
        ]
    )


class NiceCIWSensor(SensorEntity):
    """Nice TT6 CIW Sensor."""

    def __init__(
        self,
        ciw_id: str,
        entity_description: NiceCIWSensorEntityDescription,
        data: dict[str, Any],
    ) -> None:
        """A Sensor for a CIWHelper property."""
        self.entity_description: NiceCIWSensorEntityDescription = entity_description
        self._attr_unique_id = f"{ciw_id}_{entity_description.key}"
        self._attr_should_poll = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, data["screen_cover_id"])}
        }  # Image area is part of screen
        self._attr_has_entity_name = True
        self._helper: CIWHelper = data["ciw_helper"]
        self._updater = EntityUpdater(self.handle_update)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._helper.screen.attach(self._updater)
        self._helper.mask.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._helper.screen.detach(self._updater)
        self._helper.mask.detach(self._updater)

    async def handle_update(self):
        self._attr_native_value = self.entity_description.value_fn(self._helper)
        self.async_write_ha_state()


class NiceCoverSensor(SensorEntity):
    """Nice TT6 Cover Sensor."""

    def __init__(
        self,
        cover_id: str,
        entity_description: NiceCoverSensorEntityDescription,
        data: dict[str, Any],
    ) -> None:
        """A Sensor for a Cover property."""
        self.entity_description: NiceCoverSensorEntityDescription = entity_description
        self._attr_unique_id = f"{cover_id}_{entity_description.key}"
        self._attr_should_poll = False
        self._attr_device_info = {"identifiers": {(DOMAIN, cover_id)}}
        self._attr_has_entity_name = True
        self._cover: Cover = data["tt6_cover"].cover
        self._updater = EntityUpdater(self.handle_update)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._cover.detach(self._updater)

    async def handle_update(self):
        self._attr_native_value = self.entity_description.value_fn(self._cover)
        self.async_write_ha_state()
