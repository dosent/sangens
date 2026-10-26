"""Одно общее подключение для всех пользователей HA."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from .api import SangensClient, SangensAuthError, SangensConnectionError
from .const import DOMAIN
from .models import SangensProtocolError

TOKEN_SCHEMA = vol.Schema({vol.Required('access_token'): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))})

class SangensConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id('shared')
        self._abort_if_unique_id_configured()
        return await self._token_step(user_input, 'user')

    async def _token_step(self, user_input, step):
        errors = {}
        if user_input is not None:
            try:
                client = SangensClient(async_get_clientsession(self.hass), user_input['access_token'])
                states = await client.list_devices()
                if not states:
                    errors['base'] = 'no_devices'
                elif step == 'reauth_confirm':
                    entry = self._get_reauth_entry()
                    chips = {s.binding_id: s.microchip_id for s in states}
                    if any(chips.get(b) != chip for b, chip in entry.data['microchip_ids'].items()):
                        errors['base'] = 'wrong_account'
                    else:
                        return self.async_update_reload_and_abort(entry, data_updates={'access_token': user_input['access_token']})
                else:
                    self._token = user_input['access_token']
                    self._devices = {s.binding_id: s for s in states}
                    return await self.async_step_devices()
            except SangensAuthError:
                errors['base'] = 'invalid_auth'
            except SangensConnectionError:
                errors['base'] = 'cannot_connect'
            except (SangensProtocolError, ValueError):
                errors['base'] = 'invalid_response'
        return self.async_show_form(step_id=step, data_schema=TOKEN_SCHEMA, errors=errors)

    async def async_step_devices(self, user_input=None):
        errors = {}
        if user_input is not None:
            bindings = user_input['binding_ids']
            if bindings and len(set(bindings)) == len(bindings) and all(b in self._devices for b in bindings):
                return self.async_create_entry(title='Печь Sangens', data={
                    'access_token': self._token, 'binding_ids': bindings,
                    'microchip_ids': {b: self._devices[b].microchip_id for b in bindings}}, options={'allow_control': False})
            errors['base'] = 'no_devices'
        options = [selector.SelectOptionDict(value=b, label=s.title) for b, s in self._devices.items()]
        return self.async_show_form(step_id='devices', data_schema=vol.Schema({vol.Required('binding_ids'): selector.SelectSelector(selector.SelectSelectorConfig(options=options, multiple=True))}), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._token_step(user_input, 'reauth_confirm')

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SangensOptionsFlow()

class SangensOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title='', data=user_input)
        return self.async_show_form(step_id='init', data_schema=vol.Schema({vol.Required('allow_control', default=self.config_entry.options.get('allow_control', False)): bool}))
