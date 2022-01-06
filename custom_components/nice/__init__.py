"""The Nice integration."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from nicett6.ciw_helper import ImageDef
from nicett6.ciw_manager import CIWAspectRatioMode, CIWManager
from nicett6.cover import Cover, TT6Cover
from nicett6.cover_manager import CoverManager
from nicett6.ttbus_device import TTBusDeviceAddress
from nicett6.utils import AsyncObservable, AsyncObserver

from .const import (
    CONF_ADDRESS,
    CONF_ASPECT_RATIO,
    CONF_ASPECT_RATIO_MODE,
    CONF_BASELINE_DROP,
    CONF_CIW_MANAGERS,
    CONF_CONTROLLER,
    CONF_CONTROLLERS,
    CONF_COVER,
    CONF_COVERS,
    CONF_DROP,
    CONF_DROPS,
    CONF_FORCE_DIAGONAL_IMPERIAL,
    CONF_IMAGE_AREA,
    CONF_IMAGE_ASPECT_RATIO,
    CONF_IMAGE_BORDER_BELOW,
    CONF_IMAGE_HEIGHT,
    CONF_MASK_COVER,
    CONF_NODE,
    CONF_PRESETS,
    CONF_SCREEN_COVER,
    CONF_SENSOR_PREFS,
    CONF_SERIAL_PORT,
    DOMAIN,
    SERVICE_APPLY_PRESET,
    SERVICE_SET_ASPECT_RATIO,
)

CIW_ASPECT_RATIO_MODE_MAP = {
    "FIXED_TOP": CIWAspectRatioMode.FIXED_TOP,
    "FIXED_MIDDLE": CIWAspectRatioMode.FIXED_MIDDLE,
    "FIXED_BOTTOM": CIWAspectRatioMode.FIXED_BOTTOM,
}

PLATFORMS = ["cover", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def _await_cancel(task):
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


class NiceControllerWrapper:
    def __init__(self, name):
        self.name = name
        self._controller = None
        self._message_tracker_task = None
        self._undo_listener = None

    async def open(self, hass, serial_port):
        self._controller = CoverManager(serial_port)
        await self._controller.open()

        self._message_tracker_task = asyncio.create_task(
            self._controller.message_tracker()
        )

        async def handle_stop(event):
            _LOGGER.debug(f"Stop Event for Nice Controller {self.name}")
            await self._close()

        self._undo_listener = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, handle_stop
        )

    async def add_cover(self, *args) -> TT6Cover:
        return await self._controller.add_cover(*args)

    async def _close(self):
        await _await_cancel(self._message_tracker_task)
        await self._controller.close()

    async def close(self):
        _LOGGER.debug(f"Closing Nice Controller {self.name}")
        self._undo_listener()
        await self._close()


def image_def_from_config(config):
    image_config = config[CONF_IMAGE_AREA]
    if image_config is not None:
        return ImageDef(
            image_config[CONF_IMAGE_BORDER_BELOW],
            image_config[CONF_IMAGE_HEIGHT],
            image_config[CONF_IMAGE_ASPECT_RATIO],
        )
    else:
        return None


class NiceData:
    def __init__(self):
        self.config_unit_system: str = None
        self.controllers: dict[str, CoverManager] = {}
        self.tt6_covers: dict[str, dict[str, Any]] = {}
        self.ciw_mgrs: dict[str, CIWManager] = {}
        self.force_imperial_diagonal: bool = False
        self.sensor_unit_system: str = CONF_UNIT_SYSTEM_METRIC

    async def add_controller(self, hass, id, config):
        controller = NiceControllerWrapper(config[CONF_NAME])
        await controller.open(hass, config[CONF_SERIAL_PORT])
        self.controllers[id] = controller

    async def add_cover(self, id, config):
        controller = self.controllers[config[CONF_CONTROLLER]]
        tt6_cover = await controller.add_cover(
            TTBusDeviceAddress(config[CONF_ADDRESS], config[CONF_NODE]),
            Cover(config[CONF_NAME], config[CONF_DROP]),
        )
        self.tt6_covers[id] = {
            "tt6_cover": tt6_cover,
            "controller_id": config[CONF_CONTROLLER],
            "image_def": image_def_from_config(config),
        }

    def add_ciw_manager(self, id, config):
        self.ciw_mgrs[id] = {
            "name": config[CONF_NAME],
            "ciw_manager": CIWManager(
                self.tt6_covers[config[CONF_SCREEN_COVER]]["tt6_cover"],
                self.tt6_covers[config[CONF_MASK_COVER]]["tt6_cover"],
                self.tt6_covers[config[CONF_SCREEN_COVER]]["image_def"],
            ),
            "mode": CIW_ASPECT_RATIO_MODE_MAP[config[CONF_ASPECT_RATIO_MODE]],
            "baseline_drop": config[CONF_BASELINE_DROP],
        }

    async def close(self):
        self.ciw_mgrs = {}
        self.tt6_covers = {}
        for controller in self.controllers.values():
            await controller.close()
        self.controllers = {}


class EntityUpdater(AsyncObserver):
    def __init__(self, entity):
        super().__init__()
        self.entity = entity

    async def update(self, observable: AsyncObservable):
        self.entity.async_schedule_update_ha_state(False)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nice from a config entry."""
    _LOGGER.debug("nice async_setup_entry")

    nd = NiceData()

    nd.config_unit_system = entry.data[CONF_UNIT_SYSTEM]
    nd.sensor_unit_system = entry.options[CONF_SENSOR_PREFS].get(
        CONF_UNIT_SYSTEM,
        nd.config_unit_system,
    )
    nd.force_imperial_diagonal = entry.options[CONF_SENSOR_PREFS].get(
        CONF_FORCE_DIAGONAL_IMPERIAL,
        False,
    )

    for controller_id, controller_config in entry.data[CONF_CONTROLLERS].items():
        await nd.add_controller(hass, controller_id, controller_config)

    for cover_id, cover_config in entry.data[CONF_COVERS].items():
        await nd.add_cover(cover_id, cover_config)

    if CONF_CIW_MANAGERS in entry.options:
        for ciw_id, ciw_config in entry.options[CONF_CIW_MANAGERS].items():
            nd.add_ciw_manager(ciw_id, ciw_config)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = nd

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def apply_preset(call) -> None:
        """Service call to apply a preset."""
        for preset in entry.options[CONF_PRESETS].values():
            if preset[CONF_NAME] == call.data.get(CONF_NAME):
                for item in preset[CONF_DROPS]:
                    tt6_cover: TT6Cover = nd.tt6_covers[item[CONF_COVER]]["tt6_cover"]
                    await tt6_cover.send_drop_pct_command(
                        1.0 - item[CONF_DROP] / tt6_cover.cover.max_drop
                    )

    if CONF_PRESETS in entry.options:
        names = [config[CONF_NAME] for config in entry.options[CONF_PRESETS].values()]
        SERVICE_APPLY_PRESET_SCHEMA = vol.Schema(
            {vol.Required(CONF_NAME): vol.In(names)}
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_APPLY_PRESET,
            apply_preset,
            schema=SERVICE_APPLY_PRESET_SCHEMA,
        )

    async def set_aspect_ratio(call) -> None:
        """Service call to set the aspect ratio of a CIWManager."""
        for ciw in nd.ciw_mgrs.values():
            if ciw[CONF_NAME] == call.data.get(CONF_NAME):
                mgr: CIWManager = ciw["ciw_manager"]
                mode: CIWAspectRatioMode = ciw["mode"]
                baseline_drop = ciw["baseline_drop"]
                if baseline_drop is None:
                    baseline_drop = mgr.default_baseline_drop(mode)
                await mgr.send_set_aspect_ratio(
                    call.data.get(CONF_ASPECT_RATIO),
                    mode,
                    baseline_drop,
                )

    if CONF_CIW_MANAGERS in entry.options:
        names = [
            config[CONF_NAME] for config in entry.options[CONF_CIW_MANAGERS].values()
        ]
        SERVICE_SET_ASPECT_RATIO_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_NAME): vol.In(names),
                vol.Required(CONF_ASPECT_RATIO): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=0.4, max=3.5),
                    msg="invalid aspect ratio",
                ),
            }
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_ASPECT_RATIO,
            set_aspect_ratio,
            schema=SERVICE_SET_ASPECT_RATIO_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("nice async_unload_entry")
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_PRESET):
        hass.services.async_remove(DOMAIN, SERVICE_APPLY_PRESET)
    if hass.services.has_service(DOMAIN, SERVICE_SET_ASPECT_RATIO):
        hass.services.async_remove(DOMAIN, SERVICE_SET_ASPECT_RATIO)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data[DOMAIN].pop(entry.entry_id)
        await api.close()

    return unload_ok
