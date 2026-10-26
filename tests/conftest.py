"""Искусственные данные; запросы к настоящей печи в тестах запрещены."""
import pytest

@pytest.fixture
def device_data():
    return {
        "id": "binding-17", "title": "Сауна",
        "mode": {"id": 2, "title": "Финская сауна", "data": {
            "minAirTemp": 40, "maxAirTemp": 100,
            "minHeaterTemp": 100, "maxHeaterTemp": 500}},
        "microchip": {"id": "chip-42", "connectionStatus": "online", "data": {
            "remoteControlStatus": "ON", "currentAirTemperature": 28.7,
            "setAirTemperature": 81, "firstStoneTemperature": 78,
            "targetStoneTemperature": 300, "airHeaterStatus": "ON",
            "firstStoneHeaterStatus": "off"}}}

@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations):
    yield
