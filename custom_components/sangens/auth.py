"""Ручной вход по почте: без фоновых повторов и поддельных CAPTCHA."""
import asyncio
import re
import logging
import aiohttp
from .const import API_URL
from .headers import request_headers, retry_after_seconds
from .api import SangensConnectionError, SangensRateLimited
from .models import SangensProtocolError

_LOGGER=logging.getLogger(__name__)

class SangensInvalidEmail(Exception):
    """Сервис явно отклонил поле почты."""

class SangensUnsupportedClient(Exception):
    """Отклонены версия или обязательные заголовки клиента."""

class SangensAuthRejected(Exception):
    """Другой отказ сервиса: не выдавать его за ошибку почты."""

class SangensCaptchaRequired(Exception):
    """Сервис запросил штатную проверку пользователя."""

class SangensInvalidCode(Exception):
    """Код отклонён или срок его действия истёк."""


def _secret(value):
    if not isinstance(value,str) or not value or len(value)>8192 or any(c.isspace() for c in value):
        raise SangensProtocolError('Сервис не вернул действительные данные входа')
    return value


class SangensAuthClient:
    def __init__(self,session,device_id,*,base_url=API_URL,timeout=20):
        self._session=session
        self._headers=request_headers(device_id)
        self._url=base_url.rstrip('/')
        self._timeout=aiohttp.ClientTimeout(total=timeout)

    async def _post(self,path,payload):
        try:
            async with self._session.post(self._url+path,json=payload,headers=self._headers,timeout=self._timeout,allow_redirects=False) as response:
                if response.status==429:
                    raise SangensRateLimited(retry_after=retry_after_seconds(response.headers.get('Retry-After')))
                try:
                    body=await response.json()
                except (ValueError,aiohttp.ContentTypeError) as err:
                    raise SangensProtocolError('Неизвестный ответ сервиса входа') from err
                if not isinstance(body,dict):
                    raise SangensProtocolError('Неизвестный ответ сервиса входа')
                errors=body.get('errors')
                fields={str(key).casefold() for key in errors} if isinstance(errors,dict) else set()
                message=body.get('message')
                text=message.casefold() if isinstance(message,str) else ''
                if response.status>=400:
                    reason='unknown'
                    exception=SangensAuthRejected
                    if any('captcha' in key for key in fields) or 'captcha' in text or 'капч' in text:
                        reason='captcha';exception=SangensCaptchaRequired
                    elif response.status==426 or any(term in text for term in ('device id header','platform header','version is invalid','version header')):
                        reason='client';exception=SangensUnsupportedClient
                    elif 'email' in fields:
                        reason='email';exception=SangensInvalidEmail
                    elif path in ('/email/check','/auth/loginByEmail') and fields & {'code','emailtoken','token'}:
                        reason='code';exception=SangensInvalidCode
                    # Только заранее определённые признаки. Ответ сервера, почта и код не логируются.
                    _LOGGER.warning('Sangens: отказ входа; endpoint=%s; HTTP=%s; причина=%s',path,response.status,reason)
                    raise exception('Sangens отклонил запрос входа')
                if response.status not in (200,201):
                    raise SangensConnectionError('Сервис входа отклонил запрос')
                data=body.get('data')
                if not isinstance(data,dict):
                    raise SangensProtocolError('Сервис не вернул данные входа')
                return data
        except (aiohttp.ClientError,asyncio.TimeoutError) as err:
            # При тайм-ауте письмо уже могло уйти. Повтор возможен только вручную после паузы.
            raise SangensConnectionError('Ответ на запрос входа не получен. Запрос автоматически не повторялся') from err

    async def request_code(self,email: str) -> str:
        if not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):
            raise ValueError('Укажите корректную почту аккаунта Sangens')
        return _secret((await self._post('/email/send',{'email':email})).get('emailToken'))

    async def check_code(self,email_token: str,code: str) -> bool:
        self._validate_code(code)
        data=await self._post('/email/check',{'emailToken':_secret(email_token),'code':code})
        value=data.get('isNeedRegister')
        if not isinstance(value,bool):
            raise SangensProtocolError('Неизвестный результат проверки кода')
        return value

    async def login(self,email_token: str,code: str) -> str:
        self._validate_code(code)
        return _secret((await self._post('/auth/loginByEmail',{'token':_secret(email_token),'code':code})).get('token'))

    @staticmethod
    def _validate_code(code):
        if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,32}',code):
            raise ValueError('Укажите код из письма без пробелов')
