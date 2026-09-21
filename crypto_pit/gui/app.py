from __future__ import annotations

import sqlite3
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk

from crypto_pit import __version__
from crypto_pit.config import DEFAULT_DB_PATH
from crypto_pit.gui.tabs.holdings import HoldingsTab
from crypto_pit.gui.tabs.pit import PitTab
from crypto_pit.gui.tabs.transactions import TransactionsTab
from crypto_pit.gui.tabs.years import YearsTab
from crypto_pit.gui.theme import COLORS, FONT_HEADING, FONT_UI_BOLD, apply_theme
from crypto_pit.gui.window_pos import askyesno, center_window, showerror, showinfo
from crypto_pit.infrastructure.database import Database
from crypto_pit.services.backup import export_backup, parse_backup
from crypto_pit.services.calculator import settle_years
from crypto_pit.services.crypto_rates import CryptoRatesService
from crypto_pit.services.reporting import export_report

_AUTHOR_URL = "https://github.com/Artyum"

PAD = 12
GAP = 8


class CryptoPitApp(tk.Tk):
    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__()
        self.title("Crypto-PIT")
        self.geometry("1280x780")
        self.minsize(1024, 640)
        apply_theme(self)

        self.db = Database(db_path or DEFAULT_DB_PATH)
        self.crypto_rates = CryptoRatesService()
        self.settlements: dict = {}

        self._build()
        self.refresh_all()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(self, style="TNotebook")
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=PAD, pady=GAP)

        tab_tx = ttk.Frame(self.notebook, padding=PAD)
        tab_holdings = ttk.Frame(self.notebook, padding=PAD)
        tab_years = ttk.Frame(self.notebook, padding=PAD)
        tab_pit = ttk.Frame(self.notebook, padding=PAD)

        self.notebook.add(tab_tx, text="Transakcje")
        self.notebook.add(tab_holdings, text="Portfel")
        self.notebook.add(tab_years, text="Rozliczenie lat")
        self.notebook.add(tab_pit, text="Pola PIT-38")

        self.tab_tx = TransactionsTab(tab_tx, self)
        self.tab_holdings = HoldingsTab(tab_holdings, self)
        self.tab_years = YearsTab(tab_years, self)
        self.tab_pit = PitTab(tab_pit, self)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_menu()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)

        menu_file = tk.Menu(menubar, tearoff=0)
        menu_file.add_command(label="Eksport raportu CSV…", command=self.export_csv)
        menu_file.add_command(label="Eksport backupu…", command=self.export_backup)
        menu_file.add_separator()
        menu_file.add_command(label="Import backupu…", command=self.import_backup)
        menu_file.add_separator()
        menu_file.add_command(label="Odśwież", command=self.refresh_all)
        menu_file.add_separator()
        menu_file.add_command(label="Zakończ", command=self.destroy)
        menubar.add_cascade(label="Plik", menu=menu_file)

        menu_tx = tk.Menu(menubar, tearoff=0)
        menu_tx.add_command(label="Dodaj transakcję…", command=self.tab_tx.add)
        menu_tx.add_command(label="Edytuj transakcję…", command=self.tab_tx.edit)
        menu_tx.add_command(label="Usuń transakcję", command=self.tab_tx.delete)
        menubar.add_cascade(label="Transakcje", menu=menu_tx)

        menu_view = tk.Menu(menubar, tearoff=0)
        menu_view.add_command(
            label="Transakcje",
            command=lambda: self.notebook.select(self.tab_tx.frame),
        )
        menu_view.add_command(
            label="Portfel",
            command=lambda: self.notebook.select(self.tab_holdings.frame),
        )
        menu_view.add_command(
            label="Rozliczenie lat",
            command=lambda: self.notebook.select(self.tab_years.frame),
        )
        menu_view.add_command(
            label="Pola PIT-38",
            command=lambda: self.notebook.select(self.tab_pit.frame),
        )
        menubar.add_cascade(label="Widok", menu=menu_view)

        menu_help = tk.Menu(menubar, tearoff=0)
        menu_help.add_command(label="O programie", command=self._about)
        menubar.add_cascade(label="Pomoc", menu=menu_help)

        self.config(menu=menubar)

    def _on_tab_changed(self, _event: object | None = None) -> None:
        try:
            current = self.notebook.select()
        except tk.TclError:
            return
        if str(self.tab_holdings.frame) == current:
            self.tab_holdings.on_show()
        elif str(self.tab_pit.frame) == current:
            self.tab_pit.on_show()

    def _about(self) -> None:
        AboutDialog(self)

    def refresh_all(self) -> None:
        self.tab_tx.refresh()
        self.tab_holdings.refresh(fetch_rates=False)
        self.tab_years.refresh()
        self.tab_pit.refresh()

    def export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Eksport raportu",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="pit38-raport.csv",
            parent=self,
        )
        if not path:
            return
        txs = self.db.list_transactions()
        settlements = settle_years(txs)
        export_report(path, txs, settlements)
        showinfo("Eksport", f"Zapisano:\n{path}", parent=self)

    def export_backup(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Eksport backupu",
            defaultextension=".zip",
            filetypes=[("Backup ZIP", "*.zip")],
            initialfile="crypto-pit-backup.zip",
            parent=self,
        )
        if not path:
            return
        txs = self.db.list_transactions()
        holdings = self.db.list_holdings()
        export_backup(path, txs, holdings)
        showinfo(
            "Backup",
            f"Zapisano {len(txs)} transakcji i {len(holdings)} pozycji portfela:\n"
            f"{path}",
            parent=self,
        )

    def import_backup(self) -> None:
        path = filedialog.askopenfilename(
            title="Import backupu",
            filetypes=[("Backup ZIP", "*.zip"), ("Wszystkie", "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            data = parse_backup(path)
        except (ValueError, OSError) as exc:
            showerror("Import backupu", str(exc), parent=self)
            return

        existing_tx = len(self.db.list_transactions())
        existing_h = len(self.db.list_holdings())
        if not askyesno(
            "Import backupu",
            f"Wczytano {len(data.transactions)} transakcji "
            f"i {len(data.holdings)} pozycji portfela.\n\n"
            f"Obecna baza ({existing_tx} transakcji, {existing_h} pozycji) "
            f"zostanie całkowicie zastąpiona.\n\nKontynuować?",
            parent=self,
        ):
            return
        try:
            n_tx, n_h = self.db.replace_all_data(data.transactions, data.holdings)
        except sqlite3.Error as exc:
            showerror("Import backupu", str(exc), parent=self)
            return
        showinfo(
            "Import backupu",
            f"Przywrócono {n_tx} transakcji i {n_h} pozycji portfela.",
            parent=self,
        )
        self.refresh_all()

    def destroy(self) -> None:
        self.db.close()
        super().destroy()


class AboutDialog:
    def __init__(self, parent: tk.Tk) -> None:
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("O programie")
        self.dlg.configure(bg=COLORS["bg"])
        apply_theme(self.dlg)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.resizable(False, False)

        body = ttk.Frame(self.dlg, padding=PAD)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        ttk.Label(body, text="Crypto-PIT", font=FONT_UI_BOLD).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            body,
            text=f"Wersja {__version__}",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, GAP))

        ttk.Label(
            body,
            text=(
                "Program desktopowy do ewidencji transakcji kryptowalut i przygotowania kwot do PIT-38."
            ),
            wraplength=420,
            justify=tk.LEFT,
        ).grid(row=2, column=0, sticky="w")

        meta = ttk.Frame(body)
        meta.grid(row=3, column=0, sticky="w", pady=(GAP, 0))
        ttk.Label(meta, text="Autor:").pack(side=tk.LEFT)
        ttk.Label(meta, text="Artyum", font=FONT_HEADING).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        link = tk.Label(
            body,
            text=_AUTHOR_URL,
            background=COLORS["bg"],
            foreground=COLORS["select_bg"],
            font=("Segoe UI", 9, "underline"),
            cursor="hand2",
            anchor="w",
        )
        link.grid(row=4, column=0, sticky="w", pady=(4, 0))
        link.bind("<Button-1>", self._open_author)

        btns = ttk.Frame(body)
        btns.grid(row=5, column=0, sticky="e", pady=(PAD, 0))
        ttk.Button(btns, text="Zamknij", command=self.dlg.destroy).pack(side=tk.RIGHT)

        self.dlg.bind("<Escape>", lambda _e: self.dlg.destroy())
        center_window(self.dlg, parent)
        self.dlg.focus_set()

    def _open_author(self, _event: tk.Event | None = None) -> None:
        webbrowser.open(_AUTHOR_URL)


def run_app(db_path: Path | None = None) -> None:
    app = CryptoPitApp(db_path)
    app.mainloop()
