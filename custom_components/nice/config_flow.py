"""Config flow for Nice integration."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from nicett6.tt6_connection import open_connection
from serial import SerialException

from .const import (
    CONF_ADDRESS,
    CONF_DROP,
    CONF_HAS_REVERSE_MOTOR_POS,
    CONF_HAS_REVERSE_SEMANTICS,
    CONF_NODE,
    CONF_SERIAL_PORT,
    DOMAIN,
    SUBENTRY_TYPE_COVER,
)


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


class NiceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nice."""

    VERSION = 2
    MINOR_VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_COVER: CoverSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self.async_step_controller(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self.async_step_controller(user_input)

    async def async_step_controller(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}

        if user_input is not None:
            if not await validate_serial_port(user_input[CONF_SERIAL_PORT]):
                errors["base"] = "cannot_connect"
            else:
                title = f"NiceTT6: {user_input[CONF_NAME]}"
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=title,
                        data=user_input,
                    )
                elif self.source == SOURCE_USER:
                    return self.async_create_entry(title=title, data=user_input)
                else:
                    raise ValueError("Unexpected source encountered")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Controller"): str,
                vol.Required(CONF_SERIAL_PORT): str,
            }
        )

        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            data_schema = self.add_suggested_values_to_schema(data_schema, entry.data)

        return self.async_show_form(
            step_id="controller",
            errors=errors,
            data_schema=data_schema,
        )


class CoverSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a cover."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self.async_step_cover(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self.async_step_cover(user_input)

    def num_existing_subentries(self) -> int:
        config_entry = self._get_entry()
        return sum(
            1
            for e in config_entry.subentries.values()
            if e.subentry_type == SUBENTRY_TYPE_COVER
        )

    def get_default_name(self) -> str:
        if self.source == SOURCE_USER:
            seq_num = self.num_existing_subentries() + 1
            return f"Cover {seq_num}"
        elif self.source == SOURCE_RECONFIGURE:
            subentry = self._get_reconfigure_subentry()
            return subentry.data[CONF_NAME]
        else:
            raise ValueError("Unexpected source encountered")

    async def async_step_cover(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors = {}

        if user_input is not None:
            # TODO: Send a pos request to validate address, node
            unique_id = f"{user_input[CONF_ADDRESS]:02X}/{user_input[CONF_NODE]:02X}"
            title = f"Cover: {user_input[CONF_NAME]}"
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    title=title,
                    data=user_input,
                    unique_id=unique_id,
                )
            elif self.source == SOURCE_USER:
                self.hass.config_entries.async_schedule_reload(
                    self._get_entry().entry_id
                )
                return self.async_create_entry(
                    title=title, data=user_input, unique_id=unique_id
                )
            else:
                raise ValueError("Unexpected source encountered")

        default_name = self.get_default_name()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): str,
                vol.Required(CONF_ADDRESS): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Required(CONF_NODE, default=4): vol.All(
                    vol.Coerce(int), vol.Range(min=0)
                ),
                vol.Required(CONF_DROP): vol.All(
                    vol.Coerce(float), vol.Range(min=0, min_included=False)
                ),
                vol.Optional(CONF_HAS_REVERSE_MOTOR_POS, default=False): bool,
                vol.Optional(CONF_HAS_REVERSE_SEMANTICS, default=False): bool,
            }
        )

        if self.source == SOURCE_RECONFIGURE:
            subentry = self._get_reconfigure_subentry()
            data_schema = self.add_suggested_values_to_schema(
                data_schema, subentry.data
            )

        return self.async_show_form(
            step_id="cover",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"name": default_name},
        )
