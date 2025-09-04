from fastapi import HTTPException, Query

from firebase_admin import auth


import phonenumbers
from phonenumbers import PhoneNumberFormat


from datetime import datetime
import os
import random
import string
import hashlib
import base64


word = os.getenv("SECRET_API_WORD")
hash_bytes = hashlib.sha256(word.encode()).digest()
API_KEY = base64.urlsafe_b64encode(hash_bytes).rstrip(b"=").decode()
API_KEY_NAME = "api_key"


def check_api_key(api_key: str = Query(default=None, alias=API_KEY_NAME)):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(status_code=403, detail="Chave API não autorizada")


def check_uid_exists(uid: str):
    try:
        user = auth.get_user(uid)
        print(f"✅ User exists: {user.uid}, email: {user.email}")
        return True
    except auth.UserNotFoundError:
        print("❌ No user found with that UID.")
        return False
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return False


def generate_random_invite_key(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits  # A-Z, a-z, 0-9
    return "".join(random.choices(chars, k=length))


def to_e164_br(phone_number):
    try:
        parsed = phonenumbers.parse(phone_number, "BR")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        else:
            return None
    except phonenumbers.NumberParseException:
        return None


def timestamp_formatado(dt: datetime) -> str:
    try:
        return dt.replace(microsecond=0).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de timestamp inválido. Use ISO 8601 (ex: '2025-06-27T14:00:00')",
        )


# Size limits
PHOTO_LIMIT = 5 * 1024**2
VIDEO_LIMIT = 50 * 1024**2
DOCUMENT_LIMIT = 10 * 1024**2


def get_file_category(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "photo"
    elif content_type.startswith("video/"):
        return "video"
    elif content_type in {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
    }:
        return "document"
    return "unknown"


def get_size_limit(category: str) -> int:
    return {"photo": PHOTO_LIMIT, "video": VIDEO_LIMIT, "document": DOCUMENT_LIMIT}.get(
        category, 0
    )
