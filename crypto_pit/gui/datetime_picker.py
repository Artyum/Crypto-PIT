from __future__ import annotations

import calendar
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from crypto_pit.datetime_fmt import local_now, make_local_datetime
from crypto_pit.gui.window_pos import app_root, center_window

MONTHS_PL = [
    "Styczeń",
    "Luty",
    "Marzec",
    "Kwiecień",
    "Maj",
    "Czerwiec",
    "Lipiec",
    "Sierpień",
    "Wrzesień",
    "Październik",
    "Listopad",
    "Grudzień",
]


class DateTimePicker(tk.Toplevel):
    def __init__(
        self, parent: tk.Tk | tk.Toplevel, initial: datetime | None = None
    ) -> None:
        super().__init__(parent)
        self.title("Wybór daty i godziny")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.result: datetime | None = None

        now = initial or local_now()
        self._year = now.year
        self._month = now.month
        self._day = now.day
        self._hour = tk.IntVar(value=now.hour)
        self._minute = tk.IntVar(value=now.minute)

        body = ttk.Frame(self, padding=12)
        body.grid(row=0, column=0, sticky="nsew")

        nav = ttk.Frame(body)
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(nav, text="◀", width=3, command=self._prev_month).pack(side=tk.LEFT)
        self._title = ttk.Label(nav, anchor=tk.CENTER, font=("Segoe UI", 10, "bold"))
        self._title.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=8)
        ttk.Button(nav, text="▶", width=3, command=self._next_month).pack(side=tk.RIGHT)

        self._cal = ttk.Frame(body)
        self._cal.grid(row=1, column=0, sticky="nsew")

        time_row = ttk.Frame(body)
        time_row.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(time_row, text="Godzina").pack(side=tk.LEFT)
        hour = ttk.Spinbox(
            time_row, from_=0, to=23, width=4, textvariable=self._hour, format="%02.0f"
        )
        hour.pack(side=tk.LEFT, padx=(8, 12))
        ttk.Label(time_row, text="Minuta").pack(side=tk.LEFT)
        minute = ttk.Spinbox(
            time_row,
            from_=0,
            to=59,
            width=4,
            textvariable=self._minute,
            format="%02.0f",
        )
        minute.pack(side=tk.LEFT, padx=(8, 0))

        btns = ttk.Frame(body)
        btns.grid(row=3, column=0, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="Anuluj", command=self._cancel).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        ttk.Button(btns, text="OK", command=self._ok).pack(side=tk.RIGHT)

        self._render_calendar()
        center_window(self, app_root(parent))

    def _prev_month(self) -> None:
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._render_calendar()

    def _next_month(self) -> None:
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._render_calendar()

    def _render_calendar(self) -> None:
        for child in self._cal.winfo_children():
            child.destroy()

        self._title.config(text=f"{MONTHS_PL[self._month - 1]} {self._year}")

        for i, name in enumerate(["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]):
            ttk.Label(self._cal, text=name, width=4, anchor=tk.CENTER).grid(
                row=0, column=i, padx=1, pady=2
            )

        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            self._year, self._month
        )
        for r, week in enumerate(weeks, start=1):
            for c, day in enumerate(week):
                if day == 0:
                    ttk.Label(self._cal, text="", width=4).grid(row=r, column=c)
                    continue
                style_name = "Selected.TButton" if day == self._day else "TButton"
                btn = ttk.Button(
                    self._cal,
                    text=str(day),
                    width=4,
                    style=style_name,
                    command=lambda d=day: self._pick_day(d),
                )
                btn.grid(row=r, column=c, padx=1, pady=1)

    def _pick_day(self, day: int) -> None:
        self._day = day
        self._render_calendar()

    def _ok(self) -> None:
        try:
            hour = int(self._hour.get())
            minute = int(self._minute.get())
            hour = max(0, min(23, hour))
            minute = max(0, min(59, minute))
            self.result = make_local_datetime(
                self._year, self._month, self._day, hour, minute
            )
        except (ValueError, tk.TclError):
            self.result = None
            return
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


def ask_datetime(
    parent: tk.Tk | tk.Toplevel, initial: datetime | None = None
) -> datetime | None:
    picker = DateTimePicker(parent, initial)
    parent.wait_window(picker)
    return picker.result
