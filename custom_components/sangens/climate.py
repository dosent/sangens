"""Температура воздуха и явное питание печи."""
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from .entity import SangensEntity

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(SangensClimate(coordinator, binding) for binding in coordinator.data)

class SangensClimate(SangensEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

    def __init__(self, coordinator, binding):
        super().__init__(coordinator, binding, 'air', 'Воздух')

    @property
    def current_temperature(self):
        return self.snapshot.air_temperature

    @property
    def target_temperature(self):
        return self.snapshot.air_target

    @property
    def min_temp(self):
        return self.snapshot.air_limits[0] if self.snapshot.air_limits else 0

    @property
    def max_temp(self):
        return self.snapshot.air_limits[1] if self.snapshot.air_limits else 0

    @property
    def hvac_mode(self):
        return HVACMode.HEAT if self.snapshot.power is True else HVACMode.OFF if self.snapshot.power is False else None

    @property
    def hvac_action(self):
        state = self.snapshot
        if state.power is False:
            return HVACAction.OFF
        if state.power is not True or state.heating is None:
            return None
        return HVACAction.HEATING if state.heating else HVACAction.IDLE

    @property
    def extra_state_attributes(self):
        return {'control_allowed': self.coordinator.entry.options.get('allow_control', False),
                'limits_known': self.snapshot.air_limits is not None,
                'stone_temperature': self.snapshot.stone_temperature,
                'stone_target_temperature': self.snapshot.stone_target}

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()
        else:
            raise ValueError('Этот режим не поддерживается')

    async def async_turn_on(self):
        await self.coordinator.async_power(self.binding, True)

    async def async_turn_off(self):
        await self.coordinator.async_power(self.binding, False)

    async def async_set_temperature(self, **kwargs):
        await self.coordinator.async_temperature(self.binding, 'air', kwargs[ATTR_TEMPERATURE])
