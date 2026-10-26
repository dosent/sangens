"""Общее подключение печей Sangens к Home Assistant."""
from pathlib import Path
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import SangensClient
from .const import PLATFORMS
from .coordinator import SangensCoordinator

async def async_setup(hass, config):
    await hass.http.async_register_static_paths([
        StaticPathConfig('/sangens/sangens-card.js', str(Path(__file__).parent / 'frontend' / 'sangens-card.js'), cache_headers=False)
    ])
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = SangensClient(async_get_clientsession(hass), entry.data['access_token'])
    coordinator = SangensCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True

async def _async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        return True
    return False
