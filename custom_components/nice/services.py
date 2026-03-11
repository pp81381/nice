import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SERVICE_RECONNECT
from .runtime_data import NiceConfigEntry

_LOGGER = logging.getLogger(__name__)

SCHEMA_RECONNECT_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
    },
)


# Borrowed from Amazon Alexa integration:
@callback
def async_get_entry_for_service_call(call: ServiceCall) -> NiceConfigEntry:
    """Get the entry ID related to a service call (by device ID)."""
    device_registry = dr.async_get(call.hass)
    device_id = call.data[ATTR_DEVICE_ID]
    if (device_entry := device_registry.async_get(device_id)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    for entry_id in device_entry.config_entries:
        if (entry := call.hass.config_entries.async_get_entry(entry_id)) is None:
            continue
        if entry.domain == DOMAIN:
            if entry.state is not ConfigEntryState.LOADED:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                    translation_placeholders={"entry": entry.title},
                )
            return entry

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="config_entry_not_found",
        translation_placeholders={"device_id": device_id},
    )


async def async_reconnect(call: ServiceCall) -> None:
    """Reconnect the controller device."""
    config_entry = async_get_entry_for_service_call(call)
    _LOGGER.debug(
        "Reconnect service called for Nice Controller %s",
        config_entry.runtime_data.controller.name,
    )
    await config_entry.runtime_data.controller.reconnect()


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Nice integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_RECONNECT, async_reconnect, schema=SCHEMA_RECONNECT_SERVICE
    )
