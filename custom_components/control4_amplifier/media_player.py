"""Support for Control4 Amplifier media player."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUM_OUTPUTS, CONF_INPUTS, CONF_OUTPUTS, DEFAULT_INPUT_LABELS, DEFAULT_OUTPUT_LABELS
from .coordinator import Control4AmpCoordinator

_LOGGER = logging.getLogger(__name__)

SUPPORT_CONTROL4_AMP = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
)

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control4 Amplifier from config entry."""
    coordinator: Control4AmpCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Get enabled outputs from config
    enabled_outputs = []
    output_configs = config_entry.data.get(CONF_OUTPUTS, {})
    for output_id in range(1, NUM_OUTPUTS + 1):
        output_config = output_configs.get(str(output_id))
        if output_config:  # If output is configured, create entity
            enabled_outputs.append(output_id)

    # Create child entities only for enabled outputs
    child_entities = [
        Control4AmpMediaPlayer(coordinator, config_entry, output_id)
        for output_id in enabled_outputs
    ]

    # Create parent entity
    parent_entity = Control4AmpParentMediaPlayer(coordinator, config_entry, child_entities)

    # Add all entities
    async_add_entities([parent_entity] + child_entities)


class Control4AmpParentMediaPlayer(MediaPlayerEntity):
    """Parent entity for Control4 Amplifier."""

    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = SUPPORT_CONTROL4_AMP

    def __init__(
            self,
            coordinator: Control4AmpCoordinator,
            config_entry: ConfigEntry,
            children: list[Control4AmpMediaPlayer],
    ) -> None:
        """Initialize the parent entity."""
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._children = children
        self._input_labels = {}

        self._attr_unique_id = f"{config_entry.entry_id}_main"
        self._attr_name = config_entry.title or "Control4 Amplifier"

        # Initial update of labels
        self._update_labels()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Register config entry listener
        self.async_on_remove(
            self._config_entry.add_update_listener(self.async_config_entry_updated)
        )

    @callback
    async def async_config_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle config entry updates."""
        self._update_labels()
        self.async_write_ha_state()

    def _update_labels(self) -> None:
        """Update labels from config entry data."""
        input_configs = self._config_entry.data.get(CONF_INPUTS, {})

        # Update input labels only for enabled inputs
        self._input_labels = {}
        for i in range(1, 7):  # 6 total inputs (4 analog + 2 digital)
            input_config = input_configs.get(str(i), {})
            if input_config and input_config.get("enabled", True):  # Only include enabled inputs
                self._input_labels[str(i)] = input_config.get("name", DEFAULT_INPUT_LABELS[i])

        # Clear current input if it's been disabled
        if hasattr(self, '_current_input') and str(self._current_input) not in self._input_labels:
            self._current_input = None

        _LOGGER.debug(
            "Parent: Updated input labels: %s",
            self._input_labels
        )

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of any active child or OFF."""
        if any(child.state == MediaPlayerState.ON for child in self._children):
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def source_list(self) -> list[str]:
        """Return list of available input sources."""
        return list(self._input_labels.values())

    @property
    def source(self) -> str | None:
        """Return currently selected input source."""
        # Return None if children have different sources
        sources = {child.source for child in self._children if child.source is not None}
        return sources.pop() if len(sources) == 1 else None

    async def async_select_source(self, source: str) -> None:
        """Select input source for all outputs."""
        # Find input number from label
        input_number = None
        for number, label in self._input_labels.items():
            if label == source:
                input_number = int(number)
                break

        if input_number is not None:
            for child in self._children:
                await child.async_select_source(source)

    @property
    def volume_level(self) -> float | None:
        """Return average volume of all children."""
        volumes = [child.volume_level for child in self._children if child.volume_level is not None]
        return sum(volumes) / len(volumes) if volumes else None

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for all outputs."""
        for child in self._children:
            await child.async_set_volume_level(volume)


class Control4AmpMediaPlayer(MediaPlayerEntity):
    """Control4 Amplifier Media Player Entity."""

    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = SUPPORT_CONTROL4_AMP

    def __init__(
            self,
            coordinator: Control4AmpCoordinator,
            config_entry: ConfigEntry,
            output_id: int,
    ) -> None:
        """Initialize Control4 Amplifier."""
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._output_id = output_id
        self._input_labels = {}

        # Set unique ID combining config entry ID and output number
        self._attr_unique_id = f"{config_entry.entry_id}_output_{output_id}"

        self._state = MediaPlayerState.ON
        self._volume = 0
        self._current_input = None
        self._bass_level = 0
        self._treble_level = 0

        # Initial update of labels
        self._update_labels()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Register config entry listener
        self.async_on_remove(
            self._config_entry.add_update_listener(self.async_config_entry_updated)
        )

    @callback
    async def async_config_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle config entry updates."""
        self._update_labels()
        # If current input is disabled, clear it
        if self._current_input and str(self._current_input) not in self._input_labels:
            self._current_input = None
        self.async_write_ha_state()

    def _update_labels(self) -> None:
        """Update labels from config entry data."""
        input_configs = self._config_entry.data.get(CONF_INPUTS, {})
        output_configs = self._config_entry.data.get(CONF_OUTPUTS, {})

        # Update input labels only for enabled inputs
        self._input_labels = {}
        for i in range(1, 7):
            str_i = str(i)
            input_config = input_configs.get(str_i, {})
            if input_config and input_config.get("enabled", True):
                self._input_labels[str_i] = input_config.get("name", DEFAULT_INPUT_LABELS[i])

        # Update output name if custom label exists
        output_config = output_configs.get(str(self._output_id), {})
        self._attr_name = output_config.get("name", DEFAULT_OUTPUT_LABELS[self._output_id])

        # Clear current input if it's been disabled
        if self._current_input and str(self._current_input) not in self._input_labels:
            self._current_input = None

        _LOGGER.debug(
            "Output %s: Updated labels: inputs=%s, name=%s",
            self._output_id,
            self._input_labels,
            self._attr_name
        )

    @property
    def state(self) -> MediaPlayerState:
        """Return current state."""
        return self._state

    @property
    def source_list(self) -> list[str]:
        """Return list of available input sources."""
        return list(self._input_labels.values())

    @property
    def source(self) -> str | None:
        """Return currently selected input source."""
        if self._current_input and str(self._current_input) in self._input_labels:
            return self._input_labels[str(self._current_input)]
        return None

    @property
    def volume_level(self) -> float | None:
        """Return current volume level."""
        return self._volume

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "bass_level": self._bass_level,
            "treble_level": self._treble_level,
        }

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        _LOGGER.debug("Selecting source: %s", source)
        # Find input number from label
        input_number = None
        for number, label in self._input_labels.items():
            if label == source:
                input_number = int(number)
                break

        if input_number is not None:
            await self.coordinator.async_select_input(self._output_id, input_number)
            self._current_input = input_number
            self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self.coordinator.async_set_volume(self._output_id, volume)
        self._volume = volume
        self.async_write_ha_state()