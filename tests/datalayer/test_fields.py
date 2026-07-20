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


def test_extract_materials_scans_all_texts_case_insensitive():
    mats = fields.extract_materials("100% Cashmere Sweater", "wool, silk", "")
    assert set(mats) == {"cashmere", "wool", "silk"}


def test_extract_materials_empty_when_no_keyword():
    assert fields.extract_materials("plain top", "") == []


def test_extract_item_prefers_product_type():
    assert fields.extract_item("Sweater", "Cozy Knit", ["knit"]) == "Sweater"


def test_extract_item_none_when_empty_and_no_llm():
    assert fields.extract_item("", "Cozy Knit", ["knit"], llm_fn=None) is None
    assert fields.extract_item(None, "Cozy Knit", ["knit"]) is None


def test_extract_item_llm_fallback_when_product_type_blank():
    calls = []

    def fake_llm(prompt: str) -> str:
        calls.append(prompt)
        return "Cardigan"

    out = fields.extract_item("", "Wool Button Front", ["outerwear"], llm_fn=fake_llm)
    assert out == "Cardigan"
    assert len(calls) == 1


def test_extract_item_llm_unknown_maps_to_none():
    out = fields.extract_item("", "Mystery", [], llm_fn=lambda p: "unknown")
    assert out is None
