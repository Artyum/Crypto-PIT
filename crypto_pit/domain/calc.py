from __future__ import annotations

from typing import TypedDict

from crypto_pit.domain.enums import TxType
from crypto_pit.domain.exchange_profiles import get_profile


class ValidationError(ValueError):
    pass


class CalcResult(TypedDict):
    value: float
    fee: float
    fee_coin: float
    coin_amount: float
    final_coin: float
    price: float
    price_pln: float
    fee_pln: float
    value_pln: float
    curr_to_pln: float


def _to_result(fields: dict[str, float], curr_to_pln: float) -> CalcResult:
    if fields["value"] <= 0:
        raise ValidationError("Wartość musi być większa od zera")
    if fields["fee"] < 0:
        raise ValidationError("Prowizja nie może być ujemna")
    if fields["coin_amount"] <= 0:
        raise ValidationError("Ilość waloru musi być większa od zera")
    if curr_to_pln <= 0:
        raise ValidationError("Kurs waluta/PLN musi być większe od zera")
    if fields["price"] <= 0:
        raise ValidationError("Cena musi być większa od zera")
    if fields["fee_coin"] < 0:
        raise ValidationError("Prowizja w walorze nie może być ujemne")
    if fields["final_coin"] <= 0:
        raise ValidationError("Finalna ilość waloru musi być większa od zera")
    rate = curr_to_pln
    return CalcResult(
        value=fields["value"],
        fee=fields["fee"],
        fee_coin=fields["fee_coin"],
        coin_amount=fields["coin_amount"],
        final_coin=fields["final_coin"],
        price=fields["price"],
        price_pln=round(fields["price"] * rate, 2),
        fee_pln=round(fields["fee"] * rate, 2),
        value_pln=round(fields["value"] * rate, 2),
        curr_to_pln=rate,
    )


def resolve_trade(
    *,
    exchange: str,
    tx_type: TxType,
    curr_to_pln: float,
    value: float | None = None,
    fee: float | None = None,
    fee_coin: float | None = None,
    coin_amount: float | None = None,
    final_coin: float | None = None,
) -> CalcResult | None:
    """Wylicza pola według profilu giełdy; None gdy brak danych lub błąd."""
    try:
        profile = get_profile(exchange, tx_type)
    except KeyError as exc:
        raise ValidationError(str(exc)) from exc

    if value is None:
        return None

    raw = {
        "fee": fee,
        "fee_coin": fee_coin,
        "coin_amount": coin_amount,
        "final_coin": final_coin,
    }
    inputs: dict[str, float] = {}
    for key in profile.input_fields:
        val = raw[key]
        if val is None:
            return None
        inputs[key] = val

    try:
        return _to_result(profile.compute(value=value, **inputs), curr_to_pln)
    except (ValidationError, ValueError, ZeroDivisionError):
        return None
