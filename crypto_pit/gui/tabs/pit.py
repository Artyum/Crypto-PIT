from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Literal

from crypto_pit.domain.pit38 import (
    PIT38_FIELD_KEYS,
    PIT38_SECTION,
    pit38_field_range,
    pit38_fields_for_year,
)
from crypto_pit.gui.formatters import fmt_money, fmt_money_compact
from crypto_pit.gui.theme import COLORS, FONT_HEADING, FONT_UI, FONT_UI_BOLD
from crypto_pit.gui.widgets import FilterDropdown

if TYPE_CHECKING:
    from crypto_pit.gui.app import CryptoPitApp

GAP = 8
_Anchor = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]

_COL_FIELD = 56
_COL_LABEL = 360
_COL_VALUE = 168


class PitTab:
    def __init__(self, parent: ttk.Frame, app: CryptoPitApp) -> None:
        self.app = app
        self.frame = parent
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        top = ttk.Frame(self.frame)
        top.grid(row=0, column=0, sticky="ew", pady=(0, GAP))
        ttk.Label(top, text="Rok podatkowy").pack(side=tk.LEFT)
        self.year_var = tk.StringVar()
        self.year = FilterDropdown(
            top, self.year_var, [], width=10, on_change=self.refresh
        )
        self.year.pack(side=tk.LEFT, padx=(8, 0))

        box = ttk.LabelFrame(
            self.frame,
            text=f"PIT-38 część {PIT38_SECTION} — waluty wirtualne",
            padding=(0, 0),
        )
        box.grid(row=1, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        self.grid = tk.Frame(box, background=COLORS["card"])
        self.grid.grid(row=0, column=0, sticky="nsew")
        self.grid.columnconfigure(0, minsize=_COL_FIELD, weight=0)
        self.grid.columnconfigure(1, minsize=_COL_LABEL, weight=2)
        self.grid.columnconfigure(2, minsize=_COL_VALUE, weight=0)

        self._add_header()
        self.field_no_labels: dict[str, tk.Label] = {}
        self.field_desc_labels: dict[str, tk.Label] = {}
        self.labels: dict[str, tk.Label] = {}
        self._values: dict[str, float | None] = dict.fromkeys(PIT38_FIELD_KEYS)
        for i, key in enumerate(PIT38_FIELD_KEYS):
            self._add_field_row(i, key)

        self.footer_label = ttk.Label(
            self.frame,
            text="",
            wraplength=1000,
            style="Muted.TLabel",
        )
        self.footer_label.grid(row=2, column=0, sticky="ew", pady=(GAP, 0))

    def _add_header(self) -> None:
        bg = COLORS["header_bg"]
        fg = COLORS["ink"]
        headers: tuple[tuple[int, str, _Anchor], ...] = (
            (0, "PIT-38", "center"),
            (1, "Pole", "w"),
            (2, "Wartość", "e"),
        )
        for col, text, anchor in headers:
            tk.Label(
                self.grid,
                text=text,
                background=bg,
                foreground=fg,
                font=FONT_HEADING,
                anchor=anchor,
                padx=14,
                pady=10,
            ).grid(row=0, column=col, sticky="nsew")

    def _update_fields_for_year(self, year: int) -> None:
        for field in pit38_fields_for_year(year):
            label = field.label
            if field.formula:
                label += f"\n({field.formula})"
            self.field_no_labels[field.key].config(text=field.field_no or "—")
            self.field_desc_labels[field.key].config(text=label)
        self.footer_label.config(
            text=(
                f"Numery pól ({pit38_field_range(year)}) odpowiadają pozycjom "
                "w wierszu walut wirtualnych w części E PIT-38. "
                "Podwójne kliknięcie wartości kopiuje ją do schowka."
            )
        )

    def _add_field_row(self, index: int, key: str) -> None:
        row = index + 1
        bg = COLORS["row_odd"] if index % 2 else COLORS["card"]

        no_lab = tk.Label(
            self.grid,
            text="—",
            background=bg,
            foreground=COLORS["accent"],
            font=("Segoe UI", 12, "bold"),
            anchor="center",
            padx=14,
            pady=10,
        )
        no_lab.grid(row=row, column=0, sticky="nsew")
        self.field_no_labels[key] = no_lab

        desc_lab = tk.Label(
            self.grid,
            text="",
            background=bg,
            foreground=COLORS["ink"],
            font=FONT_UI,
            justify=tk.LEFT,
            anchor="w",
            padx=14,
            pady=10,
        )
        desc_lab.grid(row=row, column=1, sticky="nsew")
        self.field_desc_labels[key] = desc_lab

        lab = tk.Label(
            self.grid,
            text="—",
            background=bg,
            foreground=COLORS["ink"],
            font=FONT_UI_BOLD,
            anchor="e",
            padx=14,
            pady=10,
            cursor="hand2",
        )
        lab.grid(row=row, column=2, sticky="nsew")
        lab.bind("<Double-1>", lambda _e, field_key=key: self._copy_value(field_key))
        self.labels[key] = lab

    def _copy_value(self, key: str) -> None:
        val = self._values.get(key)
        if val is None:
            return
        text = fmt_money_compact(val)
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)
        self.frame.update_idletasks()
        self.footer_label.config(text=f"Skopiowano do schowka: {text}")

    def set_years(self, years: list[str]) -> None:
        self.year.set_values(years)
        if not years:
            self.year_var.set("")
        elif self.year_var.get() not in years:
            self.year_var.set(years[-1])

    def select_year(self, year: str) -> None:
        self.year_var.set(year)
        self.refresh()

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        year_s = self.year_var.get()
        if not year_s:
            for key in PIT38_FIELD_KEYS:
                self._values[key] = None
            for lab in self.labels.values():
                lab.config(text="—")
            return
        year = int(year_s)
        self._update_fields_for_year(year)
        s = self.app.settlements.get(year)
        if not s:
            for key in PIT38_FIELD_KEYS:
                self._values[key] = None
            return
        for key, val in s.pit_fields().items():
            self._values[key] = val
            self.labels[key].config(text=fmt_money(val))
