from datalayer import fields


def test_to_float_strips_commas_and_handles_none():
    assert fields.to_float("1,250.00") == 1250.0
    assert fields.to_float("240.00") == 240.0
    assert fields.to_float(None) is None
    assert fields.to_float("") is None


def test_extract_price_detects_sale_when_compare_greater():
    # arch4 실측: price=240 compare=625 → 세일
    price, compare, on_sale = fields.extract_price(
        {"price": "240.00", "compare_at_price": "625.00"})
    assert (price, compare, on_sale) == (240.0, 625.0, True)


def test_extract_price_equal_compare_is_not_sale():
    # guestinresidence 실측: 445==445 → 세일 아님
    _, _, on_sale = fields.extract_price(
        {"price": "445.00", "compare_at_price": "445.00"})
    assert on_sale is False


def test_extract_price_none_compare_is_not_sale():
    # extreme 실측: compare=None → 세일 아님
    price, compare, on_sale = fields.extract_price(
        {"price": "650.00", "compare_at_price": None})
    assert (price, compare, on_sale) == (650.0, None, False)
