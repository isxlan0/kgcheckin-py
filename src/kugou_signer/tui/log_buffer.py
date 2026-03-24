from __future__ import annotations

from queue import Empty, SimpleQueue


class ThreadSafeLogBuffer:
    def __init__(self) -> None:
        self._messages: SimpleQueue[str] = SimpleQueue()

    def push(self, message: str) -> None:
        self._messages.put(str(message))

    def drain(self) -> list[str]:
        drained: list[str] = []
        while True:
            try:
                drained.append(self._messages.get_nowait())
            except Empty:
                return drained
