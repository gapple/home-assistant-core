"""The tests for the JSON MQTT device tracker platform."""
import json
import logging
import os
from unittest.mock import patch

import pytest

from homeassistant.components.device_tracker.legacy import (
    DOMAIN as DT_DOMAIN,
    YAML_DEVICES,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_mqtt_message

LOCATION_MESSAGE = {
    "longitude": 1.0,
    "gps_accuracy": 60,
    "latitude": 2.0,
    "battery_level": 99.9,
}

LOCATION_MESSAGE_INCOMPLETE = {"longitude": 2.0}


@pytest.fixture(autouse=True)
async def setup_comp(hass, mqtt_mock_entry_with_yaml_config):
    """Initialize components."""
    yaml_devices = hass.config.path(YAML_DEVICES)
    yield
    if os.path.isfile(yaml_devices):
        os.remove(yaml_devices)


async def test_ensure_device_tracker_platform_validation(hass: HomeAssistant) -> None:
    """Test if platform validation was done."""

    async def mock_setup_scanner(hass, config, see, discovery_info=None):
        """Check that Qos was added by validation."""
        assert "qos" in config

    with patch(
        "homeassistant.components.mqtt_json.device_tracker.async_setup_scanner",
        autospec=True,
        side_effect=mock_setup_scanner,
    ) as mock_sp:
        dev_id = "paulus"
        topic = "location/paulus"
        assert await async_setup_component(
            hass,
            DT_DOMAIN,
            {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: topic}}},
        )
        assert mock_sp.call_count == 1


async def test_json_message(hass: HomeAssistant) -> None:
    """Test json location message."""
    dev_id = "zanzito"
    topic = "location/zanzito"
    location = json.dumps(LOCATION_MESSAGE)

    assert await async_setup_component(
        hass,
        DT_DOMAIN,
        {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: topic}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.zanzito")
    assert state.attributes.get("latitude") == 2.0
    assert state.attributes.get("longitude") == 1.0


async def test_non_json_message(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test receiving a non JSON message."""
    dev_id = "zanzito"
    topic = "location/zanzito"
    location = "home"

    assert await async_setup_component(
        hass,
        DT_DOMAIN,
        {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: topic}}},
    )

    caplog.set_level(logging.ERROR)
    caplog.clear()
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert "Error parsing JSON payload: home" in caplog.text


async def test_incomplete_message(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test receiving an incomplete message."""
    dev_id = "zanzito"
    topic = "location/zanzito"
    location = json.dumps(LOCATION_MESSAGE_INCOMPLETE)

    assert await async_setup_component(
        hass,
        DT_DOMAIN,
        {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: topic}}},
    )

    caplog.set_level(logging.ERROR)
    caplog.clear()
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert (
        "Skipping update for following data because of missing "
        'or malformatted data: {"longitude": 2.0}' in caplog.text
    )


async def test_single_level_wildcard_topic(hass: HomeAssistant) -> None:
    """Test single level wildcard topic."""
    dev_id = "zanzito"
    subscription = "location/+/zanzito"
    topic = "location/room/zanzito"
    location = json.dumps(LOCATION_MESSAGE)

    assert await async_setup_component(
        hass,
        DT_DOMAIN,
        {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.zanzito")
    assert state.attributes.get("latitude") == 2.0
    assert state.attributes.get("longitude") == 1.0


async def test_multi_level_wildcard_topic(hass: HomeAssistant) -> None:
    """Test multi level wildcard topic."""
    dev_id = "zanzito"
    subscription = "location/#"
    topic = "location/zanzito"
    location = json.dumps(LOCATION_MESSAGE)

    assert await async_setup_component(
        hass,
        DT_DOMAIN,
        {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.zanzito")
    assert state.attributes.get("latitude") == 2.0
    assert state.attributes.get("longitude") == 1.0


async def test_single_level_wildcard_topic_not_matching(hass: HomeAssistant) -> None:
    """Test not matching single level wildcard topic."""
    dev_id = "zanzito"
    entity_id = f"{DT_DOMAIN}.{dev_id}"
    subscription = "location/+/zanzito"
    topic = "location/zanzito"
    location = json.dumps(LOCATION_MESSAGE)

    assert await async_setup_component(
        hass,
        DT_DOMAIN,
        {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None


async def test_multi_level_wildcard_topic_not_matching(hass: HomeAssistant) -> None:
    """Test not matching multi level wildcard topic."""
    dev_id = "zanzito"
    entity_id = f"{DT_DOMAIN}.{dev_id}"
    subscription = "location/#"
    topic = "somewhere/zanzito"
    location = json.dumps(LOCATION_MESSAGE)

    assert await async_setup_component(
        hass,
        DT_DOMAIN,
        {DT_DOMAIN: {CONF_PLATFORM: "mqtt_json", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
