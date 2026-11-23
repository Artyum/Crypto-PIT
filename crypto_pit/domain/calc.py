from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

from crypto_pit.domain.enums import TxType
from crypto_pit.domain.exchange_profiles import get_profile
from crypto_pit.domain.money import DecimalError, parse_decimal, quantize


class ValidationError(ValueError):
    pass


class CalcResult(TypedDict):
    value: Decimal
    fee: Decimal
    fee_coin: Decimal
    coin_amount: Decimal
    final_coin: Decimal
    price: Decimal
    price_pln: Decimal
    fee_pln: Decimal
    value_pln: Decimal
    curr_to_pln: Decimal


def _finite(value: Decimal, label: str) -> Decimal:
    try:
        return parse_decimal(value)
    except DecimalError as exc:
        raise ValidationError(f"{label}: {exc}") from exc


def _to_result(fields: dict[str, Decimal], curr_to_pln: Decimal) -> CalcResult:
    value = _finite(fields["value"], "Wartość")
    fee = _finite(fields["fee"], "Prowizja")
    fee_coin = _finite(fields["fee_coin"], "Prowizja w walorze")
    coin_amount = _finite(fields["coin_amount"], "Ilość waloru")
    final_coin = _finite(fields["final_coin"], "Finalna ilość")
    price = _finite(fields["price"], "Cena")
    rate = _finite(curr_to_pln, "Kurs")
    if value <= 0:
        raise ValidationError("Wartość musi być większa od zera")
    if fee < 0:
        raise ValidationError("Prowizja nie może być ujemna")
    if coin_amount <= 0:
        raise ValidationError("Ilość waloru musi być większa od zera")
    if rate <= 0:
        raise ValidationError("Kurs waluta/PLN musi być większe od zera")
    if price <= 0:
        raise ValidationError("Cena musi być większa od zera")
    if fee_coin < 0:
        raise ValidationError("Prowizja w walorze nie może być ujemna")
    if final_coin <= 0:
        raise ValidationError("Finalna ilość waloru musi być większa od zera")
    return CalcResult(
        value=value,
        fee=fee,
        fee_coin=fee_coin,
        coin_amount=coin_amount,
        final_coin=final_coin,
        price=price,
        price_pln=quantize(price * rate, 2),
        fee_pln=quantize(fee * rate, 2),
        value_pln=quantize(value * rate, 2),
        curr_to_pln=rate,
    )


def resolve_trade(
    *,
    exchange: str,
    tx_type: TxType,
    curr_to_pln: Decimal | int | str,
    value: Decimal | int | str | None = None,
    fee: Decimal | int | str | None = None,
    fee_coin: Decimal | int | str | None = None,
    coin_amount: Decimal | int | str | None = None,
    final_coin: Decimal | int | str | None = None,
) -> CalcResult | None:
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
    inputs: dict[str, Decimal] = {}
    for key in profile.input_fields:
        item = raw[key]
        if item is None:
            return None
        inputs[key] = _finite(parse_decimal(item), key)
    try:
        fields = profile.compute(
            value=_finite(parse_decimal(value), "Wartość"), **inputs
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return _to_result(fields, _finite(parse_decimal(curr_to_pln), "Kurs"))
