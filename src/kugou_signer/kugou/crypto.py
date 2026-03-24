from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad
from Crypto.Util.number import bytes_to_long, long_to_bytes


def compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def md5_hex(data: Any) -> str:
    payload = compact_json(data) if isinstance(data, (dict, list)) else str(data)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def sha1_hex(data: Any) -> str:
    payload = compact_json(data) if isinstance(data, (dict, list)) else str(data)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def random_string(length: int = 16) -> str:
    alphabet = "1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    chooser = random.SystemRandom()
    return "".join(chooser.choice(alphabet) for _ in range(length))


@dataclass(slots=True)
class AesEncrypted:
    cipher_hex: str
    key_seed: str


def aes_encrypt(data: Any, key: str | None = None, iv: str | None = None) -> AesEncrypted | str:
    payload = compact_json(data) if isinstance(data, (dict, list)) else str(data)
    if key is not None and iv is not None:
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
        encrypted = cipher.encrypt(pad(payload.encode("utf-8"), AES.block_size))
        return encrypted.hex()
    key_seed = random_string(16).lower()
    digest = md5_hex(key_seed)
    cipher_key = digest[:32]
    cipher_iv = cipher_key[-16:]
    cipher = AES.new(cipher_key.encode("utf-8"), AES.MODE_CBC, cipher_iv.encode("utf-8"))
    encrypted = cipher.encrypt(pad(payload.encode("utf-8"), AES.block_size))
    return AesEncrypted(cipher_hex=encrypted.hex(), key_seed=key_seed)


def aes_decrypt(data_hex: str, key: str, iv: str | None = None) -> Any:
    cipher_key = key
    if iv is None:
        cipher_key = md5_hex(key)[:32]
        iv = cipher_key[-16:]
    cipher = AES.new(cipher_key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
    decrypted = unpad(cipher.decrypt(bytes.fromhex(data_hex)), AES.block_size).decode("utf-8")
    try:
        return json.loads(decrypted)
    except json.JSONDecodeError:
        return decrypted


def rsa_encrypt_no_padding(data: Any, public_key: str) -> str:
    payload = compact_json(data) if isinstance(data, (dict, list)) else str(data)
    payload_bytes = payload.encode("utf-8")
    key = RSA.import_key(public_key)
    key_size = key.size_in_bytes()
    if len(payload_bytes) > key_size:
        raise ValueError("RSA 输入超出长度限制")
    padded = payload_bytes + b"\x00" * (key_size - len(payload_bytes))
    encrypted = pow(bytes_to_long(padded), key.e, key.n)
    return long_to_bytes(encrypted, key_size).hex()
