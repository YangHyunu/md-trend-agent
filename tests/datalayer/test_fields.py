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


def test_pick_structured_colors_handles_both_spellings():
    us = [{"name": "Color", "values": ["Camel", "Grey"]}]
    uk = [{"name": "Colour", "values": ["Navy"]}]
    assert fields.pick_structured_colors(us) == ["Camel", "Grey"]
    assert fields.pick_structured_colors(uk) == ["Navy"]


def test_pick_structured_colors_empty_when_no_color_option():
    assert fields.pick_structured_colors([{"name": "Size", "values": ["S"]}]) == []


def test_verify_substring_case_insensitive():
    assert fields.verify_substring("Camel", "soft CAMEL wool") is True
    assert fields.verify_substring("Emerald", "soft camel wool") is False
    assert fields.verify_substring("", "anything") is False


def test_extract_colors_prefers_structured_no_llm_call():
    called = []
    opts = [{"name": "color", "values": ["Ivory"]}]
    out = fields.extract_colors(opts, "t", [], "raw", llm_fn=lambda p: called.append(p) or "X")
    assert out == ["Ivory"]
    assert called == []  # 구조화 성공 시 LLM 미호출


def test_extract_colors_llm_fallback_keeps_only_verified():
    # LLM이 Camel(원본 존재)·Emerald(원본 없음) 반환 → Camel만 채택
    raw = "Beautiful camel knit cardigan"
    out = fields.extract_colors(
        [], "Camel Cardigan", ["knit"], raw, llm_fn=lambda p: "Camel, Emerald")
    assert out == ["Camel"]


def test_extract_colors_no_structured_no_llm_returns_empty():
    assert fields.extract_colors([], "t", [], "raw", llm_fn=None) == []
