from __future__ import annotations

from typing import Any

from kugou_signer.constants import (
    ANDROID_SIGNATURE_SECRET,
    APP_ID,
    CLIENT_VERSION,
    WEB_SIGNATURE_SECRET,
)
from kugou_signer.kugou.crypto import compact_json, md5_hex


def signature_web_params(params: dict[str, Any]) -> str:
    chunks = sorted(f"{key}={params[key]}" for key in params)
    return md5_hex(f"{WEB_SIGNATURE_SECRET}{''.join(chunks)}{WEB_SIGNATURE_SECRET}")


def signature_android_params(params: dict[str, Any], data: str = "") -> str:
    parts: list[str] = []
    for key in sorted(params):
        value = params[key]
        parts.append(f"{key}={compact_json(value) if isinstance(value, (dict, list)) else value}")
    return md5_hex(f"{ANDROID_SIGNATURE_SECRET}{''.join(parts)}{data}{ANDROID_SIGNATURE_SECRET}")


def sign_params_key(timestamp_ms: int, appid: int = APP_ID, clientver: int = CLIENT_VERSION) -> str:
    return md5_hex(f"{appid}{ANDROID_SIGNATURE_SECRET}{clientver}{timestamp_ms}")


def mask_phone_number(phone: str) -> str:
    stripped = str(phone).strip()
    return f"{stripped[:2]}*****{stripped[-1:]}"
