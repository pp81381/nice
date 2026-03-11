from dataclasses import dataclass
from typing import Callable, List

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_system import METRIC_SYSTEM
from nicett6.cover import Cover

from .const import DOMAIN
from .runtime_data import EntityUpdater, NiceConfigEntry, NiceRuntimeData

COVER_VALUE_FN = Callable[[Cover], float | None]


@dataclass(frozen=True)
class NiceCoverSensorEntityDescription:
    """Describes a Nice TT6 Cover"""

    entity_description: SensorEntityDescription
    value_fn: COVER_VALUE_FN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NiceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the entities."""
    native_length_unit = (
        UnitOfLength.METERS
        if hass.config.units is METRIC_SYSTEM
        else UnitOfLength.INCHES
    )

    cover_descriptions: List[NiceCoverSensorEntityDescription] = [
        NiceCoverSensorEntityDescription(
            SensorEntityDescription(
                key="drop",
                name="Drop",
                icon="mdi:arrow-collapse-down",
                native_unit_of_measurement=native_length_unit,
                device_class=SensorDeviceClass.DISTANCE,
            ),
            value_fn=lambda cover: cover.drop,
        )
    ]

    runtime_data: NiceRuntimeData = config_entry.runtime_data

    for se in config_entry.subentries.values():
        cover_id = se.subentry_id
        cover_runtime_data = runtime_data.covers[cover_id]
        async_add_entities(
            [
                NiceCoverSensor(
                    cover_id,
                    desc.entity_description,
                    desc.value_fn,
                    cover_runtime_data.tt6_cover.cover,
                )
                for desc in cover_descriptions
            ],
            update_before_add=False,
            config_subentry_id=se.subentry_id,
        )


class NiceCoverSensor(SensorEntity):
    """Nice TT6 Cover Sensor."""

    def __init__(
        self,
        cover_id: str,
        entity_description: SensorEntityDescription,
        value_fn: COVER_VALUE_FN,
        cover: Cover,
    ) -> None:
        """A Sensor for a Cover property."""
        self.entity_description = entity_description
        self._value_fn = value_fn
        self._attr_unique_id = f"{cover_id}_{entity_description.key}"
        self._attr_should_poll = False
        self._attr_device_info = {"identifiers": {(DOMAIN, cover_id)}}
        self._attr_has_entity_name = True
        self._cover: Cover = cover
        self._updater = EntityUpdater(self.handle_update)

    async def async_added_to_hass(self):
        """Register device notification."""
        self._cover.attach(self._updater)

    async def async_will_remove_from_hass(self):
        self._cover.detach(self._updater)

    async def handle_update(self):
        self._attr_native_value = self._value_fn(self._cover)
        self.async_write_ha_state()
