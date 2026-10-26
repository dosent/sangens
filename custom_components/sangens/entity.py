"""Общие свойства сущностей одного контроллера."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

class SangensEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, binding, suffix, name):
        super().__init__(coordinator)
        self.binding = binding
        state = coordinator.data[binding]
        self._attr_unique_id = f'{state.microchip_id}_{suffix}'
        self._attr_name = name
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, state.microchip_id)}, name=state.title, manufacturer='Sangens')

    @property
    def snapshot(self):
        return self.coordinator.data[self.binding]

    @property
    def available(self):
        return super().available and self.binding in (self.coordinator.data or {})

    @property
    def extra_state_attributes(self):
        # Статус контроллера не определяет доступность ответа облака.
        return {'controller_online': self.snapshot.online}
