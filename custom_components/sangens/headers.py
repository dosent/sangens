"""Обязательные заголовки мобильного протокола Sangens."""
import re


def request_headers(device_id: str, token: str | None = None) -> dict[str, str]:
    if not isinstance(device_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',device_id):
        raise ValueError('Некорректный идентификатор клиента')
    headers = {
        'Accept':'application/json', 'Content-Type':'application/json',
        'App-DeviceId':device_id,
        # Сервер принимает платформы мобильного протокола; свой клиент обозначен в User-Agent.
        'App-Platform':'android', 'App-Version':'0.3.1', 'App-Lang':'ru',
        'User-Agent':'HomeAssistant-Sangens/0.3.1',
    }
    if token:
        headers['Authorization']=f'Bearer {token}'
    return headers


def retry_after_seconds(value: str | None) -> int:
    """Уважать числовой Retry-After и HTTP-дату; минимум пять минут."""
    from datetime import datetime, UTC
    from email.utils import parsedate_to_datetime
    from math import ceil
    try:
        seconds=int(value)
    except (TypeError,ValueError):
        try:
            date=parsedate_to_datetime(value)
            if date.tzinfo is None:date=date.replace(tzinfo=UTC)
            seconds=ceil((date-datetime.now(UTC)).total_seconds())
        except (TypeError,ValueError,OverflowError):
            seconds=300
    return max(300,seconds)
