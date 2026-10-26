"""Раздача только локального ресурса карточки."""
from homeassistant.setup import async_setup_component
from custom_components.sangens.const import DOMAIN

async def test_ресурс_доступен_без_токена_sangens(hass, hass_client):
    assert await async_setup_component(hass, 'http', {})
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_client()
    response = await client.get('/sangens/sangens-card.js')
    assert response.status == 200
    text = await response.text()
    assert 'customElements.define' in text
    assert 'api.sangens.com' not in text
    assert 'Authorization' not in text
    response = await client.get('/sangens/../config/.storage/core.config_entries')
    assert response.status != 200
