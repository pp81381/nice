"""The Nice integration."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any, Callable

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_UNIT_SYSTEM, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from nicett6.ciw_helper import ImageDef
from nicett6.ciw_manager import CIWAspectRatioMode, CIWManager
from nicett6.cover import Cover, TT6Cover
from nicett6.cover_manager import CoverManager
from nicett6.ttbus_device import TTBusDeviceAddress
from nicett6.utils import AsyncObservable, AsyncObserver

from .const import (
    CHOICE_ASPECT_RATIO_2_35_1,
    CHOICE_ASPECT_RATIO_4_3,
    CHOICE_ASPECT_RATIO_16_9,
    CHOICE_ASPECT_RATIO_OTHER,
    CONF_ADDRESS,
    CONF_AREA_DECIMAL_PLACES,
    CONF_ASPECT_RATIO,
    CONF_ASPECT_RATIO_MODE,
    CONF_BASELINE_DROP,
    CONF_CIW_MANAGERS,
    CONF_CONTROLLER,
    CONF_CONTROLLERS,
    CONF_COVER,
    CONF_COVERS,
    CONF_DIAGONAL_DECIMAL_PLACES,
    CONF_DIMENSIONS_DECIMAL_PLACES,
    CONF_DROP,
    CONF_DROPS,
    CONF_FORCE_DIAGONAL_IMPERIAL,
    CONF_IMAGE_AREA,
    CONF_IMAGE_ASPECT_RATIO_CHOICE,
    CONF_IMAGE_ASPECT_RATIO_OTHER,
    CONF_IMAGE_BORDER_BELOW,
    CONF_IMAGE_HEIGHT,
    CONF_MASK_COVER,
    CONF_NODE,
    CONF_PRESETS,
    CONF_RATIO_DECIMAL_PLACES,
    CONF_SCREEN_COVER,
    CONF_SENSOR_PREFS,
    CONF_SERIAL_PORT,
    DEFAULT_AREA_DECIMAL_PLACES,
    DEFAULT_DIAGONAL_DECIMAL_PLACES,
    DEFAULT_DIMENSIONS_DECIMAL_PLACES,
    DEFAULT_RATIO_DECIMAL_PLACES,
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


def image_aspect_ratio_from_config_params(choice, other):
    if choice == CHOICE_ASPECT_RATIO_16_9:
        return 16 / 9
    elif choice == CHOICE_ASPECT_RATIO_2_35_1:
        return 2.35
    elif choice == CHOICE_ASPECT_RATIO_4_3:
        return 4 / 3
    elif choice == CHOICE_ASPECT_RATIO_OTHER:
        return other
    else:
        ValueError("Invalid aspect ratio choice")


def image_def_from_config(config):
    image_config = config[CONF_IMAGE_AREA]
    if image_config is not None:
        return ImageDef(
            image_config[CONF_IMAGE_BORDER_BELOW],
            image_config[CONF_IMAGE_HEIGHT],
            image_aspect_ratio_from_config_params(
                image_config[CONF_IMAGE_ASPECT_RATIO_CHOICE],
                image_config[CONF_IMAGE_ASPECT_RATIO_OTHER],
            ),
        )
    else:
        return None


class NiceData:
    def __init__(self, config_unit_system: str, sensor_prefs: dict[str, Any]):
        self.config_unit_system: str = config_unit_system
        self.controllers: dict[str, CoverManager] = {}
        self.tt6_covers: dict[str, dict[str, Any]] = {}
        self.ciw_mgrs: dict[str, CIWManager] = {}
        self._sensor_prefs: dict[str, Any] = sensor_prefs

    @property
    def sensor_unit_system(self):
        return self._sensor_prefs.get(
            CONF_UNIT_SYSTEM,
            self.config_unit_system,
        )

    @property
    def force_imperial_diagonal(self):
        return self._sensor_prefs.get(
            CONF_FORCE_DIAGONAL_IMPERIAL,
            False,
        )

    @property
    def dimensions_decimal_places(self) -> int:
        return self._sensor_prefs.get(
            CONF_DIMENSIONS_DECIMAL_PLACES,
            DEFAULT_DIMENSIONS_DECIMAL_PLACES,
        )

    @property
    def diagonal_decimal_places(self) -> int:
        return self._sensor_prefs.get(
            CONF_DIAGONAL_DECIMAL_PLACES,
            DEFAULT_DIAGONAL_DECIMAL_PLACES,
        )

    @property
    def area_decimal_places(self) -> int:
        return self._sensor_prefs.get(
            CONF_AREA_DECIMAL_PLACES,
            DEFAULT_AREA_DECIMAL_PLACES,
        )

    @property
    def ratio_decimal_places(self) -> int:
        return self._sensor_prefs.get(
            CONF_RATIO_DECIMAL_PLACES,
            DEFAULT_RATIO_DECIMAL_PLACES,
        )

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


async def make_nice_data(hass: HomeAssistant, entry: ConfigEntry) -> NiceData:
    """Factory for NiceData object"""
    data = NiceData(
        entry.data[CONF_UNIT_SYSTEM],
        entry.options.get(CONF_SENSOR_PREFS, {}),
    )

    for controller_id, controller_config in entry.data[CONF_CONTROLLERS].items():
        await data.add_controller(hass, controller_id, controller_config)

    for cover_id, cover_config in entry.data[CONF_COVERS].items():
        await data.add_cover(cover_id, cover_config)

    if CONF_CIW_MANAGERS in entry.options:
        for ciw_id, ciw_config in entry.options[CONF_CIW_MANAGERS].items():
            data.add_ciw_manager(ciw_id, ciw_config)

    return data


class EntityUpdater(AsyncObserver):
    def __init__(self, handler: Callable[[], None]):
        super().__init__()
        self.handler = handler

    async def update(self, observable: AsyncObservable):
        await self.handler()


def make_device_info(controller_id):
    """Return parent device information."""
    return {
        "identifiers": {(DOMAIN, controller_id)},
        "name": f"Nice TT6 ({controller_id})",
        "manufacturer": "Nice",
        "model": "TT6 Control Unit",
    }


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nice from a config entry."""
    _LOGGER.debug("nice async_setup_entry")

    nd = await make_nice_data(hass, entry)

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
