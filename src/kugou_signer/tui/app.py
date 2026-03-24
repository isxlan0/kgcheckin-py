from __future__ import annotations

from dataclasses import dataclass
import shlex
import threading
from typing import Callable

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from kugou_signer.scheduler.commands import CommandResult, CommandSpec, RuntimeCommandHandler
from kugou_signer.scheduler.engine import SchedulerController


class CommandInput(Input):
    class Navigate(Message):
        def __init__(self, delta: int) -> None:
            self.delta = delta
            super().__init__()

    class Complete(Message):
        pass

    class Cancel(Message):
        pass

    def on_key(self, event: events.Key) -> None:
        if event.key == "down":
            event.prevent_default()
            event.stop()
            self.post_message(self.Navigate(1))
            return
        if event.key == "up":
            event.prevent_default()
            event.stop()
            self.post_message(self.Navigate(-1))
            return
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self.post_message(self.Complete())
            return
        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self.post_message(self.Cancel())


class CommandPaletteScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center middle;
        background: rgba(6, 10, 16, 0.78);
    }

    #command-panel {
        width: 88;
        max-width: 92%;
        height: auto;
        background: #0f1722;
        border: round #2f89ff;
        padding: 1 1 0 1;
    }

    #command-title {
        color: #d8e6fb;
        text-style: bold;
        padding: 0 1 1 1;
    }

    #command-input-row {
        height: 3;
        width: 100%;
        border: round #23364d;
        background: #09111b;
        padding: 0 1;
    }

    #command-prompt {
        width: 3;
        color: #6ab5ff;
        content-align: center middle;
        text-style: bold;
    }

    #command-input {
        width: 1fr;
        border: none;
        background: transparent;
    }

    #command-options {
        height: 14;
        border: none;
        margin-top: 1;
        background: transparent;
    }

    #command-help {
        color: #8192a8;
        padding: 0 1 1 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "取消", show=False)]

    def __init__(self, handler: RuntimeCommandHandler, *, initial_text: str = "/") -> None:
        super().__init__()
        self.handler = handler
        self.initial_text = initial_text
        self._matches: list[CommandSpec] = []

    def compose(self) -> ComposeResult:
        with Container(id="command-panel"):
            yield Static("命令栏", id="command-title")
            with Horizontal(id="command-input-row"):
                yield Static("›", id="command-prompt")
                yield CommandInput(
                    value=self.initial_text,
                    placeholder="/help 查看命令，Tab 补全，Esc 取消",
                    id="command-input",
                )
            yield OptionList(id="command-options")
            yield Static("↑/↓ 选择  Tab 补全  Enter 执行  Esc 取消", id="command-help")

    def on_mount(self) -> None:
        command_input = self.query_one("#command-input", CommandInput)
        command_input.focus()
        command_input.cursor_position = len(command_input.value)
        self._refresh_matches(command_input.value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_command_input_navigate(self, message: CommandInput.Navigate) -> None:
        options = self.query_one("#command-options", OptionList)
        if message.delta > 0:
            options.action_cursor_down()
        else:
            options.action_cursor_up()

    def on_command_input_complete(self, _: CommandInput.Complete) -> None:
        self._apply_highlighted()

    def on_command_input_cancel(self, _: CommandInput.Cancel) -> None:
        self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "command-input":
            self._refresh_matches(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input":
            return
        current = self.handler.normalize_command_text(event.value)
        highlighted = self._highlighted_spec()
        if highlighted is not None and highlighted.mode == "expand" and current.rstrip() == highlighted.completion.rstrip():
            self._apply_spec(highlighted)
            return
        if current in {"", "/"} and highlighted is not None:
            self._apply_spec(highlighted)
            return
        self.dismiss(current)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.disabled:
            return
        if 0 <= event.option_index < len(self._matches):
            self._apply_spec(self._matches[event.option_index])

    def _refresh_matches(self, current_text: str) -> None:
        self._matches = self.handler.matching_commands(current_text)
        width = max((len(spec.display) for spec in self._matches), default=12) + 4
        options = self.query_one("#command-options", OptionList)
        options.clear_options()
        if not self._matches:
            options.add_option(Option("没有匹配命令，按 Esc 取消", disabled=True))
            return
        options.add_options(Option(spec.display_text(width)) for spec in self._matches)

    def _highlighted_spec(self) -> CommandSpec | None:
        options = self.query_one("#command-options", OptionList)
        highlighted = options.highlighted
        if highlighted is None or not (0 <= highlighted < len(self._matches)):
            return None
        return self._matches[highlighted]

    def _apply_highlighted(self) -> None:
        spec = self._highlighted_spec()
        if spec is not None:
            self._apply_spec(spec)

    def _apply_spec(self, spec: CommandSpec) -> None:
        if spec.mode == "expand":
            command_input = self.query_one("#command-input", CommandInput)
            command_input.value = spec.insert_text
            command_input.cursor_position = len(command_input.value)
            self._refresh_matches(command_input.value)
            return
        self.dismiss(spec.completion)


class SingleInputScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    SingleInputScreen {
        align: center middle;
        background: rgba(6, 10, 16, 0.78);
    }

    #single-panel {
        width: 62;
        max-width: 92%;
        background: #0f1722;
        border: round #2f89ff;
        padding: 1 1 0 1;
    }

    .form-title {
        color: #d8e6fb;
        text-style: bold;
        padding: 0 1 1 1;
    }

    .form-help {
        color: #8192a8;
        padding: 0 1 1 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "取消", show=False)]

    def __init__(self, *, title: str, placeholder: str, initial_value: str = "", help_text: str = "") -> None:
        super().__init__()
        self.title = title
        self.placeholder = placeholder
        self.initial_value = initial_value
        self.help_text = help_text

    def compose(self) -> ComposeResult:
        with Container(id="single-panel"):
            yield Static(self.title, classes="form-title")
            if self.help_text:
                yield Static(self.help_text, classes="form-help")
            yield Input(value=self.initial_value, placeholder=self.placeholder, id="single-input")

    def on_mount(self) -> None:
        input_widget = self.query_one("#single-input", Input)
        input_widget.focus()
        input_widget.cursor_position = len(input_widget.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "single-input":
            self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)


class PairInputScreen(ModalScreen[tuple[str, str] | None]):
    DEFAULT_CSS = """
    PairInputScreen {
        align: center middle;
        background: rgba(6, 10, 16, 0.78);
    }

    #pair-panel {
        width: 68;
        max-width: 92%;
        background: #0f1722;
        border: round #2f89ff;
        padding: 1 1 0 1;
    }

    .form-title {
        color: #d8e6fb;
        text-style: bold;
        padding: 0 1 1 1;
    }

    .form-help {
        color: #8192a8;
        padding: 0 1 1 1;
    }

    .field-label {
        color: #9bb6d6;
        padding: 0 1;
    }

    .field-input {
        margin-bottom: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "取消", show=False)]

    def __init__(
        self,
        *,
        title: str,
        first_label: str,
        second_label: str,
        first_placeholder: str,
        second_placeholder: str,
        first_value: str = "",
        second_value: str = "",
        help_text: str = "",
        focus_second: bool = False,
        submit_on_first_submit: bool = False,
    ) -> None:
        super().__init__()
        self.title = title
        self.first_label = first_label
        self.second_label = second_label
        self.first_placeholder = first_placeholder
        self.second_placeholder = second_placeholder
        self.first_value = first_value
        self.second_value = second_value
        self.help_text = help_text
        self.focus_second = focus_second
        self.submit_on_first_submit = submit_on_first_submit

    def compose(self) -> ComposeResult:
        with Container(id="pair-panel"):
            yield Static(self.title, classes="form-title")
            if self.help_text:
                yield Static(self.help_text, classes="form-help")
            yield Static(self.first_label, classes="field-label")
            yield Input(value=self.first_value, placeholder=self.first_placeholder, id="pair-first", classes="field-input")
            yield Static(self.second_label, classes="field-label")
            yield Input(value=self.second_value, placeholder=self.second_placeholder, id="pair-second", classes="field-input")

    def on_mount(self) -> None:
        first = self.query_one("#pair-first", Input)
        second = self.query_one("#pair-second", Input)
        if self.focus_second:
            second.focus()
            second.cursor_position = len(second.value)
        else:
            first.focus()
            first.cursor_position = len(first.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "pair-first":
            if self.submit_on_first_submit:
                self.dismiss(self.values())
                return
            self.query_one("#pair-second", Input).focus()
            return
        if event.input.id == "pair-second":
            self.dismiss(self.values())

    def values(self) -> tuple[str, str]:
        return (
            self.query_one("#pair-first", Input).value.strip(),
            self.query_one("#pair-second", Input).value.strip(),
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


@dataclass(slots=True)
class PhoneLoginResult:
    action: str
    phone: str
    code: str = ""


class PhoneLoginScreen(ModalScreen[PhoneLoginResult | None]):
    DEFAULT_CSS = """
    PhoneLoginScreen {
        align: center middle;
        background: rgba(6, 10, 16, 0.78);
    }

    #phone-panel {
        width: 68;
        max-width: 92%;
        background: #0f1722;
        border: round #2f89ff;
        padding: 1 1 0 1;
    }

    .form-title {
        color: #d8e6fb;
        text-style: bold;
        padding: 0 1 1 1;
    }

    .form-help {
        color: #8192a8;
        padding: 0 1 1 1;
    }

    .field-label {
        color: #9bb6d6;
        padding: 0 1;
    }

    .field-input {
        margin-bottom: 1;
    }

    #resend-button {
        margin-bottom: 1;
        width: auto;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "取消", show=False)]

    def __init__(self, *, phone: str = "", code: str = "", awaiting_code: bool = False) -> None:
        super().__init__()
        self.phone = phone
        self.code = code
        self.awaiting_code = awaiting_code
        self._remaining_seconds = 60 if awaiting_code else 0

    def compose(self) -> ComposeResult:
        with Container(id="phone-panel"):
            yield Static("手机号登录", classes="form-title")
            yield Static(
                "第一次只填手机号后回车即可发送验证码；收到验证码后填写第二项并提交登录。",
                id="phone-help",
                classes="form-help",
            )
            yield Static("手机号", classes="field-label")
            yield Input(value=self.phone, placeholder="手机号", id="phone-input", classes="field-input")
            yield Static("验证码", classes="field-label")
            yield Input(value=self.code, placeholder="验证码", id="code-input", classes="field-input")
            if self.awaiting_code:
                yield Button("", id="resend-button", disabled=True)

    def on_mount(self) -> None:
        phone_input = self.query_one("#phone-input", Input)
        code_input = self.query_one("#code-input", Input)
        if self.awaiting_code:
            code_input.focus()
            code_input.cursor_position = len(code_input.value)
            self._update_resend_button()
            self.set_interval(1.0, self._tick_resend_countdown)
            return
        phone_input.focus()
        phone_input.cursor_position = len(phone_input.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        phone = self.query_one("#phone-input", Input).value.strip()
        code = self.query_one("#code-input", Input).value.strip()
        if event.input.id == "phone-input" and not self.awaiting_code:
            self.dismiss(PhoneLoginResult(action="send", phone=phone))
            return
        if event.input.id == "phone-input":
            self.query_one("#code-input", Input).focus()
            return
        if not code:
            self.query_one("#phone-help", Static).update("请输入验证码后再提交，或等待按钮恢复后重新发送。")
            return
        self.dismiss(PhoneLoginResult(action="login", phone=phone, code=code))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "resend-button" or event.button.disabled:
            return
        phone = self.query_one("#phone-input", Input).value.strip()
        self.dismiss(PhoneLoginResult(action="resend", phone=phone))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _tick_resend_countdown(self) -> None:
        if self._remaining_seconds <= 0:
            return
        self._remaining_seconds -= 1
        self._update_resend_button()

    def _update_resend_button(self) -> None:
        button = self.query_one("#resend-button", Button)
        if self._remaining_seconds > 0:
            button.label = f"{self._remaining_seconds} 秒后可重发"
            button.disabled = True
            return
        button.label = "重新发送验证码"
        button.disabled = False


class SchedulerTUIApp(App[None]):
    CSS = """
    Screen {
        layout: vertical;
        background: #0b1118;
        color: #d8e6fb;
    }

    #log {
        height: 1fr;
        border: none;
        padding: 1 1 0 1;
        background: #0b1118;
    }

    #status-bar {
        height: 1;
        padding: 0 1;
        background: #122132;
        color: #d8e6fb;
        text-style: bold;
    }

    Footer {
        background: #09111b;
        color: #9bb6d6;
    }
    """

    BINDINGS = [
        Binding("/", "open_commands", "命令", show=True),
        Binding("f5", "run_now", "立即签到", show=True),
        Binding("ctrl+c", "quit", "退出", show=True, priority=True),
    ]

    def __init__(self, controller: SchedulerController) -> None:
        super().__init__()
        self.controller = controller
        self._run_thread_active = False
        self._run_thread_lock = threading.Lock()

    def compose(self) -> ComposeResult:
        yield RichLog(id="log", wrap=True, highlight=False, markup=False)
        yield Static(id="status-bar")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.write_log(self.controller.describe_next_run())
        self.write_log("命令栏已启用：按 / 打开，↑/↓ 选择，Tab 补全，Esc 取消。")
        self._refresh_status()
        self.set_interval(1.0, self._refresh_status)

    def action_open_commands(self) -> None:
        self.push_screen(
            CommandPaletteScreen(self.controller.command_handler, initial_text="/"),
            self._handle_command_result,
        )

    def action_run_now(self) -> None:
        self._start_sign_in(manual=True)

    def action_quit(self) -> None:
        self.exit()

    def write_log(self, message: str) -> None:
        log = self.query_one("#log", RichLog)
        lines = str(message).splitlines() or [""]
        for line in lines:
            log.write(line)

    def _thread_emit(self, message: str) -> None:
        try:
            self.call_from_thread(self.write_log, message)
        except Exception:
            pass

    def _refresh_status(self) -> None:
        snapshot = self.controller.status_snapshot()
        self.query_one("#status-bar", Static).update(self.controller.format_status(snapshot))
        if snapshot.remaining_seconds <= 0 and not snapshot.running:
            self._start_sign_in(manual=False)

    def _handle_command_result(self, command_text: str | None) -> None:
        if not command_text:
            return
        normalized = self.controller.command_handler.normalize_command_text(command_text)
        if self._handle_incomplete_command(normalized):
            return
        self._execute_command(normalized)

    def _execute_command(self, command_text: str) -> None:
        def worker() -> CommandResult:
            return self.controller.command_handler.handle(command_text, emit=self._thread_emit)

        self._run_background("执行命令", worker, self._after_command)

    def _after_command(self, result: object) -> None:
        if not isinstance(result, CommandResult):
            self._refresh_status()
            return
        if result.action == "reload_schedule":
            self.write_log(self.controller.reload_schedule())
        elif result.action == "run_now":
            self._start_sign_in(manual=True)
        elif result.action == "quit":
            self.exit()
            return
        self._refresh_status()

    def _handle_incomplete_command(self, command_text: str) -> bool:
        try:
            parts = shlex.split(command_text[1:])
        except ValueError:
            return False
        if not parts:
            return False

        command = parts[0]
        args = parts[1:]

        if command == "add":
            return self._handle_incomplete_add(args)
        if command == "remove" and not args:
            self.push_screen(
                CommandPaletteScreen(self.controller.command_handler, initial_text="/remove "),
                self._handle_command_result,
            )
            return True
        if command == "schedule":
            return self._handle_incomplete_schedule(args)
        if command == "settings":
            return self._handle_incomplete_settings(args)
        return False

    def _handle_incomplete_add(self, args: list[str]) -> bool:
        if not args:
            self.push_screen(
                CommandPaletteScreen(self.controller.command_handler, initial_text="/add "),
                self._handle_command_result,
            )
            return True
        if args[0] == "qr":
            return False
        if args[0] == "phone":
            phone = args[1] if len(args) > 1 else ""
            code = args[2] if len(args) > 2 else ""
            if code:
                return False
            self._open_phone_screen(phone=phone)
            return True
        phone = args[0]
        code = args[1] if len(args) > 1 else ""
        if code:
            return False
        self._open_phone_screen(phone=phone)
        return True

    def _handle_incomplete_schedule(self, args: list[str]) -> bool:
        config = self.controller.current_config()
        if not args:
            self.push_screen(
                CommandPaletteScreen(self.controller.command_handler, initial_text="/schedule "),
                self._handle_command_result,
            )
            return True
        if args[0] != "set" or len(args) >= 3:
            return False
        if len(args) == 1:
            self.push_screen(
                CommandPaletteScreen(self.controller.command_handler, initial_text="/schedule set "),
                self._handle_command_result,
            )
            return True
        if args[1] == "time":
            self.push_screen(
                SingleInputScreen(
                    title="设置执行时间",
                    placeholder="HH:MM",
                    initial_value=config.schedule.time,
                    help_text="例如 00:01，提交后立即刷新下一次签到时间。",
                ),
                self._handle_schedule_time_result,
            )
            return True
        if args[1] == "jitter":
            self.push_screen(
                SingleInputScreen(
                    title="设置计划任务波动",
                    placeholder="秒数",
                    initial_value=str(abs(config.schedule.jitter_max_seconds)),
                    help_text="输入 30 表示 -30..30 秒。",
                ),
                self._handle_schedule_jitter_result,
            )
            return True
        return False

    def _handle_incomplete_settings(self, args: list[str]) -> bool:
        config = self.controller.current_config()
        if not args:
            self.push_screen(
                CommandPaletteScreen(self.controller.command_handler, initial_text="/settings "),
                self._handle_command_result,
            )
            return True
        if args[0] != "set" or len(args) >= 4:
            return False
        if len(args) == 1:
            self.push_screen(
                CommandPaletteScreen(self.controller.command_handler, initial_text="/settings set "),
                self._handle_command_result,
            )
            return True
        if args[1] == "account-gap":
            self.push_screen(
                PairInputScreen(
                    title="设置多账号间隔",
                    first_label="最小秒数",
                    second_label="最大秒数",
                    first_placeholder="最小秒数",
                    second_placeholder="最大秒数",
                    first_value=args[2] if len(args) > 2 else str(config.execution.account_gap_min_seconds),
                    second_value=str(config.execution.account_gap_max_seconds),
                    help_text="影响多账号模式下，下一个账号开始领取前的等待区间。",
                ),
                self._handle_account_gap_result,
            )
            return True
        if args[1] == "ad-gap":
            self.push_screen(
                PairInputScreen(
                    title="设置广告领取间隔",
                    first_label="最小秒数",
                    second_label="最大秒数",
                    first_placeholder="最小秒数",
                    second_placeholder="最大秒数",
                    first_value=args[2] if len(args) > 2 else str(config.execution.vip_ad_gap_min_seconds),
                    second_value=str(config.execution.vip_ad_gap_max_seconds),
                    help_text="影响每次广告领取之间的随机等待区间。",
                ),
                self._handle_ad_gap_result,
            )
            return True
        return False

    def _handle_schedule_time_result(self, value: str | None) -> None:
        if value:
            self._execute_command(f"/schedule set time {value}")

    def _handle_schedule_jitter_result(self, value: str | None) -> None:
        if value:
            self._execute_command(f"/schedule set jitter {value}")

    def _handle_account_gap_result(self, result: tuple[str, str] | None) -> None:
        if result is None:
            return
        minimum, maximum = result
        self._execute_command(f"/settings set account-gap {minimum} {maximum}")

    def _handle_ad_gap_result(self, result: tuple[str, str] | None) -> None:
        if result is None:
            return
        minimum, maximum = result
        self._execute_command(f"/settings set ad-gap {minimum} {maximum}")

    def _open_phone_screen(
        self,
        *,
        phone: str = "",
        code: str = "",
        awaiting_code: bool = False,
    ) -> None:
        self.push_screen(
            PhoneLoginScreen(
                phone=phone,
                code=code,
                awaiting_code=awaiting_code,
            ),
            self._handle_phone_screen_result,
        )

    def _handle_phone_screen_result(self, result: PhoneLoginResult | None) -> None:
        if result is None:
            return
        phone = result.phone.strip()
        if not phone:
            self.write_log("手机号不能为空。")
            return
        if result.action == "login":
            self._execute_command(f"/add phone {phone} {result.code.strip()}")
            return

        def worker() -> bool:
            return self.controller.management.send_phone_code(phone, emit=self._thread_emit)

        def reopen(success: bool) -> None:
            if success:
                self._open_phone_screen(phone=phone, awaiting_code=True)

        if result.action in {"send", "resend"}:
            self._run_background("发送验证码", worker, reopen)

    def _start_sign_in(self, *, manual: bool) -> None:
        with self._run_thread_lock:
            if self._run_thread_active:
                if manual:
                    self.write_log("已有任务执行中，请稍候。")
                return
            self._run_thread_active = True

        def worker() -> bool:
            if manual:
                return self.controller.run_now(emit=self._thread_emit)
            return self.controller.run_due(emit=self._thread_emit)

        def finalize(_: bool) -> None:
            with self._run_thread_lock:
                self._run_thread_active = False
            self._refresh_status()

        self._run_background("执行签到", worker, finalize)

    def _run_background(
        self,
        label: str,
        worker: Callable[[], object],
        on_complete: Callable[[object], None] | None = None,
    ) -> None:
        def runner() -> None:
            try:
                result = worker()
            except Exception as exc:
                self._thread_emit(f"{label}失败: {exc}")
                result = None
            if on_complete is not None:
                try:
                    self.call_from_thread(on_complete, result)
                except Exception:
                    pass

        thread = threading.Thread(target=runner, name=f"kugou-{label}", daemon=True)
        thread.start()
