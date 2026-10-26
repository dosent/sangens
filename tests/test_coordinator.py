"""Команды и опрос с настоящим координатором HA, без реальной печи."""
import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock
import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.sangens.models import DeviceSnapshot, DeviceMode
from custom_components.sangens.api import SangensCommandUncertain, SangensAuthError
from custom_components.sangens.coordinator import SangensCoordinator

@pytest.fixture
async def coordinator(hass, device_data):
    entry = MockConfigEntry(domain='sangens', data={"binding_ids": ["binding-17"], "microchip_ids": {"binding-17": "chip-42"}, "access_token": "synthetic-token"}, options={"allow_control": True})
    entry.add_to_hass(hass)
    snapshot = DeviceSnapshot.parse(device_data)
    client = AsyncMock()
    client.get_device.return_value = snapshot
    client.list_modes.return_value = (snapshot.mode,)
    state = SangensCoordinator(hass, entry, client)
    await state.async_refresh()
    yield state, client, entry
    await state.async_shutdown()

async def test_опрос_не_отправляет_команду(coordinator):
    state, client, _ = coordinator
    assert state.data['binding-17'].air_temperature == 28.7
    assert state.update_interval.total_seconds() == 30
    assert client.set_power.await_count == 0
    assert client.set_temperature.await_count == 0

async def test_команда_идёт_контроллеру_а_не_привязке(coordinator):
    state, client, _ = coordinator
    await state.async_power('binding-17', False)
    client.set_power.assert_awaited_once_with('chip-42', False)

async def test_режим_только_чтение_общий(coordinator, hass):
    state, client, entry = coordinator
    hass.config_entries.async_update_entry(entry, options={"allow_control": False})
    with pytest.raises(HomeAssistantError):
        await state.async_power('binding-17', True)
    assert client.set_power.await_count == 0

@pytest.mark.parametrize('value', [39, 101, float('nan'), True])
async def test_температура_проверяется_на_сервере(coordinator, value):
    state, client, _ = coordinator
    with pytest.raises(HomeAssistantError):
        await state.async_temperature('binding-17', 'air', value)
    assert client.set_temperature.await_count == 0

async def test_нет_неявного_запуска_при_уставке(coordinator):
    state, client, _ = coordinator
    client.get_device.return_value = replace(client.get_device.return_value, power=False)
    await state.async_refresh()
    with pytest.raises(HomeAssistantError):
        await state.async_temperature('binding-17', 'air', 80)
    assert client.set_temperature.await_count == 0
    assert client.set_power.await_count == 0

async def test_таймаут_не_повторяет_команду(coordinator):
    state, client, _ = coordinator
    client.set_power.side_effect = SangensCommandUncertain('Неизвестно')
    with pytest.raises(HomeAssistantError):
        await state.async_power('binding-17', True)
    assert client.set_power.await_count == 1
    assert client.get_device.await_count >= 2

async def test_другая_печь_в_ответе_не_получает_команды(coordinator):
    state, client, _ = coordinator
    client.get_device.return_value = replace(client.get_device.return_value, microchip_id='another')
    await state.async_refresh()
    assert state.last_update_success is False
    with pytest.raises(HomeAssistantError):
        await state.async_power('binding-17', True)
    assert client.set_power.await_count == 0

async def test_повторный_вход_и_увеличение_интервала(coordinator):
    state, client, _ = coordinator
    client.get_device.side_effect = SangensAuthError('Нужен вход')
    with pytest.raises(ConfigEntryAuthFailed):
        await state._async_update_data()

async def test_причина_отказа_входа_и_восстановление(coordinator):
    state, client, _ = coordinator
    client.get_device.side_effect = SangensAuthError('Нужен вход')
    with pytest.raises(ConfigEntryAuthFailed):
        await state._async_update_data()
    assert state.auth_required is True
    client.get_device.side_effect = None
    await state._async_update_data()
    assert state.auth_required is False

async def test_две_печи_получают_свои_команды(coordinator, hass):
    state, client, entry = coordinator
    first = client.get_device.return_value
    second = replace(first, binding_id='binding-99', microchip_id='chip-88', title='Вторая сауна')
    hass.config_entries.async_update_entry(entry,data={**entry.data,'binding_ids':['binding-17','binding-99'],'microchip_ids':{'binding-17':'chip-42','binding-99':'chip-88'}})
    async def get_device(binding):
        return first if binding=='binding-17' else second
    client.get_device.side_effect = get_device
    await state.async_refresh()
    await state.async_power('binding-17',False)
    await state.async_power('binding-99',False)
    assert client.set_power.await_args_list[0].args == ('chip-42',False)
    assert client.set_power.await_args_list[1].args == ('chip-88',False)
    assert set(state.data) == {'binding-17','binding-99'}

async def test_частые_ошибки_замедляют_опрос_и_успех_сбрасывает_паузу(coordinator):
    from custom_components.sangens.api import SangensConnectionError
    from homeassistant.helpers.update_coordinator import UpdateFailed
    state, client, _ = coordinator
    client.get_device.side_effect = SangensConnectionError('Нет связи')
    for expected in (60,120,240,300,300):
        with pytest.raises(UpdateFailed):
            await state._async_update_data()
        assert state.update_interval.total_seconds() == expected
    client.get_device.side_effect = None
    await state._async_update_data()
    assert state.update_interval.total_seconds() == 30

async def test_устаревшие_данные_не_позволяют_запуск(coordinator):
    state, client, _ = coordinator
    state._last_success -= 61
    with pytest.raises(HomeAssistantError):
        await state.async_power('binding-17',True)
    assert client.set_power.await_count == 0

async def test_вторая_команда_не_ставится_в_очередь(coordinator):
    state, client, _ = coordinator
    started, finish = asyncio.Event(), asyncio.Event()
    async def pending(*args):
        started.set()
        await finish.wait()
    client.set_power.side_effect = pending
    first = asyncio.create_task(state.async_power('binding-17',False))
    await started.wait()
    try:
        with pytest.raises(HomeAssistantError):
            await state.async_power('binding-17',True)
    finally:
        finish.set()
        await first
    assert client.set_power.await_count == 1
