from __future__ import annotations

import random
import time
from datetime import datetime
from typing import Callable

from kugou_signer.config.store import AccountStore
from kugou_signer.kugou.client import KugouClient
from kugou_signer.models import Account, AppConfig, ExecutionSettings, SignInResult

VIP_CLAIM_EXHAUSTED_CODES = {30002}
VIP_CLAIM_STOP_CODES = {30000}


class SignInService:
    def __init__(
        self,
        account_store: AccountStore,
        client: KugouClient,
        *,
        config: AppConfig | None = None,
        rng: random.Random | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.account_store = account_store
        self.client = client
        self.execution = (config.execution if config is not None else ExecutionSettings())
        self.rng = rng or random.Random()
        self.sleep = sleep

    def run_once(self, now: datetime, emit: Callable[[str], None] = print) -> list[SignInResult]:
        accounts = self.account_store.load()
        enabled_accounts = [account for account in accounts if account.enabled]
        if not enabled_accounts:
            emit("当前没有启用的账号，本次跳过。")
            return []

        results: list[SignInResult] = []
        updated_accounts: list[Account] = accounts[:]
        for account_index, account in enumerate(enabled_accounts):
            try:
                result = self._run_for_account(account, now, emit)
            except Exception as exc:
                result = SignInResult(
                    user_id=account.user_id,
                    nickname=account.nickname,
                    success=False,
                    messages=[f"执行异常: {exc}"],
                )
            results.append(result)
            for stored_index, existing in enumerate(updated_accounts):
                if existing.user_id == account.user_id:
                    updated_accounts[stored_index] = account
                    break
            self.account_store.save(updated_accounts)
            if account_index < len(enabled_accounts) - 1:
                delay_seconds = self._next_delay(
                    self.execution.account_gap_min_seconds,
                    self.execution.account_gap_max_seconds,
                )
                if delay_seconds > 0:
                    emit(f"等待下一个账号 {delay_seconds} 秒")
                    self.sleep(delay_seconds)
        return results

    def _run_for_account(self, account: Account, now: datetime, emit: Callable[[str], None]) -> SignInResult:
        display_name = account.nickname or account.user_id
        emit(f"开始处理账号 {display_name}")

        user_detail = self.client.get_user_detail(account)
        nickname = user_detail.get("data", {}).get("nickname")
        if not nickname:
            return SignInResult(
                user_id=account.user_id,
                nickname=account.nickname,
                success=False,
                messages=[f"token 失效或账号不存在: {user_detail}"],
            )

        account.nickname = str(nickname)
        messages: list[str] = []
        listen_success = True

        if now.weekday() == 6:
            refresh = self.client.refresh_token(account)
            refresh_token = refresh.get("data", {}).get("token")
            if refresh.get("status") == 1 and refresh_token and refresh_token != account.token:
                account.token = str(refresh_token)
                account.last_refresh_at = now.isoformat(timespec="seconds")
                messages.append("周日已刷新 token")

        listen = self.client.listen_song(account)
        listen_code = listen.get("error_code")
        if listen.get("status") == 1:
            messages.append("听歌领取成功")
        elif listen_code == 130012:
            messages.append("听歌奖励今日已领取")
        else:
            listen_success = False
            messages.append(f"听歌领取失败: {listen}")

        vip_claim_count = 0
        vip_success = True
        for index in range(8):
            vip_response = self.client.claim_vip(account)
            if vip_response.get("status") == 1:
                vip_claim_count += 1
                emit(f"{account.nickname} 第 {index + 1} 次广告领取成功")
                if index != 7:
                    delay_seconds = self._next_delay(
                        self.execution.vip_ad_gap_min_seconds,
                        self.execution.vip_ad_gap_max_seconds,
                    )
                    if delay_seconds > 0:
                        emit(f"{account.nickname} 广告领取间隔等待 {delay_seconds} 秒")
                        self.sleep(delay_seconds)
                continue

            error_code = vip_response.get("error_code")
            if error_code in VIP_CLAIM_EXHAUSTED_CODES:
                messages.append("今日广告领取次数已用完")
                break
            if error_code in VIP_CLAIM_STOP_CODES:
                if vip_claim_count > 0:
                    messages.append("广告领取提示过于频繁，视为今日已领完，停止重试")
                    break
                vip_success = False
                messages.append("广告领取过于频繁，本轮停止重试")
                break

            vip_success = False
            messages.append(f"广告领取失败: {vip_response}")
            break

        vip_details = self.client.get_vip_detail(account)
        vip_end_time = None
        if vip_details.get("status") == 1:
            vip_info = vip_details.get("data", {}).get("busi_vip", [])
            if isinstance(vip_info, list) and vip_info:
                vip_end_time = vip_info[0].get("vip_end_time")
        else:
            messages.append(f"VIP 信息获取失败: {vip_details}")

        account.last_run_at = now.isoformat(timespec="seconds")
        return SignInResult(
            user_id=account.user_id,
            nickname=account.nickname,
            success=vip_success and listen_success,
            vip_claim_count=vip_claim_count,
            vip_end_time=vip_end_time,
            messages=messages,
        )

    def _next_delay(self, minimum: int, maximum: int) -> int:
        if maximum <= 0 and minimum <= 0:
            return 0
        if minimum == maximum:
            return minimum
        return self.rng.randint(minimum, maximum)
