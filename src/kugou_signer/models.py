from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kugou_signer.constants import DEFAULT_SCHEDULE_TIME, DEFAULT_TIMEZONE, VIP_AD_DELAY_SECONDS


@dataclass(slots=True)
class Account:
    user_id: str
    token: str
    nickname: str = ""
    enabled: bool = True
    last_refresh_at: str | None = None
    last_run_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Account":
        user_id = str(data.get("user_id") or data.get("userid") or "").strip()
        token = str(data.get("token") or "").strip()
        if not user_id or not token:
            raise ValueError("账号记录缺少 user_id 或 token")
        return cls(
            user_id=user_id,
            token=token,
            nickname=str(data.get("nickname") or ""),
            enabled=bool(data.get("enabled", True)),
            last_refresh_at=data.get("last_refresh_at"),
            last_run_at=data.get("last_run_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "token": self.token,
            "nickname": self.nickname,
            "enabled": self.enabled,
            "last_refresh_at": self.last_refresh_at,
            "last_run_at": self.last_run_at,
        }


@dataclass(slots=True)
class ScheduleSettings:
    time: str = DEFAULT_SCHEDULE_TIME
    jitter_min_seconds: int = 0
    jitter_max_seconds: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleSettings":
        return cls(
            time=str(data.get("time", DEFAULT_SCHEDULE_TIME)),
            jitter_min_seconds=int(data.get("jitter_min_seconds", 0)),
            jitter_max_seconds=int(data.get("jitter_max_seconds", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.time,
            "jitter_min_seconds": self.jitter_min_seconds,
            "jitter_max_seconds": self.jitter_max_seconds,
        }


@dataclass(slots=True)
class ExecutionSettings:
    account_gap_min_seconds: int = 0
    account_gap_max_seconds: int = 0
    vip_ad_gap_min_seconds: int = VIP_AD_DELAY_SECONDS
    vip_ad_gap_max_seconds: int = VIP_AD_DELAY_SECONDS

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionSettings":
        return cls(
            account_gap_min_seconds=int(data.get("account_gap_min_seconds", 0)),
            account_gap_max_seconds=int(data.get("account_gap_max_seconds", 0)),
            vip_ad_gap_min_seconds=int(data.get("vip_ad_gap_min_seconds", VIP_AD_DELAY_SECONDS)),
            vip_ad_gap_max_seconds=int(data.get("vip_ad_gap_max_seconds", VIP_AD_DELAY_SECONDS)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_gap_min_seconds": self.account_gap_min_seconds,
            "account_gap_max_seconds": self.account_gap_max_seconds,
            "vip_ad_gap_min_seconds": self.vip_ad_gap_min_seconds,
            "vip_ad_gap_max_seconds": self.vip_ad_gap_max_seconds,
        }


@dataclass(slots=True)
class AppConfig:
    timezone: str = DEFAULT_TIMEZONE
    schedule: ScheduleSettings = field(default_factory=ScheduleSettings)
    execution: ExecutionSettings = field(default_factory=ExecutionSettings)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            timezone=str(data.get("timezone", DEFAULT_TIMEZONE)),
            schedule=ScheduleSettings.from_dict(data.get("schedule", {})),
            execution=ExecutionSettings.from_dict(data.get("execution", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timezone": self.timezone,
            "schedule": self.schedule.to_dict(),
            "execution": self.execution.to_dict(),
        }


@dataclass(slots=True)
class ScheduledRun:
    run_at: datetime
    base_time: str
    jitter_seconds: int


@dataclass(slots=True)
class SignInResult:
    user_id: str
    nickname: str
    success: bool
    vip_claim_count: int = 0
    vip_end_time: str | None = None
    messages: list[str] = field(default_factory=list)

    def summary_line(self) -> str:
        name = self.nickname or self.user_id
        status = "成功" if self.success else "失败"
        details = f"{name} | {status}"
        if self.vip_claim_count:
            details += f" | 领取次数 {self.vip_claim_count}"
        if self.vip_end_time:
            details += f" | VIP 到期 {self.vip_end_time}"
        if self.messages:
            details += f" | {'; '.join(self.messages)}"
        return details
