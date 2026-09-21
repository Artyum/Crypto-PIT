from __future__ import annotations

import sqlite3
import threading
import tkinter as tk
from collections.abc import Callable
from datetime import timedelta
from tkinter import ttk
from typing import TYPE_CHECKING

from crypto_pit.datetime_fmt import local_now
from crypto_pit.domain.calc import CalcResult, ValidationError, resolve_trade
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.exchange_profiles import (
    EXCHANGES,
    CalcProfile,
    get_profile,
    has_profile,
)
from crypto_pit.domain.models import Transaction
from crypto_pit.gui.datetime_picker import ask_datetime
from crypto_pit.gui.formatters import fmt_datetime, parse_datetime, parse_float
from crypto_pit.gui.theme import COLORS, apply_theme
from crypto_pit.gui.window_pos import center_window, showerror, showinfo
from crypto_pit.services.nbp_rates import NbpRate, RateFetchError, fetch_pln_rate

if TYPE_CHECKING:
    from crypto_pit.infrastructure.database import Database

GAP = 4
ROW_PADY = 2
SECTION_PAD = 6
CURRENCIES = ("PLN", "USD", "EUR", "GBP", "CHF")
_PROFILE_INPUT_KEYS = ("fee", "fee_coin", "coin_amount", "final_coin")
_TYPE_MAP = {"Kupno": TxType.BUY, "Sprzedaż": TxType.SELL}
_FIELD_LABELS = {
    "coin_amount": "Ilość waloru",
    "final_coin": "Finalna ilość waloru",
    "fee": "Prowizja (waluta)",
    "fee_coin": "Prowizja (walor)",
}
_DEFAULT_VALUE_LABELS = {
    "Kupno": (
        "Wartość",
        "Pełna kwota obciążenia konta (z prowizją w walucie).",
    ),
    "Sprzedaż": (
        "Wartość sprzedaży brutto",
        "Kwota uzyskana ze sprzedaży przed potrąceniem prowizji.",
    ),
}


def _fmt_num(v: float, digits: int = 8) -> str:
    if abs(v) < 1e-12:
        return "0"
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _safe_float(text: str) -> float | None:
    s = text.strip()
    if not s:
        return None
    try:
        return parse_float(s)
    except ValueError:
        return None


def _tx_field(
    tx: Transaction | None,
    primary: str,
    fallback: str | None = None,
    *,
    digits: int = 8,
) -> str:
    if tx is None:
        return ""
    val = float(getattr(tx, primary) or 0)
    if not val and fallback:
        val = float(getattr(tx, fallback) or 0)
    return _fmt_num(val, digits)


def migrate_profile_inputs(
    values: dict[str, float | None],
    old_profile: CalcProfile | None,
    new_profile: CalcProfile,
) -> dict[str, float | None]:
    """Zachowaj wspólne pola wejściowe przy zmianie profilu; wyczyść resztę."""
    keep = set(new_profile.input_fields)
    if old_profile is not None:
        keep &= set(old_profile.input_fields)
    return {k: (values.get(k) if k in keep else None) for k in _PROFILE_INPUT_KEYS}


def visible_input_fields(exchange: str, tx_type: TxType) -> tuple[str, ...]:
    return get_profile(exchange, tx_type).input_fields


def value_input_labels(exchange: str, tx_type: TxType) -> tuple[str, str]:
    """Zwróć opis wartości zgodny z profilem raportowania giełdy."""
    default = _DEFAULT_VALUE_LABELS.get(tx_type.label_pl, ("Wartość", ""))
    try:
        profile = get_profile(exchange, tx_type)
    except KeyError:
        return default
    return (
        profile.value_label or default[0],
        profile.value_hint or default[1],
    )


def _match_exchange(raw: str | None) -> str:
    if raw and raw.strip():
        needle = raw.strip().lower()
        for name in EXCHANGES:
            if name.lower() == needle:
                return name
        return raw.strip()
    return EXCHANGES[0]


def open_transaction_dialog(
    parent: tk.Tk,
    db: Database,
    on_saved: Callable[[], None],
    tx: Transaction | None = None,
) -> None:
    TransactionDialog(parent, db, on_saved, tx)


class TransactionDialog:
    def __init__(
        self,
        parent: tk.Tk,
        db: Database,
        on_saved: Callable[[], None],
        tx: Transaction | None = None,
    ) -> None:
        self.db = db
        self.on_saved = on_saved
        self.tx = tx
        self._updating = False
        self._last_calc: CalcResult | None = None
        self._rate_busy = False
        self._last_nbp: NbpRate | None = None
        self._user_fields: set[str] = set()
        self._lockable_entries: list[ttk.Entry] = []
        self._lockable_buttons: list[ttk.Button] = []
        self._profile: CalcProfile | None = None
        self._field_rows: dict[str, tuple[ttk.Label, ttk.Entry]] = {}

        self.dlg = tk.Toplevel(parent)
        self.dlg.title("Edycja transakcji" if tx else "Nowa transakcja")
        self.dlg.configure(bg=COLORS["bg"])
        apply_theme(self.dlg)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.resizable(False, False)

        initial_exchange = _match_exchange(tx.exchange if tx else None)
        type_label = "Sprzedaż" if tx and tx.type == TxType.SELL else "Kupno"
        initial_dt = tx.date if tx else local_now().replace(second=0, microsecond=0)

        self.date_var = tk.StringVar(value=fmt_datetime(initial_dt))
        self.type_var = tk.StringVar(value=type_label)
        self.exchange_var = tk.StringVar(value=initial_exchange)
        self.asset_var = tk.StringVar(value=(tx.asset if tx else "").upper())
        self.currency_var = tk.StringVar(value=(tx.currency if tx else "") or "PLN")
        self.rate_var = tk.StringVar(value=_fmt_num(tx.curr_to_pln, 6) if tx else "1")
        self.value_var = tk.StringVar(value=_tx_field(tx, "value", "value_pln"))
        self.fee_var = tk.StringVar(value=_tx_field(tx, "fee", "fee_pln"))
        self.fee_coin_var = tk.StringVar(value=_tx_field(tx, "fee_coin"))
        self.coin_amount_var = tk.StringVar(
            value=_tx_field(tx, "coin_amount", "amount")
        )
        self.final_coin_var = tk.StringVar(value=_tx_field(tx, "final_coin", "amount"))
        self.confirmed_var = tk.BooleanVar(value=bool(tx and tx.confirmed))

        self.out_price = tk.StringVar(value="—")
        self.out_price_pln = tk.StringVar(value="—")
        self.out_value = tk.StringVar(value="—")
        self.out_value_pln = tk.StringVar(value="—")
        self.out_coin_amount = tk.StringVar(value="—")
        self.out_final_coin = tk.StringVar(value="—")
        self.out_fee = tk.StringVar(value="—")
        self.out_fee_pln = tk.StringVar(value="—")
        self.out_fee_coin = tk.StringVar(value="—")
        self._out_vars = (
            self.out_price,
            self.out_price_pln,
            self.out_value,
            self.out_value_pln,
            self.out_coin_amount,
            self.out_final_coin,
            self.out_fee,
            self.out_fee_pln,
            self.out_fee_coin,
        )

        self._vars = {
            "value": self.value_var,
            "fee": self.fee_var,
            "fee_coin": self.fee_coin_var,
            "coin_amount": self.coin_amount_var,
            "final_coin": self.final_coin_var,
        }
        if tx:
            try:
                profile = get_profile(initial_exchange, _TYPE_MAP[type_label])
                self._user_fields = {
                    k for k in profile.input_fields if self._vars[k].get().strip()
                }
                if self.value_var.get().strip():
                    self._user_fields.add("value")
            except KeyError:
                pass

        self._build()
        self._bind_traces()
        self._apply_profile(initial=True)
        self._set_fields_locked(self.confirmed_var.get())
        center_window(self.dlg, parent)

    def _build(self) -> None:
        body = ttk.Frame(self.dlg, padding=10)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        basic = ttk.LabelFrame(body, text="Podstawowe dane", padding=SECTION_PAD)
        basic.grid(row=0, column=0, sticky="ew", pady=(0, GAP))
        basic.columnconfigure(1, weight=1)

        self._add_label(basic, 0, "Giełda")
        self.exchange_cb = ttk.Combobox(
            basic,
            textvariable=self.exchange_var,
            values=list(EXCHANGES),
            state="readonly",
            width=36,
        )
        self.exchange_cb.grid(row=0, column=1, sticky="ew", pady=ROW_PADY)

        self._add_label(basic, 1, "Typ")
        self.type_cb = ttk.Combobox(
            basic,
            textvariable=self.type_var,
            values=list(_TYPE_MAP),
            state="readonly",
            width=36,
        )
        self.type_cb.grid(row=1, column=1, sticky="ew", pady=ROW_PADY)

        self._add_label(basic, 2, "Data i godzina")
        date_row = ttk.Frame(basic)
        date_row.grid(row=2, column=1, sticky="ew", pady=ROW_PADY)
        date_row.columnconfigure(0, weight=1)
        self.date_entry = ttk.Entry(date_row, textvariable=self.date_var, width=28)
        self.date_entry.grid(row=0, column=0, sticky="ew")
        self.date_btn = ttk.Button(date_row, text="Wybierz…", command=self._pick_date)
        self.date_btn.grid(row=0, column=1, padx=(6, 0))
        self._lockable_entries.append(self.date_entry)
        self._lockable_buttons.append(self.date_btn)

        self._add_label(basic, 3, "Walor")
        self.asset_entry = ttk.Entry(basic, textvariable=self.asset_var, width=38)
        self.asset_entry.grid(row=3, column=1, sticky="ew", pady=ROW_PADY)
        self._lockable_entries.append(self.asset_entry)

        self._add_label(basic, 4, "Waluta")
        curr_row = ttk.Frame(basic)
        curr_row.grid(row=4, column=1, sticky="ew", pady=ROW_PADY)
        self.currency_cb = ttk.Combobox(
            curr_row, textvariable=self.currency_var, values=CURRENCIES, width=10
        )
        self.currency_cb.grid(row=0, column=0, sticky="w")
        ttk.Label(curr_row, text="Kurs").grid(row=0, column=1, sticky="e", padx=(10, 4))
        self.rate_entry = ttk.Entry(curr_row, textvariable=self.rate_var, width=12)
        self.rate_entry.grid(row=0, column=2, sticky="e")
        self.rate_btn = ttk.Button(
            curr_row,
            text="NBP",
            command=self._fetch_rate,
            width=4,
            style="Compact.TButton",
        )
        self.rate_btn.grid(row=0, column=3, sticky="e", padx=(4, 0))
        self._lockable_entries.append(self.rate_entry)
        self._lockable_buttons.append(self.rate_btn)

        self.rate_info_row = ttk.Frame(basic)
        self.rate_info_row.grid(row=5, column=1, sticky="ew")
        self.rate_info_row.columnconfigure(0, weight=1)
        self.rate_info = ttk.Label(self.rate_info_row, text="", style="Muted.TLabel")
        self.rate_info.grid(row=0, column=0, sticky="w")
        self.rate_details_btn = ttk.Button(
            self.rate_info_row,
            text="i",
            width=1,
            style="Compact.TButton",
            command=self._show_rate_details,
        )
        self.rate_details_btn.grid(row=0, column=1, padx=(4, 0))
        self.rate_details_btn.grid_remove()

        self.value_label = ttk.Label(basic, text="Wartość")
        self.value_label.grid(row=6, column=0, sticky="w", padx=(0, 10), pady=ROW_PADY)
        self.value_entry = ttk.Entry(basic, textvariable=self.value_var, width=38)
        self.value_entry.grid(row=6, column=1, sticky="ew", pady=ROW_PADY)
        self._lockable_entries.append(self.value_entry)
        self.value_hint = ttk.Label(basic, text="", style="Muted.TLabel")
        self.value_hint.grid(row=7, column=1, sticky="w")

        trade = ttk.LabelFrame(body, text="Dane transakcji", padding=SECTION_PAD)
        trade.grid(row=1, column=0, sticky="ew", pady=(0, GAP))
        trade.columnconfigure(1, weight=1)
        for i, key in enumerate(_PROFILE_INPUT_KEYS):
            label = ttk.Label(trade, text=_FIELD_LABELS[key])
            label.grid(row=i, column=0, sticky="w", padx=(0, 10), pady=ROW_PADY)
            entry = ttk.Entry(trade, textvariable=self._vars[key], width=38)
            entry.grid(row=i, column=1, sticky="ew", pady=ROW_PADY)
            self._lockable_entries.append(entry)
            self._field_rows[key] = (label, entry)

        results = ttk.LabelFrame(
            body, text="Wyniki (automatycznie)", padding=SECTION_PAD
        )
        results.grid(row=2, column=0, sticky="ew", pady=(0, GAP))
        results.columnconfigure(1, weight=1)
        results.columnconfigure(3, weight=1)
        for r, l1, v1, l2, v2 in (
            (0, "Cena", self.out_price, "Cena PLN", self.out_price_pln),
            (1, "Wartość", self.out_value, "Wartość PLN", self.out_value_pln),
            (
                2,
                "Prowizja (w walucie)",
                self.out_fee,
                "Prowizja PLN",
                self.out_fee_pln,
            ),
            (
                3,
                "Ilość waloru",
                self.out_coin_amount,
                "Finalna ilość",
                self.out_final_coin,
            ),
        ):
            ttk.Label(results, text=l1).grid(row=r, column=0, sticky="w", padx=(0, 6))
            ttk.Label(results, textvariable=v1).grid(
                row=r, column=1, sticky="w", padx=(0, 14)
            )
            ttk.Label(results, text=l2).grid(row=r, column=2, sticky="w", padx=(0, 6))
            ttk.Label(results, textvariable=v2).grid(row=r, column=3, sticky="w")

        note_frame = ttk.LabelFrame(body, text="Opis / uwagi", padding=SECTION_PAD)
        note_frame.grid(row=3, column=0, sticky="ew", pady=(0, GAP))
        note_frame.columnconfigure(0, weight=1)
        self.note_text = tk.Text(
            note_frame,
            width=56,
            height=2,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg=COLORS["card"],
            fg=COLORS["ink"],
            insertbackground=COLORS["ink"],
            relief=tk.SOLID,
            borderwidth=1,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["select_bg"],
        )
        self.note_text.grid(row=0, column=0, sticky="ew")
        if self.tx and self.tx.note:
            self.note_text.insert("1.0", self.tx.note)

        footer = ttk.Frame(body)
        footer.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            footer,
            text="Zatwierdzone",
            variable=self.confirmed_var,
            command=lambda: self._set_fields_locked(self.confirmed_var.get()),
        ).pack(side=tk.LEFT)
        self.save_btn = ttk.Button(footer, text="Zapisz", command=self._save)
        self.save_btn.pack(side=tk.RIGHT)
        ttk.Button(footer, text="Anuluj", command=self.dlg.destroy).pack(
            side=tk.RIGHT, padx=(0, GAP)
        )

    @staticmethod
    def _add_label(parent: ttk.LabelFrame, row: int, text: str) -> None:
        ttk.Label(parent, text=text).grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=ROW_PADY
        )

    def _tx_type(self) -> TxType:
        return _TYPE_MAP[self.type_var.get()]

    def _set_fields_locked(self, locked: bool) -> None:
        state = "disabled" if locked else "normal"
        for entry in self._lockable_entries:
            entry.configure(state=state)
        self.type_cb.configure(state="disabled" if locked else "readonly")
        self.exchange_cb.configure(state="disabled" if locked else "readonly")
        self.currency_cb.configure(state="disabled" if locked else "normal")
        for btn in self._lockable_buttons:
            btn.configure(state=state)
        self.note_text.configure(state=state)
        if not locked:
            self._sync_rate_widgets()
            self._apply_profile(initial=False)

    def _bind_traces(self) -> None:
        self.type_var.trace_add("write", lambda *_: self._on_type_or_exchange_change())
        self.exchange_var.trace_add(
            "write", lambda *_: self._on_type_or_exchange_change()
        )
        self.asset_var.trace_add("write", lambda *_: self._force_asset_caps())
        self.currency_var.trace_add("write", lambda *_: self._on_currency_change())
        self.rate_var.trace_add("write", lambda *_: self._recalc())
        self.value_var.trace_add("write", lambda *_: self._on_field_edit("value"))
        for key in _PROFILE_INPUT_KEYS:
            self._vars[key].trace_add(
                "write", lambda *_a, k=key: self._on_field_edit(k)
            )

    def _force_asset_caps(self) -> None:
        value = self.asset_var.get()
        upper = value.upper()
        if value == upper:
            return
        pos = self.asset_entry.index(tk.INSERT)
        self.asset_var.set(upper)
        self.asset_entry.icursor(pos)

    def _on_field_edit(self, key: str) -> None:
        if self._updating:
            return
        if self._vars[key].get().strip():
            self._user_fields.add(key)
        else:
            self._user_fields.discard(key)
        self._refresh_user_markers()
        self._recalc()

    def _refresh_user_markers(self) -> None:
        inputs = self._profile.input_fields if self._profile else ()
        for key, (label, _) in self._field_rows.items():
            base = _FIELD_LABELS[key]
            label.config(
                text=f"{base} *" if key in self._user_fields and key in inputs else base
            )
        title, _hint = value_input_labels(
            self.exchange_var.get().strip(), self._tx_type()
        )
        self.value_label.config(
            text=f"{title} *" if "value" in self._user_fields else title
        )

    def _pick_date(self) -> None:
        try:
            current = parse_datetime(self.date_var.get())
        except ValueError:
            current = local_now()
        chosen = ask_datetime(self.dlg, current)
        if chosen is not None:
            self.date_var.set(fmt_datetime(chosen))

    def _on_type_or_exchange_change(self) -> None:
        if self._updating:
            return
        self._apply_profile(initial=False)

    def _apply_profile(self, *, initial: bool) -> None:
        exchange = self.exchange_var.get().strip()
        tx_type = self._tx_type()
        title, hint = value_input_labels(exchange, tx_type)
        self.value_hint.config(text=hint)
        if "value" not in self._user_fields:
            self.value_label.config(text=title)

        if not has_profile(exchange, tx_type):
            self._profile = None
            for label, entry in self._field_rows.values():
                label.grid_remove()
                entry.grid_remove()
            self._last_calc = None
            self._clear_outputs()
            return

        new_profile = get_profile(exchange, tx_type)
        old_profile = self._profile
        if not initial and old_profile is not None and old_profile.id != new_profile.id:
            self._migrate_inputs(old_profile, new_profile)

        self._profile = new_profile
        for label, entry in self._field_rows.values():
            label.grid_remove()
            entry.grid_remove()
        for i, key in enumerate(new_profile.input_fields):
            label, entry = self._field_rows[key]
            label.grid(row=i, column=0, sticky="w", padx=(0, 10), pady=ROW_PADY)
            entry.grid(row=i, column=1, sticky="ew", pady=ROW_PADY)
        self._refresh_user_markers()
        if not self.confirmed_var.get():
            self._sync_rate_widgets()
        self._recalc()

    def _migrate_inputs(
        self, old_profile: CalcProfile, new_profile: CalcProfile
    ) -> None:
        current = {k: _safe_float(self._vars[k].get()) for k in _PROFILE_INPUT_KEYS}
        migrated = migrate_profile_inputs(current, old_profile, new_profile)
        self._updating = True
        try:
            for key in _PROFILE_INPUT_KEYS:
                val = migrated[key]
                if key in new_profile.input_fields and val is not None:
                    self._vars[key].set(_fmt_num(val))
                else:
                    self._vars[key].set("")
                    self._user_fields.discard(key)
        finally:
            self._updating = False
        self._user_fields = {
            k
            for k in self._user_fields
            if k == "value" or k in new_profile.input_fields
        }

    def _on_currency_change(self) -> None:
        if self.confirmed_var.get():
            return
        self._sync_rate_widgets()
        self._recalc()

    def _sync_rate_widgets(self) -> None:
        if self.currency_var.get().strip().upper() == "PLN":
            self._updating = True
            try:
                self.rate_var.set("1")
            finally:
                self._updating = False
            self.rate_entry.configure(state="disabled")
            self.rate_btn.configure(state="disabled")
            self._reset_nbp_info("Dla PLN kurs = 1")
        else:
            self.rate_entry.configure(state="normal")
            self.rate_btn.configure(state="normal")
            self._reset_nbp_info()

    def _reset_nbp_info(self, text: str = "") -> None:
        self._last_nbp = None
        self.rate_info.config(text=text)
        self.rate_details_btn.grid_remove()

    def _clear_outputs(self) -> None:
        for var in self._out_vars:
            var.set("—")

    def _set_outputs(self, result: CalcResult) -> None:
        self.out_price.set(_fmt_num(result["price"], 6))
        self.out_price_pln.set(_fmt_num(result["price_pln"], 2))
        self.out_value.set(_fmt_num(result["value"]))
        self.out_value_pln.set(_fmt_num(result["value_pln"], 2))
        self.out_coin_amount.set(_fmt_num(result["coin_amount"]))
        self.out_final_coin.set(_fmt_num(result["final_coin"]))
        self.out_fee.set(_fmt_num(result["fee"]))
        self.out_fee_pln.set(_fmt_num(result["fee_pln"], 2))
        self.out_fee_coin.set(_fmt_num(result["fee_coin"]))

    def _recalc(self) -> None:
        if self._updating:
            return
        if self._profile is None:
            self._last_calc = None
            self._clear_outputs()
            return
        rate = _safe_float(self.rate_var.get())
        if rate is None or rate <= 0:
            self._last_calc = None
            self._clear_outputs()
            return

        kwargs = {
            key: _safe_float(self._vars[key].get()) for key in _PROFILE_INPUT_KEYS
        }
        try:
            result = resolve_trade(
                exchange=self.exchange_var.get().strip(),
                tx_type=self._tx_type(),
                curr_to_pln=rate,
                value=_safe_float(self.value_var.get()),
                fee=kwargs["fee"],
                fee_coin=kwargs["fee_coin"],
                coin_amount=kwargs["coin_amount"],
                final_coin=kwargs["final_coin"],
            )
        except ValidationError:
            result = None

        self._last_calc = result
        if result is None:
            self._clear_outputs()
        else:
            self._set_outputs(result)

    def _fetch_rate(self) -> None:
        if self._rate_busy:
            return
        code = self.currency_var.get().strip().upper()
        if code == "PLN":
            self.rate_var.set("1")
            return
        try:
            dt = parse_datetime(self.date_var.get())
        except ValueError:
            showerror(
                "Kurs", "Najpierw ustaw poprawną datę transakcji.", parent=self.dlg
            )
            return
        before = (dt - timedelta(days=1)).date()
        self._rate_busy = True
        self.rate_btn.configure(state="disabled", text="…")
        self._reset_nbp_info(f"Szukam kursu {code}/PLN…")

        def worker() -> None:
            try:
                result = fetch_pln_rate(code, before)
                self.dlg.after(0, lambda: self._on_rate_ok(result))
            except RateFetchError as exc:
                msg = str(exc)
                self.dlg.after(0, lambda m=msg: self._on_rate_err(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_rate_ok(self, result: NbpRate) -> None:
        self._rate_busy = False
        self._last_nbp = result
        self.rate_btn.configure(state="normal", text="NBP")
        self.rate_entry.configure(state="normal")
        self.rate_var.set(_fmt_num(result.mid, 6))
        self.rate_info.config(
            text=(
                f"NBP: 1 {result.code} = {result.mid} PLN"
                f" ({result.effective_date.isoformat()})"
            )
        )
        self.rate_details_btn.grid()
        self._recalc()

    def _show_rate_details(self) -> None:
        r = self._last_nbp
        if r is None:
            return
        showinfo(
            "Kurs NBP",
            (
                f"Pobrano z API NBP (tabela A):\n\n"
                f"Waluta: {r.currency_name} ({r.code})\n"
                f"Kurs średni: 1 {r.code} = {r.mid} PLN\n"
                f"Data tabeli: {r.effective_date.isoformat()}\n"
                f"Nr tabeli: {r.table_no}\n\n"
                f"Szukano kursu z dnia przed transakcją "
                f"({r.requested_before.isoformat()})."
            ),
            parent=self.dlg,
        )

    def _on_rate_err(self, message: str) -> None:
        self._rate_busy = False
        code = self.currency_var.get().strip().upper()
        self.rate_btn.configure(
            state="normal" if code != "PLN" else "disabled",
            text="NBP",
        )
        self._reset_nbp_info()
        showerror(
            "Kurs NBP",
            f"{message}\nMożesz wpisać kurs ręcznie.",
            parent=self.dlg,
        )

    def _save(self) -> None:
        try:
            tx_type = self._tx_type()
            exchange = self.exchange_var.get().strip()
            if not exchange:
                raise ValueError("Wybierz giełdę")
            if not has_profile(exchange, tx_type):
                raise ValidationError(
                    f"Brak profilu kalkulacji dla {exchange} / {tx_type.label_pl}"
                )
            note = self.note_text.get("1.0", "end-1c").strip()
            dt = parse_datetime(self.date_var.get())
            asset = self.asset_var.get().strip().upper()
            if not asset:
                raise ValueError("Podaj walor")

            self._recalc()
            if self._last_calc is None:
                raise ValidationError(
                    "Uzupełnij pola tak, aby dało się wyliczyć wartość i ilość"
                )
            c = self._last_calc
            amount = c["final_coin"] if tx_type == TxType.BUY else c["coin_amount"]

            new_tx = Transaction(
                id=self.tx.id if self.tx else None,
                date=dt,
                type=tx_type,
                asset=asset,
                amount=amount,
                value_pln=c["value_pln"],
                fee_pln=c["fee_pln"],
                exchange=exchange,
                note=note,
                currency=self.currency_var.get().strip().upper() or "PLN",
                value=c["value"],
                curr_to_pln=c["curr_to_pln"],
                coin_amount=c["coin_amount"],
                price=c["price"],
                price_pln=c["price_pln"],
                fee_coin=c["fee_coin"],
                fee=c["fee"],
                final_coin=c["final_coin"],
                confirmed=bool(self.confirmed_var.get()),
            )
            if self.tx:
                self.db.update_transaction(new_tx)
            else:
                self.db.insert_transaction(new_tx)
            self.dlg.destroy()
            self.on_saved()
        except (ValueError, KeyError, sqlite3.Error) as exc:
            showerror("Błąd", str(exc), parent=self.dlg)
