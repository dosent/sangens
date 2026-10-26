"""Общее состояние и серверные ограничения управления."""
import asyncio
from dataclasses import replace
from datetime import timedelta
import logging
import time
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import SangensAuthError, SangensRateLimited, SangensCommandUncertain, SangensConnectionError, SangensBusyError
from .const import DOMAIN, POLL_SECONDS
from .models import SangensProtocolError, number

_LOGGER = logging.getLogger(__name__)

class SangensCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=POLL_SECONDS))
        self.entry = entry
        self.client = client
        self._lock = asyncio.Lock()
        self._last_success = 0.0
        self._failures = 0
        self.auth_required = False
        self._blocked_until = 0.0

    async def _async_update_data(self):
        if time.monotonic()<self._blocked_until:
            raise UpdateFailed('Sangens попросил подождать перед следующим запросом')
        try:
            async with self._lock:
                devices = {}
                # Режимы получаются из того же аккаунта, команды опроса не отправляются.
                modes = await self.client.list_modes()
                for binding in self.entry.data['binding_ids']:
                    state = await self.client.get_device(binding)
                    if state.microchip_id != self.entry.data['microchip_ids'][binding]:
                        raise SangensProtocolError("Изменилась привязка контроллера")
                    devices[binding] = replace(state, modes=modes)
            self.auth_required = False
            self._last_success = time.monotonic()
            self._failures = 0
            self.update_interval = timedelta(seconds=POLL_SECONDS)
            return devices
        except SangensAuthError as err:
            self.auth_required = True
            raise ConfigEntryAuthFailed("Требуется повторный вход в Sangens") from err
        except (SangensConnectionError, SangensProtocolError, SangensBusyError) as err:
            self._failures += 1
            delay=min(300,POLL_SECONDS*2**min(self._failures,4))
            if isinstance(err,SangensRateLimited):
                delay=max(delay,err.retry_after)
                self._blocked_until=time.monotonic()+delay
            self.update_interval=timedelta(seconds=delay)
            raise UpdateFailed("Нет достоверных данных Sangens") from err

    def _state_for_command(self, binding):
        if time.monotonic()<self._blocked_until:
            raise HomeAssistantError('Sangens попросил подождать перед следующим запросом')
        if not self.entry.options.get('allow_control', False):
            raise HomeAssistantError("Включён режим только чтения. Управление разрешается администратором в настройках интеграции")
        if not self.last_update_success or time.monotonic() - self._last_success > 60:
            raise HomeAssistantError("Данные устарели. Обновите состояние печи")
        state = (self.data or {}).get(binding)
        if not state or not state.online:
            raise HomeAssistantError("Нет связи с печью")
        if self._lock.locked():
            raise HomeAssistantError("Предыдущий запрос ещё выполняется")
        return state

    async def async_command(self, command, *, starts_heating: bool):
        """Выполнить один запрос без очереди и повторов; затем прочитать состояние."""
        if self._lock.locked():
            raise HomeAssistantError("Предыдущий запрос ещё выполняется")
        error = None
        async with self._lock:
            try:
                await command()
            except SangensAuthError as err:
                self.entry.async_start_reauth(self.hass)
                error = HomeAssistantError("Требуется повторный вход в Sangens")
            except (SangensConnectionError, SangensBusyError, SangensProtocolError) as err:
                if isinstance(err,SangensRateLimited):
                    self._blocked_until=time.monotonic()+err.retry_after
                    self.update_interval=timedelta(seconds=err.retry_after)
                error = HomeAssistantError(str(err))
        await self.async_refresh()
        if error:
            raise error
        if not self.last_update_success:
            raise HomeAssistantError("Команда отправлена, но состояние не подтверждено")

    async def async_power(self, binding, enabled):
        state = self._state_for_command(binding)
        if enabled and (state.power is None or state.air_temperature is None or state.air_limits is None):
            raise HomeAssistantError("Запуск недоступен: состояние или ограничения печи неизвестны")
        await self.async_command(lambda: self.client.set_power(state.microchip_id, enabled), starts_heating=enabled)

    async def async_temperature(self, binding, kind, value):
        state = self._state_for_command(binding)
        bounds = state.air_limits if kind == 'air' else state.stone_limits if kind == 'stone' else None
        if state.power is not True:
            raise HomeAssistantError("Изменение температуры при выключенной печи пока не подтверждено")
        if number(value) is None or bounds is None or not bounds[0] <= value <= bounds[1]:
            raise HomeAssistantError("Температура вне разрешённого диапазона")
        await self.async_command(lambda: self.client.set_temperature(state.microchip_id, kind, value), starts_heating=False)

    async def async_mode(self, binding, mode_id):
        state = self._state_for_command(binding)
        if state.power is not True:
            raise HomeAssistantError("Смена режима при выключенной печи пока не подтверждена")
        if mode_id not in {mode.id for mode in state.modes}:
            raise HomeAssistantError("Режим недоступен для этого аккаунта")
        await self.async_command(lambda: self.client.set_mode(state.binding_id, mode_id), starts_heating=False)
