"""The Control4 Amplifier integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import Control4AmpCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Control4 Amplifier component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Control4 Amplifier from a config entry."""
    coordinator = Control4AmpCoordinator(
        hass,
        entry.data[CONF_HOST],
    )

    try:
        await coordinator.async_start()
    except Exception as ex:
        _LOGGER.error("Error starting coordinator: %s", ex)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register update listener to handle config updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: Control4AmpCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok