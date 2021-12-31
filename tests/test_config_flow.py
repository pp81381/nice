"""Test the Nice config flow."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
    FlowResult,
)
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry
from voluptuous import MultipleInvalid

import custom_components.nice.config_flow
from custom_components.nice.config_flow import make_id
from custom_components.nice.const import (
    ACTION_ADD_CIW,
    ACTION_ADD_PRESET,
    ACTION_DEL_CIW,
    ACTION_DEL_PRESET,
    CONF_ACTION,
    DOMAIN,
)

TEST_TITLE = "Nice TT6 Test"

CONTROLLER_INPUT = {
    "name": "Controller 1 Test",
    "serial_port": "socket://localhost:50200",
    "add_another": False,
}

SCREEN_COVER_INPUT = {
    "name": "Screen",
    "controller": "controller_1_id",
    "address": 2,
    "node": 4,
    "drop": 1.8,
    "has_image_area": True,
}


MASK_COVER_INPUT = {
    "name": "Mask",
    "controller": "controller_1_id",
    "address": 3,
    "node": 4,
    "drop": 0.5,
    "has_image_area": False,
}

SCREEN_IMAGE_INPUT = {
    "image_border_below": 0.05,
    "image_height": 1.57,
    "image_aspect_ratio": 16 / 9,
}

INVALID_SCREEN_IMAGE_INPUT = {
    "image_border_below": 0.05,
    "image_height": 2.0,
    "image_aspect_ratio": 16 / 9,
}

TEST_CONTROLLER = {
    "name": "Controller 1 Test",
    "serial_port": "socket://localhost:50200",
}

TEST_PARTIAL_SCREEN = {
    "name": "Screen",
    "controller": "controller_1_id",
    "address": 2,
    "node": 4,
    "drop": 1.8,
    "image_area": None,
}

TEST_SCREEN = {
    "name": "Screen",
    "controller": "controller_1_id",
    "address": 2,
    "node": 4,
    "drop": 1.8,
    "image_area": {
        "image_border_below": 0.05,
        "image_height": 1.57,
        "image_aspect_ratio": 16 / 9,
    },
}

TEST_MASK = {
    "name": "Mask",
    "controller": "controller_1_id",
    "address": 3,
    "node": 4,
    "drop": 0.5,
    "image_area": None,
}


TEST_CONFIG_NO_MASK = {
    "controllers": {
        "controller_1_id": TEST_CONTROLLER,
    },
    "covers": {
        "cover_1_id": TEST_SCREEN,
    },
}

TEST_CONFIG_WITH_MASK = {
    "controllers": {
        "controller_1_id": TEST_CONTROLLER,
    },
    "covers": {
        "cover_1_id": TEST_SCREEN,
        "cover_2_id": TEST_MASK,
    },
}

TEST_CIW_MANAGER = {
    "name": "CIW Manager 1",
    "screen_cover": "cover_1_id",
    "mask_cover": "cover_2_id",
}

TEST_PRESET_1 = {
    "name": "Preset 1",
    "drops": [
        {"cover": "cover_1_id", "drop": 1.77},
        {"cover": "cover_2_id", "drop": 0.5},
    ],
}

TEST_PRESET_2 = {
    "name": "Preset 2",
    "drops": [
        {"cover": "cover_1_id", "drop": 0.0},
        {"cover": "cover_2_id", "drop": 0.0},
    ],
}

TEST_OPTIONS = {
    "ciw_managers": {
        "ciw_1_id": TEST_CIW_MANAGER,
    },
    "presets": {
        "preset_1_id": TEST_PRESET_1,
        "preset_2_id": TEST_PRESET_2,
    },
}


@asynccontextmanager
async def dummy_open_connection(serial_port=None):
    yield True


def get_flow(hass, flow_id):
    return hass.config_entries.flow._progress[flow_id]


async def _dummy_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    pass


@pytest.fixture(autouse=True)
def no_reload():
    """To ensure a clean teardown."""
    with patch(
        "custom_components.nice._async_update_listener",
        new=_dummy_update_listener,
    ):
        yield


@pytest.fixture
def config_entry_title_override():
    return None


@pytest.fixture
def config_entry_data_override():
    return None


@pytest.fixture
def config_entry_tmp_override():
    return None


@pytest.fixture
async def config_flow_id(
    hass: HomeAssistant,
    step_id,
    config_entry_title_override,
    config_entry_data_override,
    config_entry_tmp_override,
):
    async def async_step_setup_test(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input["title_override"] is not None:
            self.title = user_input["title_override"]
        if user_input["data_override"] is not None:
            self.data = user_input["data_override"]
        if user_input["tmp_override"] is not None:
            self.tmp = user_input["tmp_override"]
        method = f"async_step_{user_input['step_id']}"
        return await getattr(self, method)(None)

    user_input = {
        "step_id": step_id,
        "title_override": config_entry_title_override,
        "data_override": config_entry_data_override,
        "tmp_override": config_entry_tmp_override,
    }
    with patch.object(
        custom_components.nice.config_flow.ConfigFlow,
        "async_step_setup_test",
        async_step_setup_test,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "setup_test"},
            data=user_input,
        )

    assert result["errors"] == {}
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == step_id

    return result["flow_id"]


@pytest.fixture
async def options_flow_id(hass: HomeAssistant, config_entry):
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    return result["flow_id"]


@pytest.fixture()
def config_entry_options():
    return {}


@pytest.fixture()
async def config_entry(
    hass: HomeAssistant,
    config_entry_data,
    config_entry_options,
) -> None:
    with patch(
        "nicett6.multiplexer.create_serial_connection",
        return_value=[MagicMock(), MagicMock()],
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="my_unique_id",
            data=config_entry_data,
            options=config_entry_options,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry


async def test_make_id():
    with patch(
        "custom_components.nice.config_flow.uuid4",
        return_value=uuid.UUID("12345678123456781234567812345678"),
    ):
        id = make_id()
    assert id == "12345678_1234_5678_1234_567812345678"


class TestUserStep:
    @pytest.fixture
    def step_id(self):
        return "user"

    async def test_user(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test user step."""
        result = await hass.config_entries.flow.async_configure(
            config_flow_id, {"title": TEST_TITLE}
        )
        await hass.async_block_till_done()

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "controller"

        flow = get_flow(hass, config_flow_id)
        assert flow.title == TEST_TITLE


class TestControllerStep:
    @pytest.fixture
    def step_id(self):
        return "controller"

    async def test_controller_valid_port(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test valid serial port."""
        with patch(
            "custom_components.nice.config_flow.open_connection",
            new=dummy_open_connection,
        ), patch(
            "custom_components.nice.config_flow.make_id",
            return_value="controller_1_id",
        ):
            result = await hass.config_entries.flow.async_configure(
                config_flow_id,
                CONTROLLER_INPUT,
            )
            await hass.async_block_till_done()

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "cover"

        flow = get_flow(hass, config_flow_id)
        assert flow.data == {
            "controllers": {
                "controller_1_id": TEST_CONTROLLER,
            },
            "covers": {},
        }

    async def test_controller_invalid_port(
        self,
        hass: HomeAssistant,
        config_flow_id,
        step_id,
    ) -> None:
        """Test invalid serial port."""
        with patch(
            "custom_components.nice.config_flow.open_connection",
            side_effect=ValueError,
        ), patch(
            "custom_components.nice.config_flow.make_id",
            return_value="controller_1_id",
        ):
            result = await hass.config_entries.flow.async_configure(
                config_flow_id,
                CONTROLLER_INPUT,
            )
            await hass.async_block_till_done()

        assert result["errors"] == {"base": "cannot_connect"}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == step_id


class TestCoverStep:
    @pytest.fixture
    def step_id(self):
        return "cover"

    @pytest.fixture
    def config_entry_data_override(self):
        return {
            "controllers": {"controller_1_id": TEST_CONTROLLER},
            "covers": {},
        }

    async def test_cover_with_image_area(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test a cover with an image area."""
        with patch(
            "custom_components.nice.config_flow.make_id",
            return_value="cover_1_id",
        ):
            result = await hass.config_entries.flow.async_configure(
                config_flow_id,
                SCREEN_COVER_INPUT,
            )
            await hass.async_block_till_done()

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "image_area"

        flow = get_flow(hass, config_flow_id)
        assert flow.tmp == "cover_1_id"
        assert flow.data["covers"]["cover_1_id"] == TEST_PARTIAL_SCREEN

    async def test_cover_without_image_area(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test a cover without an image area."""
        with patch(
            "custom_components.nice.config_flow.make_id",
            return_value="cover_2_id",
        ):
            result = await hass.config_entries.flow.async_configure(
                config_flow_id,
                MASK_COVER_INPUT,
            )
            await hass.async_block_till_done()

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "finish_cover"

        flow = get_flow(hass, config_flow_id)
        assert flow.data["covers"]["cover_2_id"] == TEST_MASK


class TestImageDataStep:
    @pytest.fixture
    def step_id(self):
        return "image_area"

    @pytest.fixture
    def config_entry_data_override(self):
        return {
            "controllers": {"controller_1_id": TEST_CONTROLLER},
            "covers": {"cover_1_id": TEST_PARTIAL_SCREEN},
        }

    @pytest.fixture
    def config_entry_tmp_override(self):
        return "cover_1_id"

    async def test_image_area(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test an image area."""
        result = await hass.config_entries.flow.async_configure(
            config_flow_id,
            SCREEN_IMAGE_INPUT,
        )
        await hass.async_block_till_done()

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "finish_cover"

    async def test_invalid_image_area(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test an invalid image area."""
        result = await hass.config_entries.flow.async_configure(
            config_flow_id,
            INVALID_SCREEN_IMAGE_INPUT,
        )
        await hass.async_block_till_done()

        assert result["errors"] == {"base": "image_area_too_tall"}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "image_area"


class TestFinishCoverStep:
    @pytest.fixture
    def step_id(self):
        return "finish_cover"

    @pytest.fixture
    def config_entry_title_override(self):
        return TEST_TITLE

    @pytest.fixture
    def config_entry_data_override(self):
        return {
            "controllers": {"controller_1_id": TEST_CONTROLLER},
            "covers": {"cover_1_id": TEST_SCREEN},
        }

    async def test_finish_cover(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test finishing a cover."""
        with patch(
            "custom_components.nice.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry:
            result = await hass.config_entries.flow.async_configure(
                config_flow_id,
                {"add_another": False},
            )
            await hass.async_block_till_done()

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == TEST_TITLE
        assert result["data"] == TEST_CONFIG_NO_MASK
        assert len(mock_setup_entry.mock_calls) == 1

    async def test_add_another_cover(
        self,
        hass: HomeAssistant,
        config_flow_id,
    ) -> None:
        """Test add another cover."""
        result = await hass.config_entries.flow.async_configure(
            config_flow_id,
            {"add_another": True},
        )
        await hass.async_block_till_done()

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "cover"


class TestOptionsFlowInitWithMask:
    @pytest.fixture
    def config_entry_data(self):
        return TEST_CONFIG_WITH_MASK

    async def test_options_init_mask_add_ciw(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify Add CIW menu item."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_CIW}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_ciw_manager"

    async def test_options_init_mask_no_del_ciw(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify no Del CIW menu item."""
        with pytest.raises(MultipleInvalid):
            await hass.config_entries.options.async_configure(
                options_flow_id, user_input={CONF_ACTION: ACTION_DEL_CIW}
            )

    async def test_options_init_mask_add_preset(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify Add Preset menu item."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_preset"

    async def test_options_init_mask_no_del_preset(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify no Del Preset menu item."""
        with pytest.raises(MultipleInvalid):
            await hass.config_entries.options.async_configure(
                options_flow_id, user_input={CONF_ACTION: ACTION_DEL_PRESET}
            )


class TestOptionsFlowInitWithoutMask:
    @pytest.fixture
    def config_entry_data(self):
        return TEST_CONFIG_NO_MASK

    async def test_options_init_nomask_no_add_ciw(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify no Add CIW menu item."""
        with pytest.raises(MultipleInvalid):
            await hass.config_entries.options.async_configure(
                options_flow_id, user_input={CONF_ACTION: ACTION_ADD_CIW}
            )

    async def test_options_init_nomask_no_del_ciw(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify no Del CIW menu item."""
        with pytest.raises(MultipleInvalid):
            await hass.config_entries.options.async_configure(
                options_flow_id, user_input={CONF_ACTION: ACTION_DEL_CIW}
            )

    async def test_options_init_nomask_add_preset(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify Add Preset menu item."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_preset"

    async def test_options_init_nomask_no_del_preset(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify no Del Preset menu item."""
        with pytest.raises(MultipleInvalid):
            await hass.config_entries.options.async_configure(
                options_flow_id, user_input={CONF_ACTION: ACTION_DEL_PRESET}
            )


class TestOptionsFlowInitWithOptions:
    @pytest.fixture
    def config_entry_data(self):
        return TEST_CONFIG_WITH_MASK

    @pytest.fixture
    def config_entry_options(self):
        return TEST_OPTIONS

    async def test_options_init_opt_add_ciw(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify Add CIW menu item."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_CIW}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_ciw_manager"

    async def test_options_init_opt_del_ciw(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify Del CIW menu item."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_CIW}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "del_ciw_manager"

    async def test_options_init_opt_add_preset(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify Add Preset menu item."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_preset"

    async def test_options_init_opt_del_preset(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Verify Del Preset menu item."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "del_preset"


class TestOptionsFlowAddActions:
    @pytest.fixture
    def config_entry_data(self):
        return TEST_CONFIG_WITH_MASK

    async def test_add_ciw(self, hass: HomeAssistant, options_flow_id) -> None:
        """Test Add CIW action."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_CIW}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_ciw_manager"

        with patch(
            "custom_components.nice.config_flow.make_id",
            return_value="ciw_1_id",
        ):
            result = await hass.config_entries.options.async_configure(
                options_flow_id,
                user_input={
                    "name": "CIW Manager 1",
                    "screen_cover": "cover_1_id",
                    "mask_cover": "cover_2_id",
                },
            )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == ""
        assert result["result"] is True
        assert result["data"] == {
            "ciw_managers": {
                "ciw_1_id": TEST_CIW_MANAGER,
            },
            "presets": {},
        }

    async def test_add_preset(self, hass: HomeAssistant, options_flow_id) -> None:
        """Test Add Preset action."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_preset"

        with patch(
            "custom_components.nice.config_flow.make_id",
            return_value="preset_1_id",
        ):
            result = await hass.config_entries.options.async_configure(
                options_flow_id,
                user_input={
                    "name": "Preset 1",
                    "select": ["cover_1_id", "cover_2_id"],
                },
            )

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "define_drop"

        result = await hass.config_entries.options.async_configure(
            options_flow_id,
            user_input={"drop": 1.77},
        )

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "define_drop"

        result = await hass.config_entries.options.async_configure(
            options_flow_id,
            user_input={"drop": 0.5},
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == ""
        assert result["result"] is True
        assert result["data"] == {
            "ciw_managers": {},
            "presets": {
                "preset_1_id": TEST_PRESET_1,
            },
        }

    async def test_add_preset_invalid_drop(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Test Add Preset action with invalid drop."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_preset"

        with patch(
            "custom_components.nice.config_flow.make_id",
            return_value="preset_1_id",
        ):
            result = await hass.config_entries.options.async_configure(
                options_flow_id,
                user_input={
                    "name": "Preset 1",
                    "select": ["cover_1_id", "cover_2_id"],
                },
            )

        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "define_drop"

        with pytest.raises(MultipleInvalid):
            await hass.config_entries.options.async_configure(
                options_flow_id,
                user_input={"drop": 2.0},
            )

    async def test_add_preset_no_selection(
        self, hass: HomeAssistant, options_flow_id
    ) -> None:
        """Test Add Preset action with no selection."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_ADD_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_preset"

        result = await hass.config_entries.options.async_configure(
            options_flow_id,
            user_input={
                "name": "Preset 1",
                "select": [],
            },
        )

        assert result["errors"] == {"base": "no_covers_selected"}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "add_preset"


async def count_entities(hass, entry_id, unique_id_prefix):
    entity_registry = await async_get_registry(hass)
    entries = async_entries_for_config_entry(entity_registry, entry_id)
    return sum(1 for e in entries if e.unique_id.startswith(unique_id_prefix))


class TestOptionsFlowDelActions:
    @pytest.fixture
    def config_entry_data(self):
        return TEST_CONFIG_WITH_MASK

    @pytest.fixture
    def config_entry_options(self):
        return TEST_OPTIONS

    async def test_del_ciw(
        self, hass: HomeAssistant, config_entry, options_flow_id
    ) -> None:
        """Test Del CIW action."""

        id = "ciw_1_id"

        num_entities = await count_entities(hass, config_entry.entry_id, id)
        assert num_entities > 0

        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_CIW}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "del_ciw_manager"

        result = await hass.config_entries.options.async_configure(
            options_flow_id,
            user_input={"select": [id]},
        )

        num_entities = await count_entities(hass, config_entry.entry_id, id)
        assert num_entities == 0

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == ""
        assert result["result"] is True
        assert result["data"] == {
            "ciw_managers": {},
            "presets": {"preset_1_id": TEST_PRESET_1, "preset_2_id": TEST_PRESET_2},
        }

    async def test_del_preset(self, hass: HomeAssistant, options_flow_id) -> None:
        """Test Del Preset action."""
        result = await hass.config_entries.options.async_configure(
            options_flow_id, user_input={CONF_ACTION: ACTION_DEL_PRESET}
        )
        assert result["errors"] == {}
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "del_preset"

        result = await hass.config_entries.options.async_configure(
            options_flow_id,
            user_input={"select": ["preset_1_id", "preset_2_id"]},
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == ""
        assert result["result"] is True
        assert result["data"] == {
            "ciw_managers": {"ciw_1_id": TEST_CIW_MANAGER},
            "presets": {},
        }
