"""Ручной вход в HA: почта и код, одна общая сессия."""
from unittest.mock import AsyncMock, patch
import pytest
from homeassistant.data_entry_flow import FlowResultType
from custom_components.sangens.auth import SangensInvalidCode, SangensCaptchaRequired
from custom_components.sangens.const import DOMAIN

async def start_email(hass):
    result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':'user'})
    assert result['type'] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(result['flow_id'],{'next_step_id':'email'})

@pytest.fixture
def login_mocks(device_data):
    with patch('custom_components.sangens.auth.SangensAuthClient.request_code',AsyncMock(return_value='email-challenge')) as request, \
         patch('custom_components.sangens.auth.SangensAuthClient.check_code',AsyncMock(return_value=False)) as check, \
         patch('custom_components.sangens.auth.SangensAuthClient.login',AsyncMock(return_value='account-session')) as login, \
         patch('custom_components.sangens.api.SangensClient._request',AsyncMock(return_value={'items':[device_data]})), \
         patch('custom_components.sangens.async_setup_entry',AsyncMock(return_value=True)):
        yield request,check,login

async def test_почта_код_выбор_и_общая_сессия(hass,login_mocks):
    request,check,login=login_mocks
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    assert result['step_id']=='email_code'
    assert 'email-challenge' not in str(result)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'code':'123456'})
    assert result['step_id']=='devices'
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'binding_ids':['binding-17']})
    assert result['type'] is FlowResultType.CREATE_ENTRY
    assert result['data']['access_token']=='account-session'
    assert result['data']['device_id']
    assert result['data']['email']=='person@example.test'
    assert 'code' not in result['data'] and 'email_token' not in result['data']
    request.assert_awaited_once_with('person@example.test')
    check.assert_awaited_once_with('email-challenge','123456')
    login.assert_awaited_once_with('email-challenge','123456')
    await hass.async_block_till_done()

async def test_неверный_код_не_создаёт_подключение(hass,login_mocks):
    _,check,login=login_mocks;check.side_effect=SangensInvalidCode('Неверный код')
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'code':'000000'})
    assert result['errors']=={'base':'invalid_code'}
    assert hass.config_entries.async_entries(DOMAIN)==[]
    assert login.await_count==0

async def test_три_неверных_кода_останавливают_попытки(hass,login_mocks):
    _,check,login=login_mocks;check.side_effect=SangensInvalidCode('Неверный код')
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    for _ in range(3):result=await hass.config_entries.flow.async_configure(result['flow_id'],{'code':'000000'})
    assert result['type'] is FlowResultType.ABORT
    assert result['reason']=='too_many_attempts'
    assert check.await_count==3 and login.await_count==0

async def test_повторный_запрос_письма_требует_паузы(hass,login_mocks):
    request,_,_=login_mocks
    first=await start_email(hass)
    await hass.config_entries.flow.async_configure(first['flow_id'],{'email':'person@example.test'})
    hass.config_entries.flow.async_abort(first['flow_id'])
    second=await start_email(hass)
    second=await hass.config_entries.flow.async_configure(second['flow_id'],{'email':'person@example.test'})
    assert second['errors']=={'base':'wait_before_retry'}
    assert request.await_count==1

async def test_запрос_captcha_не_обходится_и_не_повторяется(hass,login_mocks):
    request,_,_=login_mocks;request.side_effect=SangensCaptchaRequired('Нужна CAPTCHA')
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    assert result['type'] is FlowResultType.ABORT
    assert result['reason']=='captcha_required'
    assert request.await_count==1

async def test_новый_аккаунт_не_регистрируется_автоматически(hass,login_mocks):
    _,check,login=login_mocks;check.return_value=True
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'code':'123456'})
    assert result['reason']=='registration_required'
    assert login.await_count==0

async def test_сбой_чтения_после_входа_не_повторяет_авторизацию(hass,login_mocks,device_data):
    from custom_components.sangens.api import SangensConnectionError
    request,check,login=login_mocks
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    with patch('custom_components.sangens.api.SangensClient._request',AsyncMock(side_effect=[SangensConnectionError('Нет связи'),{'items':[device_data]}])):
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'code':'123456'})
        assert result['step_id']=='load_devices'
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{})
    assert result['step_id']=='devices'
    assert request.await_count==check.await_count==login.await_count==1

async def test_соблюдается_retry_after_а_не_только_локальная_пауза(hass,login_mocks):
    from custom_components.sangens.auth import SangensRateLimited
    request,_,_=login_mocks;request.side_effect=SangensRateLimited(retry_after=1800)
    with patch('custom_components.sangens.config_flow.monotonic',return_value=1000):
        result=await start_email(hass)
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
        assert result['errors']=={'base':'wait_before_retry'}
    with patch('custom_components.sangens.config_flow.monotonic',return_value=1600):
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    assert result['errors']=={'base':'wait_before_retry'}
    assert request.await_count==1

async def test_параллельное_нажатие_не_отправляет_несколько_кодов(hass,login_mocks):
    import asyncio
    _,check,login=login_mocks
    started,finish=asyncio.Event(),asyncio.Event()
    async def pending(*args):
        started.set();await finish.wait();raise SangensInvalidCode('Неверный код')
    check.side_effect=pending
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    flow_id=result['flow_id']
    first=asyncio.create_task(hass.config_entries.flow.async_configure(flow_id,{'code':'000000'}))
    await started.wait()
    try:
        others=await asyncio.wait_for(asyncio.gather(*(hass.config_entries.flow.async_configure(flow_id,{'code':'000000'}) for _ in range(3))),timeout=1)
    finally:
        finish.set();await first
    assert check.await_count==1 and login.await_count==0
    assert all(r['errors']=={'base':'request_in_progress'} for r in others)

async def test_ручное_чтение_после_429_не_обходит_паузу(hass,login_mocks):
    from custom_components.sangens.auth import SangensRateLimited
    result=await start_email(hass)
    result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
    with patch('custom_components.sangens.api.SangensClient._request',AsyncMock(side_effect=SangensRateLimited(retry_after=1800))) as request:
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'code':'123456'})
        assert result['step_id']=='load_devices'
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{})
    assert result['errors']=={'base':'wait_before_retry'}
    assert request.await_count==1

async def test_почтовый_повторный_вход_сохраняет_контроллер_и_device_id(hass,login_mocks):
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    entry=MockConfigEntry(domain=DOMAIN,unique_id='shared',data={'access_token':'old','device_id':'persisted-ha-client','binding_ids':['binding-17'],'microchip_ids':{'binding-17':'chip-42'}},options={'allow_control':False})
    entry.add_to_hass(hass)
    with patch.object(hass.config_entries,'async_reload',AsyncMock(return_value=True)):
        result=await hass.config_entries.flow.async_init(DOMAIN,context={'source':'reauth','entry_id':entry.entry_id},data=entry.data)
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'next_step_id':'email'})
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'email':'person@example.test'})
        result=await hass.config_entries.flow.async_configure(result['flow_id'],{'code':'123456'})
    assert result['reason']=='reauth_successful'
    assert entry.data['access_token']=='account-session'
    assert entry.data['device_id']=='persisted-ha-client'
    assert entry.data['microchip_ids']=={'binding-17':'chip-42'}
    assert entry.options=={'allow_control':False}
