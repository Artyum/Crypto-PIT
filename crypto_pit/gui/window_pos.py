from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any, cast


def app_root(widget: tk.Misc) -> tk.Tk:
    return cast(tk.Tk, widget.nametowidget("."))


def center_window(
    window: tk.Tk | tk.Toplevel,
    relative_to: tk.Misc | None = None,
) -> None:
    window.update_idletasks()
    anchor = relative_to if relative_to is not None else app_root(window)
    try:
        anchor.update_idletasks()
    except tk.TclError:
        return
    if not anchor.winfo_ismapped():
        return

    aw = max(int(anchor.winfo_width()), 1)
    ah = max(int(anchor.winfo_height()), 1)
    ax = int(anchor.winfo_rootx())
    ay = int(anchor.winfo_rooty())
    ww = max(int(window.winfo_reqwidth()), int(window.winfo_width()), 1)
    wh = max(int(window.winfo_reqheight()), int(window.winfo_height()), 1)
    x = ax + (aw - ww) // 2
    y = ay + (ah - wh) // 2
    window.geometry(f"+{max(0, x)}+{max(0, y)}")


def _message_parent(parent: tk.Misc | None) -> tk.Misc | None:
    if parent is None:
        return None
    try:
        if parent.winfo_exists() and parent.winfo_ismapped():
            return parent
        root = app_root(parent)
        if root.winfo_exists() and root.winfo_ismapped():
            return root
    except tk.TclError:
        return None
    return None


def showinfo(title: str, message: str, parent: tk.Misc | None = None, **kwargs: Any):
    target = _message_parent(parent)
    if target is None:
        return messagebox.showinfo(title, message, **kwargs)
    return messagebox.showinfo(title, message, parent=target, **kwargs)


def showerror(title: str, message: str, parent: tk.Misc | None = None, **kwargs: Any):
    target = _message_parent(parent)
    if target is None:
        return messagebox.showerror(title, message, **kwargs)
    return messagebox.showerror(title, message, parent=target, **kwargs)


def askyesno(
    title: str, message: str, parent: tk.Misc | None = None, **kwargs: Any
) -> bool:
    target = _message_parent(parent)
    if target is None:
        return bool(messagebox.askyesno(title, message, **kwargs))
    return bool(messagebox.askyesno(title, message, parent=target, **kwargs))
