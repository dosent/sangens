"""Уставка камней с ограничениями текущего режима."""
from homeassistant.components.number import NumberEntity, NumberMode, NumberDeviceClass
from homeassistant.const import UnitOfTemperature
from .entity import SangensEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    added = set()
    def discover():
        entities = []
        for binding, state in (coordinator.data or {}).items():
            if state.stone_limits is not None and binding not in added:
                added.add(binding)
                entities.append(SangensStoneTarget(coordinator, binding))
        if entities:
            async_add_entities(entities)
    entry.async_on_unload(coordinator.async_add_listener(discover))
    discover()

class SangensStoneTarget(SangensEntity, NumberEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, binding):
        super().__init__(coordinator, binding, 'stone_target', 'Заданная температура камней')

    @property
    def available(self):
        return super().available and self.snapshot.stone_limits is not None

    @property
    def native_value(self):
        return self.snapshot.stone_target

    @property
    def native_min_value(self):
        return self.snapshot.stone_limits[0] if self.snapshot.stone_limits else 0

    @property
    def native_max_value(self):
        return self.snapshot.stone_limits[1] if self.snapshot.stone_limits else 0

    async def async_set_native_value(self, value):
        await self.coordinator.async_temperature(self.binding, 'stone', value)
