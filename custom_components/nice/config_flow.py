"""Config flow for Nice integration."""
from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any
from uuid import uuid4

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)
from homeassistant.util import slugify
from nicett6.ciw_manager import check_baseline_drop
from nicett6.connection import open_connection
from nicett6.utils import MAX_ASPECT_RATIO, MIN_ASPECT_RATIO
from serial import SerialException

from . import CIW_ASPECT_RATIO_MODE_MAP, image_def_from_config
from .const import (
    ACTION_ADD_CIW,
    ACTION_ADD_PRESET,
    ACTION_DEL_CIW,
    ACTION_DEL_PRESET,
    ACTION_SENSOR_PREFS,
    CHOICE_ASPECT_RATIO_2_35_1,
    CHOICE_ASPECT_RATIO_4_3,
    CHOICE_ASPECT_RATIO_16_9,
    CHOICE_ASPECT_RATIO_OTHER,
    CONF_ACTION,
    CONF_ADD_ANOTHER,
    CONF_ADDRESS,
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
    CONF_HAS_IMAGE_AREA,
    CONF_IMAGE_AREA,
    CONF_IMAGE_ASPECT_RATIO_CHOICE,
    CONF_IMAGE_ASPECT_RATIO_OTHER,
    CONF_IMAGE_BORDER_BELOW,
    CONF_IMAGE_HEIGHT,
    CONF_MASK_COVER,
    CONF_NODE,
    CONF_PRESETS,
    CONF_SCREEN_COVER,
    CONF_SELECT,
    CONF_SENSOR_PREFS,
    CONF_SERIAL_PORT,
    CONF_TITLE,
    DOMAIN,
)

UNIT_SYSTEMS = {
    CONF_UNIT_SYSTEM_METRIC: "Metric",
    CONF_UNIT_SYSTEM_IMPERIAL: "Imperial",
}

_LOGGER = logging.getLogger(__name__)

# TODO: localise embedded strings somehow


async def validate_serial_port(serial_port: str) -> bool:
    try:
        async with open_connection(serial_port):
            pass
    except (ValueError, SerialException):
        # bad port:
        # serial.serialutil.SerialException: could not open port 'BAD': FileNotFoundError(2, 'The system cannot find the file specified.', None, 2)
        # bad protocol:
        # ValueError: invalid URL, protocol 'http' not known
        # If the server is down:
        # serial.serialutil.SerialException: Could not open port socket://localhost:50200: [WinError 10061] No connection could be made because the target machine actively refused it
        return False
    return True


def make_id():
    return slugify(str(uuid4()))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nice."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    def __init__(self):
        self.title = ""
        self.data = {
            CONF_UNIT_SYSTEM: None,
            CONF_CONTROLLERS: {},
            CONF_COVERS: {},
        }
        self.tmp = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_define()

    async def async_step_define(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            self.title = user_input[CONF_TITLE]
            self.data[CONF_UNIT_SYSTEM] = user_input[CONF_UNIT_SYSTEM]
            return await self.async_step_controller()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_TITLE, default="Nice TT6"): str,
                vol.Required(
                    CONF_UNIT_SYSTEM,
                    default=self.hass.config.units.name,
                ): vol.In(UNIT_SYSTEMS),
            }
        )

        return self.async_show_form(
            step_id="define",
            errors=errors,
            data_schema=data_schema,
        )

    async def async_step_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            if not await validate_serial_port(user_input[CONF_SERIAL_PORT]):
                errors["base"] = "cannot_connect"
            else:
                self.data[CONF_CONTROLLERS][make_id()] = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
                }
                if user_input[CONF_ADD_ANOTHER]:
                    return await self.async_step_controller()
                else:
                    return await self.async_step_cover()

        next_num = len(self.data[CONF_CONTROLLERS]) + 1

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=f"Controller {next_num}"): str,
                vol.Required(CONF_SERIAL_PORT): str,
                vol.Optional(CONF_ADD_ANOTHER, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="controller",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"sequence_number": next_num},
        )

    async def async_step_cover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            cover_id = make_id()
            # TODO: Send a pos request to validate address, node
            self.data[CONF_COVERS][cover_id] = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_CONTROLLER: user_input[CONF_CONTROLLER],
                CONF_ADDRESS: user_input[CONF_ADDRESS],
                CONF_NODE: user_input[CONF_NODE],
                CONF_DROP: user_input[CONF_DROP],
                CONF_IMAGE_AREA: None,
            }
            if user_input[CONF_HAS_IMAGE_AREA]:
                self.tmp = cover_id
                return await self.async_step_image_area()
            else:
                return await self.async_step_finish_cover()

        next_num = len(self.data[CONF_COVERS]) + 1
        valid_controllers = {
            id: config[CONF_NAME] for id, config in self.data[CONF_CONTROLLERS].items()
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=f"Cover {next_num}"): str,
                vol.Required(CONF_CONTROLLER): vol.In(valid_controllers),
                vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Required(CONF_NODE, default=4): vol.All(
                    vol.Coerce(int), vol.Range(min=0)
                ),
                vol.Required(CONF_DROP): vol.All(
                    vol.Coerce(float), vol.Range(min=0, min_included=False)
                ),
                vol.Optional(CONF_HAS_IMAGE_AREA, default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="cover",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"sequence_number": next_num},
        )

    async def async_step_image_area(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        cover_config = self.data[CONF_COVERS][self.tmp]
        errors = {}

        if user_input is not None:
            if (
                user_input[CONF_IMAGE_BORDER_BELOW] + user_input[CONF_IMAGE_HEIGHT]
                > cover_config[CONF_DROP]
            ):
                errors["base"] = "image_area_too_tall"
            elif (
                user_input[CONF_IMAGE_ASPECT_RATIO_CHOICE] == "aspect_ratio_other"
                and user_input.get(CONF_IMAGE_ASPECT_RATIO_OTHER) is None
            ):
                errors[CONF_IMAGE_ASPECT_RATIO_OTHER] = "aspect_ratio_other_required"
            else:
                cover_config[CONF_IMAGE_AREA] = {
                    CONF_IMAGE_BORDER_BELOW: user_input[CONF_IMAGE_BORDER_BELOW],
                    CONF_IMAGE_HEIGHT: user_input[CONF_IMAGE_HEIGHT],
                    CONF_IMAGE_ASPECT_RATIO_CHOICE: user_input[
                        CONF_IMAGE_ASPECT_RATIO_CHOICE
                    ],
                    CONF_IMAGE_ASPECT_RATIO_OTHER: user_input.get(
                        CONF_IMAGE_ASPECT_RATIO_OTHER
                    ),
                }
                return await self.async_step_finish_cover()

        aspect_ratio_choices = {
            CHOICE_ASPECT_RATIO_16_9: "16:9",
            CHOICE_ASPECT_RATIO_2_35_1: "2.35:1",
            CHOICE_ASPECT_RATIO_4_3: "4:3",
            CHOICE_ASPECT_RATIO_OTHER: "Other",
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_IMAGE_BORDER_BELOW): vol.All(
                    vol.Coerce(float), vol.Range(min=0, min_included=False)
                ),
                vol.Required(CONF_IMAGE_HEIGHT): vol.All(
                    vol.Coerce(float), vol.Range(min=0, min_included=False)
                ),
                vol.Required(CONF_IMAGE_ASPECT_RATIO_CHOICE): vol.In(
                    aspect_ratio_choices
                ),
                vol.Optional(CONF_IMAGE_ASPECT_RATIO_OTHER): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=MIN_ASPECT_RATIO, max=MAX_ASPECT_RATIO),
                ),
            }
        )

        return self.async_show_form(
            step_id="image_area",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"cover_name": cover_config[CONF_NAME]},
        )

    async def async_step_finish_cover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            if user_input[CONF_ADD_ANOTHER]:
                return await self.async_step_cover()
            else:
                return self.async_create_entry(title=self.title, data=self.data)

        data_schema = vol.Schema({vol.Optional(CONF_ADD_ANOTHER, default=False): bool})

        return self.async_show_form(
            step_id="finish_cover",
            data_schema=data_schema,
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the Nice component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self.data = {
            CONF_CIW_MANAGERS: deepcopy(
                self.config_entry.options.get(CONF_CIW_MANAGERS, {})
            ),
            CONF_PRESETS: deepcopy(self.config_entry.options.get(CONF_PRESETS, {})),
            CONF_SENSOR_PREFS: deepcopy(
                self.config_entry.options.get(CONF_SENSOR_PREFS, {})
            ),
        }
        self.valid_screen_covers = {
            id: config[CONF_NAME]
            for id, config in self.config_entry.data[CONF_COVERS].items()
            if config[CONF_IMAGE_AREA] is not None
        }
        self.valid_mask_covers = {
            id: config[CONF_NAME]
            for id, config in self.config_entry.data[CONF_COVERS].items()
            if config[CONF_IMAGE_AREA] is None
        }
        self.tmp_preset_id = None
        self.tmp_drops_to_define = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for the custom component."""
        return await self.async_step_select_action()

    async def async_step_select_action(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select the desired action."""

        errors = {}

        if user_input is not None:
            if user_input[CONF_ACTION] == ACTION_ADD_CIW:
                return await self.async_step_add_ciw_manager()
            elif user_input[CONF_ACTION] == ACTION_DEL_CIW:
                return await self.async_step_del_ciw_manager()
            elif user_input[CONF_ACTION] == ACTION_ADD_PRESET:
                return await self.async_step_add_preset()
            elif user_input[CONF_ACTION] == ACTION_DEL_PRESET:
                return await self.async_step_del_preset()
            elif user_input[CONF_ACTION] == ACTION_SENSOR_PREFS:
                return await self.async_step_sensor_prefs()
            else:  # pragma: no cover
                return self.async_abort(reason="not_implemented")

        actions = []
        if len(self.valid_screen_covers) > 0 and len(self.valid_mask_covers) > 0:
            actions.append(ACTION_ADD_CIW)
        if len(self.data[CONF_CIW_MANAGERS]) > 0:
            actions.append(ACTION_DEL_CIW)
        actions.append(ACTION_ADD_PRESET)
        if len(self.data[CONF_PRESETS]) > 0:
            actions.append(ACTION_DEL_PRESET)
        actions.append(ACTION_SENSOR_PREFS)

        data_schema = vol.Schema({vol.Required(CONF_ACTION): vol.In(actions)})

        return self.async_show_form(
            step_id="select_action",
            data_schema=data_schema,
            errors=errors,
        )

    def validate_baseline_drop(self, screen_id, mask_id, mode_str, baseline_drop):
        if baseline_drop is None:
            return True
        mode = CIW_ASPECT_RATIO_MODE_MAP[mode_str]
        screen_config = self.config_entry.data[CONF_COVERS][screen_id]
        mask_config = self.config_entry.data[CONF_COVERS][mask_id]
        image_def = image_def_from_config(screen_config)
        try:
            check_baseline_drop(
                mode,
                baseline_drop,
                screen_config[CONF_DROP],
                mask_config[CONF_DROP],
                image_def,
            )
            return True
        except ValueError as exc:
            _LOGGER.warning(str(exc))
        return False

    async def async_step_add_ciw_manager(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            screen_id = user_input[CONF_SCREEN_COVER]
            mask_id = user_input[CONF_MASK_COVER]
            mode_str = user_input[CONF_ASPECT_RATIO_MODE]
            baseline_drop = user_input.get(CONF_BASELINE_DROP)
            if self.validate_baseline_drop(screen_id, mask_id, mode_str, baseline_drop):
                self.data[CONF_CIW_MANAGERS][make_id()] = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_SCREEN_COVER: screen_id,
                    CONF_MASK_COVER: mask_id,
                    CONF_ASPECT_RATIO_MODE: mode_str,
                    CONF_BASELINE_DROP: baseline_drop,
                }
                return self.async_create_entry(title="", data=self.data)
            else:
                errors[CONF_BASELINE_DROP] = "invalid_baseline_drop"

        next_num = len(self.data[CONF_CIW_MANAGERS]) + 1

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=f"CIW Manager {next_num}"): str,
                vol.Required(CONF_SCREEN_COVER): vol.In(self.valid_screen_covers),
                vol.Required(CONF_MASK_COVER): vol.In(self.valid_mask_covers),
                vol.Required(CONF_ASPECT_RATIO_MODE): vol.In(
                    CIW_ASPECT_RATIO_MODE_MAP.keys()
                ),
                vol.Optional(CONF_BASELINE_DROP): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="add_ciw_manager",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"sequence_number": next_num},
        )

    async def async_step_del_ciw_manager(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            entity_registry = await async_get_registry(self.hass)
            entries = async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )

            for id in user_input[CONF_SELECT]:
                del self.data[CONF_CIW_MANAGERS][id]
                for e in entries:
                    if e.unique_id.startswith(id):
                        entity_registry.async_remove(e.entity_id)

            return self.async_create_entry(title="", data=self.data)

        names = {
            id: config[CONF_NAME] for id, config in self.data[CONF_CIW_MANAGERS].items()
        }

        data_schema = vol.Schema({vol.Required(CONF_SELECT): cv.multi_select(names)})

        return self.async_show_form(
            step_id="del_ciw_manager",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_add_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            self.tmp_drops_to_define = user_input[CONF_SELECT]
            if len(self.tmp_drops_to_define) == 0:
                errors[CONF_SELECT] = "no_covers_selected"
            else:
                self.tmp_preset_id = make_id()
                self.data[CONF_PRESETS][self.tmp_preset_id] = {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_DROPS: [],
                }
                return await self.async_step_define_drop()

        next_num = len(self.data[CONF_PRESETS]) + 1
        covers = {
            id: config[CONF_NAME]
            for id, config in self.config_entry.data[CONF_COVERS].items()
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=f"Preset {next_num}"): str,
                vol.Required(CONF_SELECT, default=list(covers.keys())): cv.multi_select(
                    covers
                ),
            }
        )

        return self.async_show_form(
            step_id="add_preset",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"sequence_number": next_num},
        )

    async def async_step_define_drop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        preset_config = self.data[CONF_PRESETS][self.tmp_preset_id]
        cover_id = self.tmp_drops_to_define[0]
        cover_config = self.config_entry.data[CONF_COVERS][cover_id]

        if user_input is not None:
            preset_config[CONF_DROPS].append(
                {
                    CONF_COVER: cover_id,
                    CONF_DROP: user_input[CONF_DROP],
                }
            )
            self.tmp_drops_to_define.pop(0)
            if len(self.tmp_drops_to_define) > 0:
                return await self.async_step_define_drop()
            else:
                return self.async_create_entry(title="", data=self.data)

        max_drop = cover_config[CONF_DROP]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_DROP, default=max_drop): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=0, max=max_drop),
                ),
            }
        )

        return self.async_show_form(
            step_id="define_drop",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "preset_name": preset_config[CONF_NAME],
                "cover_name": cover_config[CONF_NAME],
                "max_drop": max_drop,
            },
        )

    async def async_step_del_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            for id in user_input[CONF_SELECT]:
                del self.data[CONF_PRESETS][id]
            return self.async_create_entry(title="", data=self.data)

        presets = {
            id: config[CONF_NAME] for id, config in self.data[CONF_PRESETS].items()
        }

        data_schema = vol.Schema({vol.Required(CONF_SELECT): cv.multi_select(presets)})

        return self.async_show_form(
            step_id="del_preset",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_sensor_prefs(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:

        errors = {}

        if user_input is not None:
            self.data[CONF_SENSOR_PREFS] = {
                CONF_UNIT_SYSTEM: user_input[CONF_UNIT_SYSTEM],
                CONF_FORCE_DIAGONAL_IMPERIAL: user_input[CONF_FORCE_DIAGONAL_IMPERIAL],
            }
            return self.async_create_entry(title="", data=self.data)

        sensor_prefs = self.data[CONF_SENSOR_PREFS]
        default_unit_system = sensor_prefs.get(
            CONF_UNIT_SYSTEM,
            self.config_entry.data[CONF_UNIT_SYSTEM],
        )
        default_force_diagonal_imperial = sensor_prefs.get(
            CONF_FORCE_DIAGONAL_IMPERIAL, False
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_UNIT_SYSTEM,
                    default=default_unit_system,
                ): vol.In(UNIT_SYSTEMS),
                vol.Required(
                    CONF_FORCE_DIAGONAL_IMPERIAL,
                    default=default_force_diagonal_imperial,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="sensor_prefs",
            data_schema=data_schema,
            errors=errors,
        )
