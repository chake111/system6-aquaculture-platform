import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

import jwt

from aquaculture_api.config import Settings

_ACCESS_LIFETIME_SECONDS = 60 * 60
_REFRESH_LIFETIME_SECONDS = 24 * 60 * 60
_OFFLINE_LIFETIME_SECONDS = 7 * 24 * 60 * 60


def hash_credential(credential: str, salt: str) -> str:
    hashed = hashlib.pbkdf2_hmac("sha256", credential.encode(), salt.encode(), 120_000)
    return hashed.hex()


def validate_credential(credential: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_credential(credential, salt), expected_hash)


def issue_access_token(user_id: str, settings: Settings) -> str:
    payload = {
        "sub": user_id,
        "kind": "access",
        "exp": int(time.time()) + _ACCESS_LIFETIME_SECONDS,
        "nonce": uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def issue_refresh_token(user_id: str, settings: Settings) -> str:
    payload = {
        "sub": user_id,
        "kind": "refresh",
        "exp": int(time.time()) + _REFRESH_LIFETIME_SECONDS,
        "nonce": uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def issue_offline_grant(
    user_id: str, permissions: list[str], pond_scope: list[str], settings: Settings
) -> tuple[str, int]:
    expiry = int(time.time()) + _OFFLINE_LIFETIME_SECONDS
    payload: dict[str, Any] = {
        "sub": user_id,
        "kind": "offline",
        "permissions": permissions,
        "pond_scope": pond_scope,
        "exp": expiry,
        "nonce": uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expiry


def validated_subject(token: str, settings: Settings, expected_kind: str = "access") -> str | None:
    try:
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if decoded.get("kind") != expected_kind:
        return None
    subject = decoded.get("sub")
    return subject if isinstance(subject, str) else None


def sign_edge_payload(
    body: dict[str, object], timestamp: str, nonce: str, settings: Settings | None = None
) -> str:
    actual_settings = settings or Settings.from_environment()
    message = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    material = f"{timestamp}.{nonce}.{message}".encode()
    return hmac.new(actual_settings.edge_secret.encode(), material, hashlib.sha256).hexdigest()


def valid_edge_signature(
    body: dict[str, object], timestamp: str, nonce: str, signature: str, settings: Settings
) -> bool:
    expected = sign_edge_payload(body, timestamp, nonce, settings)
    return hmac.compare_digest(expected, signature)
