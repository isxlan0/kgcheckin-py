from __future__ import annotations

import sys
import time
from typing import Any

from kugou_signer.scheduler.commands import RuntimeCommandHandler
from kugou_signer.scheduler.hotkey import HotkeyListener

PROMPT_TOOLKIT_AVAILABLE = False

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.application.current import get_app
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.shortcuts.prompt import CompleteStyle
    from prompt_toolkit.styles import Style

    PROMPT_TOOLKIT_AVAILABLE = True
except ModuleNotFoundError:
    PromptSession = Any  # type: ignore[assignment]
    Buffer = Any  # type: ignore[assignment]
    Completer = object  # type: ignore[assignment,misc]
    Completion = Any  # type: ignore[assignment]
    EditingMode = Any  # type: ignore[assignment]
    CompleteStyle = Any  # type: ignore[assignment]
    KeyBindings = Any  # type: ignore[assignment]
    Style = Any  # type: ignore[assignment]
    get_app = None  # type: ignore[assignment]


if PROMPT_TOOLKIT_AVAILABLE:

    class _SlashCommandCompleter(Completer):
        def __init__(self, handler: RuntimeCommandHandler) -> None:
            self.handler = handler

        def get_completions(self, document, _complete_event):
            current_text = document.text_before_cursor
            command_text = f"/{current_text.strip()}" if current_text.strip() else "/"
            for spec in self.handler.matching_commands(command_text):
                yield Completion(
                    spec.insert_text[1:],
                    start_position=-len(current_text),
                    display=spec.display,
                    display_meta=spec.description,
                )


class CommandPalette:
    def __init__(self, handler: RuntimeCommandHandler, hotkeys: HotkeyListener) -> None:
        self.handler = handler
        self.hotkeys = hotkeys
        self._last_rendered_lines = 0
        self._prompt_session = self._build_prompt_session()

    @property
    def uses_prompt_toolkit(self) -> bool:
        return self._prompt_session is not None

    def activation_notice(self) -> str | None:
        if not self.hotkeys.enabled:
            return None
        if self.uses_prompt_toolkit:
            return "命令栏已启用：按 / 打开，输入框显示为 › /，并自动给出命令候选。"
        return "命令栏已启用：按 / 打开输入，Enter 执行，Esc 取消。"

    def capture(self) -> str | None:
        if not self.hotkeys.enabled:
            return None
        if self._prompt_session is not None:
            return self._capture_with_prompt_toolkit()
        return self._capture_legacy()

    def _capture_with_prompt_toolkit(self) -> str | None:
        if self._prompt_session is None:
            return None
        self.hotkeys.pause()
        self.hotkeys.flush_pending_keys()
        try:
            text = self._prompt_session.prompt(
                message=[("class:prompt.marker", "› /")],
                default="",
                reserve_space_for_menu=8,
                bottom_toolbar=self._build_toolbar,
                pre_run=self._start_completion,
            )
        except EOFError:
            return None
        finally:
            self.hotkeys.resume()
        self._erase_prompt_line()
        command = text.strip().lstrip("/")
        if not command:
            return None
        return f"/{command}"

    def _capture_legacy(self) -> str | None:
        buffer = "/"
        self._render(buffer)
        while True:
            key = self.hotkeys.read_key(include_control=True)
            if key is None:
                time.sleep(0.02)
                continue
            if key == "\x03":
                self._clear()
                raise KeyboardInterrupt
            if key == "\x1b":
                self._clear()
                return None
            if key in ("\r", "\n"):
                self._clear()
                print()
                return buffer
            if key in ("\x08", "\x7f"):
                if len(buffer) > 1:
                    buffer = buffer[:-1]
                    self._render(buffer)
                continue
            if key.isprintable():
                buffer += key
                self._render(buffer)

    def _build_prompt_session(self):
        if not (PROMPT_TOOLKIT_AVAILABLE and self.hotkeys.enabled and sys.stdin.isatty() and sys.stdout.isatty()):
            return None
        bindings = KeyBindings()

        @bindings.add("escape")
        def _cancel(event) -> None:
            event.app.exit(result="")

        @bindings.add("enter")
        def _accept_or_expand(event) -> None:
            buffer = event.current_buffer
            spec = self._selected_spec(buffer)
            if spec is None:
                spec = self.handler.find_exact_spec(f"/{buffer.text}")
            if spec is not None:
                buffer.text = spec.insert_text[1:]
                buffer.cursor_position = len(buffer.text)
                if spec.mode == "expand":
                    self._show_completions(buffer)
                    return
            event.app.exit(result=buffer.text)

        @bindings.add("tab")
        def _tab_complete(event) -> None:
            buffer = event.current_buffer
            spec = self._selected_spec(buffer)
            if spec is not None:
                buffer.text = spec.insert_text[1:]
                buffer.cursor_position = len(buffer.text)
            self._show_completions(buffer)

        style = Style.from_dict(
            {
                "prompt.marker": "#00d7ff bold",
                "bottom-toolbar": "bg:#1f2937 #d1d5db",
                "completion-menu.completion.current": "bg:#1d4ed8 #ffffff",
                "completion-menu.meta.completion.current": "bg:#1d4ed8 #bfdbfe",
                "completion-menu.completion": "bg:#111111 #e5e7eb",
                "completion-menu.meta.completion": "bg:#111111 #9ca3af",
            }
        )
        return PromptSession(
            completer=_SlashCommandCompleter(self.handler),
            complete_while_typing=True,
            complete_style=CompleteStyle.COLUMN,
            editing_mode=EditingMode.EMACS,
            key_bindings=bindings,
            style=style,
        )

    def _build_toolbar(self):
        return " ↑↓ 选择 | Tab 补全 | Enter 确认/进入下级 | Esc 取消 "

    def _start_completion(self) -> None:
        if get_app is None:
            return
        buffer = get_app().current_buffer
        if buffer is None:
            return
        self._show_completions(buffer)

    @staticmethod
    def _show_completions(buffer: Buffer) -> None:
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    def _selected_spec(self, buffer: Buffer):
        state = buffer.complete_state
        if state is None or state.current_completion is None:
            return None
        inserted = f"/{state.current_completion.text}".rstrip()
        current_text = f"/{buffer.text.strip()}" if buffer.text.strip() else "/"
        for spec in self.handler.matching_commands(current_text):
            if spec.insert_text.rstrip() == inserted:
                return spec
        return None

    @staticmethod
    def _erase_prompt_line() -> None:
        sys.stdout.write("\r\033[2K\033[1A\r\033[2K\r")
        sys.stdout.flush()

    def _render(self, current_text: str) -> None:
        suggestions = self.handler.suggestions(current_text)[:5]
        lines = [f"› {current_text}"]
        lines.extend(f"  {item}" for item in suggestions)
        self._clear()
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()
        self._last_rendered_lines = len(lines)

    def _clear(self) -> None:
        if self._last_rendered_lines == 0:
            return
        for index in range(self._last_rendered_lines):
            sys.stdout.write("\r\033[2K")
            if index < self._last_rendered_lines - 1:
                sys.stdout.write("\033[1A")
        sys.stdout.flush()
        self._last_rendered_lines = 0
