from __future__ import annotations

from crypto_pit.domain.pit38 import pit38_field_range, pit38_fields_for_year


def test_pit38_field_numbers_before_2025() -> None:
    fields = {field.key: field.field_no for field in pit38_fields_for_year(2024)}

    assert fields["przychod"] == "34"
    assert fields["koszty_biezace"] == "35"
    assert fields["koszty_lat_ubieglych"] == "36"
    assert fields["dochod"] == "37"
    assert fields["koszty_do_przeniesienia"] == "38"
    assert pit38_field_range(2024) == "34–38"


def test_pit38_field_numbers_from_2025() -> None:
    fields = {field.key: field.field_no for field in pit38_fields_for_year(2025)}

    assert fields["przychod"] == "36"
    assert fields["koszty_biezace"] == "37"
    assert fields["koszty_lat_ubieglych"] == "38"
    assert fields["dochod"] == "39"
    assert fields["koszty_do_przeniesienia"] == "40"
    assert pit38_field_range(2025) == "36–40"


def test_pit38_formulas_use_field_numbers() -> None:
    fields = {field.key: field for field in pit38_fields_for_year(2025)}

    assert fields["dochod"].formula == "36 − (37 + 38)"
    assert fields["koszty_do_przeniesienia"].formula == "(37 + 38) − 36"
