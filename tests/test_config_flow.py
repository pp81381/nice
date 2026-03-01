"""Test the Nice config flow."""

from contextlib import asynccontextmanager

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nice.const import (
    CONF_ADDRESS,
    CONF_DROP,
    CONF_HAS_REVERSE_MOTOR_POS,
    CONF_HAS_REVERSE_SEMANTICS,
    CONF_NODE,
    CONF_SERIAL_PORT,
    DOMAIN,
    SUBENTRY_TYPE_COVER,
)

from .const import (
    CONTROLLER_INPUT,
    CONTROLLER_TITLE,
    TEST_COVER_1_INPUT,
    TEST_COVER_1_TITLE,
)
from .util import get_suggested_values_from_schema, init_integration

CONTROLLER_TITLE_UPDATE = "NiceTT6: Controller 2 Test"

CONTROLLER_INPUT_UPDATE = {
    CONF_NAME: "Controller 2 Test",
    CONF_SERIAL_PORT: "socket://hadev2:50200",
}


TEST_COVER_1_TITLE_UPDATE = "Cover: Screen 2"

TEST_COVER_1_INPUT_UPDATE = {
    CONF_NAME: "Screen 2",
    CONF_ADDRESS: 3,
    CONF_NODE: 4,
    CONF_DROP: 2.0,
    CONF_HAS_REVERSE_MOTOR_POS: True,
    CONF_HAS_REVERSE_SEMANTICS: True,
}

TEST_COVER_1_UNIQUE_ID_UPDATE = "03/04"


@asynccontextmanager
async def dummy_open_connection(serial_port=None):
    yield True


@pytest.fixture
def mock_open_connection_success(mocker):
    mocker.patch(
        "custom_components.nice.config_flow.open_connection",
        new=dummy_open_connection,
    )


@pytest.fixture
def mock_open_connection_failure(mocker):
    mocker.patch(
        "custom_components.nice.config_flow.open_connection",
        side_effect=ValueError,
    )


@pytest.fixture
async def init_config_flow(hass: HomeAssistant, config_flow_state_override):
    step_id = config_flow_state_override["step_id"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == step_id

    return result


@pytest.fixture
async def config_flow_id(init_config_flow):
    return init_config_flow["flow_id"]


@pytest.fixture
def mock_config_entry_before_add() -> MockConfigEntry:
    return MockConfigEntry(
        title=CONTROLLER_TITLE,
        domain=DOMAIN,
        data=CONTROLLER_INPUT,
        version=2,
        minor_version=1,
        subentries_data=[],
    )


@pytest.mark.usefixtures("mock_open_connection_success")
async def test_user_step(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "controller"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONTROLLER_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == CONTROLLER_TITLE
    assert result.get("data") == CONTROLLER_INPUT


@pytest.mark.usefixtures("mock_open_connection_failure")
async def test_user_step_connection_failure(hass: HomeAssistant) -> None:
    """Test invalid serial port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "controller"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        CONTROLLER_INPUT,
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {"base": "cannot_connect"}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "controller"


async def test_reconfigure_step(mocker, hass, mock_config_entry):
    mocker.patch(
        "custom_components.nice.config_flow.open_connection",
        new=dummy_open_connection,
    )

    await init_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "controller"
    data_schema = result.get("data_schema")
    assert data_schema is not None
    suggested_values = get_suggested_values_from_schema(data_schema)
    assert suggested_values == [
        CONTROLLER_INPUT[CONF_NAME],
        CONTROLLER_INPUT[CONF_SERIAL_PORT],
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONTROLLER_INPUT_UPDATE
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data == CONTROLLER_INPUT_UPDATE
    assert updated_entry.title == CONTROLLER_TITLE_UPDATE


async def test_cover_subentry(
    hass: HomeAssistant, mock_config_entry_before_add: MockConfigEntry
) -> None:
    await init_integration(hass, mock_config_entry_before_add)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry_before_add.entry_id, SUBENTRY_TYPE_COVER),
        context={"source": SOURCE_USER},
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "cover"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], TEST_COVER_1_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == TEST_COVER_1_TITLE
    assert result.get("data") == TEST_COVER_1_INPUT


async def test_cover_subentry_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    await init_integration(hass, mock_config_entry)
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_COVER),
        context={"source": SOURCE_USER},
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "cover"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], TEST_COVER_1_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_cover_subentry_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    await init_integration(hass, mock_config_entry)
    existing_subentry = next(iter(mock_config_entry.subentries.values()))
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, existing_subentry.subentry_id
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "cover"
    data_schema = result.get("data_schema")
    assert data_schema is not None
    suggested_values = get_suggested_values_from_schema(data_schema)
    assert suggested_values == [
        TEST_COVER_1_INPUT[CONF_NAME],
        TEST_COVER_1_INPUT[CONF_ADDRESS],
        TEST_COVER_1_INPUT[CONF_NODE],
        TEST_COVER_1_INPUT[CONF_DROP],
        TEST_COVER_1_INPUT[CONF_HAS_REVERSE_MOTOR_POS],
        TEST_COVER_1_INPUT[CONF_HAS_REVERSE_SEMANTICS],
    ]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], TEST_COVER_1_INPUT_UPDATE
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry is not None
    updated_subentries = list(updated_entry.subentries.values())
    assert len(updated_subentries) == 1
    updated_subentry = updated_subentries[0]
    assert updated_subentry.data == TEST_COVER_1_INPUT_UPDATE
    assert updated_subentry.title == TEST_COVER_1_TITLE_UPDATE
    assert updated_subentry.unique_id == TEST_COVER_1_UNIQUE_ID_UPDATE
