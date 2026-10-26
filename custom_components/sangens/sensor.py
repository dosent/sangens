"""Измеренные температуры камней."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from .entity import SangensEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = []
    for binding, state in coordinator.data.items():
        entities.append(SangensTemperature(coordinator, binding, 'stone', 'Камни', 'stone_temperature'))
        if state.second_stone_temperature is not None:
            entities.append(SangensTemperature(coordinator, binding, 'second_stone', 'Камни — второй датчик', 'second_stone_temperature'))
    async_add_entities(entities)

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
