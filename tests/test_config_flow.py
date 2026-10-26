"""Общее подключение и повторный вход через настоящий механизм HA."""
from unittest.mock import AsyncMock, patch
import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.sangens.api import SangensAuthError

async def test_одно_подключение_и_выбор_печи(hass, device_data):
    with patch('custom_components.sangens.api.SangensClient._request', AsyncMock(return_value={"items": [device_data]})), \
         patch('custom_components.sangens.async_setup_entry', AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_init('sangens', context={"source": config_entries.SOURCE_USER})
        assert result['type'] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {'next_step_id':'token'})
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {"access_token": "synthetic-token"})
        assert result['step_id'] == 'devices'
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {"binding_ids": ["binding-17"]})
        assert result['type'] is FlowResultType.CREATE_ENTRY
        assert result['data']['binding_ids'] == ["binding-17"]
        assert result['data']['microchip_ids'] == {"binding-17": "chip-42"}
        assert result['options'].get('allow_control', False) is False
        await hass.async_block_till_done()
        duplicate = await hass.config_entries.flow.async_init('sangens', context={"source": config_entries.SOURCE_USER})
        assert duplicate['type'] is FlowResultType.ABORT
        assert len(hass.config_entries.async_entries('sangens')) == 1

async def test_отказ_входа_не_сохраняет_токен(hass):
    with patch('custom_components.sangens.api.SangensClient._request', AsyncMock(side_effect=SangensAuthError('Нужен вход'))):
        result = await hass.config_entries.flow.async_init('sangens', context={"source": 'user'})
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {'next_step_id':'token'})
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {"access_token": "bad-token"})
    assert result['errors'] == {'base': 'invalid_auth'}
    assert hass.config_entries.async_entries('sangens') == []

async def test_повторный_вход_не_подменяет_печь(hass, device_data):
    entry = MockConfigEntry(domain='sangens', unique_id='shared', data={"access_token": "old", "binding_ids": ["binding-17"], "microchip_ids": {"binding-17": "different-chip"}})
    entry.add_to_hass(hass)
    with patch('custom_components.sangens.api.SangensClient._request', AsyncMock(return_value={"items": [device_data]})):
        result = await hass.config_entries.flow.async_init('sangens', context={'source': 'reauth', 'entry_id': entry.entry_id}, data=entry.data)
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {'next_step_id':'reauth_confirm'})
        result = await hass.config_entries.flow.async_configure(result['flow_id'], {"access_token": "new"})
    assert result['errors'] == {'base': 'wrong_account'}
    assert entry.data['access_token'] == 'old'

async def test_успешный_повторный_вход_сохраняет_общую_запись(hass, device_data):
    entry = MockConfigEntry(domain='sangens', unique_id='shared', data={'access_token':'old','binding_ids':['binding-17'],'microchip_ids':{'binding-17':'chip-42'}}, options={'allow_control':False})
    entry.add_to_hass(hass)
    with patch('custom_components.sangens.api.SangensClient._request', AsyncMock(return_value={'items':[device_data]})), patch.object(hass.config_entries,'async_reload',AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_init('sangens',context={'source':'reauth','entry_id':entry.entry_id},data=entry.data)
        result = await hass.config_entries.flow.async_configure(result['flow_id'],{'next_step_id':'reauth_confirm'})
        result = await hass.config_entries.flow.async_configure(result['flow_id'],{'access_token':'new-token'})
    assert result['type'] is FlowResultType.ABORT
    assert result['reason'] == 'reauth_successful'
    assert entry.data['access_token'] == 'new-token'
    assert entry.data['binding_ids'] == ['binding-17']
    assert entry.options['allow_control'] is False
    assert len(hass.config_entries.async_entries('sangens')) == 1

async def test_сохранённое_подключение_не_требует_нового_входа(hass):
    entry = MockConfigEntry(domain='sangens', unique_id='shared', data={'access_token':'persisted-token','binding_ids':['binding-17'],'microchip_ids':{'binding-17':'chip-42'}})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init('sangens', context={'source':'user'})
    assert result['type'] is FlowResultType.ABORT
    assert result['reason'] == 'already_configured'
