"""Config flow for Control4 Amplifier."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    ATTR_MAC_ADDRESS,
    CONF_IP_ADDRESS,
    DEFAULT_NAME,
    DOMAIN,
    NUM_ANALOG_INPUTS,
    NUM_DIGITAL_INPUTS,
    NUM_OUTPUTS,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_INPUT_NAMES = {
    "analog": "Analog Input {number}",
    "digital": "Digital Input {number}"
}

DEFAULT_OUTPUT_NAME = "Stereo Output {number}"


class Control4AmplifierConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control4 Amplifier."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_ip: str | None = None
        self._discovered_mac: str | None = None

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_IP_ADDRESS): str,
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle a flow initialized by SSDP discovery."""
        _LOGGER.debug("SSDP discovery_info: %s", discovery_info)

        if not discovery_info.ssdp_st.startswith("c4:v1_8chanamp"):
            return self.async_abort(reason="not_control4_amplifier")

        if discovery_info.ssdp_usn:
            mac = discovery_info.ssdp_usn.split(":")[-1].replace("-", ":")
        else:
            return self.async_abort(reason="no_mac_address")

        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured(
            updates={
                CONF_IP_ADDRESS: discovery_info.ssdp_location.split(":")[0]
            }
        )

        self._discovered_ip = discovery_info.ssdp_location.split(":")[0]
        self._discovered_mac = mac

        return await self.async_step_confirm_discovery()

    async def async_step_confirm_discovery(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-confirmation of discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_IP_ADDRESS: self._discovered_ip,
                    ATTR_MAC_ADDRESS: self._discovered_mac,
                },
            )

        placeholders = {
            "host": self._discovered_ip,
        }

        return self.async_show_form(
            step_id="confirm_discovery",
            description_placeholders=placeholders,
        )

    @staticmethod
    def async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
    ) -> Control4AmplifierOptionsFlow:
        """Get the options flow for this handler."""
        return Control4AmplifierOptionsFlow(config_entry)


class Control4AmplifierOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._input_config = None

    async def async_step_init(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_input_config()

    async def async_step_input_config(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure all inputs at once."""
        if user_input is not None:
            self._input_config = user_input
            return await self.async_step_output_config()

        options = self.config_entry.options
        schema = {}

        # Add fields for each analog input
        for i in range(1, NUM_ANALOG_INPUTS + 1):
            input_name = DEFAULT_INPUT_NAMES["analog"].format(number=i)
            schema.update({
                vol.Optional(
                    f"input_{i}_enabled",
                    default=options.get(f"input_{i}_enabled", True)
                ): selector.BooleanSelector(
                    selector.BooleanSelectorConfig(
                    )
                ),
                vol.Optional(
                    f"input_{i}_name",
                    default=options.get(f"input_{i}_name", input_name)
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT
                    )
                ),
                vol.Optional(
                    f"input_{i}_gain",
                    default=options.get(f"input_{i}_gain", 0)
                ): vol.All(vol.Coerce(int), vol.Range(min=-12, max=12)),
            })

        # Add fields for each digital input
        for i in range(1, NUM_DIGITAL_INPUTS + 1):
            input_num = i + NUM_ANALOG_INPUTS
            input_name = DEFAULT_INPUT_NAMES["digital"].format(number=i)
            schema.update({
                vol.Optional(
                    f"input_{input_num}_enabled",
                    default=options.get(f"input_{input_num}_enabled", True)
                ): selector.BooleanSelector(
                    selector.BooleanSelectorConfig(
                    )
                ),
                vol.Optional(
                    f"input_{input_num}_name",
                    default=options.get(f"input_{input_num}_name", input_name)
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT
                    )
                ),
                vol.Optional(
                    f"input_{input_num}_gain",
                    default=options.get(f"input_{input_num}_gain", 0)
                ): vol.All(vol.Coerce(int), vol.Range(min=-12, max=12)),
            })

        return self.async_show_form(
            step_id="input_config",
            data_schema=vol.Schema(schema),
        )

    async def async_step_output_config(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure outputs."""
        if user_input is not None:
            combined_config = {**self._input_config, **user_input}
            return self.async_create_entry(title="", data=combined_config)

        options = self.config_entry.options
        schema = {}

        for i in range(1, NUM_OUTPUTS + 1):
            output_name = DEFAULT_OUTPUT_NAME.format(number=i)
            schema.update({
                vol.Optional(
                    f"output_{i}_name",
                    default=options.get(f"output_{i}_name", output_name)
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT
                    )
                ),
                vol.Optional(
                    f"output_{i}_bass",
                    default=options.get(f"output_{i}_bass", 0)
                ): vol.All(vol.Coerce(int), vol.Range(min=-12, max=12)),
                vol.Optional(
                    f"output_{i}_treble",
                    default=options.get(f"output_{i}_treble", 0)
                ): vol.All(vol.Coerce(int), vol.Range(min=-12, max=12)),
            })

        return self.async_show_form(
            step_id="output_config",
            data_schema=vol.Schema(schema),
        )