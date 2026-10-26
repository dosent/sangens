"""Настоящий HTTP-клиент против локального искусственного сервиса."""
import asyncio
import aiohttp
from aiohttp import web
import pytest
from custom_components.sangens.api import (
    SangensClient, SangensAuthError, SangensConnectionError,
    SangensCommandUncertain, SangensProtocolError, SangensBusyError)

@pytest.fixture
async def service(socket_enabled, unused_tcp_port):
    calls = []
    response = {"status": 200, "body": {"data": {}}, "delay": 0}
    async def handler(request):
        response["headers"] = dict(request.headers)
        calls.append((request.method, request.path, await request.json() if request.can_read_body else None,
                      request.headers.get("Authorization")))
        await asyncio.sleep(response["delay"])
        return web.json_response(response["body"], status=response["status"])
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", unused_tcp_port).start()
    async with aiohttp.ClientSession() as session:
        yield SangensClient(session, "synthetic-token", base_url=f"http://127.0.0.1:{unused_tcp_port}/api", timeout=.05), calls, response
    await runner.cleanup()

async def test_список_и_вложенное_состояние(service, device_data):
    client, calls, response = service
    response["body"] = {"data": {"items": [device_data]}}
    states = await client.list_devices()
    assert states[0].microchip_id == "chip-42"
    assert calls[0][:2] == ("GET", "/api/microchip-user")
    assert calls[0][3] == "Bearer synthetic-token"
    response["body"] = {"data": device_data}
    assert (await client.get_device("binding-17")).air_temperature == 28.7

@pytest.mark.parametrize("enabled,payload", [(True, "ON"), (False, "off")])
async def test_явная_команда_правильному_контроллеру(service, enabled, payload):
    client, calls, _ = service
    await client.set_power("chip-42", enabled)
    assert calls == [("POST", "/api/microchips/chip-42/set-remote-control-status", {"remoteControlStatus": payload}, "Bearer synthetic-token")]

@pytest.mark.parametrize("status,expected", [(401, SangensAuthError), (403, SangensAuthError), (409, SangensBusyError), (429, SangensConnectionError), (500, SangensCommandUncertain)])
async def test_ошибка_без_повтора_и_утечки_токена(service, status, expected):
    client, calls, response = service
    response.update(status=status, body={"secret": "synthetic-token"})
    with pytest.raises(expected) as error:
        await client.set_power("chip-42", True)
    assert len(calls) == 1
    assert "synthetic-token" not in str(error.value)

async def test_таймаут_команды_не_означает_отказ(service):
    client, calls, response = service
    response["delay"] = .15
    with pytest.raises(SangensCommandUncertain):
        await client.set_power("chip-42", True)
    assert len(calls) == 1

@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "80"])
async def test_недопустимая_температура_не_отправляется(service, value):
    client, calls, _ = service
    with pytest.raises(ValueError):
        await client.set_temperature("chip-42", "air", value)
    assert calls == []

async def test_идентификатор_не_может_изменить_путь(service):
    client, calls, _ = service
    with pytest.raises(ValueError):
        await client.set_power("../../another", True)
    assert calls == []

async def test_повреждённый_список_не_пустой_успешный_ответ(service):
    client, _, response = service
    response["body"] = {"data": {"items": "broken"}}
    with pytest.raises(SangensProtocolError):
        await client.list_devices()

async def test_обязательные_заголовки_стабильны_для_клиента(service,device_data):
    client,calls,response=service
    response['body']={'data':device_data}
    await client.get_device('binding-17')
    assert response['headers']['App-DeviceId']
    first_id=response['headers']['App-DeviceId']
    await client.get_device('binding-17')
    assert response['headers']['App-DeviceId']==first_id
    assert response['headers']['App-Platform']=='android'
