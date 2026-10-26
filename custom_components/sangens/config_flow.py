"""Ручной вход и одна серверная настройка для всех пользователей HA."""
from time import monotonic
from hashlib import sha256
from functools import wraps
from uuid import uuid4
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from .api import SangensClient, SangensAuthError, SangensConnectionError
from .auth import SangensAuthClient, SangensCaptchaRequired, SangensInvalidCode, SangensRateLimited, SangensInvalidEmail, SangensUnsupportedClient, SangensAuthRejected
from .const import DOMAIN
from .models import SangensProtocolError

TOKEN_SCHEMA=vol.Schema({vol.Required('access_token'):selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))})
EMAIL_SCHEMA=vol.Schema({vol.Required('email'):selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL))})
CAPTCHA_SCHEMA=vol.Schema({vol.Required('recaptcha'):selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))})
CODE_SCHEMA=vol.Schema({vol.Required('code'):selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))})

def _serial_step(step,schema):
    """Повторное нажатие не ставит запросы авторизации в очередь."""
    def decorate(method):
        @wraps(method)
        async def wrapped(self,user_input=None,*args):
            if getattr(self,'_request_pending',False):
                return self.async_show_form(step_id=step or args[0],data_schema=schema,errors={'base':'request_in_progress'})
            self._request_pending=True
            try:
                return await method(self,user_input,*args)
            finally:
                self._request_pending=False
        return wrapped
    return decorate

class SangensConfigFlow(config_entries.ConfigFlow,domain=DOMAIN):
    VERSION=1

    def _ensure_client(self):
        if not getattr(self,'_device_id',None):
            entry=self._get_reauth_entry() if self.context.get('source')=='reauth' else None
            self._device_id=(entry.data.get('device_id') if entry else None) or uuid4().hex
        return SangensAuthClient(async_get_clientsession(self.hass),self._device_id)

    def _limits(self):
        return self.hass.data.setdefault(DOMAIN,{}).setdefault('login_limits',{})

    def _blocked(self):
        return monotonic()<self._limits().get('blocked_until',0)

    def _pause(self,seconds=300):
        self._limits()['blocked_until']=max(self._limits().get('blocked_until',0),monotonic()+max(300,seconds))

    async def async_step_user(self,user_input=None):
        await self.async_set_unique_id('shared')
        self._abort_if_unique_id_configured()
        return self.async_show_menu(step_id='user',menu_options=['email','token'])

    @_serial_step('email',EMAIL_SCHEMA)
    async def async_step_email(self,user_input=None):
        errors={}
        client=self._ensure_client()
        if user_input is not None:
            if self._blocked() or monotonic()<self._limits().get('next_email',0):
                errors['base']='wait_before_retry'
            else:
                # Пауза ставится до запроса: при тайм-ауте письмо уже могло уйти.
                self._limits()['next_email']=monotonic()+60
                try:
                    self._email=user_input['email'].strip()
                    self._email_token=await client.request_code(self._email)
                    self._email_tries=0
                    self._email_expires=monotonic()+900
                    return self.async_show_form(step_id='email_code',data_schema=CODE_SCHEMA)
                except SangensCaptchaRequired:
                    self._captcha_tries=0
                    self._captcha_used=set()
                    self._captcha_expires=monotonic()+900
                    self._captcha_retry_after=0
                    return self.async_show_form(step_id='captcha',data_schema=CAPTCHA_SCHEMA)
                except SangensRateLimited as err:
                    self._pause(err.retry_after)
                    errors['base']='wait_before_retry'
                except ValueError:
                    self._limits()['next_email']=0
                    errors['base']='invalid_email'
                except SangensInvalidEmail:
                    errors['base']='invalid_email'
                except SangensUnsupportedClient:
                    self._pause()
                    errors['base']='unsupported_client'
                except SangensAuthRejected:
                    self._pause()
                    errors['base']='auth_rejected'
                except SangensConnectionError:
                    errors['base']='cannot_connect'
                except SangensProtocolError:
                    errors['base']='invalid_response'
        return self.async_show_form(step_id='email',data_schema=EMAIL_SCHEMA,errors=errors)

    @_serial_step('captcha',CAPTCHA_SCHEMA)
    async def async_step_captcha(self,user_input=None):
        """Только настоящий результат ручной проверки, без повторного использования."""
        errors={}
        if not getattr(self,'_email',None) or monotonic()>getattr(self,'_captcha_expires',0):
            return self.async_abort(reason='code_expired')
        if user_input is not None:
            proof=user_input['recaptcha'].strip()
            fingerprint=sha256(proof.encode()).hexdigest()
            if self._blocked() or monotonic()<self._captcha_retry_after:
                errors['base']='wait_before_retry'
            elif fingerprint in self._captcha_used:
                errors['base']='captcha_reused'
            elif not proof or len(proof)>8192 or any(c.isspace() for c in proof):
                errors['base']='captcha_rejected'
            else:
                self._captcha_used.add(fingerprint)
                self._captcha_tries+=1
                # Не сохраняем сам результат даже в состоянии потока. После тайм-аута он уже мог быть использован.
                self._limits()['next_email']=monotonic()+60
                self._captcha_retry_after=monotonic()+60
                try:
                    self._email_token=await self._ensure_client().request_code(self._email,recaptcha=proof)
                    self._email_tries=0
                    self._email_expires=monotonic()+900
                    return self.async_show_form(step_id='email_code',data_schema=CODE_SCHEMA)
                except SangensCaptchaRequired:
                    self._captcha_retry_after=0
                    errors['base']='captcha_rejected'
                except SangensRateLimited as err:
                    self._pause(err.retry_after)
                    errors['base']='wait_before_retry'
                except SangensConnectionError:
                    errors['base']='cannot_connect'
                except SangensUnsupportedClient:
                    self._pause()
                    errors['base']='unsupported_client'
                except (SangensAuthRejected,SangensInvalidEmail):
                    self._pause()
                    errors['base']='auth_rejected'
                except (ValueError,SangensProtocolError):
                    errors['base']='invalid_response'
                if self._captcha_tries>=2:
                    self._pause()
                    return self.async_abort(reason='captcha_failed')
        return self.async_show_form(step_id='captcha',data_schema=CAPTCHA_SCHEMA,errors=errors)

    @_serial_step('email_code',CODE_SCHEMA)
    async def async_step_email_code(self,user_input=None):
        errors={}
        if not getattr(self,'_email_token',None) or monotonic()>self._email_expires:
            return self.async_abort(reason='code_expired')
        if user_input is not None:
            if self._blocked():
                errors['base']='wait_before_retry'
            else:
                try:
                    code=user_input['code'].strip()
                    client=self._ensure_client()
                    if await client.check_code(self._email_token,code):
                        return self.async_abort(reason='registration_required')
                    token=await client.login(self._email_token,code)
                    self._pending_token=token
                    return await self._load_devices()
                except SangensCaptchaRequired:
                    self._pause()
                    return self.async_abort(reason='captcha_required')
                except SangensRateLimited as err:
                    self._pause(err.retry_after)
                    errors['base']='wait_before_retry'
                except (SangensInvalidCode,SangensAuthError):
                    self._email_tries+=1
                    if self._email_tries>=3:
                        self._pause()
                        return self.async_abort(reason='too_many_attempts')
                    errors['base']='invalid_code'
                except SangensUnsupportedClient:
                    self._pause()
                    errors['base']='unsupported_client'
                except (SangensAuthRejected,SangensInvalidEmail):
                    self._pause()
                    errors['base']='auth_rejected'
                except ValueError:
                    errors['base']='invalid_code'
                except SangensConnectionError:
                    errors['base']='cannot_connect'
                except SangensProtocolError:
                    errors['base']='invalid_response'
        return self.async_show_form(step_id='email_code',data_schema=CODE_SCHEMA,errors=errors)

    @_serial_step('load_devices',vol.Schema({}))
    async def async_step_load_devices(self,user_input=None):
        return await self._load_devices()

    async def _load_devices(self):
        errors={}
        if self._blocked():
            return self.async_show_form(step_id='load_devices',data_schema=vol.Schema({}),errors={'base':'wait_before_retry'})
        try:
            return await self._accept_token(self._pending_token)
        except SangensAuthError:
            return self.async_abort(reason='login_expired')
        except SangensRateLimited as err:
            self._pause(err.retry_after)
            errors['base']='wait_before_retry'
        except SangensConnectionError:
            errors['base']='cannot_connect'
        except (SangensProtocolError,ValueError):
            errors['base']='invalid_response'
        return self.async_show_form(step_id='load_devices',data_schema=vol.Schema({}),errors=errors)

    async def _accept_token(self,token):
        self._ensure_client()
        client=SangensClient(async_get_clientsession(self.hass),token,device_id=self._device_id)
        states=await client.list_devices()
        if not states:
            raise SangensProtocolError('Нет доступных устройств')
        if self.context.get('source')=='reauth':
            entry=self._get_reauth_entry()
            chips={s.binding_id:s.microchip_id for s in states}
            if any(chips.get(binding)!=chip for binding,chip in entry.data['microchip_ids'].items()):
                return self.async_abort(reason='wrong_account')
            updates={'access_token':token,'device_id':self._device_id}
            if getattr(self,'_email',None):updates['email']=self._email
            return self.async_update_reload_and_abort(entry,data_updates=updates)
        self._token=token
        self._devices={s.binding_id:s for s in states}
        return await self.async_step_devices()

    async def async_step_token(self,user_input=None):
        return await self._token_step(user_input,'token')

    @_serial_step(None,TOKEN_SCHEMA)
    async def _token_step(self,user_input,step):
        errors={}
        if user_input is not None:
            if self._blocked():
                errors['base']='wait_before_retry'
            else:
                try:
                    result=await self._accept_token(user_input['access_token'])
                    if result.get('reason')=='wrong_account':
                        errors['base']='wrong_account'
                    else:return result
                except SangensAuthError:
                    errors['base']='invalid_auth'
                except SangensRateLimited as err:
                    self._pause(err.retry_after)
                    errors['base']='wait_before_retry'
                except SangensConnectionError:
                    errors['base']='cannot_connect'
                except (SangensProtocolError,ValueError):
                    errors['base']='invalid_response'
        return self.async_show_form(step_id=step,data_schema=TOKEN_SCHEMA,errors=errors)

    async def async_step_devices(self,user_input=None):
        errors={}
        if user_input is not None:
            bindings=user_input['binding_ids']
            if bindings and len(set(bindings))==len(bindings) and all(b in self._devices for b in bindings):
                data={'access_token':self._token,'device_id':self._device_id,'binding_ids':bindings,'microchip_ids':{b:self._devices[b].microchip_id for b in bindings}}
                if getattr(self,'_email',None):data['email']=self._email
                return self.async_create_entry(title='Печь Sangens',data=data,options={'allow_control':False})
            errors['base']='no_devices'
        options=[selector.SelectOptionDict(value=b,label=s.title) for b,s in self._devices.items()]
        return self.async_show_form(step_id='devices',data_schema=vol.Schema({vol.Required('binding_ids'):selector.SelectSelector(selector.SelectSelectorConfig(options=options,multiple=True))}),errors=errors)

    async def async_step_reauth(self,entry_data):
        return await self.async_step_reauth_method()

    async def async_step_reauth_method(self,user_input=None):
        return self.async_show_menu(step_id='reauth_method',menu_options=['email','reauth_confirm'])

    async def async_step_reauth_confirm(self,user_input=None):
        return await self._token_step(user_input,'reauth_confirm')

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SangensOptionsFlow()

class SangensOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self,user_input=None):
        if user_input is not None:return self.async_create_entry(title='',data=user_input)
        return self.async_show_form(step_id='init',data_schema=vol.Schema({vol.Required('allow_control',default=self.config_entry.options.get('allow_control',False)):bool}))
