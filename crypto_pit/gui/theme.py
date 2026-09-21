from __future__ import annotations

import tkinter as tk
from tkinter import ttk

COLORS = {
    "bg": "#E8EDF3",
    "surface": "#F7F9FC",
    "card": "#FFFFFF",
    "ink": "#152033",
    "muted": "#5A6A7D",
    "border": "#C5D0DE",
    "border_strong": "#9AABC0",
    "header_bg": "#D5DEEA",
    "row_odd": "#F0F4F9",
    "row_hover": "#E4EBF4",
    "select_bg": "#2A5F8F",
    "select_active": "#3A6F9F",
    "select_pressed": "#1F4A73",
    "accent": "#B86B2A",
}

FONT_UI = ("Segoe UI", 10)
FONT_UI_SM = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADING = ("Segoe UI", 9, "bold")

ROW_HEIGHT = 30


def apply_theme(root: tk.Tk | tk.Toplevel) -> ttk.Style:
    root.configure(bg=COLORS["bg"])
    try:
        root.option_add("*Font", FONT_UI)
    except tk.TclError:
        pass

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    c = COLORS
    style.configure(".", font=FONT_UI, foreground=c["ink"], focuscolor="")
    style.configure("TFrame", background=c["bg"])
    style.configure("Card.TFrame", background=c["card"])

    style.configure("TLabel", background=c["bg"], foreground=c["ink"], font=FONT_UI)
    style.configure(
        "Muted.TLabel",
        background=c["bg"],
        foreground=c["muted"],
        font=FONT_UI_SM,
    )

    style.configure(
        "TButton",
        font=FONT_UI,
        padding=(12, 6),
        background=c["surface"],
        foreground=c["ink"],
        bordercolor=c["border"],
        lightcolor=c["surface"],
        darkcolor=c["border"],
    )
    style.map(
        "TButton",
        background=[("active", c["row_hover"]), ("pressed", c["border"])],
    )
    style.configure("Compact.TButton", font=FONT_UI_SM, padding=(4, 1))
    style.configure(
        "Accent.TButton",
        background=c["select_bg"],
        foreground=c["card"],
        bordercolor=c["select_bg"],
        lightcolor=c["select_bg"],
        darkcolor=c["select_pressed"],
        padding=(14, 6),
        font=FONT_UI_BOLD,
    )
    style.map(
        "Accent.TButton",
        background=[
            ("active", c["select_active"]),
            ("pressed", c["select_pressed"]),
        ],
        foreground=[("disabled", c["muted"])],
    )

    style.configure(
        "TEntry",
        fieldbackground=c["card"],
        foreground=c["ink"],
        bordercolor=c["border"],
        lightcolor=c["border"],
        darkcolor=c["border"],
        insertcolor=c["ink"],
        padding=4,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", c["select_bg"])],
        lightcolor=[("focus", c["select_bg"])],
        darkcolor=[("focus", c["select_bg"])],
    )

    style.configure(
        "TMenubutton",
        background=c["card"],
        foreground=c["ink"],
        bordercolor=c["border"],
        relief="raised",
        padding=(8, 4),
    )
    style.map("TMenubutton", background=[("active", c["surface"])])

    style.configure(
        "TCombobox",
        fieldbackground=c["card"],
        background=c["surface"],
        foreground=c["ink"],
        bordercolor=c["border"],
        arrowcolor=c["ink"],
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", c["card"])],
        selectbackground=[("readonly", c["card"])],
        selectforeground=[("readonly", c["ink"])],
    )

    style.configure(
        "TLabelframe",
        background=c["bg"],
        bordercolor=c["border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=c["bg"],
        foreground=c["ink"],
        font=FONT_HEADING,
    )
    style.configure(
        "TRadiobutton",
        background=c["bg"],
        foreground=c["ink"],
        font=FONT_UI,
    )
    style.map(
        "TRadiobutton",
        background=[("active", c["bg"]), ("selected", c["bg"])],
        indicatorcolor=[("selected", c["select_bg"])],
    )
    style.configure(
        "TCheckbutton",
        background=c["bg"],
        foreground=c["ink"],
        font=FONT_UI,
    )
    style.map(
        "TCheckbutton",
        background=[("active", c["bg"]), ("selected", c["bg"])],
        indicatorcolor=[("selected", c["select_bg"])],
    )

    tab_pad = (12, 6)
    style.configure(
        "TNotebook",
        background=c["bg"],
        borderwidth=0,
        tabmargins=(4, 4, 4, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=c["bg"],
        foreground=c["muted"],
        padding=tab_pad,
        font=FONT_UI,
        bordercolor=c["bg"],
        lightcolor=c["bg"],
        darkcolor=c["bg"],
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", c["card"]), ("active", c["row_hover"])],
        foreground=[("selected", c["ink"]), ("active", c["ink"])],
        padding=[("selected", tab_pad)],
        expand=[("selected", (0, 0, 0, 0))],
        bordercolor=[("selected", c["border"]), ("!selected", c["bg"])],
        lightcolor=[("selected", c["card"]), ("!selected", c["bg"])],
        darkcolor=[("selected", c["card"]), ("!selected", c["bg"])],
    )

    style.configure(
        "Treeview",
        background=c["card"],
        fieldbackground=c["card"],
        foreground=c["ink"],
        bordercolor=c["border"],
        lightcolor=c["border"],
        darkcolor=c["border"],
        rowheight=ROW_HEIGHT,
        font=FONT_UI,
        borderwidth=0,
        relief="flat",
    )
    style.configure(
        "Treeview.Heading",
        background=c["header_bg"],
        foreground=c["ink"],
        font=FONT_HEADING,
        relief="flat",
        borderwidth=0,
        padding=(10, 8),
    )
    style.map(
        "Treeview",
        background=[("selected", c["select_bg"])],
        foreground=[("selected", c["card"])],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", c["border"]), ("pressed", c["header_bg"])],
        foreground=[("active", c["ink"])],
        relief=[("active", "flat")],
    )

    _configure_scrollbar(style, "Vertical.TScrollbar")
    _configure_scrollbar(style, "Horizontal.TScrollbar")

    style.configure("TSeparator", background=c["border"])
    return style


def _configure_scrollbar(style: ttk.Style, name: str) -> None:
    c = COLORS
    style.configure(
        name,
        background=c["border_strong"],
        troughcolor=c["row_odd"],
        bordercolor=c["border"],
        arrowcolor=c["ink"],
        lightcolor=c["border"],
        darkcolor=c["border_strong"],
        arrowsize=14,
    )
    style.map(
        name,
        background=[("active", c["muted"]), ("pressed", c["ink"])],
        arrowcolor=[("active", c["ink"]), ("pressed", c["card"])],
    )


def configure_tree_tags(tree: ttk.Treeview) -> None:
    c = COLORS
    tree.tag_configure("even", background=c["card"])
    tree.tag_configure("odd", background=c["row_odd"])
