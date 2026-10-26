"""Измеренные температуры камней."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from .entity import SangensEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    added = set()
    def discover():
        entities = []
        for binding, state in (coordinator.data or {}).items():
            for suffix, name, field, present in (
                ('stone', 'Камни', 'stone_temperature', True),
                ('second_stone', 'Камни — второй датчик', 'second_stone_temperature', state.second_stone_temperature is not None),
            ):
                key = (binding, suffix)
                if present and key not in added:
                    added.add(key)
                    entities.append(SangensTemperature(coordinator, binding, suffix, name, field))
        if entities:
            async_add_entities(entities)
    entry.async_on_unload(coordinator.async_add_listener(discover))
    discover()

class SangensTemperature(SangensEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, binding, suffix, name, field):
        super().__init__(coordinator, binding, suffix, name)
        self.field = field

    @property
    def native_value(self):
        return getattr(self.snapshot, self.field)
