import httpx
from app.config import SMS_PROVIDER, SMS_API_KEY, SMS_SENDER

async def send_sms(phone: str, text: str) -> bool:
    # Тестовый режим — просто печатаем код
    if SMS_PROVIDER == "dev":
        print(f"[DEV SMS] to={phone} text={text}")
        return True

    if SMS_PROVIDER == "sms_ru":
        # Документация: https://sms.ru/api/send
        params = {
            "api_id": SMS_API_KEY,
            "to": phone,
            "msg": text,
            "json": 1,
        }
        if SMS_SENDER:
            params["from"] = SMS_SENDER
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://sms.ru/sms/send", params=params)
                r.raise_for_status()
                data = r.json()
                return str(data.get("status")) == "OK"
        except Exception as e:
            print(f"[SMS_RU] error: {e}")
            return False

    print(f"[SMS] Unsupported provider: {SMS_PROVIDER}")
    return False
