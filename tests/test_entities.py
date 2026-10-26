"""Сущности проверяются через реальную загрузку интеграции HA."""
from unittest.mock import patch
import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.sangens.api import SangensClient

@pytest.fixture
async def loaded(hass, device_data):
    calls = []
    async def response(self, method, path, payload=None):
        calls.append((method, path, payload))
        if path == '/modes':
            return [device_data['mode'], {"id": 1, "title": "Русская баня", "data": {"minAirTemp": 40, "maxAirTemp": 90}}]
        return device_data
    entry = MockConfigEntry(domain='sangens', unique_id='shared', data={'access_token': 'synthetic-token', 'binding_ids': ['binding-17'], 'microchip_ids': {'binding-17': 'chip-42'}}, options={'allow_control': True})
    entry.add_to_hass(hass)
    with patch.object(SangensClient, '_request', response):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield entry, calls
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

def entity_id(hass, domain, suffix):
    return er.async_get(hass).async_get_entity_id(domain, 'sangens', f'chip-42_{suffix}')

async def test_показания_и_режимы_без_команд_при_загрузке(hass, loaded):
    entry, calls = loaded
    state = hass.states.get(entity_id(hass, 'climate', 'air'))
    assert state.state == 'heat'
    assert state.attributes['current_temperature'] == 28.7
    assert state.attributes['temperature'] == 81
    assert state.attributes['hvac_action'] == 'heating'
    assert state.attributes['min_temp'] == 40
    assert state.attributes['max_temp'] == 100
    assert hass.states.get(entity_id(hass, 'sensor', 'stone')).state == '78.0'
    assert entity_id(hass, 'sensor', 'second_stone') is None
    assert hass.states.get(entity_id(hass, 'select', 'mode')).attributes['options'] == ['Финская сауна', 'Русская баня']
    assert all(call[0] == 'GET' for call in calls)

async def test_выключение_через_службу_ha(hass, loaded):
    entry, calls = loaded
    await hass.services.async_call('climate', 'turn_off', {'entity_id': entity_id(hass, 'climate', 'air')}, blocking=True)
    assert ('POST', '/microchips/chip-42/set-remote-control-status', {'remoteControlStatus': 'off'}) in calls

async def test_сервер_отклоняет_температуру_даже_без_карточки(hass, loaded):
    entry, calls = loaded
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call('climate', 'set_temperature', {'entity_id': entity_id(hass, 'climate', 'air'), 'temperature': 110}, blocking=True)
    assert all(call[0] == 'GET' for call in calls)

async def test_повторная_загрузка_сохраняет_настройку(hass, loaded):
    entry, calls = loaded
    before = entity_id(hass, 'climate', 'air')
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entity_id(hass, 'climate', 'air') == before
    assert len(hass.config_entries.async_entries('sangens')) == 1
    assert all(call[0] == 'GET' for call in calls)

async def test_поздние_данные_добавляют_сущности_без_перезапуска(hass, device_data):
    bounds = device_data['mode']['data'].copy()
    device_data['mode']['data'].pop('minHeaterTemp')
    device_data['mode']['data'].pop('maxHeaterTemp')
    async def response(self, method, path, payload=None):
        return [device_data['mode']] if path == '/modes' else device_data
    entry = MockConfigEntry(domain='sangens', data={'access_token':'synthetic-token','binding_ids':['binding-17'],'microchip_ids':{'binding-17':'chip-42'}})
    entry.add_to_hass(hass)
    with patch.object(SangensClient, '_request', response):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entity_id(hass,'number','stone_target') is None
        assert entity_id(hass,'sensor','second_stone') is None
        device_data['mode']['data'].update(bounds)
        device_data['microchip']['data']['secondStoneTemperature'] = 79
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert entity_id(hass,'number','stone_target') is not None
        assert hass.states.get(entity_id(hass,'sensor','second_stone')).state == '79.0'
        await hass.config_entries.async_unload(entry.entry_id)
