"""Coordinator for Control4 Amplifier."""
from __future__ import annotations

import asyncio
import logging
import random
from enum import Enum
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_PORT,
    DOMAIN,
    NUM_ANALOG_INPUTS,
    NUM_DIGITAL_INPUTS,
    NUM_OUTPUTS,
    CMD_DIGITAL,
    CMD_VOLUME,
    CMD_BALANCE,
    CMD_INPUT_GAIN,
    CMD_BASS,
    CMD_TREBLE,
    CMD_OUTPUT,
    BALANCE_MAX,
    BALANCE_MIN,
    GAIN_MAX,
    GAIN_MIN,
    NO_INPUT_SOURCE,
)

_LOGGER = logging.getLogger(__name__)

class InputSource(Enum):
    """Input source types."""
    ANALOG = "analog"
    DIGITAL = "digital"

class Control4AmpUDPProtocol(asyncio.DatagramProtocol):
    """UDP Protocol for Control4 Amplifier."""

    def __init__(self) -> None:
        """Initialize the protocol."""
        self.transport = None
        self._callbacks = []
        self._latest_response = None

    def connection_made(self, transport):
        """Handle connection made."""
        self.transport = transport

    def datagram_received(self, data, addr):
        """Handle received datagram."""
        message = data.decode()
        self._latest_response = message
        _LOGGER.debug("Received UDP message: %s", message)

        for callback in self._callbacks:
            callback(message)

    def add_callback(self, callback):
        """Add callback for data reception."""
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        """Remove callback for data reception."""
        self._callbacks.remove(callback)

class Control4AmpCoordinator(DataUpdateCoordinator):
    """Control4 Amplifier Coordinator."""

    def __init__(self, hass: HomeAssistant, host: str, port: int = DEFAULT_PORT) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # We'll update on UDP messages
        )
        self.host = host
        self.port = port
        self.protocol = None
        self._transport = None
        self._lock = asyncio.Lock()

        # Input mapping updated to reflect correct digital inputs (1 and 3)
        self._input_map = {
            1: (InputSource.ANALOG, 1),  # Analog 1 (shares with Digital 1)
            2: (InputSource.ANALOG, 2),  # Analog 2
            3: (InputSource.ANALOG, 3),  # Analog 3 (shares with Digital 3)
            4: (InputSource.ANALOG, 4),  # Analog 4
            5: (InputSource.DIGITAL, 1),  # Digital 1 (shares physical with Analog 1)
            6: (InputSource.DIGITAL, 3),  # Digital 3 (shares physical with Analog 3)
        }

    async def _async_create_udp_connection(self):
        """Create UDP connection."""
        loop = asyncio.get_event_loop()
        self.protocol = Control4AmpUDPProtocol()

        transport, _ = await loop.create_datagram_endpoint(
            lambda: self.protocol,
            local_addr=('0.0.0.0', 0),  # Let OS assign port
        )
        self._transport = transport
        return transport

    def _generate_counter(self) -> str:
        """Generate command counter."""
        return f"0s2a{random.randint(10, 99)}"

    async def async_send_command(self, command: str, expect_response: bool = True) -> str | None:
        """Send command to amplifier."""
        async with self._lock:
            if self._transport is None:
                await self._async_create_udp_connection()

            counter = self._generate_counter()
            full_command = f"{counter} {command} \r\n"

            _LOGGER.debug("Sending command: %s", full_command)
            self._transport.sendto(
                full_command.encode(), (self.host, self.port)
            )

            if expect_response:
                try:
                    await asyncio.wait_for(
                        asyncio.sleep(0.1),  # Adjust timeout as needed
                        timeout=1.0
                    )
                    return self.protocol._latest_response
                except asyncio.TimeoutError:
                    _LOGGER.warning("Timeout waiting for response to command: %s", command)
                    return None

    async def async_select_input(self, channel, input_number: int) -> None:
        """Select input by number."""
        if input_number == NO_INPUT_SOURCE:
            # Special case for "no input" (power off)
            await self.async_send_command(f"{CMD_OUTPUT} {channel:02d} 00")
            return

        if input_number not in self._input_map:
            _LOGGER.error("Invalid input number: %s", input_number)
            return

        source_type, physical_number = self._input_map[input_number]
        is_digital = 1 if source_type == InputSource.DIGITAL else 0

        await self.async_send_command(f"{CMD_OUTPUT} {channel:02d} {physical_number:02d}")
        await self.async_send_command(f"{CMD_DIGITAL} {physical_number:02d} {is_digital:02d}")

    async def async_set_volume(self, output: int, volume: float) -> None:
        """Set volume for an output."""
        if not 1 <= output <= NUM_OUTPUTS:
            _LOGGER.error("Invalid output number: %s", output)
            return

        # Convert 0-1 to amplifier volume range (0-100 + 160 offset, hex)
        volume_value = int(float(volume) * 100) + 160
        volume_hex = hex(volume_value)[2:]
        await self.async_send_command(f"{CMD_VOLUME} {output:02d} {volume_hex}")

    async def async_set_balance(self, output: int, balance: int) -> None:
        """Set balance for an output (-10 to 10)."""
        if not 1 <= output <= NUM_OUTPUTS:
            _LOGGER.error("Invalid output number: %s", output)
            return

        if not BALANCE_MIN <= balance <= BALANCE_MAX:
            _LOGGER.error("Invalid balance value: %s", balance)
            return

        await self.async_send_command(f"{CMD_BALANCE} {output:02d} {balance:02d}")

    async def async_set_input_gain(self, input_num: int, gain: int, is_digital: bool = False) -> None:
        """Set input gain."""
        if is_digital and input_num not in [1, 3]:
            _LOGGER.error("Invalid digital input number: %s", input_num)
            return

        if not GAIN_MIN <= gain <= GAIN_MAX:
            _LOGGER.error("Invalid gain value: %s", gain)
            return

        # Adjust command based on whether it's digital or analog input
        cmd_suffix = f"d{input_num}" if is_digital else str(input_num)
        await self.async_send_command(f"{CMD_INPUT_GAIN} {cmd_suffix} {gain:02d}")

    async def async_set_bass(self, output: int, level: int) -> None:
        """Set bass level for an output (-12 to +12)."""
        if not 1 <= output <= NUM_OUTPUTS:
            _LOGGER.error("Invalid output number: %s", output)
            return

        if not -12 <= level <= 12:
            _LOGGER.error("Invalid bass level: %s", level)
            return

        await self.async_send_command(f"{CMD_BASS} {output:02d} {level:02d}")

    async def async_set_treble(self, output: int, level: int) -> None:
        """Set treble level for an output (-12 to +12)."""
        if not 1 <= output <= NUM_OUTPUTS:
            _LOGGER.error("Invalid output number: %s", output)
            return

        if not -12 <= level <= 12:
            _LOGGER.error("Invalid treble level: %s", level)
            return

        await self.async_send_command(f"{CMD_TREBLE} {output:02d} {level:02d}")

    async def async_start(self):
        """Start coordinator."""
        await self._async_create_udp_connection()

    async def async_stop(self):
        """Stop coordinator."""
        if self._transport:
            self._transport.close()
            self._transport = None