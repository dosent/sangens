"""Проверка границ и состояний, влияющих на управление печью."""
import math
import pytest
from custom_components.sangens.models import DeviceSnapshot, SangensProtocolError


def test_разные_идентификаторы_и_температуры(device_data):
    state = DeviceSnapshot.parse(device_data)
    assert (state.binding_id, state.microchip_id) == ("binding-17", "chip-42")
    assert state.air_temperature == 28.7
    assert state.air_target == 81
    assert state.stone_temperature == 78
    assert state.second_stone_temperature is None
    assert state.power is True and state.heating is True
    assert state.air_limits == (40, 100)


@pytest.mark.parametrize("value,expected", [("off", False), ("ON", True), ("OFF", None), (None, None), (False, None)])
def test_неизвестное_питание_не_выключение(device_data, value, expected):
    device_data["microchip"]["data"]["remoteControlStatus"] = value
    assert DeviceSnapshot.parse(device_data).power is expected


@pytest.mark.parametrize("value", [None, "unavailable", float("nan"), float("inf"), True, "28.7"])
def test_нечисловые_данные_не_превращаются_в_ноль(device_data, value):
    device_data["microchip"]["data"]["currentAirTemperature"] = value
    assert DeviceSnapshot.parse(device_data).air_temperature is None


def test_нет_связи_и_неподтверждённый_нагрев(device_data):
    device_data["microchip"]["connectionStatus"] = "offline"
    device_data["microchip"]["data"]["airHeaterStatus"] = "unknown"
    state = DeviceSnapshot.parse(device_data)
    assert state.online is False and state.heating is None


@pytest.mark.parametrize("field", ["id", "microchip"])
def test_без_идентификатора_нельзя_направить_команду(device_data, field):
    del device_data[field]
    with pytest.raises(SangensProtocolError):
        DeviceSnapshot.parse(device_data)


def test_перевёрнутые_границы_не_используются(device_data):
    device_data["mode"]["data"].update(minAirTemp=100, maxAirTemp=40)
    assert DeviceSnapshot.parse(device_data).air_limits is None
