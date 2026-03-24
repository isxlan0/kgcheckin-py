from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable

from kugou_signer.config.paths import RepoPaths
from kugou_signer.config.toml_compat import dumps as dump_toml
from kugou_signer.config.toml_compat import loads as load_toml
from kugou_signer.exceptions import ConfigError
from kugou_signer.models import Account, AppConfig


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


class ConfigStore:
    def __init__(self, paths: RepoPaths | None = None) -> None:
        self.paths = paths or RepoPaths.resolve()

    def ensure_layout(self) -> None:
        self.paths.config_dir.mkdir(parents=True, exist_ok=True)
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.qrcode_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppConfig:
        self.ensure_layout()
        if not self.paths.config_file.exists():
            config = AppConfig()
            self.save(config)
            return config
        try:
            raw = self.paths.config_file.read_text(encoding="utf-8")
            config = AppConfig.from_dict(load_toml(raw))
        except Exception as exc:  # pragma: no cover - validation path
            raise ConfigError(f"配置文件读取失败: {exc}") from exc
        self._validate(config)
        return config

    def save(self, config: AppConfig) -> None:
        self.ensure_layout()
        self._validate(config)
        _write_text(self.paths.config_file, dump_toml(config.to_dict()))

    @staticmethod
    def _validate(config: AppConfig) -> None:
        parts = config.schedule.time.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ConfigError("定时格式必须为 HH:MM")
        hour, minute = (int(parts[0]), int(parts[1]))
        if hour not in range(24) or minute not in range(60):
            raise ConfigError("定时时间超出有效范围")
        if config.schedule.jitter_min_seconds > config.schedule.jitter_max_seconds:
            raise ConfigError("jitter_min_seconds 不能大于 jitter_max_seconds")
        if config.execution.account_gap_min_seconds < 0 or config.execution.account_gap_max_seconds < 0:
            raise ConfigError("账号间隔秒数不能为负数")
        if config.execution.vip_ad_gap_min_seconds < 0 or config.execution.vip_ad_gap_max_seconds < 0:
            raise ConfigError("广告间隔秒数不能为负数")
        if config.execution.account_gap_min_seconds > config.execution.account_gap_max_seconds:
            raise ConfigError("account_gap_min_seconds 不能大于 account_gap_max_seconds")
        if config.execution.vip_ad_gap_min_seconds > config.execution.vip_ad_gap_max_seconds:
            raise ConfigError("vip_ad_gap_min_seconds 不能大于 vip_ad_gap_max_seconds")


class AccountStore:
    def __init__(self, paths: RepoPaths | None = None) -> None:
        self.paths = paths or RepoPaths.resolve()

    def ensure_layout(self) -> None:
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.qrcode_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[Account]:
        self.ensure_layout()
        if not self.paths.accounts_file.exists():
            accounts = self._load_from_env()
            if accounts:
                self.save(accounts)
            return accounts
        raw = self.paths.accounts_file.read_text(encoding="utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"账号文件不是有效 JSON: {exc}") from exc
        if not isinstance(payload, list):
            raise ConfigError("账号文件必须是数组")
        accounts = [Account.from_dict(item) for item in payload]
        if self._needs_migration(payload):
            self.save(accounts)
        return accounts

    def save(self, accounts: Iterable[Account]) -> None:
        self.ensure_layout()
        payload = [account.to_dict() for account in accounts]
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        _write_text(self.paths.accounts_file, content)

    def upsert(self, account: Account) -> tuple[Account, bool]:
        accounts = self.load()
        for index, existing in enumerate(accounts):
            if existing.user_id == account.user_id:
                accounts[index] = account
                self.save(accounts)
                return account, False
        accounts.append(account)
        self.save(accounts)
        return account, True

    def remove(self, user_id: str) -> bool:
        accounts = self.load()
        next_accounts = [account for account in accounts if account.user_id != str(user_id)]
        changed = len(next_accounts) != len(accounts)
        if changed:
            self.save(next_accounts)
        return changed

    def _load_from_env(self) -> list[Account]:
        payload = os.environ.get("USERINFO")
        if not payload:
            return []
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"环境变量 USERINFO 不是有效 JSON: {exc}") from exc
        if not isinstance(data, list):
            raise ConfigError("环境变量 USERINFO 必须是数组")
        return [Account.from_dict(item) for item in data]

    @staticmethod
    def _needs_migration(payload: list[object]) -> bool:
        for item in payload:
            if isinstance(item, dict) and ("userid" in item or "user_id" not in item):
                return True
        return False
