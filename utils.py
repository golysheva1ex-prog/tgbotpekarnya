import re
import hashlib
from typing import Optional, Dict, Any
from app.config import OTP_SECRET, OTP_CODE_LENGTH

def normalize_phone(phone: str) -> Optional[str]:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) >= 10:
        return "+" + digits
    return None

def format_address(addr: Dict[str, Any]) -> str:
    parts = [addr.get("address_line","")]
    if addr.get("apt"): parts.append(f"кв/оф {addr['apt']}")
    if addr.get("entrance"): parts.append(f"подъезд {addr['entrance']}")
    if addr.get("floor"): parts.append(f"этаж {addr['floor']}")
    if addr.get("comment"): parts.append(f"коммент: {addr['comment']}")
    return ", ".join([p for p in parts if p])

def make_otp_code(length: int = OTP_CODE_LENGTH) -> str:
    import random
    length = min(max(length, 4), 8)  # 4..8
    return "".join(str(random.randint(0,9)) for _ in range(length))

def hash_otp(code: str) -> str:
    s = (code + "|" + OTP_SECRET).encode()
    return hashlib.sha256(s).hexdigest()
