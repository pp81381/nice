from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def init_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    if config_entry.entry_id not in hass.config_entries.async_entry_ids():
        config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def get_suggested_values_from_schema(data_schema: vol.Schema) -> list[Any]:
    return [
        field.description.get("suggested_value") for field in data_schema.schema.keys()
    ]
