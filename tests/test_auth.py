"""Вход проверяется на локальном сервисе, без писем и настоящих кодов."""
import asyncio
import aiohttp
from aiohttp import web
import pytest
from custom_components.sangens.auth import SangensAuthClient, SangensCaptchaRequired, SangensInvalidCode, SangensRateLimited
from custom_components.sangens.api import SangensConnectionError
from custom_components.sangens.models import SangensProtocolError

@pytest.fixture
async def login_service(socket_enabled, unused_tcp_port):
    state = {'status':200, 'body':{'data':{}}, 'calls':[], 'delay':0}
    async def handler(request):
        state['calls'].append((request.path,await request.json(),dict(request.headers)))
        await asyncio.sleep(state['delay'])
        return web.json_response(state['body'], status=state['status'],headers={'Retry-After':state['retry_after']} if state.get('retry_after') else {})
    app=web.Application();app.router.add_post('/api/{tail:.*}',handler)
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',unused_tcp_port).start()
    async with aiohttp.ClientSession() as session:
        yield SangensAuthClient(session,'test-ha-device',base_url=f'http://127.0.0.1:{unused_tcp_port}/api',timeout=.05), state
    await runner.cleanup()

async def test_запрос_письма_без_поддельной_captcha(login_service):
    client, state=login_service;state['body']={'data':{'emailToken':'challenge-token'}}
    assert await client.request_code('person@example.test') == 'challenge-token'
    path,payload,headers=state['calls'][0]
    assert path=='/api/email/send'
    assert payload=={'email':'person@example.test'}
    assert headers['App-DeviceId']=='test-ha-device'
    assert headers['App-Platform']=='android'
    assert 'Authorization' not in headers

async def test_проверка_кода_и_получение_сессии(login_service):
    client,state=login_service
    state['body']={'data':{'isNeedRegister':False}}
    assert await client.check_code('challenge-token','123456') is False
    assert state['calls'][0][0:2]==('/api/email/check',{'emailToken':'challenge-token','code':'123456'})
    state['body']={'data':{'token':'account-session'}}
    assert await client.login('challenge-token','123456')=='account-session'
    assert state['calls'][1][0:2]==('/api/auth/loginByEmail',{'token':'challenge-token','code':'123456'})

@pytest.mark.parametrize('status,body,expected',[
 (422,{'errors':{'recaptcha':['Проверка обязательна']}},SangensCaptchaRequired),
 (403,{'errors':{'recaptcha':['Проверка не пройдена']}},SangensCaptchaRequired),
 (422,{'errors':{'code':['Неверный код']}},SangensInvalidCode),
 (429,{'message':'Слишком часто'},SangensRateLimited),
])
async def test_отказ_не_вызывает_повтор(login_service,status,body,expected):
    client,state=login_service;state.update(status=status,body=body)
    with pytest.raises(expected):
        await client.check_code('challenge-token','123456')
    assert len(state['calls'])==1

async def test_таймаут_не_отправляет_второе_письмо(login_service):
    client,state=login_service;state['delay']=.15
    with pytest.raises(SangensConnectionError):
        await client.request_code('person@example.test')
    assert len(state['calls'])==1

async def test_пустой_ответ_не_считается_успешной_авторизацией(login_service):
    client,state=login_service;state['body']={'data':{'token':''}}
    with pytest.raises(SangensProtocolError):
        await client.login('ticket','123456')

@pytest.mark.parametrize('email',['','not-an-email','person@example.test\r\nInjected: yes'])
async def test_неправильная_почта_не_отправляется(login_service,email):
    client,state=login_service
    with pytest.raises(ValueError):await client.request_code(email)
    assert state['calls']==[]

async def test_ограничение_частоты_сохраняет_паузу_сервиса(login_service):
    client,state=login_service;state.update(status=429,retry_after='1800')
    with pytest.raises(SangensRateLimited) as error:
        await client.request_code('person@example.test')
    assert error.value.retry_after==1800
    assert len(state['calls'])==1

@pytest.mark.parametrize('status,body,expected_name',[
 (422,{'message':'Recaptcha is invalid','errors':None},'SangensCaptchaRequired'),
 (403,{'errors':{'recaptcha_token':['Нужна проверка']}},'SangensCaptchaRequired'),
 (422,{'message':'Device Id header is invalid','errors':None},'SangensUnsupportedClient'),
 (426,{'message':'Application version is invalid'},'SangensUnsupportedClient'),
 (422,{'errors':{'email':['Неверная почта']}},'SangensInvalidEmail'),
 (403,{'message':'Unexpected refusal person@example.test 123456','errors':None},'SangensAuthRejected'),
])
async def test_причина_отказа_письма_не_теряется(login_service,caplog,status,body,expected_name):
    client,state=login_service;state.update(status=status,body=body)
    try:
        await client.request_code('person@example.test')
    except Exception as error:
        assert type(error).__name__==expected_name
        assert 'person@example.test' not in str(error)
        assert '123456' not in str(error)
    else:
        pytest.fail('Отказ сервера должен быть явным')
    assert len(state['calls'])==1
    assert 'person@example.test' not in caplog.text
    assert '123456' not in caplog.text
