"""Test component setup."""

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nice.const import DOMAIN

from .util import init_integration


async def test_async_setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Test the component gets setup."""
    await init_integration(hass, mock_config_entry)
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.fixture
def mock_config_entry_v1() -> MockConfigEntry:
    return MockConfigEntry(
        title="Projector Screen",
        domain=DOMAIN,
        data={
            "controllers": {
                "667ef095_20e0_4823_bab2_93764291409d": {
                    "name": "Projector Screen Controller",
                    "serial_port": "socket://localhost:50200",
                }
            },
            "covers": {
                "8727e754_30f6_4334_a470_cda7c11635f8": {
                    "address": 3,
                    "controller": "667ef095_20e0_4823_bab2_93764291409d",
                    "drop": 0.67,
                    "has_reverse_semantics": True,
                    "image_area": None,
                    "name": "Mask",
                    "node": 4,
                },
                "bb8d650d_2c26_4eb6_8581_9a081245d491": {
                    "address": 2,
                    "controller": "667ef095_20e0_4823_bab2_93764291409d",
                    "drop": 1.825,
                    "has_reverse_semantics": True,
                    "image_area": {
                        "image_aspect_ratio_choice": "aspect_ratio_16_9",
                        "image_aspect_ratio_other": None,
                        "image_border_below": 0.1,
                        "image_height": 1.57,
                    },
                    "name": "Screen",
                    "node": 4,
                },
            },
        },
        version=1,
        options={
            "ciw_helpers": {
                "09042892_b5b3_468b_af80_068e15c7e5a6": {
                    "aspect_ratio_mode": "FIXED_BOTTOM",
                    "baseline_drop": None,
                    "mask_cover": "8727e754_30f6_4334_a470_cda7c11635f8",
                    "name": "CIW Helper 1",
                    "screen_cover": "bb8d650d_2c26_4eb6_8581_9a081245d491",
                }
            },
            "presets": {
                "47edfe4c_a781_45c3_9f82_55f508e896ee": {
                    "drops": [
                        {"cover": "bb8d650d_2c26_4eb6_8581_9a081245d491", "drop": 0.0},
                        {"cover": "8727e754_30f6_4334_a470_cda7c11635f8", "drop": 0.0},
                    ],
                    "name": "Preset 2",
                },
                "d0be34c3_5642_4a2b_800a_2c1e572b7523": {
                    "drops": [
                        {
                            "cover": "bb8d650d_2c26_4eb6_8581_9a081245d491",
                            "drop": 1.735,
                        },
                        {"cover": "8727e754_30f6_4334_a470_cda7c11635f8", "drop": 0.46},
                    ],
                    "name": "Preset 1",
                },
            },
        },
    )


@pytest.fixture
def mock_config_entry_v1_added_to_hass(
    hass: HomeAssistant, mock_config_entry_v1: MockConfigEntry
) -> MockConfigEntry:
    mock_config_entry_v1.add_to_hass(hass)
    return mock_config_entry_v1


@pytest.fixture
def mock_v1_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry_v1_added_to_hass: MockConfigEntry,
) -> None:
    for controller_id, controller_config in mock_config_entry_v1_added_to_hass.data[
        "controllers"
    ].items():
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry_v1_added_to_hass.entry_id,
            identifiers={(DOMAIN, controller_id)},
            manufacturer="Nice",
            name=controller_config[CONF_NAME],
            model="Nice TT6 Control Unit",
        )
    for cover_id, cover_config in mock_config_entry_v1_added_to_hass.data[
        "covers"
    ].items():
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry_v1_added_to_hass.entry_id,
            identifiers={(DOMAIN, cover_id)},
            name=cover_config[CONF_NAME],
            manufacturer="Nice",
            model="Nice Tubular Motor",
            via_device=(DOMAIN, cover_config["controller"]),
        )


@pytest.mark.usefixtures("mock_v1_devices")
async def test_async_migrate_entry_v1_to_v2_1(
    hass: HomeAssistant, mock_config_entry_v1: MockConfigEntry
):
    """Test the migration from v1 to v2.1."""
    await init_integration(hass, mock_config_entry_v1)
    entry_id = mock_config_entry_v1.entry_id

    assert await async_setup_component(hass, DOMAIN, {}) is True

    updated_entry = hass.config_entries.async_get_entry(entry_id)
    assert updated_entry is not None
    assert updated_entry.state is ConfigEntryState.LOADED
    assert updated_entry.version == 2
    assert updated_entry.minor_version == 1
    assert updated_entry.title == "NiceTT6: Projector Screen Controller"
    assert updated_entry.data == {
        "name": "Projector Screen Controller",
        "serial_port": "socket://localhost:50200",
    }
    assert updated_entry.options == {}

    updated_subentries = list(updated_entry.subentries.values())
    assert len(updated_subentries) == 2

    mask_subentry = updated_subentries[0]
    assert mask_subentry.title == "Cover: Mask"
    expected_mask_subentry_data = {
        "name": "Mask",
        "address": 3,
        "node": 4,
        "drop": 0.67,
        "has_inverse_semantics": True,
    }
    assert mask_subentry.data == expected_mask_subentry_data
    assert mask_subentry.unique_id == "03/04"

    screen_subentry = updated_subentries[1]
    assert screen_subentry.title == "Cover: Screen"
    expected_screen_subentry_data = {
        "name": "Screen",
        "address": 2,
        "node": 4,
        "drop": 1.825,
        "has_inverse_semantics": True,
    }
    assert screen_subentry.data == expected_screen_subentry_data
    assert screen_subentry.unique_id == "02/04"

    device_registry = dr.async_get(hass)
    updated_controller_device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry_id)}
    )
    updated_mask_device = device_registry.async_get_device(
        identifiers={(DOMAIN, mask_subentry.subentry_id)}
    )
    updated_screen_device = device_registry.async_get_device(
        identifiers={(DOMAIN, screen_subentry.subentry_id)}
    )
    assert updated_controller_device is not None
    assert updated_mask_device is not None
    assert updated_screen_device is not None
