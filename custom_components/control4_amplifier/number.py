"""Number entities for Control4 Amplifier."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    NUM_OUTPUTS,
    NUM_ANALOG_INPUTS,
    NUM_DIGITAL_INPUTS, CONF_INPUTS, CONF_OUTPUTS,
)

_LOGGER = logging.getLogger(__name__)

# Value ranges
GAIN_MIN = -6
GAIN_MAX = 0
BALANCE_MIN = -10  # L10
BALANCE_MAX = 10   # R10
TONE_MIN = -12
TONE_MAX = 12

# Custom unit of measurement
UNIT_DECIBELS = "dB"
UNIT_BALANCE = None  # No unit for balance (L/R values shown in name)

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for Control4 Amplifier."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []

    # Get configuration from data instead of options
    input_configs = config_entry.data.get(CONF_INPUTS, {})
    output_configs = config_entry.data.get(CONF_OUTPUTS, {})

    _LOGGER.debug("Input configs: %s", input_configs)

    # Input gain controls - only for enabled inputs
    for input_num in range(1, NUM_ANALOG_INPUTS + 1):
        str_input_num = str(input_num)
        input_config = input_configs.get(str_input_num, {})
        _LOGGER.debug("Checking analog input %s: %s", str_input_num, input_config)

        if input_config and input_config.get("enabled", True):
            _LOGGER.debug("Creating analog input gain for input %s", input_num)
            entities.append(
                Control4InputGainNumber(
                    coordinator,
                    config_entry,
                    input_num,
                    is_digital=False,
                )
            )

    # Digital input gain controls - only for enabled inputs
    for input_num in [1, 3]:  # Only digital inputs 1 and 3
        digital_input_num = input_num + 4  # Digital inputs are 5 and 6
        str_digital_input_num = str(digital_input_num)
        input_config = input_configs.get(str_digital_input_num, {})
        _LOGGER.debug("Checking digital input %s: %s", str_digital_input_num, input_config)

        if input_config and input_config.get("enabled", True):
            _LOGGER.debug("Creating digital input gain for input %s", input_num)
            entities.append(
                Control4InputGainNumber(
                    coordinator,
                    config_entry,
                    input_num,
                    is_digital=True,
                )
            )

    # Output controls for configured outputs
    for output_num in range(1, NUM_OUTPUTS + 1):
        str_output_num = str(output_num)
        output_config = output_configs.get(str_output_num)
        _LOGGER.debug("Checking output %s: %s", str_output_num, output_config)

        if output_config:  # Only create entities if output is configured
            _LOGGER.debug("Creating controls for output %s", output_num)
            entities.extend([
                Control4BalanceNumber(coordinator, config_entry, output_num),
                Control4BassNumber(coordinator, config_entry, output_num),
                Control4TrebleNumber(coordinator, config_entry, output_num),
            ])

    _LOGGER.debug("Created %d entities", len(entities))
    async_add_entities(entities)

class Control4BaseNumber(NumberEntity):
    """Base class for Control4 number entities."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.AUTO
    _attr_should_poll = False

    def __init__(
            self,
            coordinator,
            config_entry: ConfigEntry,
            entity_type: str,
    ) -> None:
        """Initialize base number entity."""
        self.coordinator = coordinator
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_{entity_type}"
        self._attr_native_value = 0
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title,
            manufacturer="Control4",
            model="C4-8AMP1-B",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._config_entry.add_update_listener(self.async_config_entry_updated)
        )

    @callback
    async def async_config_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle config entry updates."""
        self._handle_config_update()
        self.async_write_ha_state()

    def _handle_config_update(self) -> None:
        """Handle configuration updates."""
        pass  # Override in child classes if needed

class Control4InputGainNumber(Control4BaseNumber):
    """Input gain control for Control4 Amplifier."""

    _attr_native_min_value = GAIN_MIN
    _attr_native_max_value = GAIN_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UNIT_DECIBELS

    def __init__(
            self,
            coordinator,
            config_entry: ConfigEntry,
            input_num: int,
            is_digital: bool,
    ) -> None:
        """Initialize input gain control."""
        self._input_num = input_num
        self._is_digital = is_digital
        self._input_id = input_num + 4 if is_digital else input_num

        input_type = "digital" if is_digital else "analog"
        entity_type = f"{input_type}_input_{input_num}_gain"

        super().__init__(coordinator, config_entry, entity_type)
        self._update_name_from_config()

    def _update_name_from_config(self) -> None:
        """Update name from config."""
        input_configs = self._config_entry.options.get("inputs", {})
        input_config = input_configs.get(str(self._input_id), {})
        base_name = input_config.get("name",
                                     f"{'Digital' if self._is_digital else 'Analog'} Input {self._input_num}")
        self._attr_name = f"{base_name} Gain"

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.coordinator.async_set_input_gain(
            self._input_num,
            int(value),
            is_digital=self._is_digital
        )
        self._attr_native_value = value
        self.async_write_ha_state()

    def _handle_config_update(self) -> None:
        """Handle configuration updates."""
        self._update_name_from_config()

class Control4BalanceNumber(Control4BaseNumber):
    """Balance control for Control4 Amplifier."""

    _attr_native_min_value = BALANCE_MIN
    _attr_native_max_value = BALANCE_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UNIT_BALANCE

    def __init__(
            self,
            coordinator,
            config_entry: ConfigEntry,
            output_num: int,
    ) -> None:
        """Initialize balance control."""
        super().__init__(coordinator, config_entry, f"output_{output_num}_balance")
        self._output_num = output_num
        self._update_name_from_config()

    def _update_name_from_config(self) -> None:
        """Update name from config."""
        output_configs = self._config_entry.options.get("outputs", {})
        output_config = output_configs.get(str(self._output_num), {})
        output_name = output_config.get("name", f"Output {self._output_num}")
        self._attr_name = f"{output_name} Balance"

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.coordinator.async_set_balance(self._output_num, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()

    def _handle_config_update(self) -> None:
        """Handle configuration updates."""
        self._update_name_from_config()

class Control4BassNumber(Control4BaseNumber):
    """Bass control for Control4 Amplifier."""

    _attr_native_min_value = TONE_MIN
    _attr_native_max_value = TONE_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UNIT_DECIBELS

    def __init__(
            self,
            coordinator,
            config_entry: ConfigEntry,
            output_num: int,
    ) -> None:
        """Initialize bass control."""
        super().__init__(coordinator, config_entry, f"output_{output_num}_bass")
        self._output_num = output_num
        self._update_name_from_config()

    def _update_name_from_config(self) -> None:
        """Update name from config."""
        output_configs = self._config_entry.options.get("outputs", {})
        output_config = output_configs.get(str(self._output_num), {})
        output_name = output_config.get("name", f"Output {self._output_num}")
        self._attr_name = f"{output_name} Bass"

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.coordinator.async_set_bass(self._output_num, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()

    def _handle_config_update(self) -> None:
        """Handle configuration updates."""
        self._update_name_from_config()

class Control4TrebleNumber(Control4BaseNumber):
    """Treble control for Control4 Amplifier."""

    _attr_native_min_value = TONE_MIN
    _attr_native_max_value = TONE_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UNIT_DECIBELS

    def __init__(
            self,
            coordinator,
            config_entry: ConfigEntry,
            output_num: int,
    ) -> None:
        """Initialize treble control."""
        super().__init__(coordinator, config_entry, f"output_{output_num}_treble")
        self._output_num = output_num
        self._update_name_from_config()

    def _update_name_from_config(self) -> None:
        """Update name from config."""
        output_configs = self._config_entry.options.get("outputs", {})
        output_config = output_configs.get(str(self._output_num), {})
        output_name = output_config.get("name", f"Output {self._output_num}")
        self._attr_name = f"{output_name} Treble"

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.coordinator.async_set_treble(self._output_num, int(value))
        self._attr_native_value = value
        self.async_write_ha_state()

    def _handle_config_update(self) -> None:
        """Handle configuration updates."""
        self._update_name_from_config()