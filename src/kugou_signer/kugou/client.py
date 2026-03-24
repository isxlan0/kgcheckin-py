from __future__ import annotations

import base64
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

warnings.filterwarnings(
    "ignore",
    message="urllib3 .* doesn't match a supported version!",
    category=Warning,
)

import requests

from kugou_signer.constants import (
    APP_ID,
    CLIENT_VERSION,
    DEFAULT_USER_AGENT,
    LISTEN_MIXSONG_ID,
    LISTEN_USER_AGENT,
    LOGIN_TOKEN_AES_IV,
    LOGIN_TOKEN_AES_KEY,
    PUBLIC_RSA_KEY,
    QR_APP_ID,
    QR_POLL_INTERVAL_SECONDS,
    QR_POLL_MAX_ATTEMPTS,
    REQUEST_TIMEOUT_SECONDS,
    SRC_APP_ID,
    VIP_AD_ID,
    VIP_AD_PLAY_SECONDS,
)
from kugou_signer.exceptions import ApiRequestError, LoginTimeoutError
from kugou_signer.kugou.crypto import AesEncrypted, aes_decrypt, aes_encrypt, compact_json, md5_hex, rsa_encrypt_no_padding
from kugou_signer.kugou.protocol import mask_phone_number, sign_params_key, signature_android_params, signature_web_params
from kugou_signer.models import Account


@dataclass(slots=True)
class QrCodePayload:
    key: str
    image_bytes: bytes
    file_path: Path


class KugouClient:
    def __init__(self, timeout: int = REQUEST_TIMEOUT_SECONDS, session: requests.Session | None = None) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

    def close(self) -> None:
        self.session.close()

    def get_qr_code(self, output_dir: Path) -> QrCodePayload:
        payload = self._request(
            "GET",
            "/v2/qrcode",
            base_url="https://login-user.kugou.com",
            params={
                "appid": QR_APP_ID,
                "type": 1,
                "plat": 4,
                "qrcode_txt": f"https://h5.kugou.com/apps/loginQRCode/html/index.html?appid={APP_ID}&",
                "srcappid": SRC_APP_ID,
            },
            encrypt_type="web",
        )
        data = payload.get("data", {})
        image_raw = str(data.get("qrcode_img") or "")
        if image_raw.startswith("data:image"):
            image_raw = image_raw.split(",", 1)[1]
        image_bytes = base64.b64decode(image_raw)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"login-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"
        file_path.write_bytes(image_bytes)
        return QrCodePayload(key=str(data.get("qrcode") or ""), image_bytes=image_bytes, file_path=file_path)

    def wait_for_qr_login(self, key: str) -> dict[str, Any]:
        for _ in range(QR_POLL_MAX_ATTEMPTS):
            payload = self._request(
                "GET",
                "/v2/get_userinfo_qrcode",
                base_url="https://login-user.kugou.com",
                params={"plat": 4, "appid": APP_ID, "srcappid": SRC_APP_ID, "qrcode": key},
                encrypt_type="web",
            )
            status = payload.get("data", {}).get("status")
            if status == 4:
                return payload
            if status == 0:
                raise LoginTimeoutError("二维码已过期，请重新生成")
            time.sleep(QR_POLL_INTERVAL_SECONDS)
        raise LoginTimeoutError("等待二维码确认超时")

    def send_captcha(self, phone: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v7/send_mobile_code",
            base_url="http://login.user.kugou.com",
            data={"businessid": 5, "mobile": str(phone), "plat": 3},
            encrypt_type="android",
        )

    def login_with_phone(self, phone: str, code: str) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        encrypted = aes_encrypt({"mobile": phone, "code": code})
        assert isinstance(encrypted, AesEncrypted)
        body = {
            "plat": 1,
            "support_multi": 1,
            "t1": 0,
            "t2": 0,
            "clienttime_ms": now_ms,
            "mobile": mask_phone_number(phone),
            "key": sign_params_key(now_ms),
            "t3": "MCwwLDAsMCwwLDAsMCwwLDA=",
            "params": encrypted.cipher_hex,
            "pk": rsa_encrypt_no_padding({"clienttime_ms": now_ms, "key": encrypted.key_seed}, PUBLIC_RSA_KEY).upper(),
        }
        payload = self._request(
            "POST",
            "/v7/login_by_verifycode",
            data=body,
            headers={"x-router": "login.user.kugou.com"},
            encrypt_type="android",
        )
        return self._merge_secure_payload(payload, encrypted.key_seed)

    def refresh_token(self, account: Account) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        encrypted = aes_encrypt({"clienttime": int(now_ms / 1000), "token": account.token}, LOGIN_TOKEN_AES_KEY, LOGIN_TOKEN_AES_IV)
        secure_seed = aes_encrypt({})
        assert isinstance(secure_seed, AesEncrypted)
        body = {
            "dfid": "-",
            "p3": encrypted,
            "plat": 1,
            "t1": 0,
            "t2": 0,
            "t3": "MCwwLDAsMCwwLDAsMCwwLDA=",
            "pk": rsa_encrypt_no_padding({"clienttime_ms": now_ms, "key": secure_seed.key_seed}, PUBLIC_RSA_KEY),
            "params": secure_seed.cipher_hex,
            "userid": account.user_id,
            "clienttime_ms": now_ms,
        }
        payload = self._request(
            "POST",
            "/v5/login_by_token",
            base_url="http://login.user.kugou.com",
            data=body,
            headers={"x-router": "login.user.kugou.com"},
            encrypt_type="android",
            cookie=self._cookie_for_account(account),
        )
        return self._merge_secure_payload(payload, secure_seed.key_seed)

    def get_user_detail(self, account: Account) -> dict[str, Any]:
        clienttime_seconds = int(time.time())
        body = {
            "visit_time": clienttime_seconds,
            "usertype": 1,
            "p": rsa_encrypt_no_padding(
                {"token": account.token, "clienttime": clienttime_seconds},
                PUBLIC_RSA_KEY,
            ).upper(),
            "userid": int(account.user_id),
        }
        return self._request(
            "POST",
            "/v3/get_my_info",
            data=body,
            params={"plat": 1},
            headers={"x-router": "usercenter.kugou.com"},
            encrypt_type="android",
            cookie=self._cookie_for_account(account),
        )

    def get_user_detail_by_credentials(self, user_id: str, token: str) -> dict[str, Any]:
        account = Account(user_id=str(user_id), token=str(token))
        return self.get_user_detail(account)

    def listen_song(self, account: Account) -> dict[str, Any]:
        return self._request(
            "POST",
            "/youth/v2/report/listen_song",
            data={"mixsongid": LISTEN_MIXSONG_ID},
            params={"clientver": 10566},
            headers={
                "User-Agent": LISTEN_USER_AGENT,
                "Content-Type": "application/json; charset=utf-8",
            },
            encrypt_type="android",
            cookie=self._cookie_for_account(account),
        )

    def claim_vip(self, account: Account) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        return self._request(
            "POST",
            "/youth/v1/ad/play_report",
            data={
                "ad_id": VIP_AD_ID,
                "play_end": now_ms,
                "play_start": now_ms - (VIP_AD_PLAY_SECONDS * 1000),
            },
            encrypt_type="android",
            cookie=self._cookie_for_account(account),
        )

    def get_vip_detail(self, account: Account) -> dict[str, Any]:
        return self._request(
            "GET",
            "/v1/get_union_vip",
            base_url="https://kugouvip.kugou.com",
            params={"busi_type": "concept"},
            encrypt_type="android",
            cookie=self._cookie_for_account(account),
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        base_url: str = "https://gateway.kugou.com",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        encrypt_type: str = "android",
        cookie: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cookie = cookie or {}
        dfid = str(cookie.get("dfid", "-"))
        md5_dfid = md5_hex(dfid)
        mid = f"{md5_dfid}{md5_dfid[:7]}"
        uuid = md5_hex(f"{dfid}{mid}")
        clienttime = int(time.time())
        request_params: dict[str, Any] = {
            "dfid": dfid,
            "mid": mid,
            "uuid": uuid,
            "appid": APP_ID,
            "clientver": CLIENT_VERSION,
            "userid": str(cookie.get("userid", "0")),
            "clienttime": clienttime,
        }
        if cookie.get("token"):
            request_params["token"] = str(cookie["token"])
        if params:
            request_params.update(params)
        payload_text = compact_json(data) if data is not None else ""
        if "signature" not in request_params:
            if encrypt_type == "web":
                request_params["signature"] = signature_web_params(request_params)
            else:
                request_params["signature"] = signature_android_params(request_params, payload_text)
        request_headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "dfid": dfid,
            "clienttime": str(request_params["clienttime"]),
            "mid": mid,
        }
        if headers:
            request_headers.update(headers)
        request_kwargs: dict[str, Any] = {
            "method": method.upper(),
            "url": f"{base_url}{path}",
            "params": request_params,
            "headers": request_headers,
            "timeout": self.timeout,
        }
        if data is not None:
            request_kwargs["data"] = payload_text
            request_headers.setdefault("Content-Type", "application/json")
        try:
            response = self.session.request(**request_kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ApiRequestError(f"请求 KuGou 失败: {exc}") from exc
        except ValueError as exc:
            raise ApiRequestError(f"KuGou 返回了无法解析的响应: {exc}") from exc

    @staticmethod
    def _merge_secure_payload(payload: dict[str, Any], key_seed: str) -> dict[str, Any]:
        data = payload.get("data")
        if isinstance(data, dict) and data.get("secu_params"):
            decrypted = aes_decrypt(str(data["secu_params"]), key_seed)
            if isinstance(decrypted, dict):
                payload["data"] = {**data, **decrypted}
            else:
                payload["data"]["token"] = decrypted
        return payload

    @staticmethod
    def _cookie_for_account(account: Account) -> dict[str, Any]:
        return {"token": account.token, "userid": account.user_id}
