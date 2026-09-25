import hmac
import secrets
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def verify_password(plain: str, encoded: str) -> bool:
    try:
        return password_hash.verify(plain, encoded)
    except Exception:
        return False


def csrf_token(session: dict) -> str:
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def valid_csrf(session: dict, supplied: str | None) -> bool:
    expected = session.get("csrf", "")
    return bool(supplied and expected and hmac.compare_digest(supplied, expected))

