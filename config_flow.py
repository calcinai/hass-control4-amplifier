"""Config flow for Control4 Amplifier integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_INPUTS,
    CONF_OUTPUTS,
    DEFAULT_PORT,
    DOMAIN,
    DEFAULT_INPUT_LABELS,
    DEFAULT_OUTPUT_LABELS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_NAME): str,
    }
)

def create_default_inputs_config():
    """Create default input configuration."""
    return {
        "1": {"name": "Analog Input 1", "enabled": True},
        "2": {"name": "Analog Input 2", "enabled": True},
        "3": {"name": "Analog Input 3", "enabled": True},
        "4": {"name": "Analog Input 4", "enabled": True},
        "5": {"name": "Digital Input 1", "enabled": True},
        "6": {"name": "Digital Input 3", "enabled": True},
    }

def create_default_outputs_config():
    """Create default output configuration."""
    return {
        str(i): {
            "name": DEFAULT_OUTPUT_LABELS[i]
        } for i in range(1, 5)
    }

class Control4AmpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Control4 Amplifier."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._name: str | None = None
        self._port: int = DEFAULT_PORT

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: config_entries.ConfigEntry,
    ) -> Control4AmpOptionsFlow:
        """Get the options flow for this handler."""
        return Control4AmpOptionsFlow(config_entry)

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input.get(CONF_NAME)
            self._port = user_input.get(CONF_PORT, DEFAULT_PORT)

            # Create entry with all configuration in data
            await self.async_set_unique_id(self._host)
            self._abort_if_unique_id_configured()

            title = self._name or self._host
            return self.async_create_entry(
                title=title,
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_NAME: self._name,
                    CONF_INPUTS: create_default_inputs_config(),
                    CONF_OUTPUTS: create_default_outputs_config(),
                }
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle SSDP discovery."""
        netloc = urlparse(discovery_info.ssdp_location).netloc
        self._host = netloc.split(":")[0]
        self._name = discovery_info.upnp.get("friendlyName", self._host)

        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_confirm()

    async def async_step_confirm(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user confirmation of discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name or self._host,
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_NAME: self._name,
                    CONF_INPUTS: create_default_inputs_config(),
                    CONF_OUTPUTS: create_default_outputs_config(),
                }
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._name,
                "host": self._host,
            },
        )

class Control4AmpOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Control4 Amplifier."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # Initialize from data instead of options
        self._input_configs = dict(config_entry.data.get(CONF_INPUTS, create_default_inputs_config()))
        self._output_configs = dict(config_entry.data.get(CONF_OUTPUTS, create_default_outputs_config()))

    async def async_step_init(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """First step in options flow."""
        return await self.async_step_inputs()

    async def async_step_inputs(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle input configuration."""
        if user_input is not None:
            # Update input configurations
            for i in range(1, 7):
                enabled_key = f"input_{i}_enabled"
                name_key = f"input_{i}_name"
                if enabled_key in user_input:
                    self._input_configs[str(i)] = {
                        "name": user_input.get(name_key, DEFAULT_INPUT_LABELS[i]),
                        "enabled": user_input[enabled_key]
                    }
            return await self.async_step_outputs()

        # Get current configuration from data
        current_inputs = self.config_entry.data.get(CONF_INPUTS, {})

        schema = {}
        for i in range(1, 7):
            input_config = current_inputs.get(str(i), {
                "name": DEFAULT_INPUT_LABELS[i],
                "enabled": True
            })
            schema[vol.Required(f"input_{i}_enabled",
                                default=input_config.get("enabled", True))] = bool
            schema[vol.Required(f"input_{i}_name",
                                default=input_config.get("name", DEFAULT_INPUT_LABELS[i]))] = str

        return self.async_show_form(
            step_id="inputs",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "device_name": self.config_entry.title
            },
        )

    async def async_step_outputs(
            self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle output configuration."""
        if user_input is not None:
            # Save output configurations
            for i in range(1, 5):
                name_key = f"output_{i}_name"
                if name_key in user_input:
                    self._output_configs[str(i)] = {
                        "name": user_input[name_key]
                    }

            # Update the config entry's data instead of options
            new_data = dict(self.config_entry.data)
            new_data[CONF_INPUTS] = self._input_configs
            new_data[CONF_OUTPUTS] = self._output_configs

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data
            )

            return self.async_create_entry(title="", data={})

        # Get current configuration from data
        current_outputs = self.config_entry.data.get(CONF_OUTPUTS, {})

        schema = {}
        for i in range(1, 5):
            output_config = current_outputs.get(str(i), {
                "name": DEFAULT_OUTPUT_LABELS[i]
            })
            schema[vol.Required(f"output_{i}_name",
                                default=output_config.get("name", DEFAULT_OUTPUT_LABELS[i]))] = str

        return self.async_show_form(
            step_id="outputs",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "device_name": self.config_entry.title
            },
        )