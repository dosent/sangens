"""Асинхронный клиент. Управляющие запросы никогда не повторяются."""
import asyncio
from typing import Any
import aiohttp
from .const import API_URL
from .models import DeviceMode, DeviceSnapshot, SangensProtocolError, identifier, number

class SangensAuthError(Exception):
    """Нужен повторный вход."""

class SangensConnectionError(Exception):
    """Сервис недоступен или ограничил частоту запросов."""

class SangensCommandUncertain(SangensConnectionError):
    """Неизвестно, успел ли контроллер принять команду."""

class SangensBusyError(Exception):
    """Контроллер ещё выполняет предыдущую команду."""


class SangensClient:
    def __init__(self, session: aiohttp.ClientSession, token: str, *, base_url: str = API_URL, timeout: float = 15):
        if not isinstance(token, str) or not token.strip() or any(c.isspace() for c in token):
            raise ValueError("Некорректный токен доступа")
        self._session = session
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _request(self, method: str, path: str, payload: dict | None = None) -> Any:
        mutation = method != "GET"
        try:
            async with self._session.request(method, f"{self._base_url}{path}", json=payload,
                headers={"Authorization": f"Bearer {self._token}"}, timeout=self._timeout,
                allow_redirects=False) as response:
                if response.status in (401, 403):
                    raise SangensAuthError("Требуется повторный вход в Sangens")
                if response.status == 409:
                    raise SangensBusyError("Печь ещё выполняет предыдущую команду")
                if response.status == 429:
                    raise SangensConnectionError("Сервис ограничил частоту запросов")
                if response.status >= 500 and mutation:
                    raise SangensCommandUncertain("Результат команды неизвестен. Проверьте состояние печи")
                if response.status >= 400 or 300 <= response.status < 400:
                    raise SangensConnectionError("Сервис отклонил запрос")
                if mutation:
                    return None
                try:
                    body = await response.json()
                    return body["data"]
                except (ValueError, TypeError, KeyError, aiohttp.ContentTypeError) as err:
                    raise SangensProtocolError("Неизвестный формат ответа Sangens") from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            error = SangensCommandUncertain if mutation else SangensConnectionError
            raise error("Результат команды неизвестен" if mutation else "Нет связи с Sangens") from err

    async def list_devices(self) -> list[DeviceSnapshot]:
        data = await self._request("GET", "/microchip-user")
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise SangensProtocolError("Неизвестный формат списка устройств")
        states = [DeviceSnapshot.parse(item) for item in data["items"]]
        if len({s.binding_id for s in states}) != len(states) or len({s.microchip_id for s in states}) != len(states):
            raise SangensProtocolError("Сервис вернул повторяющиеся устройства")
        return states

    async def get_device(self, binding_id: str) -> DeviceSnapshot:
        state = DeviceSnapshot.parse(await self._request("GET", f"/microchip-user/{identifier(binding_id)}"))
        if state.binding_id != str(binding_id):
            raise SangensProtocolError("Ответ относится к другому устройству")
        return state

    async def list_modes(self) -> tuple[DeviceMode, ...]:
        data = await self._request("GET", "/modes")
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise SangensProtocolError("Неизвестный формат списка режимов")
        return tuple(DeviceMode.parse(item) for item in items)

    async def set_power(self, microchip_id: str, enabled: bool) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("Нужно явно указать включение или выключение")
        await self._request("POST", f"/microchips/{identifier(microchip_id)}/set-remote-control-status",
                            {"remoteControlStatus": "ON" if enabled else "off"})

    async def set_temperature(self, microchip_id: str, kind: str, value: float) -> None:
        if number(value) is None or kind not in ("air", "stone"):
            raise ValueError("Некорректная температура")
        endpoint, key = ("set-air-temperature", "setAirTemperature") if kind == "air" else ("set-target-stone-temperature", "targetStoneTemperature")
        await self._request("POST", f"/microchips/{identifier(microchip_id)}/{endpoint}", {key: value})

    async def set_mode(self, binding_id: str, mode_id: str) -> None:
        await self._request("POST", f"/microchip-user/{identifier(binding_id)}/set-mode", {"modeId": identifier(mode_id)})
