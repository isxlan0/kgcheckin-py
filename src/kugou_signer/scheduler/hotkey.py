from __future__ import annotations

import os
import sys
from types import TracebackType


class HotkeyListener:
    def __init__(self) -> None:
        self.enabled = sys.stdin.isatty()
        self._active = False
        self._fd: int | None = None
        self._original_settings = None

    def __enter__(self) -> "HotkeyListener":
        self.resume()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.pause()

    def resume(self) -> None:
        if not self.enabled or self._active:
            return
        if os.name == "nt":
            self._active = True
            return
        import termios
        import tty

        self._fd = sys.stdin.fileno()
        self._original_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        self._active = True

    def pause(self) -> None:
        if not self.enabled or not self._active:
            return
        if os.name != "nt" and self._fd is not None and self._original_settings is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._original_settings)
        self._active = False

    def flush_pending_keys(self) -> None:
        if not self.enabled:
            return
        if os.name == "nt":
            import msvcrt

            while msvcrt.kbhit():
                msvcrt.getwch()
            return

        import select

        while True:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if not ready:
                break
            sys.stdin.read(1)

    def read_key(self, *, include_control: bool = False) -> str | None:
        if not self.enabled or not self._active:
            return None
        if os.name == "nt":
            import msvcrt

            if not msvcrt.kbhit():
                return None
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                if msvcrt.kbhit():
                    msvcrt.getwch()
                return None
            if not include_control and key in ("\r", "\n", "\x08"):
                return None
            return key

        import select

        ready, _, _ = select.select([sys.stdin], [], [], 0)
        if not ready:
            return None
        key = sys.stdin.read(1)
        if not include_control and key in ("\r", "\n", "\x08", "\x7f"):
            return None
        return key
