from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Literal, cast

from crypto_pit.gui.theme import COLORS, FONT_HEADING, FONT_UI, configure_tree_tags

_Anchor = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]
_COL_PAD = 28
_COL_MIN = 40


class FilterDropdown:
    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
        values: Sequence[str],
        *,
        width: int = 10,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self.variable = variable
        self.on_change = on_change
        self._values: list[str] = []
        self.button = ttk.Menubutton(parent, textvariable=variable, width=width)
        self.menu = tk.Menu(self.button, tearoff=0)
        self.button["menu"] = self.menu
        self.button.bind("<Enter>", lambda _e: self.button.focus_set())
        self.button.bind("<MouseWheel>", self._on_wheel)
        self.button.bind("<Button-4>", lambda _e: self._step(-1))
        self.button.bind("<Button-5>", lambda _e: self._step(1))
        self.set_values(values)

    def set_values(self, values: Sequence[str]) -> None:
        self._values = list(values)
        self.menu.delete(0, "end")
        for value in self._values:
            self.menu.add_radiobutton(
                label=value,
                variable=self.variable,
                value=value,
                command=self._emit,
            )

    def _on_wheel(self, event: tk.Event) -> str:
        return self._step(-1 if event.delta > 0 else 1)

    def _step(self, direction: int) -> str:
        if len(self._values) < 2:
            return "break"
        try:
            idx = self._values.index(self.variable.get())
        except ValueError:
            idx = 0
        next_idx = idx + direction
        if 0 <= next_idx < len(self._values):
            self.variable.set(self._values[next_idx])
            self._emit()
        return "break"

    def _emit(self) -> None:
        if self.on_change is not None:
            self.on_change()

    def pack(self, **kwargs: Any) -> None:
        self.button.pack(**kwargs)


def create_tree(
    parent: ttk.Frame | tk.Misc,
) -> tuple[tk.Frame, ttk.Treeview]:
    outer = tk.Frame(
        parent,
        background=COLORS["border_strong"],
        highlightthickness=0,
        bd=0,
    )
    frame = ttk.Frame(outer, style="Card.TFrame", padding=0)
    frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    tree = ttk.Treeview(frame, show="headings", selectmode="browse")
    yscroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    xscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    configure_tree_tags(tree)

    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    tree.grid(row=0, column=0, sticky="nsew")
    yscroll.grid(row=0, column=1, sticky="ns")
    xscroll.grid(row=1, column=0, sticky="ew")
    return outer, tree


def setup_columns(
    tree: ttk.Treeview,
    columns: tuple[str, ...],
    headings: dict[str, str],
    *,
    stretch_last: bool = True,
    anchors: dict[str, str] | None = None,
) -> None:
    tree["columns"] = columns
    for c in columns:
        tree.heading(c, text=headings[c], anchor=tk.W)
        stretch = stretch_last and c == columns[-1]
        tree.column(
            c,
            width=_COL_MIN,
            minwidth=_COL_MIN,
            stretch=stretch,
            anchor=cast(_Anchor, (anchors or {}).get(c, "w")),
        )


def autosize_columns(tree: ttk.Treeview) -> None:
    style = ttk.Style(tree)
    body = tkfont.Font(font=style.lookup("Treeview", "font") or FONT_UI)
    head = tkfont.Font(font=style.lookup("Treeview.Heading", "font") or FONT_HEADING)
    rows = tree.get_children()
    for i, col in enumerate(tree.cget("columns")):
        best = head.measure(str(tree.heading(col, "text") or ""))
        for iid in rows:
            values = tree.item(iid, "values")
            if i < len(values):
                best = max(best, body.measure(str(values[i])))
        width = max(best + _COL_PAD, _COL_MIN)
        tree.column(col, width=width, minwidth=width)


def zebra_tag(index: int) -> str:
    return "odd" if index % 2 else "even"


def insert_row(
    tree: ttk.Treeview,
    values: Sequence[Any],
    *,
    iid: str | None = None,
    index: int | None = None,
) -> str:
    if index is None:
        index = len(tree.get_children())
    kwargs: dict[str, Any] = {"values": values, "tags": (zebra_tag(index),)}
    if iid is not None:
        kwargs["iid"] = iid
    return tree.insert("", tk.END, **kwargs)
