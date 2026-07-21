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


def test_extract_item_canonicalizes_product_type():
    # 깨끗한 몰: product_type이 아이템 → 닫힌집합 canonical로 정규화
    assert fields.extract_item("Sweater", "Cozy Knit") == "Sweater"
    assert fields.extract_item("PULLOVER", "x") == "Sweater"   # 동의어→Sweater
    assert fields.extract_item("sweaters", "x") == "Sweater"   # 복수형
    assert fields.extract_item("CARDIGAN", "x") == "Cardigan"  # 대소문자 정규화


def test_extract_item_falls_back_to_title_when_product_type_junk():
    # Lisa Yang: product_type=시즌태그, 아이템은 title에
    assert fields.extract_item("SS26 - Seasonal", "The Alain Sweater") == "Sweater"
    assert fields.extract_item("AW26 Drop 1", "The Suzette Cardigan") == "Cardigan"
    # cashmereinlove: product_type=소재%, 아이템은 title에
    assert fields.extract_item("70%Wool 30% Cashmere", "Elen Cardigan") == "Cardigan"
    assert fields.extract_item("100%Cashmere", "Cara Fine Knit Cashmere Tee") == "Top"


def test_extract_item_none_when_no_keyword_anywhere():
    # 시즌/소재/성별 = 비아이템 → None (조용히 통과 X)
    assert fields.extract_item("SS26 - Seasonal", "Mystery Object") is None
    assert fields.extract_item("70%Wool 30% Cashmere", "Nameless") is None
    assert fields.extract_item("MENS", "Just A Gender") is None
    assert fields.extract_item(None, "") is None
    assert fields.extract_item("", "") is None


def test_extract_item_word_boundary_avoids_substring_false_match():
    # 'wool'이 아이템 아님, 'lambswool' 안의 wool로 오매칭 안됨
    assert fields.extract_item("Lambswool Jumper", "x") == "Sweater"  # jumper만 매칭
    # 'top'이 다른 단어 내부로 안 걸림
    assert fields.extract_item("Laptop Bag", "x") == "Accessory"      # bag, top 아님


def test_extract_item_longest_keyword_wins_in_multi_item_title():
    # 'Sari Wrap Knit Skirt': skirt(5) > wrap(4) → Skirt
    assert fields.extract_item("70% Wool 30% Cashmere", "Sari Wrap Knit Skirt") == "Skirt"


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
