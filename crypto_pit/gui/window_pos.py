from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
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


def _run_message(
    fn: Callable[..., Any],
    title: str,
    message: str,
    parent: tk.Misc | None = None,
    **kwargs: Any,
) -> Any:

    cleanup: tk.Toplevel | None = None
    msg_parent: tk.Misc | None = parent
    if parent is not None:
        try:
            root = app_root(parent)
            if root.winfo_ismapped():
                cleanup = tk.Toplevel(root)
                cleanup.withdraw()
                cleanup.overrideredirect(True)
                cleanup.geometry("1x1+0+0")
                try:
                    cleanup.attributes("-alpha", 0.0)
                except tk.TclError:
                    pass
                center_window(cleanup, root)
                cleanup.deiconify()
                cleanup.update_idletasks()
                msg_parent = cleanup
        except tk.TclError:
            pass
    try:
        return fn(title, message, parent=msg_parent, **kwargs)
    finally:
        if cleanup is not None:
            try:
                cleanup.destroy()
            except tk.TclError:
                pass


def showinfo(title: str, message: str, parent: tk.Misc | None = None, **kwargs: Any):
    return _run_message(messagebox.showinfo, title, message, parent, **kwargs)


def showerror(title: str, message: str, parent: tk.Misc | None = None, **kwargs: Any):
    return _run_message(messagebox.showerror, title, message, parent, **kwargs)


def askyesno(
    title: str, message: str, parent: tk.Misc | None = None, **kwargs: Any
) -> bool:
    return bool(_run_message(messagebox.askyesno, title, message, parent, **kwargs))
