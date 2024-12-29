"""Support for Control4 Amplifier media player."""
from __future__ import annotations

import asyncio
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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    NUM_OUTPUTS,
    CONF_INPUTS,
    CONF_OUTPUTS,
    DEFAULT_INPUT_LABELS,
    DEFAULT_OUTPUT_LABELS,
    NO_INPUT_SOURCE,
)
from .player_state import Control4StateManager

_LOGGER = logging.getLogger(__name__)

SUPPORT_CONTROL4_AMP = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_MUTE
)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Control4 Amplifier from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

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
    parent_entity = Control4AmpParentMediaPlayer(
        coordinator, config_entry, child_entities
    )

    # Add all entities
    async_add_entities([parent_entity] + child_entities)


class Control4AmpParentMediaPlayer(MediaPlayerEntity):
    """Parent entity for Control4 Amplifier."""

    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = SUPPORT_CONTROL4_AMP

    def __init__(
            self,
            coordinator: Any,
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title,
            manufacturer="Control4",
            model="C4-8AMP1-B",
        )

        # Initial update of labels
        self._update_labels()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._config_entry.add_update_listener(self._handle_config_entry_update)
        )

    @callback
    def _handle_config_entry_update(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
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
            if input_config and input_config.get("enabled", True):
                self._input_labels[str(i)] = input_config.get(
                    "name", DEFAULT_INPUT_LABELS[i]
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
        sources = {child.source for child in self._children if child.source is not None}
        return sources.pop() if len(sources) == 1 else None

    @property
    def volume_level(self) -> float | None:
        """Return average volume of all children."""
        volumes = [
            child.volume_level
            for child in self._children
            if child.volume_level is not None
        ]
        return sum(volumes) / len(volumes) if volumes else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return true if all children are muted."""
        if not self._children:
            return None
        return all(child.is_volume_muted for child in self._children)

    async def async_select_source(self, source: str) -> None:
        """Select input source for all outputs."""
        input_number = None
        for number, label in self._input_labels.items():
            if label == source:
                input_number = int(number)
                break

        if input_number is not None:
            tasks = [child.async_select_source(source) for child in self._children]
            await asyncio.gather(*tasks)

    async def async_turn_off(self) -> None:
        """Turn off all zones."""
        tasks = [child.async_turn_off() for child in self._children]
        await asyncio.gather(*tasks)
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on all zones."""
        tasks = [child.async_turn_on() for child in self._children]
        await asyncio.gather(*tasks)
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute all zones."""
        tasks = [child.async_mute_volume(mute) for child in self._children]
        await asyncio.gather(*tasks)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level for all outputs."""
        tasks = [child.async_set_volume_level(volume) for child in self._children]
        await asyncio.gather(*tasks)
        self.async_write_ha_state()


class Control4AmpMediaPlayer(MediaPlayerEntity):
    """Control4 Amplifier Media Player Entity."""

    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = SUPPORT_CONTROL4_AMP

    def __init__(
            self,
            coordinator: Any,
            config_entry: ConfigEntry,
            output_id: int,
    ) -> None:
        """Initialize Control4 Amplifier."""
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._output_id = output_id
        self._input_labels = {}
        self._state_manager = Control4StateManager()

        self._attr_unique_id = f"{config_entry.entry_id}_output_{output_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title,
            manufacturer="Control4",
            model="C4-8AMP1-B",
        )

        # Initial update of labels
        self._update_labels()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._config_entry.add_update_listener(self._handle_config_entry_update)
        )

    @callback
    def _handle_config_entry_update(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle config entry updates."""
        self._update_labels()
        current_input = self._state_manager.current.input_source
        if current_input is not None and str(current_input) not in self._input_labels:
            self._state_manager.set_input_source(None)
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
                self._input_labels[str_i] = input_config.get(
                    "name", DEFAULT_INPUT_LABELS[i]
                )

        # Update output name if custom label exists
        output_config = output_configs.get(str(self._output_id), {})
        self._attr_name = output_config.get(
            "name", DEFAULT_OUTPUT_LABELS[self._output_id]
        )

        _LOGGER.debug(
            "Output %s: Updated labels: inputs=%s, name=%s",
            self._output_id,
            self._input_labels,
            self._attr_name,
        )

    @property
    def state(self) -> MediaPlayerState:
        """Return current state."""
        return self._state_manager.current.power_state

    @property
    def source_list(self) -> list[str]:
        """Return list of available input sources."""
        return list(self._input_labels.values())

    @property
    def source(self) -> str | None:
        """Return currently selected input source."""
        input_num = self._state_manager.current.input_source
        if input_num is not None and str(input_num) in self._input_labels:
            return self._input_labels[str(input_num)]
        return None

    @property
    def volume_level(self) -> float | None:
        """Return current volume level."""
        return self._state_manager.current.volume

    @property
    def is_volume_muted(self) -> bool:
        """Return true if volume is muted."""
        return self._state_manager.current.is_muted

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        _LOGGER.debug("Selecting source: %s", source)
        input_number = None
        for number, label in self._input_labels.items():
            if label == source:
                input_number = int(number)
                break

        if input_number is not None:
            await self.coordinator.async_select_input(self._output_id, input_number)
            self._state_manager.set_input_source(input_number)
            self._state_manager.set_power(True)
            self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self.coordinator.async_set_volume(self._output_id, volume)
        self._state_manager.set_volume(volume)
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume."""
        if mute != self._state_manager.current.is_muted:
            if mute:
                self._state_manager.set_mute(True)
                await self.coordinator.async_set_volume(self._output_id, 0)
            else:
                self._state_manager.set_mute(False)
                restore_volume = self._state_manager.current.volume
                await self.coordinator.async_set_volume(
                    self._output_id, restore_volume if restore_volume > 0 else 0.3
                )
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the zone."""
        self._state_manager.set_power(False)
        await self.coordinator.async_select_input(self._output_id, NO_INPUT_SOURCE)
        self._state_manager.set_input_source(NO_INPUT_SOURCE)
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on the zone."""
        previous_state = self._state_manager.previous
        if previous_state and previous_state.input_source is not None:
            # Restore previous input
            await self.coordinator.async_select_input(
                self._output_id, previous_state.input_source
            )
            self._state_manager.set_input_source(previous_state.input_source)

            if not previous_state.is_muted:
                # If it wasn't muted, restore normal volume
                if previous_state.volume is not None:
                    await self.coordinator.async_set_volume(
                        self._output_id, previous_state.volume
                    )
                    self._state_manager.set_volume(previous_state.volume)
            else:
                # If it was muted, maintain mute state
                await self.coordinator.async_set_volume(self._output_id, 0)
                self._state_manager.set_mute(True)
        else:
            # Default to first available input if no previous state
            available_inputs = list(self._input_labels.keys())
            if available_inputs:
                first_input = int(available_inputs[0])
                await self.coordinator.async_select_input(self._output_id, first_input)
                self._state_manager.set_input_source(first_input)

                # Set a default volume if no previous state
                if not self._state_manager.current.is_muted:
                    await self.coordinator.async_set_volume(self._output_id, 0.3)
                    self._state_manager.set_volume(0.3)

        self._state_manager.set_power(True)
        self.async_write_ha_state()