"""Проверенные значения состояния без догадок о неизвестных данных."""
from dataclasses import dataclass
import math
import re
from typing import Any

class SangensProtocolError(Exception):
    """Формат ответа не соответствует восстановленному протоколу."""


def identifier(value: Any) -> str:
    """Разрешить только идентификатор, не произвольный путь запроса."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("Отсутствует идентификатор устройства")
    result = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", result):
        raise ValueError("Некорректный идентификатор устройства")
    return result


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def power(value: Any) -> bool | None:
    return {"ON": True, "off": False}.get(value) if isinstance(value, str) else None


def limits(data: dict, low: str, high: str) -> tuple[float, float] | None:
    minimum, maximum = number(data.get(low)), number(data.get(high))
    if minimum is None or maximum is None or minimum >= maximum:
        return None
    return minimum, maximum


@dataclass(frozen=True)
class DeviceMode:
    id: str
    title: str
    air_limits: tuple[float, float] | None
    stone_limits: tuple[float, float] | None

    @classmethod
    def parse(cls, raw: dict) -> "DeviceMode":
        try:
            data = raw.get("data") or {}
            if not isinstance(data, dict):
                raise ValueError
            return cls(identifier(raw["id"]), str(raw.get("title") or "Режим"),
                       limits(data, "minAirTemp", "maxAirTemp"),
                       limits(data, "minHeaterTemp", "maxHeaterTemp"))
        except (KeyError, ValueError, TypeError, AttributeError) as err:
            raise SangensProtocolError("Некорректные данные режима") from err


@dataclass(frozen=True)
class DeviceSnapshot:
    binding_id: str
    microchip_id: str
    title: str
    online: bool
    power: bool | None
    heating: bool | None
    air_temperature: float | None
    air_target: float | None
    stone_temperature: float | None
    second_stone_temperature: float | None
    stone_target: float | None
    mode: DeviceMode | None
    modes: tuple[DeviceMode, ...] = ()

    @property
    def air_limits(self):
        return self.mode.air_limits if self.mode else None

    @property
    def stone_limits(self):
        return self.mode.stone_limits if self.mode else None

    @classmethod
    def parse(cls, raw: dict) -> "DeviceSnapshot":
        try:
            chip = raw["microchip"]
            data = chip.get("data") or {}
            if not isinstance(data, dict):
                raise ValueError
            mode = DeviceMode.parse(raw["mode"]) if raw.get("mode") else None
            statuses = [power(data.get(key)) for key in (
                "airHeaterStatus", "firstStoneHeaterStatus", "secondStoneHeaterStatus") if key in data]
            heating = True if True in statuses else False if statuses and all(x is False for x in statuses) else None
            return cls(
                identifier(raw["id"]), identifier(chip["id"]), str(raw.get("title") or "Сауна"),
                chip.get("connectionStatus") == "online", power(data.get("remoteControlStatus")), heating,
                number(data.get("currentAirTemperature")), number(data.get("setAirTemperature")),
                number(data.get("firstStoneTemperature")), number(data.get("secondStoneTemperature")),
                number(data.get("targetStoneTemperature")), mode)
        except (KeyError, ValueError, TypeError, AttributeError) as err:
            raise SangensProtocolError("Некорректные данные устройства") from err
