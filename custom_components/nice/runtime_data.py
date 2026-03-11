import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, CoreState, Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from nicett6.cover import Cover
from nicett6.cover_manager import CoverManager
from nicett6.tt6_cover import TT6Cover
from nicett6.ttbus_device import TTBusDeviceAddress
from nicett6.utils import AsyncObservable, AsyncObserver

from .const import (
    CONF_ADDRESS,
    CONF_DROP,
    CONF_HAS_INVERSE_ENDPOINTS,
    CONF_HAS_INVERSE_SEMANTICS,
    CONF_NODE,
    CONF_SERIAL_PORT,
    DOMAIN,
)

PLATFORMS = ["cover", "sensor"]

_LOGGER = logging.getLogger(__name__)

type NiceConfigEntry = ConfigEntry[NiceRuntimeData]


class EntityUpdater(AsyncObserver):
    def __init__(self, handler: Callable[[], Awaitable[None]]):
        super().__init__()
        self.handler = handler

    async def update(self, observable: AsyncObservable):
        await self.handler()


class NiceControllerRunTimeData:
    def __init__(self, name: str, serial_port: str) -> None:
        self.name = name
        self._controller = CoverManager(serial_port)
        self._message_tracker_task: asyncio.Task | None = None
        self._undo_listener: CALLBACK_TYPE | None = None

    async def start(self, hass: HomeAssistant) -> None:
        _LOGGER.debug(f"Opening Nice Controller {self.name}")
        await self._controller.open()
        if hass.state is CoreState.running:
            await self.start_messages(hass)
        else:
            self.queue_start_messages(hass)

    def queue_start_messages(self, hass: HomeAssistant) -> None:
        _LOGGER.debug(f"Queuing Message Tracker for Nice Controller {self.name}")

        async def handle_started(event: Event) -> None:
            await self.start_messages(hass)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, handle_started)

    async def start_messages(self, hass: HomeAssistant) -> None:
        _LOGGER.debug(f"Starting Message Tracker for Nice Controller {self.name}")
        self._message_tracker_task = asyncio.create_task(
            self._controller.message_tracker()
        )

        async def handle_stop(event: Event) -> None:
            _LOGGER.debug(f"Stop Event for Nice Controller {self.name}")
            await self._stop()

        _LOGGER.debug(f"Starting Listener for Nice Controller {self.name}")
        self._undo_listener = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, handle_stop
        )

    async def add_cover(self, *args) -> TT6Cover:
        return await self._controller.add_cover(*args)

    async def reconnect(self) -> None:
        await self._controller.reconnect()

    async def _stop(self) -> None:
        if self._message_tracker_task is not None:
            _LOGGER.debug(f"Stopping Message Tracker for Nice Controller {self.name}")
            self._message_tracker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._message_tracker_task
            self._message_tracker_task = None
            _LOGGER.debug(f"Stopped Message Tracker for Nice Controller {self.name}")
        else:
            _LOGGER.debug(f"Message Tracker not set for Nice Controller {self.name}")
        _LOGGER.debug(f"Closing Nice Controller {self.name}")
        await self._controller.close()
        _LOGGER.debug(f"Closed Nice Controller {self.name}")

    async def stop(self) -> None:
        if self._undo_listener is not None:
            _LOGGER.debug(f"Stopping Listener for Nice Controller {self.name}")
            self._undo_listener()
            self._undo_listener = None
            _LOGGER.debug(f"Stopped Listener for Nice Controller {self.name}")
        else:
            _LOGGER.debug(f"Listener not set for Nice Controller {self.name}")
        await self._stop()


@dataclass
class NiceCoverRuntimeData:
    name: str
    tt6_cover: TT6Cover
    has_inverse_endpoints: bool
    has_inverse_semantics: bool


async def make_cover_runtime_data(
    controller: NiceControllerRunTimeData,
    data: MappingProxyType[str, Any],
) -> NiceCoverRuntimeData:
    """Factory for cover run time data"""
    name = data[CONF_NAME]
    has_inverse_endpoints = data.get(CONF_HAS_INVERSE_ENDPOINTS, False)
    has_inverse_semantics = data.get(CONF_HAS_INVERSE_SEMANTICS, False)
    cover = Cover(name, data[CONF_DROP], has_inverse_endpoints)
    tt6_cover = await controller.add_cover(
        TTBusDeviceAddress(data[CONF_ADDRESS], data[CONF_NODE]), cover
    )
    return NiceCoverRuntimeData(
        name, tt6_cover, has_inverse_endpoints, has_inverse_semantics
    )


@dataclass
class NiceRuntimeData:
    controller: NiceControllerRunTimeData
    covers: dict[str, NiceCoverRuntimeData]


async def make_runtime_data(hass: HomeAssistant, entry: ConfigEntry) -> NiceRuntimeData:
    """Factory for run time data.   Also registers devices."""
    controller_rtd = NiceControllerRunTimeData(
        entry.data[CONF_NAME], entry.data[CONF_SERIAL_PORT]
    )
    await controller_rtd.start(hass)
    controller_id = entry.entry_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller_id)},
        manufacturer="Nice",
        name=controller_rtd.name,
        model="Nice TT6 Control Unit",
    )

    covers_rtd: dict[str, NiceCoverRuntimeData] = {}
    for se in entry.subentries.values():
        cover_rtd = await make_cover_runtime_data(controller_rtd, se.data)
        cover_id = se.subentry_id
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=se.subentry_id,
            identifiers={(DOMAIN, cover_id)},
            name=cover_rtd.name,
            manufacturer="Nice",
            model="Nice Tubular Motor",
            via_device=(DOMAIN, controller_id),
        )
        covers_rtd[cover_id] = cover_rtd

    return NiceRuntimeData(controller_rtd, covers_rtd)
