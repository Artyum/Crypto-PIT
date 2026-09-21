from __future__ import annotations

import sqlite3
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import TYPE_CHECKING

from crypto_pit.domain.models import Holding
from crypto_pit.gui.formatters import fmt_money, parse_float
from crypto_pit.gui.theme import COLORS, apply_theme
from crypto_pit.gui.widgets import (
    autosize_columns,
    create_tree,
    insert_row,
    setup_columns,
)
from crypto_pit.gui.window_pos import askyesno, center_window, showerror, showinfo
from crypto_pit.services.crypto_rates import CoinInfo, CryptoRateFetchError

if TYPE_CHECKING:
    from crypto_pit.gui.app import CryptoPitApp

GAP = 8


def _fmt_amount(v: float) -> str:
    if abs(v) < 1e-12:
        return "0"
    s = f"{v:.10f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _fmt_rate(v: float | None) -> str:
    if v is None:
        return "—"
    if v >= 1000:
        return fmt_money(v)
    s = f"{v:.8f}".rstrip("0").rstrip(".")
    return s if s else "0"


class HoldingsTab:
    def __init__(self, parent: ttk.Frame, app: CryptoPitApp) -> None:
        self.app = app
        self.frame = parent
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        self._rates_loaded = False
        self._fetch_busy = False

        toolbar = ttk.Frame(self.frame)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, GAP))

        ttk.Button(
            toolbar, text="Dodaj…", style="Accent.TButton", command=self.add
        ).pack(side=tk.LEFT, padx=(0, GAP))
        ttk.Button(toolbar, text="Edytuj…", command=self.edit).pack(
            side=tk.LEFT, padx=(0, GAP)
        )
        ttk.Button(toolbar, text="Usuń", command=self.delete).pack(
            side=tk.LEFT, padx=(0, GAP)
        )
        ttk.Button(toolbar, text="Odśwież teraz", command=self.refresh_rates).pack(
            side=tk.LEFT, padx=(16, 0)
        )

        self.status_var = tk.StringVar()
        ttk.Label(toolbar, textvariable=self.status_var, style="Muted.TLabel").pack(
            side=tk.RIGHT
        )

        tree_wrap, self.tree = create_tree(self.frame)
        tree_wrap.grid(row=1, column=0, sticky="nsew")
        setup_columns(
            self.tree,
            ("symbol", "location", "amount", "usd", "pln", "value_pln", "status"),
            {
                "symbol": "Waluta",
                "location": "Lokalizacja",
                "amount": "Ilość",
                "usd": "Kurs USD",
                "pln": "Kurs PLN",
                "value_pln": "Wartość PLN",
                "status": "Status",
            },
            anchors={"amount": tk.E, "usd": tk.E, "pln": tk.E, "value_pln": tk.E},
        )
        self.tree.bind("<Double-1>", lambda _e: self.edit())

        self.sum_label = ttk.Label(self.frame, text="", style="Muted.TLabel")
        self.sum_label.grid(row=2, column=0, sticky="ew", pady=(GAP, 0))

    def on_show(self) -> None:
        self.refresh(fetch_rates=not self._rates_loaded)

    def refresh(self, *, fetch_rates: bool = False) -> None:
        holdings = self.app.db.list_holdings()
        if fetch_rates and holdings:
            self._fetch_rates(force=False)
        else:
            self._render(holdings)

    def refresh_rates(self) -> None:
        if not self.app.db.list_holdings():
            self._rates_loaded = True
            self.status_var.set("Brak pozycji — dodaj coiny.")
            self._render([])
            return
        self._fetch_rates(force=True)

    def _fetch_rates(self, *, force: bool) -> None:
        if self._fetch_busy:
            return
        holdings = self.app.db.list_holdings()
        self._fetch_busy = True
        self.status_var.set("Pobieranie kursów…")
        self._render(holdings)
        rates = self.app.crypto_rates
        ids = list(dict.fromkeys(h.coin_id for h in holdings))

        def worker() -> None:
            try:
                rates.fetch_prices(ids, force_refresh=force)
                err = ""
            except CryptoRateFetchError as exc:
                err = str(exc)
            self.frame.after(0, lambda: self._on_fetch_done(err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_done(self, error: str) -> None:
        self._fetch_busy = False
        self._rates_loaded = True
        self.status_var.set(error or "Kursy zaktualizowane")
        self._render(self.app.db.list_holdings())

    def _render(self, holdings: list[Holding]) -> None:
        self.tree.delete(*self.tree.get_children())
        total_pln = 0.0

        for i, h in enumerate(holdings):
            price = self.app.crypto_rates.get_cached_price(h.coin_id)
            usd_s = pln_s = value_s = "—"
            if price is None:
                status = (
                    "Pobieranie…"
                    if self._fetch_busy
                    else (
                        "Oczekuje na kurs" if not self._rates_loaded else "Brak kursu"
                    )
                )
            elif not price.ok:
                usd_s = _fmt_rate(price.usd)
                pln_s = _fmt_rate(price.pln)
                status = price.error or "Błąd kursu"
            else:
                usd_s = _fmt_rate(price.usd)
                pln_s = _fmt_rate(price.pln)
                value = h.amount * (price.pln or 0)
                total_pln += value
                value_s = fmt_money(value)
                status = "OK"

            insert_row(
                self.tree,
                (
                    h.symbol.upper(),
                    h.location,
                    _fmt_amount(h.amount),
                    usd_s,
                    pln_s,
                    value_s,
                    status,
                ),
                iid=str(h.id),
                index=i,
            )

        self.sum_label.config(
            text=(f"Pozycje: {len(holdings)}    |    Suma: {fmt_money(total_pln)} PLN")
        )
        autosize_columns(self.tree)

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def add(self) -> None:
        HoldingDialog(self.app, on_saved=self._after_save)

    def edit(self) -> None:
        holding_id = self._selected_id()
        if holding_id is None:
            showinfo("Edycja", "Wybierz pozycję.", parent=self.app)
            return
        holding = self.app.db.get_holding(holding_id)
        if holding:
            HoldingDialog(self.app, on_saved=self._after_save, holding=holding)

    def delete(self) -> None:
        holding_id = self._selected_id()
        if holding_id is None:
            showinfo("Usuń", "Wybierz pozycję.", parent=self.app)
            return
        holding = self.app.db.get_holding(holding_id)
        label = (
            f"{holding.symbol.upper()} ({holding.location})"
            if holding
            else f"#{holding_id}"
        )
        if askyesno("Usuń", f"Usunąć {label} z portfela?", parent=self.app):
            self.app.db.delete_holding(holding_id)
            self.refresh()

    def _after_save(self) -> None:
        if self.app.db.list_holdings():
            self._fetch_rates(force=False)
        else:
            self._render([])


class HoldingDialog:
    def __init__(
        self,
        app: CryptoPitApp,
        on_saved: Callable[[], None],
        holding: Holding | None = None,
    ) -> None:
        self.app = app
        self.on_saved = on_saved
        self.holding = holding
        self._selected: CoinInfo | None = None
        self._results: list[CoinInfo] = []
        self._search_busy = False

        self.dlg = tk.Toplevel(app)
        self.dlg.title("Edycja pozycji" if holding else "Nowa pozycja")
        self.dlg.configure(bg=COLORS["bg"])
        apply_theme(self.dlg)
        self.dlg.transient(app)
        self.dlg.grab_set()
        self.dlg.resizable(False, False)

        body = ttk.Frame(self.dlg, padding=12)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        search_box = ttk.LabelFrame(body, text="Wyszukaj coin", padding=8)
        search_box.grid(row=0, column=0, sticky="ew")
        search_box.columnconfigure(0, weight=1)

        self.query_var = tk.StringVar()
        row = ttk.Frame(search_box)
        row.grid(row=0, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        entry = ttk.Entry(row, textvariable=self.query_var, width=36)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<Return>", lambda _e: self._search())
        ttk.Button(row, text="Szukaj", command=self._search).grid(
            row=0, column=1, padx=(8, 0)
        )

        self.search_status = tk.StringVar(value="Wpisz ticker lub nazwę (np. BTC)")
        ttk.Label(
            search_box, textvariable=self.search_status, style="Muted.TLabel"
        ).grid(row=1, column=0, sticky="w", pady=(6, 4))

        self.listbox = tk.Listbox(search_box, height=8, exportselection=False)
        self.listbox.grid(row=2, column=0, sticky="ew")
        self.listbox.bind("<<ListboxSelect>>", self._on_pick)

        if holding is not None:
            self._selected = CoinInfo(
                id=holding.coin_id, symbol=holding.symbol, name=""
            )
            self.listbox.insert(tk.END, f"{holding.symbol.upper()} ({holding.coin_id})")
            self.listbox.selection_set(0)
            self.search_status.set(
                f"Wybrano: {holding.symbol.upper()} — wyszukaj, by zmienić"
            )
            self._results = [self._selected]

        fields = ttk.Frame(body)
        fields.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        fields.columnconfigure(1, weight=1)

        ttk.Label(fields, text="Lokalizacja").grid(row=0, column=0, sticky="w")
        self.location_var = tk.StringVar(value=holding.location if holding else "")
        ttk.Entry(fields, textvariable=self.location_var, width=36).grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        ttk.Label(fields, text="Ilość").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.amount_var = tk.StringVar(
            value=_fmt_amount(holding.amount) if holding else ""
        )
        ttk.Entry(fields, textvariable=self.amount_var, width=24).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0)
        )

        buttons = ttk.Frame(body)
        buttons.grid(row=2, column=0, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Anuluj", command=self.dlg.destroy).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        ttk.Button(
            buttons, text="Zapisz", style="Accent.TButton", command=self._save
        ).pack(side=tk.RIGHT)

        self.dlg.bind("<Escape>", lambda _e: self.dlg.destroy())
        if holding is None:
            entry.focus_set()
        center_window(self.dlg, app)

    def _search(self) -> None:
        if self._search_busy:
            return
        query = self.query_var.get().strip()
        if not query:
            showinfo("Szukaj", "Wpisz ticker lub nazwę.", parent=self.dlg)
            return
        self._search_busy = True
        self.search_status.set("Szukam…")

        def worker() -> None:
            try:
                results = self.app.crypto_rates.search_coins(query)
                self.dlg.after(0, lambda: self._on_search_ok(results))
            except CryptoRateFetchError as exc:
                msg = str(exc)
                self.dlg.after(0, lambda m=msg: self._on_search_err(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_ok(self, results: list[CoinInfo]) -> None:
        self._search_busy = False
        self._results = results
        self.listbox.delete(0, tk.END)
        for coin in results:
            self.listbox.insert(tk.END, coin.label())
        if results:
            self.search_status.set(f"Znaleziono: {len(results)}")
            self.listbox.selection_set(0)
            self._on_pick()
        else:
            self.search_status.set("Brak wyników")
            self._selected = None

    def _on_search_err(self, message: str) -> None:
        self._search_busy = False
        self.search_status.set(message)
        showerror("Szukaj", message, parent=self.dlg)

    def _on_pick(self, _event: object | None = None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if 0 <= idx < len(self._results):
            self._selected = self._results[idx]

    def _save(self) -> None:
        if self._selected is None:
            showerror("Zapisz", "Wybierz coin z listy.", parent=self.dlg)
            return
        location = self.location_var.get().strip()
        if not location:
            showerror("Zapisz", "Podaj lokalizację.", parent=self.dlg)
            return
        try:
            amount = parse_float(self.amount_var.get())
        except ValueError:
            showerror("Zapisz", "Niepoprawna ilość.", parent=self.dlg)
            return
        if amount < 0:
            showerror("Zapisz", "Ilość nie może być ujemna.", parent=self.dlg)
            return

        symbol = self._selected.symbol.upper()
        coin_id = self._selected.id
        holding = Holding(
            id=self.holding.id if self.holding else None,
            coin_id=coin_id,
            symbol=symbol,
            amount=amount,
            location=location,
        )

        try:
            if holding.id is None:
                self.app.db.insert_holding(holding)
            else:
                self.app.db.update_holding(holding)
        except sqlite3.IntegrityError:
            showerror(
                "Zapisz",
                f"{symbol} w lokalizacji „{location}” jest już na liście.",
                parent=self.dlg,
            )
            return
        except sqlite3.Error as exc:
            showerror("Zapisz", str(exc), parent=self.dlg)
            return

        self.dlg.destroy()
        self.on_saved()
