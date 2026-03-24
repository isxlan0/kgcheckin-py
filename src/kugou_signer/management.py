from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from typing import Callable

from PIL import Image, ImageOps

from kugou_signer.accounts.service import AccountService
from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.kugou.client import KugouClient
from kugou_signer.models import Account
from kugou_signer.models import AppConfig, ExecutionSettings, ScheduleSettings

EmitFunc = Callable[[str], None]
InputFunc = Callable[[str], str]


class ManagementController:
    def __init__(
        self,
        config_store: ConfigStore,
        account_store: AccountStore,
        *,
        client_factory: Callable[[], KugouClient] = KugouClient,
    ) -> None:
        self.config_store = config_store
        self.account_store = account_store
        self.account_service = AccountService(account_store)
        self.client_factory = client_factory

    def list_accounts(self) -> list[Account]:
        return self.account_service.list_accounts()

    def show_accounts(self, emit: EmitFunc = print) -> None:
        accounts = self.list_accounts()
        if not accounts:
            emit("当前没有账号。")
            return
        for index, account in enumerate(accounts, start=1):
            emit(
                f"{index}. user_id={account.user_id} | nickname={account.nickname or '-'} | "
                f"enabled={account.enabled} | last_run={account.last_run_at or '-'}"
            )

    def add_account_by_qr(
        self,
        emit: EmitFunc = print,
        *,
        show_preview: bool = True,
        preview_columns: int = 28,
    ) -> bool:
        client = self.client_factory()
        try:
            payload = client.get_qr_code(self.config_store.paths.qrcode_dir)
            emit(f"二维码已保存到: {payload.file_path}")
            opened, detail = self.open_local_file(payload.file_path)
            if opened:
                emit("已尝试用系统图片查看器打开二维码 PNG，请优先扫描弹出的图片。")
            else:
                emit(f"自动打开二维码失败: {detail}")
            if show_preview:
                emit("终端中仅保留缩略预览，扫码请优先使用上面的 PNG 文件。")
                for line in self.render_qr_lines(payload.image_bytes, max_columns=preview_columns):
                    emit(line)
            emit("请使用酷狗 App 扫码并确认登录。")
            response = client.wait_for_qr_login(payload.key)
            data = response.get("data", {})
            detail = client.get_user_detail_by_credentials(str(data.get("userid")), str(data.get("token")))
            nickname = detail.get("data", {}).get("nickname") or ""
            account, created = self.account_service.save_login(
                str(data.get("userid")),
                str(data.get("token")),
                str(nickname),
            )
            action = "已新增" if created else "已更新"
            emit(f"{action}账号: {account.nickname or account.user_id}")
            return True
        finally:
            client.close()

    def send_phone_code(self, phone: str, *, emit: EmitFunc = print) -> bool:
        phone = str(phone).strip()
        if not phone:
            emit("手机号不能为空。")
            return False
        client = self.client_factory()
        try:
            send_result = client.send_captcha(phone)
            if send_result.get("status") != 1:
                emit(f"验证码发送失败: {send_result}")
                return False
            emit("验证码已发送，请输入收到的验证码。")
            return True
        finally:
            client.close()

    def confirm_phone_login(self, phone: str, code: str, *, emit: EmitFunc = print) -> bool:
        phone = str(phone).strip()
        code = str(code).strip()
        if not phone:
            emit("手机号不能为空。")
            return False
        if not code:
            emit("验证码不能为空。")
            return False
        client = self.client_factory()
        try:
            login = client.login_with_phone(phone, code)
            if login.get("status") != 1:
                emit(f"登录失败: {login}")
                return False
            data = login.get("data", {})
            detail = client.get_user_detail_by_credentials(str(data.get("userid")), str(data.get("token")))
            nickname = detail.get("data", {}).get("nickname") or ""
            account, created = self.account_service.save_login(
                str(data.get("userid")),
                str(data.get("token")),
                str(nickname),
            )
            action = "已新增" if created else "已更新"
            emit(f"{action}账号: {account.nickname or account.user_id}")
            return True
        finally:
            client.close()

    def add_account_by_phone(
        self,
        phone: str | None = None,
        code: str | None = None,
        *,
        emit: EmitFunc = print,
        input_func: InputFunc = input,
    ) -> None:
        if not phone:
            phone = input_func("请输入手机号: ").strip()
        if not phone:
            emit("手机号不能为空。")
            return
        if code:
            self.confirm_phone_login(phone, code, emit=emit)
            return
        if not self.send_phone_code(phone, emit=emit):
            return
        if not code:
            code = input_func("验证码: ").strip()
        self.confirm_phone_login(phone, code, emit=emit)

    def remove_account(
        self,
        user_id: str | None = None,
        *,
        emit: EmitFunc = print,
        input_func: InputFunc = input,
    ) -> bool:
        if not user_id:
            user_id = input_func("请输入要删除的 user_id: ").strip()
        if not user_id:
            emit("user_id 不能为空。")
            return False
        if self.account_service.remove_account(user_id):
            emit("账号已删除。")
            return True
        emit("未找到对应账号。")
        return False

    def show_schedule(self, emit: EmitFunc = print) -> AppConfig:
        config = self.config_store.load()
        emit(
            f"时区: {config.timezone}\n"
            f"每日执行时间: {config.schedule.time}\n"
            f"计划任务波动: {config.schedule.jitter_min_seconds}..{config.schedule.jitter_max_seconds} 秒\n"
            f"账号间隔: {config.execution.account_gap_min_seconds}..{config.execution.account_gap_max_seconds} 秒\n"
            f"广告间隔: {config.execution.vip_ad_gap_min_seconds}..{config.execution.vip_ad_gap_max_seconds} 秒"
        )
        return config

    def prompt_schedule_update(self, *, emit: EmitFunc = print, input_func: InputFunc = input) -> None:
        config = self.config_store.load()
        time_text = input_func(f"执行时间 HH:MM [{config.schedule.time}]: ").strip() or config.schedule.time
        jitter_text = input_func("随机波动秒数（输入 30 表示 -30..30） [0]: ").strip() or "0"
        try:
            jitter_seconds = int(jitter_text)
        except ValueError as exc:
            emit(f"配置保存失败: {exc}")
            return
        self.save_schedule(
            time_text,
            -abs(jitter_seconds),
            abs(jitter_seconds),
            emit=emit,
        )

    def save_schedule(
        self,
        time_text: str,
        jitter_min_seconds: int,
        jitter_max_seconds: int,
        *,
        emit: EmitFunc = print,
    ) -> None:
        current = self.config_store.load()
        next_config = AppConfig(
            timezone=current.timezone,
            schedule=ScheduleSettings(
                time=time_text,
                jitter_min_seconds=jitter_min_seconds,
                jitter_max_seconds=jitter_max_seconds,
            ),
            execution=current.execution,
        )
        self.config_store.save(next_config)
        emit("定时配置已更新。")

    def save_execution_settings(
        self,
        *,
        account_gap_min_seconds: int | None = None,
        account_gap_max_seconds: int | None = None,
        vip_ad_gap_min_seconds: int | None = None,
        vip_ad_gap_max_seconds: int | None = None,
        emit: EmitFunc = print,
    ) -> None:
        current = self.config_store.load()
        next_config = AppConfig(
            timezone=current.timezone,
            schedule=current.schedule,
            execution=ExecutionSettings(
                account_gap_min_seconds=(
                    current.execution.account_gap_min_seconds
                    if account_gap_min_seconds is None
                    else account_gap_min_seconds
                ),
                account_gap_max_seconds=(
                    current.execution.account_gap_max_seconds
                    if account_gap_max_seconds is None
                    else account_gap_max_seconds
                ),
                vip_ad_gap_min_seconds=(
                    current.execution.vip_ad_gap_min_seconds
                    if vip_ad_gap_min_seconds is None
                    else vip_ad_gap_min_seconds
                ),
                vip_ad_gap_max_seconds=(
                    current.execution.vip_ad_gap_max_seconds
                    if vip_ad_gap_max_seconds is None
                    else vip_ad_gap_max_seconds
                ),
            ),
        )
        self.config_store.save(next_config)
        emit("执行间隔配置已更新。")

    @staticmethod
    def render_qr_lines(image_bytes: bytes, *, max_columns: int | None = None) -> list[str]:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
        image = ManagementController._prepare_qr_preview(image, max_columns=max_columns)
        if image.height % 2:
            image = ImageOps.expand(image, border=(0, 0, 0, 1), fill=255)
        width, height = image.size
        lines: list[str] = []
        for y in range(0, height, 2):
            line = []
            for x in range(width):
                top_black = image.getpixel((x, y)) == 0
                bottom_black = image.getpixel((x, y + 1)) == 0
                if top_black and bottom_black:
                    line.append("█")
                elif top_black:
                    line.append("▀")
                elif bottom_black:
                    line.append("▄")
                else:
                    line.append(" ")
            lines.append("".join(line))
        return lines

    @staticmethod
    def _prepare_qr_preview(image: Image.Image, *, max_columns: int | None = None) -> Image.Image:
        inverted_bbox = ImageOps.invert(image).getbbox()
        if inverted_bbox is not None:
            image = image.crop(inverted_bbox)
        image = ImageOps.expand(image, border=4, fill=255)
        width_limit = max_columns if max_columns is not None else ManagementController._terminal_qr_width_limit()
        width_limit = max(width_limit, 24)
        if image.width <= width_limit:
            return image.convert("1")
        scale = width_limit / float(image.width)
        target_height = max(1, int(round(image.height * scale)))
        return image.resize((width_limit, target_height), Image.Resampling.NEAREST).convert("1")

    @staticmethod
    def _terminal_qr_width_limit() -> int:
        columns = shutil.get_terminal_size(fallback=(100, 40)).columns
        return min(max(columns - 6, 24), 56)

    @staticmethod
    def open_local_file(path) -> tuple[bool, str]:
        file_path = os.fspath(path)
        try:
            if os.name == "nt":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(["xdg-open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, file_path
        except Exception as exc:
            return False, str(exc)
