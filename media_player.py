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

from .const import DOMAIN, NUM_OUTPUTS
from .coordinator import Control4AmpCoordinator, InputSource

_LOGGER = logging.getLogger(__name__)

DEFAULT_INPUT_LABELS = {
    1: "Analog Input 1",
    2: "Analog Input 2",
    3: "Analog Input 3",
    4: "Analog Input 4",
    5: "Digital Input 1",
    6: "Digital Input 2",
}

DEFAULT_OUTPUT_LABELS = {
    1: "Stereo Output 1",
    2: "Stereo Output 2",
    3: "Stereo Output 3",
    4: "Stereo Output 4",
}

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

    # Create child entities
    child_entities = [
        Control4AmpMediaPlayer(coordinator, config_entry, output_id)
        for output_id in range(1, NUM_OUTPUTS + 1)
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
        self._update_labels_from_options()

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
        self._update_labels_from_options()
        self.async_write_ha_state()

    def _update_labels_from_options(self) -> None:
        """Update labels from config entry options."""
        options = self._config_entry.options

        # Update input labels only for enabled inputs
        self._input_labels = {}
        for i in range(1, 7):  # 6 total inputs (4 analog + 2 digital)
            if options.get(f"input_{i}_enabled", True):  # Only include enabled inputs
                self._input_labels[str(i)] = options.get(
                    f"input_{i}_name",
                    DEFAULT_INPUT_LABELS[i]
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
        self._update_labels_from_options()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Register config entry listener
        self.async_on_remove(
            self._config_entry.add_update_listener(self.async_config_entry_updated)
        )

        @callback
        def _handle_volume_changed(event):
            """Handle volume changes."""
            if event.data["output"] == self._output_id:
                self._volume = event.data["volume"]
                self.async_write_ha_state()

        @callback
        def _handle_input_changed(event):
            """Handle input changes."""
            if event.data["output"] == self._output_id:
                # Map the physical input back to logical input
                input_type = event.data["input_type"]
                physical_number = event.data["state"]
                for logical_input, (source_type, phys_num) in self.coordinator._input_map.items():
                    if (input_type == "digital" and source_type == InputSource.DIGITAL or
                        input_type == "analog" and source_type == InputSource.ANALOG) and \
                            phys_num == physical_number:
                        # Only update if the input is enabled
                        if str(logical_input) in self._input_labels:
                            self._current_input = logical_input
                            break
                self.async_write_ha_state()

        @callback
        def _handle_bass_changed(event):
            """Handle bass changes."""
            if event.data["output"] == self._output_id:
                self._bass_level = event.data["level"]
                self.async_write_ha_state()

        @callback
        def _handle_treble_changed(event):
            """Handle treble changes."""
            if event.data["output"] == self._output_id:
                self._treble_level = event.data["level"]
                self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_volume_changed", _handle_volume_changed)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_input_changed", _handle_input_changed)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_bass_changed", _handle_bass_changed)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(f"{DOMAIN}_treble_changed", _handle_treble_changed)
        )

    @callback
    async def async_config_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle config entry updates."""
        self._update_labels_from_options()
        self.async_write_ha_state()

    def _update_labels_from_options(self) -> None:
        """Update labels from config entry options."""
        options = self._config_entry.options

        # Update input labels only for enabled inputs
        self._input_labels = {}
        for i in range(1, 7):  # 6 total inputs (4 analog + 2 digital)
            if options.get(f"input_{i}_enabled", True):  # Only include enabled inputs
                self._input_labels[str(i)] = options.get(
                    f"input_{i}_name",
                    DEFAULT_INPUT_LABELS[i]
                )

        # Update output name if custom label exists
        self._attr_name = options.get(
            f"output_{self._output_id}_name",
            DEFAULT_OUTPUT_LABELS[self._output_id]
        )

        # If current input is disabled, clear it
        if self._current_input and str(self._current_input) not in self._input_labels:
            self._current_input = None

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

    async def async_set_bass(self, level: int) -> None:
        """Set bass level."""
        await self.coordinator.async_set_bass(self._output_id, level)
        self._bass_level = level
        self.async_write_ha_state()

    async def async_set_treble(self, level: int) -> None:
        """Set treble level."""
        await self.coordinator.async_set_treble(self._output_id, level)
        self._treble_level = level
        self.async_write_ha_state()