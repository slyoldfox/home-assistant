"""Test config flow."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import ConnectionError
from rxv.ssdp import RxvDetails

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.yamaha.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import create_empty_config_entry, setup_integration

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch(
            "homeassistant.components.ssdp.Server._async_start_upnp_servers",
        ),
        patch(
            "homeassistant.components.ssdp.Server._async_stop_upnp_servers",
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Mock setting up a config entry."""
    with patch("homeassistant.components.yamaha.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_get_device_info_valid():
    """Mock getting valid device info from Yamaha API."""
    with patch("rxv.RXV", return_value=Mock()):
        yield


@pytest.fixture
def mock_get_device_info_invalid():
    """Mock getting invalid device info from Yamaha API."""
    with (
        patch("rxv.RXV", return_value=None),
        patch(
            "homeassistant.components.yamaha.utils.get_rxv_details",
            return_value=None,
        ),
    ):
        yield


@pytest.fixture
def mock_get_device_info_exception():
    """Mock raising an unexpected Exception."""
    with patch(
        "homeassistant.components.yamaha.utils.get_rxv_details",
        side_effect=Exception("mocked error"),
    ):
        yield


@pytest.fixture
def mock_get_device_info_mc_exception():
    """Mock raising an unexpected Exception."""
    with patch(
        "rxv.RXV",
        side_effect=ConnectionError("mocked error"),
    ):
        yield


@pytest.fixture
def mock_get_device_info_mc_ctrl_url():
    """Mock raising an unexpected Exception."""
    with (
        patch("rxv.RXV", return_value=Mock(serial_number=None)),
        patch("rxv.ssdp.rxv_details", return_value=None),
    ):
        yield


@pytest.fixture
def mock_ssdp_yamaha():
    """Mock that the SSDP detected device is a Yamaha device."""
    with patch(
        "homeassistant.components.yamaha.utils.check_yamaha_ssdp",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_ssdp_no_yamaha():
    """Mock that the SSDP detected device is not a Yamaha device."""
    with patch(
        "homeassistant.components.yamaha.utils.check_yamaha_ssdp",
        return_value=False,
    ):
        yield


@pytest.fixture
def mock_valid_discovery_information():
    """Mock that the ssdp scanner returns a useful upnp description."""
    with (
        patch(
            "homeassistant.components.ssdp.async_get_discovery_info_by_st",
            return_value=[
                ssdp.SsdpServiceInfo(
                    ssdp_usn="mock_usn",
                    ssdp_st="mock_st",
                    ssdp_location="http://127.0.0.1:9000/MediaRenderer/desc.xml",
                    ssdp_headers={
                        "_host": "127.0.0.1",
                    },
                    upnp={
                        ssdp.ATTR_UPNP_SERIAL: "1234567890",
                        ssdp.ATTR_UPNP_MODEL_NAME: "MC20",
                    },
                )
            ],
        ),
        patch(
            "homeassistant.components.yamaha.utils.get_rxv_details",
            return_value=RxvDetails(
                model_name="MC20",
                ctrl_url=None,
                unit_desc_url=None,
                friendly_name=None,
                serial_number="1234567890",
            ),
        ),
    ):
        yield


@pytest.fixture
def mock_empty_discovery_information():
    """Mock that the ssdp scanner returns no upnp description."""
    with (
        patch(
            "homeassistant.components.ssdp.async_get_discovery_info_by_st",
            return_value=[],
        ),
        patch(
            "homeassistant.components.yamaha.utils.get_rxv_details",
            return_value=RxvDetails(
                model_name="MC20",
                ctrl_url=None,
                unit_desc_url=None,
                friendly_name=None,
                serial_number="1234567890",
            ),
        ),
    ):
        yield


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create Yamaha entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Yamaha Receiver",
        data={},
    )


# User Flows


async def test_user_input_device_not_found(
    hass: HomeAssistant, mock_get_device_info_mc_exception
) -> None:
    """Test when user specifies a non-existing device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "none"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


async def test_user_input_device_with_ctrl_url(
    hass: HomeAssistant, mock_get_device_info_mc_ctrl_url
) -> None:
    """Test when user specifies a non-existing device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert isinstance(result2["result"], ConfigEntry)
    assert result2["data"] == {
        "host": "127.0.0.1",
        "serial": None,
        "upnp_description": "http://127.0.0.1:49154/MediaRenderer/desc.xml",
    }


async def test_user_input_non_yamaha_device_found(
    hass: HomeAssistant, mock_get_device_info_invalid
) -> None:
    """Test when user specifies an existing device, which does not provide the Yamaha API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


async def test_user_input_device_already_existing(
    hass: HomeAssistant, mock_get_device_info_valid, mock_valid_discovery_information
) -> None:
    """Test when user specifies an existing device."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234567890",
        data={CONF_HOST: "127.0.0.1", "model": "MC20", "serial": "1234567890"},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_user_input_unknown_error(
    hass: HomeAssistant, mock_get_device_info_exception
) -> None:
    """Test when user specifies an existing device, which does not provide the Yamaha API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unknown"


async def test_user_input_device_found(
    hass: HomeAssistant,
    mock_get_device_info_valid,
    mock_valid_discovery_information,
) -> None:
    """Test when user specifies an existing device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1"},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert isinstance(result2["result"], ConfigEntry)
    assert result2["data"] == {
        "host": "127.0.0.1",
        "serial": "1234567890",
        "upnp_description": "http://127.0.0.1:9000/MediaRenderer/desc.xml",
    }


async def test_user_input_device_found_no_ssdp(
    hass: HomeAssistant,
    mock_get_device_info_valid,
    mock_empty_discovery_information,
) -> None:
    """Test when user specifies an existing device, which no discovery data are present for."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "127.0.0.1"},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert isinstance(result2["result"], ConfigEntry)
    assert result2["data"] == {
        "host": "127.0.0.1",
        "serial": "1234567890",
        "upnp_description": "http://127.0.0.1:49154/MediaRenderer/desc.xml",
    }


# SSDP Flows


async def test_ssdp_discovery_failed(hass: HomeAssistant, mock_ssdp_no_yamaha) -> None:
    """Test when an SSDP discovered device is not a Yamaha device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://127.0.0.1/desc.xml",
            upnp={
                ssdp.ATTR_UPNP_MODEL_NAME: "MC20",
                ssdp.ATTR_UPNP_SERIAL: "123456789",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "yxc_control_url_missing"


async def test_ssdp_discovery_successful_add_device(
    hass: HomeAssistant, mock_ssdp_yamaha
) -> None:
    """Test when the SSDP discovered device is a yamaha device and the user confirms it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://127.0.0.1/desc.xml",
            upnp={
                ssdp.ATTR_UPNP_MODEL_NAME: "MC20",
                ssdp.ATTR_UPNP_SERIAL: "1234567890",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert isinstance(result2["result"], ConfigEntry)
    assert result2["data"] == {
        "host": "127.0.0.1",
        "serial": "1234567890",
        "upnp_description": "http://127.0.0.1/desc.xml",
    }


async def test_ssdp_discovery_existing_device_update(
    hass: HomeAssistant, mock_ssdp_yamaha
) -> None:
    """Test when the SSDP discovered device is a Yamaha device, but it already exists with another IP."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234567890",
        data={CONF_HOST: "192.168.188.18", "model": "MC20", "serial": "1234567890"},
    )
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://127.0.0.1/desc.xml",
            upnp={
                ssdp.ATTR_UPNP_MODEL_NAME: "MC20",
                ssdp.ATTR_UPNP_SERIAL: "1234567890",
            },
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_entry.data[CONF_HOST] == "127.0.0.1"
    assert mock_entry.data["model"] == "MC20"


async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test options flow."""

    config_entry = create_empty_config_entry()
    fake_rxv = Mock()
    fake_rxv.inputs = lambda: {"Napster": "Napster", "AV1": None, "AV2": None}
    config_entry.runtime_data = fake_rxv
    await setup_integration(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "AV1": "Projector",
            "AV2": "TV",
            "source_ignore": ["Napster"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "source_ignore": ["Napster"],
        "source_names": {"AV1": "Projector", "AV2": "TV"},
    }
