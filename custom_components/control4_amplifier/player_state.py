"""State management for Control4 Amplifier media players."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from homeassistant.components.media_player import MediaPlayerState


@dataclass
class Control4ZoneState:
    """Represents the state of a Control4 Amplifier zone."""

    volume: float = 0.0
    input_source: Optional[int] = None
    is_muted: bool = False
    pre_mute_volume: Optional[float] = None
    power_state: MediaPlayerState = MediaPlayerState.OFF

    @property
    def is_on(self) -> bool:
        """Return True if the zone is powered on."""
        return self.power_state == MediaPlayerState.ON

    def store_mute_state(self) -> None:
        """Store current volume before muting."""
        if not self.is_muted:
            self.pre_mute_volume = self.volume

    def restore_mute_state(self) -> None:
        """Restore volume from before muting."""
        if self.pre_mute_volume is not None:
            self.volume = self.pre_mute_volume

    def to_dict(self) -> dict:
        """Convert state to dictionary for storage."""
        return {
            'volume': self.volume,
            'input_source': self.input_source,
            'is_muted': self.is_muted,
            'pre_mute_volume': self.pre_mute_volume,
            'power_state': self.power_state,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Control4ZoneState:
        """Create state instance from dictionary."""
        return cls(
            volume=data.get('volume', 0.0),
            input_source=data.get('input_source'),
            is_muted=data.get('is_muted', False),
            pre_mute_volume=data.get('pre_mute_volume'),
            power_state=data.get('power_state', MediaPlayerState.OFF),
        )

    def copy(self) -> Control4ZoneState:
        """Create a copy of the current state."""
        return Control4ZoneState(
            volume=self.volume,
            input_source=self.input_source,
            is_muted=self.is_muted,
            pre_mute_volume=self.pre_mute_volume,
            power_state=self.power_state,
        )


class Control4StateManager:
    """Manages state for Control4 Amplifier zones."""

    def __init__(self) -> None:
        """Initialize the state manager."""
        self._current_state = Control4ZoneState()
        self._previous_state: Optional[Control4ZoneState] = None

    @property
    def current(self) -> Control4ZoneState:
        """Get current state."""
        return self._current_state

    @property
    def previous(self) -> Optional[Control4ZoneState]:
        """Get previous state."""
        return self._previous_state

    def store_state(self) -> None:
        """Store current state as previous state."""
        self._previous_state = self._current_state.copy()

    def restore_state(self) -> None:
        """Restore previous state to current."""
        if self._previous_state is not None:
            self._current_state = self._previous_state.copy()

    def set_power(self, is_on: bool) -> None:
        """Update power state."""
        if is_on and not self._current_state.is_on:
            self.store_state()
            self._current_state.power_state = MediaPlayerState.ON
        elif not is_on and self._current_state.is_on:
            self.store_state()
            self._current_state.power_state = MediaPlayerState.OFF

    def set_mute(self, is_muted: bool) -> None:
        """Update mute state."""
        if is_muted and not self._current_state.is_muted:
            self._current_state.store_mute_state()
            self._current_state.is_muted = True
        elif not is_muted and self._current_state.is_muted:
            self._current_state.is_muted = False
            self._current_state.restore_mute_state()

    def set_volume(self, volume: float) -> None:
        """Update volume level."""
        self._current_state.volume = volume
        if self._current_state.is_muted:
            self._current_state.is_muted = False

    def set_input_source(self, input_source: Optional[int]) -> None:
        """Update input source."""
        self._current_state.input_source = input_source

    def to_dict(self) -> dict:
        """Convert current state to dictionary."""
        return self._current_state.to_dict()

    def restore_from_dict(self, data: dict) -> None:
        """Restore state from dictionary."""
        self._current_state = Control4ZoneState.from_dict(data)