"""Test the Nice config flow."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIT_SYSTEM_METRIC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowHandler, FlowResult, FlowResultType
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry
from voluptuous import MultipleInvalid

from custom_components.nice.config_flow import ConfigFlow as NiceConfigFlow
from custom_components.nice.config_flow import OptionsFlowHandler, make_id
from custom_components.nice.const import (
    ACTION_ADD_CIW,
    ACTION_ADD_PRESET,
    ACTION_DEL_CIW,
    ACTION_DEL_PRESET,
    CONF_ACTION,
    CONF_CIW_HELPERS,
    CONF_IMAGE_ASPECT_RATIO_OTHER,
    CONF_PRESETS,
    DOMAIN,
)

TEST_TITLE = "Nice TT6 Test"

CONTROLLER_1_ID = "controller_1_id"
COVER_1_ID = "cover_1_id"
COVER_2_ID = "cover_2_id"
CIW_HELPER_ID = "ciw_1_id"
PRESET_1_ID = "preset_1_id"
PRESET_2_ID = "preset_2_id"

CONTROLLER_INPUT = {
    "name": "Controller 1 Test",
    "serial_port": "socket://localhost:50200",
    "add_another": False,
}

SCREEN_COVER_INPUT = {
    "name": "Screen",
    "controller": CONTROLLER_1_ID,
    "address": 2,
    "node": 4,
    "drop": 1.8,
    "has_image_area": True,
    "has_reverse_semantics": False,
}


MASK_COVER_INPUT = {
    "name": "Mask",
    "controller": CONTROLLER_1_ID,
    "address": 3,
    "node": 4,
    "drop": 0.5,
    "has_image_area": False,
    "has_reverse_semantics": False,
}


TEST_CONTROLLER_1 = {
    "name": "Controller 1 Test",
    "serial_port": "socket://localhost:50200",
}


TEST_PARTIAL_SCREEN = {
    "name": "Screen",
    "controller": CONTROLLER_1_ID,
    "address": 2,
    "node": 4,
    "drop": 1.8,
    "image_area": None,
    "has_reverse_semantics": False,
}

TEST_SCREEN = {
    "name": "Screen",
    "controller": CONTROLLER_1_ID,
    "address": 2,
    "node": 4,
    "drop": 1.8,
    "image_area": {
        "image_border_below": 0.05,
        "image_height": 1.57,
        "image_aspect_ratio_choice": "aspect_ratio_16_9",
        "image_aspect_ratio_other": None,
    },
    "has_reverse_semantics": False,
}

TEST_MASK = {
    "name": "Mask",
    "controller": CONTROLLER_1_ID,
    "address": 3,
    "node": 4,
    "drop": 0.5,
    "image_area": None,
    "has_reverse_semantics": False,
}

TEST_CIW_HELPER = {
    "name": "CIW Helper",
    "screen_cover": COVER_1_ID,
    "mask_cover": COVER_2_ID,
}

TEST_PARTIAL_PRESET_1_NO_DROPS = {
    "name": "Preset 1",
    "drops": [],
}

TEST_PARTIAL_PRESET_1_ONE_DROP = {
    "name": "Preset 1",
    "drops": [
        {"cover": COVER_1_ID, "drop": 1.77},
    ],
}

TEST_PRESET_1 = {
    "name": "Preset 1",
    "drops": [
        {"cover": COVER_1_ID, "drop": 1.77},
        {"cover": COVER_2_ID, "drop": 0.5},
    ],
}

TEST_PRESET_2 = {
    "name": "Preset 2",
    "drops": [
        {"cover": COVER_1_ID, "drop": 0.0},
        {"cover": COVER_2_ID, "drop": 0.0},
    ],
}


@asynccontextmanager
async def dummy_open_connection(serial_port=None):
    yield True


def get_flow(hass, flow_id) -> NiceConfigFlow:
    flow_handler: FlowHandler = hass.config_entries.flow._progress[flow_id]
    if not isinstance(flow_handler, NiceConfigFlow):
        raise ValueError("flow handler requested from get_flow isn't a NiceConfigFlow")
    return flow_handler


def get_options_flow(hass, flow_id) -> OptionsFlowHandler:
    flow_handler: FlowHandler = hass.config_entries.options._progress[flow_id]
    if not isinstance(flow_handler, OptionsFlowHandler):
        raise ValueError(
            "flow handler requested from get_options_flow isn't an OptionsFlowHandler"
        )
    return flow_handler


async def _dummy_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    pass


@pytest.fixture(autouse=True)
def no_reload(mocker):
    """To ensure a clean teardown."""
    return mocker.patch(
        "custom_components.nice._async_update_listener",
        new=_dummy_update_listener,
    )


@pytest.fixture
def config_data():
    return {
        "unit_system": None,
        "controllers": {},
        "covers": {},
    }


@pytest.fixture
def options_data():
    return {}


@pytest.fixture
def config_flow_state_override(config_data):
    return {
        "step_id": "dummy",
        "title": None,
        "data": config_data,
        "tmp": None,
    }


@pytest.fixture
async def init_config_flow(mocker, hass: HomeAssistant, config_flow_state_override):
    step_id = config_flow_state_override["step_id"]

    async def async_step_setup_test(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if config_flow_state_override["title"] is not None:
            self.title = config_flow_state_override["title"]
        self.data = config_flow_state_override["data"]
        if config_flow_state_override["tmp"] is not None:
            self.tmp = config_flow_state_override["tmp"]
        return await getattr(self, f"async_step_{step_id}")(None)

    mocker.patch.object(NiceConfigFlow, "async_step_user", async_step_setup_test)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == step_id

    return result


@pytest.fixture
async def config_flow_id(init_config_flow):
    return init_config_flow["flow_id"]


@pytest.fixture
def options_flow_state_override():
    return {
        "step_id": "dummy",
        "tmp_preset_id": None,
        "tmp_drops_to_define": [],
    }


@pytest.fixture
async def init_options_flow(
    mocker,
    options_flow_state_override,
    hass: HomeAssistant,
    config_entry,
):
    step_id = options_flow_state_override["step_id"]

    async def async_step_setup_test(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if options_flow_state_override["tmp_preset_id"] is not None:
            self.tmp_preset_id = options_flow_state_override["tmp_preset_id"]
        if options_flow_state_override["tmp_drops_to_define"] is not None:
            self.tmp_drops_to_define = options_flow_state_override[
                "tmp_drops_to_define"
            ]
        return await getattr(self, f"async_step_{step_id}")(None)

    mocker.patch.object(OptionsFlowHandler, "async_step_init", async_step_setup_test)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == step_id

    return result


@pytest.fixture
async def options_flow_id(init_options_flow):
    return init_options_flow["flow_id"]


@pytest.fixture()
async def config_entry(
    mocker,
    hass: HomeAssistant,
    config_data,
    options_data,
) -> MockConfigEntry:
    mocker.patch("custom_components.nice.CoverManager", autospec=True, spec_set=True)

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="my_unique_id",
        data=config_data,
        options=options_data,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def config_step_define(config_flow_state_override):
    config_flow_state_override["step_id"] = "define"


@pytest.fixture
def config_step_controller(config_flow_state_override):
    config_flow_state_override["step_id"] = "controller"


@pytest.fixture
def config_step_cover(config_flow_state_override):
    config_flow_state_override["step_id"] = "cover"


@pytest.fixture
def config_step_image_area(config_flow_state_override):
    config_flow_state_override["step_id"] = "image_area"


@pytest.fixture
def config_step_finish_cover(config_flow_state_override):
    config_flow_state_override["step_id"] = "finish_cover"


@pytest.fixture
def options_step_select_action(options_flow_state_override):
    options_flow_state_override["step_id"] = "select_action"


@pytest.fixture
def options_step_add_ciw_helper(options_flow_state_override):
    options_flow_state_override["step_id"] = "add_ciw_helper"


@pytest.fixture
def options_step_add_preset(options_flow_state_override):
    options_flow_state_override["step_id"] = "add_preset"


@pytest.fixture
def options_step_define_drop(options_flow_state_override):
    options_flow_state_override["step_id"] = "define_drop"


@pytest.fixture
def options_step_del_ciw_helper(options_flow_state_override):
    options_flow_state_override["step_id"] = "del_ciw_helper"


@pytest.fixture
def options_step_del_preset(options_flow_state_override):
    options_flow_state_override["step_id"] = "del_preset"


@pytest.fixture
def config_set_title(config_flow_state_override):
    config_flow_state_override["title"] = TEST_TITLE


@pytest.fixture
def config_set_unit_system_metric(config_data):
    config_data["unit_system"] = CONF_UNIT_SYSTEM_METRIC


@pytest.fixture
def config_add_controller_1(config_data):
    config_data["controllers"][CONTROLLER_1_ID] = TEST_CONTROLLER_1


@pytest.fixture
def config_add_partial_screen(config_data, config_flow_state_override):
    config_data["covers"][COVER_1_ID] = TEST_PARTIAL_SCREEN
    config_flow_state_override["tmp"] = COVER_1_ID


@pytest.fixture
def config_add_screen(config_data):
    config_data["covers"][COVER_1_ID] = TEST_SCREEN


@pytest.fixture
def config_add_mask(config_data):
    config_data["covers"][COVER_2_ID] = TEST_MASK


@pytest.fixture
def options_flow_data(options_data):
    options_data.update(
        {
            "ciw_helpers": {},
            "presets": {},
        }
    )
    return options_data


@pytest.fixture
def options_add_ciw_helper(options_flow_data):
    options_flow_data["ciw_helpers"][CIW_HELPER_ID] = TEST_CIW_HELPER


@pytest.fixture
def options_add_preset_1(options_flow_data):
    options_flow_data["presets"][PRESET_1_ID] = TEST_PRESET_1


@pytest.fixture
def options_add_partial_preset_1_no_drops(
    options_flow_data, options_flow_state_override
):
    options_flow_data["presets"][PRESET_1_ID] = TEST_PARTIAL_PRESET_1_NO_DROPS
    options_flow_state_override["tmp_preset_id"] = PRESET_1_ID


@pytest.fixture
def options_add_partial_preset_1_one_drop(
    options_flow_data, options_flow_state_override
):
    options_flow_data["presets"][PRESET_1_ID] = TEST_PARTIAL_PRESET_1_ONE_DROP
    options_flow_state_override["tmp_preset_id"] = PRESET_1_ID


@pytest.fixture
def options_add_preset_2(options_flow_data):
    options_flow_data["presets"][PRESET_2_ID] = TEST_PRESET_2


@pytest.fixture
def options_add_drop_for_screen(options_flow_state_override):
    options_flow_state_override["tmp_drops_to_define"].append(COVER_1_ID)


@pytest.fixture
def options_add_drop_for_mask(options_flow_state_override):
    options_flow_state_override["tmp_drops_to_define"].append(COVER_2_ID)


async def test_make_id(mocker):
    mocker.patch(
        "custom_components.nice.config_flow.uuid4",
        return_value=uuid.UUID("12345678123456781234567812345678"),
    )
    id = make_id()
    assert id == "12345678_1234_5678_1234_567812345678"


async def test_user_step(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "define"


async def test_define(
    hass: HomeAssistant,
    config_step_define,
    config_flow_id,
) -> None:
    """Test define step."""
    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        {"title": TEST_TITLE},
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "controller"

    flow = get_flow(hass, config_flow_id)
    assert flow.title == TEST_TITLE


async def test_controller_valid_port(
    mocker,
    hass: HomeAssistant,
    config_step_controller,
    config_set_unit_system_metric,
    config_flow_id,
) -> None:
    """Test valid serial port."""
    mocker.patch(
        "custom_components.nice.config_flow.open_connection",
        new=dummy_open_connection,
    )
    mocker.patch(
        "custom_components.nice.config_flow.make_id",
        return_value=CONTROLLER_1_ID,
    )

    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        CONTROLLER_INPUT,
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "cover"

    flow = get_flow(hass, config_flow_id)
    assert flow.data == {
        "unit_system": CONF_UNIT_SYSTEM_METRIC,
        "controllers": {CONTROLLER_1_ID: TEST_CONTROLLER_1},
        "covers": {},
    }


async def test_controller_invalid_port(
    mocker,
    hass: HomeAssistant,
    config_step_controller,
    config_set_unit_system_metric,
    config_flow_id,
) -> None:
    """Test invalid serial port."""
    mocker.patch(
        "custom_components.nice.config_flow.open_connection",
        side_effect=ValueError,
    )
    mocker.patch(
        "custom_components.nice.config_flow.make_id",
        return_value=CONTROLLER_1_ID,
    )

    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        CONTROLLER_INPUT,
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {"base": "cannot_connect"}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "controller"


async def test_cover_with_image_area(
    mocker,
    hass: HomeAssistant,
    config_step_cover,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_flow_id,
) -> None:
    """Test a cover with an image area."""
    mocker.patch(
        "custom_components.nice.config_flow.make_id",
        return_value=COVER_1_ID,
    )

    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        SCREEN_COVER_INPUT,
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "image_area"

    flow = get_flow(hass, config_flow_id)
    assert flow.tmp == COVER_1_ID
    assert flow.data["covers"][COVER_1_ID] == TEST_PARTIAL_SCREEN


async def test_cover_without_image_area(
    mocker,
    hass: HomeAssistant,
    config_step_cover,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_flow_id,
) -> None:
    """Test a cover without an image area."""
    mocker.patch(
        "custom_components.nice.config_flow.make_id",
        return_value=COVER_2_ID,
    )

    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        MASK_COVER_INPUT,
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "finish_cover"

    flow = get_flow(hass, config_flow_id)
    assert flow.data["covers"][COVER_2_ID] == TEST_MASK


async def test_image_area_16_9(
    hass: HomeAssistant,
    config_step_image_area,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_add_partial_screen,
    config_flow_id,
) -> None:
    """Test an image area."""
    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        {
            "image_border_below": 0.05,
            "image_height": 1.57,
            "image_aspect_ratio_choice": "aspect_ratio_16_9",
        },
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "finish_cover"

    flow = get_flow(hass, config_flow_id)
    assert flow.data["covers"][COVER_1_ID] == TEST_SCREEN


async def test_invalid_image_area(
    hass: HomeAssistant,
    config_step_image_area,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_add_partial_screen,
    config_flow_id,
) -> None:
    """Test an invalid image area."""
    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        {
            "image_border_below": 0.05,
            "image_height": 2.0,
            "image_aspect_ratio_choice": "aspect_ratio_16_9",
        },
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {"base": "image_area_too_tall"}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "image_area"


async def test_image_area_other(
    hass: HomeAssistant,
    config_step_image_area,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_add_partial_screen,
    config_flow_id,
) -> None:
    """Test an image area."""
    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        {
            "image_border_below": 0.05,
            "image_height": 1.57,
            "image_aspect_ratio_choice": "aspect_ratio_other",
            "image_aspect_ratio_other": 2.37,
        },
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "finish_cover"

    flow = get_flow(hass, config_flow_id)
    assert flow.data["covers"][COVER_1_ID]["image_area"] == {
        "image_border_below": 0.05,
        "image_height": 1.57,
        "image_aspect_ratio_choice": "aspect_ratio_other",
        "image_aspect_ratio_other": 2.37,
    }


async def test_image_area_other_missing(
    hass: HomeAssistant,
    config_step_image_area,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_add_partial_screen,
    config_flow_id,
) -> None:
    """Test an image area."""
    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        {
            "image_border_below": 0.05,
            "image_height": 1.57,
            "image_aspect_ratio_choice": "aspect_ratio_other",
        },
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {
        CONF_IMAGE_ASPECT_RATIO_OTHER: "aspect_ratio_other_required"
    }
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "image_area"


async def test_finish_cover(
    mocker,
    hass: HomeAssistant,
    config_step_finish_cover,
    config_set_title,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_add_screen,
    config_flow_id,
) -> None:
    """Test finishing a cover."""
    mock_setup_entry = mocker.patch(
        "custom_components.nice.async_setup_entry",
        return_value=True,
    )

    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        {"add_another": False},
    )
    await hass.async_block_till_done()

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == TEST_TITLE
    assert result.get("data") == {
        "unit_system": CONF_UNIT_SYSTEM_METRIC,
        "controllers": {CONTROLLER_1_ID: TEST_CONTROLLER_1},
        "covers": {COVER_1_ID: TEST_SCREEN},
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_add_another_cover(
    hass: HomeAssistant,
    config_step_finish_cover,
    config_set_title,
    config_set_unit_system_metric,
    config_add_controller_1,
    config_add_screen,
    config_flow_id,
) -> None:
    """Test add another cover."""
    result = await hass.config_entries.flow.async_configure(
        config_flow_id,
        {"add_another": True},
    )
    await hass.async_block_till_done()

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "cover"


async def test_options_init_step(
    hass,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    config_entry,
):
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "select_action"

    flow_id = result["flow_id"]
    flow: OptionsFlowHandler = get_options_flow(hass, flow_id)

    assert flow.data == {CONF_CIW_HELPERS: {}, CONF_PRESETS: {}}
    assert flow.valid_screen_covers == {COVER_1_ID: "Screen"}
    assert flow.valid_mask_covers == {COVER_2_ID: "Mask"}


async def test_menu_add_ciw_with_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_flow_id,
) -> None:
    """Verify Add CIW menu item."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id, user_input={CONF_ACTION: ACTION_ADD_CIW}
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_ciw_helper"


async def test_menu_add_ciw_no_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    options_flow_id,
) -> None:
    """Verify no Add CIW menu item."""
    with pytest.raises(MultipleInvalid):
        await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_CIW}
        )


async def test_menu_add_ciw_with_existing(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_ciw_helper,
    options_add_preset_1,
    options_add_preset_2,
    options_flow_id,
) -> None:
    """Verify Add CIW menu item."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id, user_input={CONF_ACTION: ACTION_ADD_CIW}
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_ciw_helper"


async def test_menu_del_ciw_with_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_flow_id,
) -> None:
    """Verify no Del CIW menu item."""
    with pytest.raises(MultipleInvalid):
        await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_CIW}
        )


async def test_menu_del_ciw_no_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    options_flow_id,
) -> None:
    """Verify no Del CIW menu item."""
    with pytest.raises(MultipleInvalid):
        await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_CIW}
        )


async def test_menu_del_ciw_with_existing(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_ciw_helper,
    options_add_preset_1,
    options_add_preset_2,
    options_flow_id,
) -> None:
    """Verify Del CIW menu item."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id, user_input={CONF_ACTION: ACTION_DEL_CIW}
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "del_ciw_helper"


async def test_menu_add_preset_with_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_flow_id,
) -> None:
    """Verify Add Preset menu item."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_preset"


async def test_menu_add_preset_no_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    options_flow_id,
) -> None:
    """Verify Add Preset menu item."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_preset"


async def test_menu_add_preset_with_existing(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_ciw_helper,
    options_add_preset_1,
    options_add_preset_2,
    options_flow_id,
) -> None:
    """Verify Add Preset menu item."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_preset"


async def test_menu_mask_del_preset_with_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_flow_id,
) -> None:
    """Verify no Del Preset menu item."""
    with pytest.raises(MultipleInvalid):
        await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_PRESET}
        )


async def test_menu_del_preset_no_mask(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    options_flow_id,
) -> None:
    """Verify no Del Preset menu item."""
    with pytest.raises(MultipleInvalid):
        await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_PRESET}
        )


async def test_menu_del_preset_with_existing(
    hass: HomeAssistant,
    options_step_select_action,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_ciw_helper,
    options_add_preset_1,
    options_add_preset_2,
    options_flow_id,
) -> None:
    """Verify Del Preset menu item."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id, user_input={CONF_ACTION: ACTION_DEL_PRESET}
    )
    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "del_preset"


async def test_add_ciw(
    mocker,
    hass: HomeAssistant,
    options_step_add_ciw_helper,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_flow_id,
) -> None:
    """Test Add CIW action."""
    mocker.patch(
        "custom_components.nice.config_flow.make_id",
        return_value=CIW_HELPER_ID,
    )

    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        user_input={
            "name": "CIW Helper",
            "screen_cover": COVER_1_ID,
            "mask_cover": COVER_2_ID,
        },
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == ""
    assert result.get("result") == True
    assert result.get("data") == {
        "ciw_helpers": {CIW_HELPER_ID: TEST_CIW_HELPER},
        "presets": {},
    }


async def test_add_preset(
    mocker,
    hass: HomeAssistant,
    options_step_add_preset,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_flow_id,
) -> None:
    """Test Add Preset action."""
    mocker.patch(
        "custom_components.nice.config_flow.make_id",
        return_value=PRESET_1_ID,
    )

    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        user_input={
            "name": "Preset 1",
            "select": [COVER_1_ID, COVER_2_ID],
        },
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "define_drop"

    flow_id = result["flow_id"]
    flow: OptionsFlowHandler = get_options_flow(hass, flow_id)

    assert flow.data == {
        "ciw_helpers": {},
        "presets": {PRESET_1_ID: TEST_PARTIAL_PRESET_1_NO_DROPS},
    }
    assert flow.tmp_drops_to_define == [COVER_1_ID, COVER_2_ID]


async def test_add_preset_no_selection(
    hass: HomeAssistant,
    options_step_add_preset,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_flow_id,
) -> None:
    """Test Add Preset action with no selection."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        user_input={
            "name": "Preset 1",
            "select": [],
        },
    )

    assert result.get("errors") == {"select": "no_covers_selected"}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_preset"


async def test_define_drop_1_of_2(
    hass: HomeAssistant,
    options_step_define_drop,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_partial_preset_1_no_drops,
    options_add_drop_for_screen,
    options_add_drop_for_mask,
    options_flow_id,
) -> None:
    """Test add first drop of two"""
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        user_input={"drop": 1.77},
    )

    assert result.get("errors") == {}
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "define_drop"

    flow_id = result["flow_id"]
    flow: OptionsFlowHandler = get_options_flow(hass, flow_id)

    assert flow.data == {
        "ciw_helpers": {},
        "presets": {PRESET_1_ID: TEST_PARTIAL_PRESET_1_ONE_DROP},
    }
    assert flow.tmp_drops_to_define == [COVER_2_ID]


async def test_define_drop_2_of_2(
    hass: HomeAssistant,
    options_step_define_drop,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_partial_preset_1_one_drop,
    options_add_drop_for_mask,
    options_flow_id,
) -> None:
    """Test add second drop of two"""
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        user_input={"drop": 0.5},
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == ""
    assert result.get("result") == True
    assert result.get("data") == {
        "ciw_helpers": {},
        "presets": {PRESET_1_ID: TEST_PRESET_1},
    }


async def test_define_drop_invalid_drop(
    hass: HomeAssistant,
    options_step_define_drop,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_partial_preset_1_no_drops,
    options_add_drop_for_screen,
    options_add_drop_for_mask,
    options_flow_id,
) -> None:
    """Test invalid drop."""
    with pytest.raises(MultipleInvalid):
        await hass.config_entries.options.async_configure(
            options_flow_id,
            user_input={"drop": 2.0},
        )


async def count_entities(hass, entry_id, unique_id_prefix):
    entity_registry = get_entity_registry(hass)
    entries = async_entries_for_config_entry(entity_registry, entry_id)
    return sum(1 for e in entries if e.unique_id.startswith(unique_id_prefix))


async def test_del_ciw(
    hass: HomeAssistant,
    options_step_del_ciw_helper,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_ciw_helper,
    config_entry,
    options_flow_id,
) -> None:
    """Test Del CIW action."""

    id = CIW_HELPER_ID

    num_entities = await count_entities(hass, config_entry.entry_id, id)
    assert num_entities > 0

    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        user_input={"select": [id]},
    )

    num_entities = await count_entities(hass, config_entry.entry_id, id)
    assert num_entities == 0

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == ""
    assert result.get("result") == True
    assert result.get("data") == {
        "ciw_helpers": {},
        "presets": {},
    }


async def test_del_preset(
    hass: HomeAssistant,
    options_step_del_preset,
    config_add_controller_1,
    config_add_screen,
    config_add_mask,
    options_add_preset_1,
    options_add_preset_2,
    options_flow_id,
) -> None:
    """Test Del Preset action."""
    result = await hass.config_entries.options.async_configure(
        options_flow_id,
        user_input={"select": [PRESET_1_ID, PRESET_2_ID]},
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == ""
    assert result.get("result") == True
    assert result.get("data") == {
        "ciw_helpers": {},
        "presets": {},
    }
