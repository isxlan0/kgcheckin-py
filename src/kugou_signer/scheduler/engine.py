from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from typing import Callable

from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.kugou.client import KugouClient
from kugou_signer.models import AppConfig, ScheduledRun
from kugou_signer.scheduler.commands import RuntimeCommandHandler
from kugou_signer.services.sign_in import SignInService
from kugou_signer.timezones import resolve_timezone


def parse_clock(value: str) -> dt_time:
    hour, minute = value.split(":", 1)
    return dt_time(hour=int(hour), minute=int(minute))


def format_seconds(total_seconds: int) -> str:
    if total_seconds < 0:
        total_seconds = 0
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def compute_next_run(now: datetime, config: AppConfig, rng: random.Random | None = None) -> ScheduledRun:
    generator = rng or random.Random()
    timezone = resolve_timezone(config.timezone)
    now_local = now.astimezone(timezone)
    schedule_time = parse_clock(config.schedule.time)

    today_candidate = _candidate_for_date(now_local.date(), schedule_time, config, generator, timezone)
    if today_candidate.run_at > now_local:
        return today_candidate
    return _candidate_for_date(now_local.date() + timedelta(days=1), schedule_time, config, generator, timezone)


def _candidate_for_date(
    target_date: date,
    schedule_time: dt_time,
    config: AppConfig,
    rng: random.Random,
    timezone,
) -> ScheduledRun:
    base = datetime.combine(target_date, schedule_time, tzinfo=timezone)
    jitter = rng.randint(config.schedule.jitter_min_seconds, config.schedule.jitter_max_seconds)
    return ScheduledRun(run_at=base + timedelta(seconds=jitter), base_time=config.schedule.time, jitter_seconds=jitter)


@dataclass(slots=True)
class RuntimeStatusSnapshot:
    scheduled: ScheduledRun
    remaining_seconds: int
    enabled_accounts: int
    total_accounts: int
    running: bool


class SchedulerController:
    def __init__(
        self,
        config_store: ConfigStore,
        account_store: AccountStore,
        *,
        client_factory: Callable[[], KugouClient] = KugouClient,
        sleep: Callable[[float], None] = time.sleep,
        now_provider: Callable[[object], datetime] | None = None,
    ) -> None:
        self.config_store = config_store
        self.account_store = account_store
        self.client_factory = client_factory
        self.sleep = sleep
        self.now_provider = now_provider
        self.rng = random.Random()
        self.command_handler = RuntimeCommandHandler(config_store, account_store)
        self.management = self.command_handler.controller
        self._state_lock = threading.RLock()
        self._run_lock = threading.Lock()
        self._config: AppConfig | None = None
        self._next_run: ScheduledRun | None = None
        self._running = False
        self.reload_schedule()

    def reload_schedule(self) -> str:
        config = self.config_store.load()
        timezone = resolve_timezone(config.timezone)
        scheduled = compute_next_run(self._now(timezone), config, self.rng)
        with self._state_lock:
            self._config = config
            self._next_run = scheduled
        return self.describe_next_run()

    def current_config(self) -> AppConfig:
        with self._state_lock:
            if self._config is not None:
                return self._config
        config = self.config_store.load()
        with self._state_lock:
            self._config = config
        return config

    def describe_next_run(self) -> str:
        config, scheduled, _ = self._state()
        return self._describe_next_run(scheduled, config)

    def status_snapshot(self) -> RuntimeStatusSnapshot:
        config, scheduled, running = self._state()
        timezone = resolve_timezone(config.timezone)
        now_local = self._now(timezone)
        remaining = math.ceil((scheduled.run_at - now_local).total_seconds())
        accounts = self.account_store.load()
        enabled_accounts = sum(1 for account in accounts if account.enabled)
        return RuntimeStatusSnapshot(
            scheduled=scheduled,
            remaining_seconds=remaining,
            enabled_accounts=enabled_accounts,
            total_accounts=len(accounts),
            running=running,
        )

    def is_due(self) -> bool:
        snapshot = self.status_snapshot()
        return not snapshot.running and snapshot.remaining_seconds <= 0

    def run_due(self, emit: Callable[[str], None] = print) -> bool:
        return self._run(emit=emit, manual=False)

    def run_now(self, emit: Callable[[str], None] = print) -> bool:
        return self._run(emit=emit, manual=True)

    @staticmethod
    def format_status(snapshot: RuntimeStatusSnapshot) -> str:
        state_label = "执行中" if snapshot.running else "待命"
        return (
            f"下一次签到: {snapshot.scheduled.run_at.strftime('%Y-%m-%d %H:%M:%S %Z')} | "
            f"倒计时 {format_seconds(snapshot.remaining_seconds)} | "
            f"抖动 {snapshot.scheduled.jitter_seconds:+d} 秒 | "
            f"账号 {snapshot.enabled_accounts}/{snapshot.total_accounts} | "
            f"状态 {state_label}"
        )

    def _run(self, *, emit: Callable[[str], None], manual: bool) -> bool:
        if not self._run_lock.acquire(blocking=False):
            if manual:
                emit("已有任务执行中，请稍候。")
            return False

        with self._state_lock:
            self._running = True

        client: KugouClient | None = None
        try:
            config = self.config_store.load()
            timezone = resolve_timezone(config.timezone)
            started_at = self._now(timezone)
            scheduled = self._current_scheduled()
            if not manual and scheduled.run_at > started_at:
                return False

            if manual:
                emit(f"[{started_at.strftime('%Y-%m-%d %H:%M:%S')}] 收到 /run 命令，立即执行签到")
            else:
                emit(f"[{started_at.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行签到")

            client = self.client_factory()
            service = SignInService(
                self.account_store,
                client,
                config=config,
                rng=self.rng,
                sleep=self.sleep,
            )
            results = service.run_once(started_at, emit)
            if results:
                for result in results:
                    emit(result.summary_line())
            emit("本轮任务已结束。")
            return True
        finally:
            if client is not None:
                client.close()
            try:
                self.reload_schedule()
            finally:
                with self._state_lock:
                    self._running = False
                self._run_lock.release()

    def _state(self) -> tuple[AppConfig, ScheduledRun, bool]:
        with self._state_lock:
            config = self._config
            scheduled = self._next_run
            running = self._running
        if config is None or scheduled is None:
            self.reload_schedule()
            with self._state_lock:
                config = self._config
                scheduled = self._next_run
                running = self._running
        assert config is not None
        assert scheduled is not None
        return config, scheduled, running

    def _current_scheduled(self) -> ScheduledRun:
        _, scheduled, _ = self._state()
        return scheduled

    def _now(self, timezone) -> datetime:
        if self.now_provider is not None:
            return self.now_provider(timezone)
        return datetime.now(timezone)

    @staticmethod
    def _describe_next_run(scheduled: ScheduledRun, config: AppConfig) -> str:
        return (
            f"已加载计划任务: 每天 {config.schedule.time} 执行, "
            f"随机波动 {config.schedule.jitter_min_seconds}..{config.schedule.jitter_max_seconds} 秒。"
            f" 下一次签到时间: {scheduled.run_at.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )


class SchedulerRunner:
    def __init__(
        self,
        config_store: ConfigStore,
        account_store: AccountStore,
        *,
        client_factory: Callable[[], KugouClient] = KugouClient,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config_store = config_store
        self.account_store = account_store
        self.client_factory = client_factory
        self.sleep = sleep

    def run_forever(self, emit: Callable[[str], None] = print) -> int:
        from kugou_signer.tui.app import SchedulerTUIApp

        controller = SchedulerController(
            self.config_store,
            self.account_store,
            client_factory=self.client_factory,
            sleep=self.sleep,
        )
        app = SchedulerTUIApp(controller)
        app.run()
        return 0
