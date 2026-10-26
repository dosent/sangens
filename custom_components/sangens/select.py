"""Выбор существующего режима из аккаунта Sangens."""
from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import HomeAssistantError
from .entity import SangensEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(SangensMode(coordinator, binding) for binding in coordinator.data)

class SangensMode(SangensEntity, SelectEntity):
    _attr_icon = 'mdi:sauna'

    def __init__(self, coordinator, binding):
        super().__init__(coordinator, binding, 'mode', 'Режим')

    def _choices(self):
        modes = self.snapshot.modes
        titles = [mode.title for mode in modes]
        return {f'{mode.title} ({mode.id})' if titles.count(mode.title) > 1 else mode.title: mode.id for mode in modes}

    @property
    def options(self):
        return list(self._choices())

    @property
    def current_option(self):
        mode = self.snapshot.mode
        return next((title for title, mode_id in self._choices().items() if mode and mode_id == mode.id), None)

    async def async_select_option(self, option):
        mode_id = self._choices().get(option)
        if mode_id is None:
            raise HomeAssistantError('Этот режим недоступен')
        await self.coordinator.async_mode(self.binding, mode_id)
