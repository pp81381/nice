from homeassistant.const import CONF_NAME

from custom_components.nice.const import (
    CONF_ADDRESS,
    CONF_DROP,
    CONF_HAS_INVERSE_ENDPOINTS,
    CONF_HAS_INVERSE_SEMANTICS,
    CONF_NODE,
    CONF_SERIAL_PORT,
    SUBENTRY_TYPE_COVER,
)

CONTROLLER_TITLE = "NiceTT6: Controller 1 Test"

CONTROLLER_INPUT = {
    CONF_NAME: "Controller 1 Test",
    CONF_SERIAL_PORT: "socket://localhost:50200",
}

TEST_COVER_1_TITLE = "Cover: Screen"

TEST_COVER_1_INPUT = {
    CONF_NAME: "Screen",
    CONF_ADDRESS: 2,
    CONF_NODE: 4,
    CONF_DROP: 1.8,
    CONF_HAS_INVERSE_ENDPOINTS: False,
    CONF_HAS_INVERSE_SEMANTICS: False,
}
TEST_COVER_1_UNIQUE_ID = "02/04"

TEST_SUBENTRY_1 = {
    "data": TEST_COVER_1_INPUT,
    "subentry_type": SUBENTRY_TYPE_COVER,
    "title": TEST_COVER_1_TITLE,
    "unique_id": TEST_COVER_1_UNIQUE_ID,
}
