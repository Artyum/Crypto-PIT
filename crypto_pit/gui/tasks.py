from __future__ import annotations

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class UiTaskRunner:
    def __init__(self, root: tk.Misc) -> None:
        self._root = root
        self._queue: queue.Queue[tuple[int, object, BaseException | None]] = (
            queue.Queue()
        )
        self._callbacks: dict[
            int, tuple[Callable[[object], None], Callable[[BaseException], None]]
        ] = {}
        self._next = 0
        self._closed = False
        self._poll()

    def submit(
        self,
        work: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[BaseException], None],
    ) -> int:
        if self._closed:
            raise RuntimeError("zadania interfejsu są zamknięte")
        self._next += 1
        token = self._next
        self._callbacks[token] = (on_success, on_error)  # type: ignore[assignment]

        def runner() -> None:
            try:
                value = work()
            except Exception as exc:  # noqa: BLE001
                self._queue.put((token, None, exc))
                return
            self._queue.put((token, value, None))

        threading.Thread(target=runner, daemon=True, name=f"crypto-pit-{token}").start()
        return token

    def cancel(self, token: int) -> None:
        self._callbacks.pop(token, None)

    def close(self) -> None:
        self._closed = True
        self._callbacks.clear()

    def _poll(self) -> None:
        if self._closed:
            return
        try:
            while True:
                token, value, error = self._queue.get_nowait()
                handlers = self._callbacks.pop(token, None)
                if handlers is None:
                    continue
                if error is None:
                    handlers[0](value)
                else:
                    handlers[1](error)
        except queue.Empty:
            pass
        try:
            self._root.after(50, self._poll)
        except tk.TclError:
            self._closed = True
