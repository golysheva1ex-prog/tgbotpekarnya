import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("Не найден BOT_TOKEN в .env")

ADMIN_TG_IDS = {int(x) for x in os.getenv("ADMIN_TG_IDS", "").split(",") if x.strip().isdigit()}
DEFAULT_COURIER_FEE_RUB = int(os.getenv("COURIER_FEE_RUB", "150"))
DB_PATH = "bot_store.db"

# SMS / OTP
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "dev").strip().lower()  # sms_ru | dev
SMS_API_KEY = os.getenv("SMS_API_KEY", "").strip()
SMS_SENDER = os.getenv("SMS_SENDER", "").strip()
OTP_TTL_MINUTES = int(os.getenv("OTP_TTL_MINUTES", "5"))
OTP_CODE_LENGTH = int(os.getenv("OTP_CODE_LENGTH", "4"))
OTP_SECRET = os.getenv("OTP_SECRET", "change_me")
