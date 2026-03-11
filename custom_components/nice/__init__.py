"""The Nice integration."""

import logging
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ADDRESS,
    CONF_DROP,
    CONF_HAS_INVERSE_SEMANTICS,
    CONF_NODE,
    DOMAIN,
    SUBENTRY_TYPE_COVER,
)
from .runtime_data import NiceConfigEntry, make_runtime_data
from .services import async_setup_services

PLATFORMS = ["cover", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Nice component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NiceConfigEntry) -> bool:
    """Set up Nice from a config entry."""
    _LOGGER.debug("Nice async_setup_entry")

    entry.runtime_data = await make_runtime_data(hass, entry)
    _LOGGER.debug(
        "runtime_data created for nice controller %s",
        entry.runtime_data.controller.name,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NiceConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("nice async_unload_entry")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.controller.stop()

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: NiceConfigEntry) -> bool:
    device_registry = dr.async_get(hass)

    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if entry.version == 1:
        controllers: dict[str, dict[str, Any]] | None = entry.data.get("controllers")
        if controllers is None:
            _LOGGER.warning("Can't migrate configuration - controller data not found")
            return False
        # Only going to support migration of entries with one controller for now
        if len(controllers) != 1:
            _LOGGER.warning("Can't migrate configuration with multiple controllers")
            return False
        old_controller_id, old_controller_data = list(controllers.items())[0]
        new_data = old_controller_data.copy()
        new_options = {}
        new_title = f"NiceTT6: {new_data[CONF_NAME]}"

        covers: dict[str, dict[str, Any]] | None = entry.data.get("covers")
        if covers is not None:
            covers_for_controller = [
                (i, c)
                for i, c in covers.items()
                if c["controller"] == old_controller_id
            ]
            for old_cover_id, cover_data in covers_for_controller:
                new_cover_data = {
                    CONF_NAME: cover_data[CONF_NAME],
                    CONF_ADDRESS: cover_data[CONF_ADDRESS],
                    CONF_NODE: cover_data[CONF_NODE],
                    CONF_DROP: cover_data[CONF_DROP],
                    CONF_HAS_INVERSE_SEMANTICS: cover_data.get(
                        "has_reverse_semantics", False
                    ),
                }
                subentry = ConfigSubentry(
                    subentry_type=SUBENTRY_TYPE_COVER,
                    title=f"Cover: {new_cover_data[CONF_NAME]}",
                    unique_id=f"{new_cover_data[CONF_ADDRESS]:02X}/{new_cover_data[CONF_NODE]:02X}",
                    data=MappingProxyType(new_cover_data),
                )
                hass.config_entries.async_add_subentry(entry, subentry)

                if device := device_registry.async_get_device({(DOMAIN, old_cover_id)}):
                    device_registry.async_update_device(
                        device.id,
                        remove_config_entry_id=entry.entry_id,
                        add_config_subentry_id=subentry.subentry_id,
                        add_config_entry_id=entry.entry_id,
                        new_identifiers={(DOMAIN, subentry.subentry_id)},
                    )

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            title=new_title,
            minor_version=1,
            version=2,
        )

        if device := device_registry.async_get_device({(DOMAIN, old_controller_id)}):
            device_registry.async_update_device(
                device.id,
                new_identifiers={(DOMAIN, entry.entry_id)},
            )

    _LOGGER.info(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True
