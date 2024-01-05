"""The Nice integration."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from nicett6.ciw_helper import CIWHelper
from nicett6.cover import Cover
from nicett6.cover_manager import CoverManager
from nicett6.image_def import ImageDef
from nicett6.tt6_cover import TT6Cover
from nicett6.ttbus_device import TTBusDeviceAddress
from nicett6.utils import AsyncObservable, AsyncObserver

from .const import (
    CHOICE_ASPECT_RATIO_2_35_1,
    CHOICE_ASPECT_RATIO_4_3,
    CHOICE_ASPECT_RATIO_16_9,
    CHOICE_ASPECT_RATIO_OTHER,
    CONF_ADDRESS,
    CONF_CIW_HELPERS,
    CONF_CONTROLLER,
    CONF_CONTROLLERS,
    CONF_COVER,
    CONF_COVERS,
    CONF_DROP,
    CONF_DROPS,
    CONF_HAS_REVERSE_SEMANTICS,
    CONF_IMAGE_AREA,
    CONF_IMAGE_ASPECT_RATIO_CHOICE,
    CONF_IMAGE_ASPECT_RATIO_OTHER,
    CONF_IMAGE_BORDER_BELOW,
    CONF_IMAGE_HEIGHT,
    CONF_MASK_COVER,
    CONF_NODE,
    CONF_PRESETS,
    CONF_SCREEN_COVER,
    CONF_SERIAL_PORT,
    DOMAIN,
    SERVICE_APPLY_PRESET,
)

PLATFORMS = ["cover", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def _await_cancel(task):
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


class NiceControllerWrapper:
    def __init__(self, name: str, serial_port: str) -> None:
        self.name = name
        self._controller = CoverManager(serial_port)
        self._message_tracker_task: asyncio.Task | None = None
        self._undo_listener: CALLBACK_TYPE | None = None

    async def start(self, hass: HomeAssistant):
        await self._controller.open()

        async def handle_started(event: Event) -> None:
            _LOGGER.debug(f"Started Event for Nice Controller {self.name}")
            await self.start_messages(hass)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, handle_started)

    async def start_messages(self, hass: HomeAssistant):
        self._message_tracker_task = asyncio.create_task(
            self._controller.message_tracker()
        )

        async def handle_stop(event: Event) -> None:
            _LOGGER.debug(f"Stop Event for Nice Controller {self.name}")
            await self._stop()

        self._undo_listener = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, handle_stop
        )

    async def add_cover(self, *args) -> TT6Cover:
        return await self._controller.add_cover(*args)

    async def _stop(self):
        await _await_cancel(self._message_tracker_task)
        await self._controller.close()

    async def stop(self) -> None:
        _LOGGER.debug(f"Stopping Nice Controller {self.name}")
        if self._undo_listener is not None:
            self._undo_listener()
        await self._stop()


async def make_nice_controller_wrapper(
    hass: HomeAssistant, name: str, serial_port: str
) -> NiceControllerWrapper:
    """Factory for NiceControllerWrapper objects"""
    wrapper = NiceControllerWrapper(name, serial_port)
    await wrapper.start(hass)
    return wrapper


def image_aspect_ratio_from_config_params(choice: str, other: float) -> float:
    if choice == CHOICE_ASPECT_RATIO_16_9:
        return 16 / 9
    elif choice == CHOICE_ASPECT_RATIO_2_35_1:
        return 2.35
    elif choice == CHOICE_ASPECT_RATIO_4_3:
        return 4 / 3
    elif choice == CHOICE_ASPECT_RATIO_OTHER:
        return other
    else:
        raise ValueError("Invalid aspect ratio choice")


def image_def_from_config(cover_config) -> ImageDef | None:
    image_config = cover_config[CONF_IMAGE_AREA]
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


@dataclass
class NiceCoverData:
    tt6_cover: TT6Cover
    has_reverse_semantics: bool
    image_def: ImageDef | None


@dataclass
class NiceCIWData:
    name: str
    screen_cover_id: str
    ciw_helper: CIWHelper


class NiceData:
    def __init__(self):
        self.controllers: dict[str, NiceControllerWrapper] = {}
        self.nice_covers: dict[str, NiceCoverData] = {}
        self.ciw_helpers: dict[str, NiceCIWData] = {}

    async def add_controller(self, hass, id, config):
        controller = await make_nice_controller_wrapper(
            hass, config[CONF_NAME], config[CONF_SERIAL_PORT]
        )
        self.controllers[id] = controller

    async def add_cover(self, id, cover_config):
        controller = self.controllers[cover_config[CONF_CONTROLLER]]
        tt6_cover = await controller.add_cover(
            TTBusDeviceAddress(cover_config[CONF_ADDRESS], cover_config[CONF_NODE]),
            Cover(cover_config[CONF_NAME], cover_config[CONF_DROP]),
        )
        has_reverse_semantics = cover_config.get(CONF_HAS_REVERSE_SEMANTICS, False)
        self.nice_covers[id] = NiceCoverData(
            tt6_cover,
            has_reverse_semantics,
            image_def_from_config(cover_config),
        )

    def add_ciw_helper(self, id, ciw_config):
        screen: NiceCoverData = self.nice_covers[ciw_config[CONF_SCREEN_COVER]]
        assert screen.image_def is not None
        mask: NiceCoverData = self.nice_covers[ciw_config[CONF_MASK_COVER]]
        self.ciw_helpers[id] = NiceCIWData(
            ciw_config[CONF_NAME],
            ciw_config[CONF_SCREEN_COVER],
            CIWHelper(screen.tt6_cover.cover, mask.tt6_cover.cover, screen.image_def),
        )

    async def close(self):
        self.ciw_helpers = {}
        self.nice_covers = {}
        for controller in self.controllers.values():
            await controller.stop()
        self.controllers = {}


async def make_nice_data(hass: HomeAssistant, entry: ConfigEntry) -> NiceData:
    """Factory for NiceData object"""
    data = NiceData()
    device_registry = dr.async_get(hass)

    for controller_id, controller_config in entry.data[CONF_CONTROLLERS].items():
        await data.add_controller(hass, controller_id, controller_config)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, controller_id)},
            manufacturer="Nice",
            name=controller_config[CONF_NAME],
            model="Nice TT6 Control Unit",
        )

    for cover_id, cover_config in entry.data[CONF_COVERS].items():
        await data.add_cover(cover_id, cover_config)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, cover_id)},
            name=cover_config[CONF_NAME],
            manufacturer="Nice",
            model="Nice Tubular Motor",
            via_device=(DOMAIN, cover_config[CONF_CONTROLLER]),
        )

    if CONF_CIW_HELPERS in entry.options:
        for ciw_id, ciw_config in entry.options[CONF_CIW_HELPERS].items():
            data.add_ciw_helper(ciw_id, ciw_config)

    return data


class EntityUpdater(AsyncObserver):
    def __init__(self, handler: Callable[[], Awaitable[None]]):
        super().__init__()
        self.handler = handler

    async def update(self, observable: AsyncObservable):
        await self.handler()


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def apply_preset(call) -> None:
        """Service call to apply a preset."""
        for preset in entry.options[CONF_PRESETS].values():
            if preset[CONF_NAME] == call.data.get(CONF_NAME):
                for item in preset[CONF_DROPS]:
                    tt6_cover: TT6Cover = nd.nice_covers[item[CONF_COVER]].tt6_cover
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("nice async_unload_entry")
    if hass.services.has_service(DOMAIN, SERVICE_APPLY_PRESET):
        hass.services.async_remove(DOMAIN, SERVICE_APPLY_PRESET)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data[DOMAIN].pop(entry.entry_id)
        await api.close()

    return unload_ok
