from __future__ import annotations

import shlex
from dataclasses import dataclass

from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.management import InputFunc, ManagementController


@dataclass(slots=True)
class CommandResult:
    action: str = "continue"


@dataclass(frozen=True, slots=True)
class CommandSpec:
    completion: str
    insert_text: str
    display: str
    description: str
    mode: str = "execute"

    def display_text(self, width: int = 32) -> str:
        padding = max(width - len(self.display), 2)
        return f"{self.display}{' ' * padding}{self.description}"


class RuntimeCommandHandler:
    def __init__(self, config_store: ConfigStore, account_store: AccountStore) -> None:
        self.config_store = config_store
        self.account_store = account_store
        self.controller = ManagementController(config_store, account_store)

    @staticmethod
    def countdown_hint() -> str:
        return "按 / 打开命令栏，Tab 补全，Esc 取消"

    def available_commands(self) -> list[str]:
        return [spec.display_text() for spec in self.command_specs()]

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return (
            CommandSpec("/help", "/help", "/help", "查看命令帮助"),
            CommandSpec("/list", "/list", "/list", "查看账号列表"),
            CommandSpec("/add", "/add ", "/add", "添加账号", mode="expand"),
            CommandSpec("/remove", "/remove ", "/remove", "删除账号", mode="expand"),
            CommandSpec("/schedule", "/schedule ", "/schedule", "计划任务设置", mode="expand"),
            CommandSpec("/settings", "/settings ", "/settings", "执行间隔设置", mode="expand"),
            CommandSpec("/run", "/run", "/run", "立即执行一轮签到"),
            CommandSpec("/quit", "/quit", "/quit", "退出守护进程"),
        )

    def matching_commands(self, current_text: str) -> list[CommandSpec]:
        normalized = self.normalize_command_text(current_text)
        if normalized in {"", "/"}:
            return list(self.command_specs())

        tokens = normalized.split()
        command = tokens[0]
        if command == "/add":
            return self._match_specs(
                normalized,
                [
                    CommandSpec("/add qr", "/add qr", "/add qr", "添加二维码账号"),
                    CommandSpec("/add phone", "/add phone ", "/add phone", "输入手机号后发送验证码", mode="expand"),
                    CommandSpec("/add 13800138000", "/add 13800138000", "/add <手机号>", "直接添加手机号账号"),
                ],
            )
        if command == "/remove":
            return self._remove_command_specs(normalized)
        if command == "/schedule":
            return self._schedule_command_specs(normalized)
        if command == "/settings":
            return self._settings_command_specs(normalized)
        return self._match_specs(normalized, self.command_specs())

    def suggestions(self, current_text: str) -> list[str]:
        matches = self.matching_commands(current_text)
        if not matches:
            return ["暂无匹配命令，输入 /help 查看帮助"]
        return [spec.display_text() for spec in matches]

    def prompt_and_handle(self, *, emit=print, input_func: InputFunc = input) -> CommandResult:
        emit("命令模式，输入 /help 查看可用命令。")
        raw = input_func("命令 > /").strip()
        if not raw:
            emit("已取消命令输入。")
            return CommandResult()
        return self.handle("/" + raw, emit=emit, input_func=input_func)

    def handle(self, raw: str, *, emit=print, input_func: InputFunc = input) -> CommandResult:
        text = self.normalize_command_text(raw)
        if not text:
            return CommandResult()
        if not text.startswith("/"):
            emit("命令必须以 / 开头，输入 /help 查看帮助。")
            return CommandResult()
        try:
            parts = shlex.split(text[1:])
        except ValueError as exc:
            emit(f"命令解析失败: {exc}")
            return CommandResult()
        if not parts:
            emit("请输入命令，输入 /help 查看帮助。")
            return CommandResult()

        command = parts[0].lower()
        if command in {"help", "h", "?"}:
            for line in self.available_commands():
                emit(line)
            return CommandResult()

        if command in {"list", "accounts"}:
            self.controller.show_accounts(emit=emit)
            return CommandResult()

        if command == "add":
            return self._handle_add(parts[1:], emit=emit, input_func=input_func)

        if command in {"remove", "del", "delete"}:
            if len(parts) < 2:
                emit("删除账号: /remove <user_id>")
                return CommandResult()
            self.controller.remove_account(parts[1], emit=emit, input_func=input_func)
            return CommandResult()

        if command == "schedule":
            return self._handle_schedule(parts[1:], emit=emit)

        if command == "settings":
            return self._handle_settings(parts[1:], emit=emit)

        if command in {"run", "now"}:
            emit("收到立即执行命令，准备开始签到。")
            return CommandResult(action="run_now")

        if command in {"quit", "exit"}:
            emit("收到退出命令，正在结束守护进程。")
            return CommandResult(action="quit")

        emit(f"未知命令: {text}，输入 /help 查看可用命令。")
        return CommandResult()

    def _handle_add(self, args: list[str], *, emit=print, input_func: InputFunc = input) -> CommandResult:
        if not args:
            emit("添加账号: /add qr 或 /add <手机号>")
            return CommandResult()
        if args[0].lower() == "qr":
            self.controller.add_account_by_qr(emit=emit)
            return CommandResult()
        if args[0].lower() == "phone":
            phone = args[1] if len(args) > 1 else None
            code = args[2] if len(args) > 2 else None
            self.controller.add_account_by_phone(phone=phone, code=code, emit=emit, input_func=input_func)
            return CommandResult()
        code = args[1] if len(args) > 1 else None
        self.controller.add_account_by_phone(phone=args[0], code=code, emit=emit, input_func=input_func)
        return CommandResult()

    def _handle_schedule(self, args: list[str], *, emit=print) -> CommandResult:
        if not args or args[0].lower() == "show":
            self.controller.show_schedule(emit=emit)
            return CommandResult()
        if args[0].lower() != "set" or len(args) < 2:
            emit(
                "定时命令: /schedule show | "
                "/schedule set time HH:MM | "
                "/schedule set jitter <秒数> | "
                "/schedule set HH:MM [波动秒数]"
            )
            return CommandResult()

        if args[1].lower() == "time":
            if len(args) < 3:
                emit("设置执行时间: /schedule set time HH:MM")
                return CommandResult()
            config = self.config_store.load()
            self.controller.save_schedule(
                args[2],
                config.schedule.jitter_min_seconds,
                config.schedule.jitter_max_seconds,
                emit=emit,
            )
            return CommandResult(action="reload_schedule")

        if args[1].lower() == "jitter":
            if len(args) < 3:
                emit("设置计划任务波动: /schedule set jitter <秒数>")
                return CommandResult()
            try:
                jitter = abs(int(args[2]))
            except ValueError as exc:
                emit(f"波动秒数无效: {exc}")
                return CommandResult()
            config = self.config_store.load()
            self.controller.save_schedule(config.schedule.time, -jitter, jitter, emit=emit)
            return CommandResult(action="reload_schedule")

        config = self.config_store.load()
        jitter = config.schedule.jitter_max_seconds
        if len(args) >= 3:
            try:
                jitter = abs(int(args[2]))
            except ValueError as exc:
                emit(f"波动秒数无效: {exc}")
                return CommandResult()
        self.controller.save_schedule(args[1], -jitter, jitter, emit=emit)
        return CommandResult(action="reload_schedule")

    def _handle_settings(self, args: list[str], *, emit=print) -> CommandResult:
        if not args or args[0].lower() == "show":
            self.controller.show_schedule(emit=emit)
            return CommandResult()
        if args[0].lower() != "set" or len(args) < 4:
            emit(
                "执行间隔命令: /settings show | "
                "/settings set account-gap <最小秒> <最大秒> | "
                "/settings set ad-gap <最小秒> <最大秒>"
            )
            return CommandResult()

        setting_name = args[1].lower()
        try:
            minimum = int(args[2])
            maximum = int(args[3])
        except ValueError as exc:
            emit(f"间隔秒数无效: {exc}")
            return CommandResult()

        if setting_name == "account-gap":
            self.controller.save_execution_settings(
                account_gap_min_seconds=minimum,
                account_gap_max_seconds=maximum,
                emit=emit,
            )
            return CommandResult()
        if setting_name == "ad-gap":
            self.controller.save_execution_settings(
                vip_ad_gap_min_seconds=minimum,
                vip_ad_gap_max_seconds=maximum,
                emit=emit,
            )
            return CommandResult()

        emit("未知执行间隔设置，仅支持 account-gap 或 ad-gap。")
        return CommandResult()

    @staticmethod
    def normalize_command_text(current_text: str) -> str:
        text = current_text.strip().lower()
        if not text:
            return "/"
        if text.startswith("/"):
            collapsed = text.lstrip("/")
            return "/" if not collapsed else f"/{collapsed}"
        return f"/{text}"

    @staticmethod
    def _match_specs(normalized: str, specs: list[CommandSpec] | tuple[CommandSpec, ...]) -> list[CommandSpec]:
        keyword = normalized[1:]
        matches: list[CommandSpec] = []
        for spec in specs:
            command_text = spec.completion.lower()
            description_text = spec.description.lower()
            if command_text.startswith(normalized) or keyword in description_text:
                matches.append(spec)
        return matches

    def find_exact_spec(self, current_text: str) -> CommandSpec | None:
        normalized = self.normalize_command_text(current_text)
        for spec in self.matching_commands(normalized):
            if spec.completion == normalized or spec.insert_text.rstrip() == normalized.rstrip():
                return spec
        return None

    def _remove_command_specs(self, normalized: str) -> list[CommandSpec]:
        account_specs = [
            CommandSpec(
                f"/remove {account.user_id}",
                f"/remove {account.user_id}",
                f"/remove {account.user_id}",
                f"删除账号 {account.nickname or account.user_id}",
            )
            for account in self.account_store.load()
        ]
        if not account_specs:
            account_specs.append(
                CommandSpec("/remove", "/remove ", "/remove", "当前没有可删除账号", mode="expand")
            )
        specs = [CommandSpec("/remove", "/remove ", "/remove", "删除账号，后续可选择具体账号", mode="expand"), *account_specs]
        return self._match_specs(normalized, specs)

    def _schedule_command_specs(self, normalized: str) -> list[CommandSpec]:
        config = self.config_store.load()
        specs = [
            CommandSpec("/schedule show", "/schedule show", "/schedule show", "查看当前计划任务"),
            CommandSpec(
                f"/schedule set time {config.schedule.time}",
                "/schedule set time ",
                "/schedule set time",
                "设置每日执行时间",
                mode="expand",
            ),
            CommandSpec(
                f"/schedule set jitter {config.schedule.jitter_max_seconds}",
                "/schedule set jitter ",
                "/schedule set jitter",
                "设置计划任务随机波动",
                mode="expand",
            ),
        ]
        return self._match_specs(normalized, specs)

    def _settings_command_specs(self, normalized: str) -> list[CommandSpec]:
        config = self.config_store.load()
        specs = [
            CommandSpec("/settings show", "/settings show", "/settings show", "查看账号与广告间隔配置"),
            CommandSpec(
                f"/settings set account-gap {config.execution.account_gap_min_seconds} {config.execution.account_gap_max_seconds}",
                "/settings set account-gap ",
                "/settings set account-gap",
                "设置多账号之间的等待区间",
                mode="expand",
            ),
            CommandSpec(
                f"/settings set ad-gap {config.execution.vip_ad_gap_min_seconds} {config.execution.vip_ad_gap_max_seconds}",
                "/settings set ad-gap ",
                "/settings set ad-gap",
                "设置每次广告领取之间的等待区间",
                mode="expand",
            ),
        ]
        return self._match_specs(normalized, specs)
