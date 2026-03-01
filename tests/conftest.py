"""Fixtures for testing."""

import pytest
from nicett6.cover import Cover
from nicett6.tt6_cover import TT6Cover
from nicett6.ttbus_device import TTBusDeviceAddress
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nice.const import DOMAIN

from .const import CONTROLLER_INPUT, CONTROLLER_TITLE, TEST_SUBENTRY_1


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def disable_cover_manager(mocker):
    """Mock the CoverManager to prevent it trying to open a serial connection during tests."""
    c = mocker.patch("custom_components.nice.CoverManager", autospec=True)

    async def add_cover(tt_addr: TTBusDeviceAddress, cover: Cover) -> TT6Cover:
        return TT6Cover(tt_addr, cover, mocker.AsyncMock())

    c.return_value.add_cover.side_effect = add_cover


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        title=CONTROLLER_TITLE,
        domain=DOMAIN,
        data=CONTROLLER_INPUT,
        version=2,
        minor_version=1,
        subentries_data=[TEST_SUBENTRY_1],
    )
