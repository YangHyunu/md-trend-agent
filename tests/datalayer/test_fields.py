from datalayer import fields
from datalayer.review_queue import IGNORE, ReviewQueue


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


def test_extract_materials_word_boundary_avoids_substring_false_positives():
    # lambswool 상품은 wool을 포함하지 않아야 하고, silky 상품은 silk를 포함하지 않아야 함 (MDA-2)
    mats = fields.extract_materials("100% Lambswool Cardigan", "silky finish", "")
    assert set(mats) == {"lambswool"}


def test_extract_silhouettes_multi_value_in_appearance_order():
    # 한 상품에 여러 fit → 등장 순서대로 전부 수집 (MDA-4 rung1)
    out = fields.extract_silhouettes("Relaxed Fit Oversized Sweater", [], "")
    assert out == ["Relaxed", "Oversized"]


def test_extract_silhouettes_reads_body_html():
    # 실루엣어는 주로 body_html(설명글)에 있음 — 거기서도 잡아야
    out = fields.extract_silhouettes("Plain Sweater", [], "A wonderfully relaxed, oversized silhouette.")
    assert out == ["Relaxed", "Oversized"]


def test_extract_silhouettes_excludes_texture_and_quality_noise():
    # ribbed/crew(텍스처·넥라인), soft/light/classic(품질) = 실루엣 아님 → 배제
    out = fields.extract_silhouettes("Ribbed Crew Sweater", ["cable"], "soft, light, classic knit")
    assert out == []


def test_extract_silhouettes_wide_bare_excluded_but_wide_leg_kept():
    # 'wide' 단독(wide neck 등)은 모호 → 배제. 'wide-leg'만 채택.
    assert fields.extract_silhouettes("Wide Neck Top", [], "") == []
    assert fields.extract_silhouettes("Wide-leg Trousers", [], "") == ["Wide-leg"]


def test_extract_silhouettes_slim_fit_folds_to_slim_no_double():
    # 'slim fit'은 bare 'slim'으로 잡힘 — 중복 카운트 안 함
    assert fields.extract_silhouettes("Slim Fit Jeans", [], "") == ["Slim"]


def test_extract_silhouettes_dedups_repeated_term():
    assert fields.extract_silhouettes("Oversized oversized cocoon coat", [], "") == ["Oversized", "Cocoon"]


# ── MDA-8 색 8계열 정규화 ──
def test_map_color_family_neutral_and_token_inside_phrase():
    assert fields.map_color_family("BLACK") == "뉴트럴"
    assert fields.map_color_family("HEATHER GREY") == "뉴트럴"   # 구절 안의 grey
    assert fields.map_color_family("Ivory") == "뉴트럴"


def test_map_color_family_maps_each_family():
    assert fields.map_color_family("Camel") == "베이지·브라운"
    assert fields.map_color_family("DELFT BLUE COMBO") == "블루·네이비"  # blue, combo는 토큰 아님
    assert fields.map_color_family("Sage Brush") == "그린"
    assert fields.map_color_family("Burgundy") == "레드·핑크"
    assert fields.map_color_family("BUTTER") == "옐로·오렌지"
    assert fields.map_color_family("Aubergine") == "퍼플"


def test_map_color_family_pattern_wins_over_color():
    # 패턴 단어가 있으면 멀티·패턴(색보다 우선)
    assert fields.map_color_family("Blue Floral") == "멀티·패턴"
    assert fields.map_color_family("Striped") == "멀티·패턴"


def test_map_color_family_word_boundary_no_substring_falsematch():
    # 'redwood' 안의 red로 오매칭 안됨 (경계)
    assert fields.map_color_family("Redwood") is None


def test_map_color_family_unknown_and_ambiguous_return_none():
    # 미지명(외국어/시적)·의도적 제외(애매) → None → 큐 대상
    for raw in ("noir", "eclipse", "limone", "deep cloud", "khaki", "midnight"):
        assert fields.map_color_family(raw) is None, raw


def test_color_field_routes_unmatched_to_queue_multi_value():
    # 색은 NormalizedField(multi_value=True)로 공유 엔진에 붙음 (MDA-7/MDA-8)
    from datalayer.review_queue import normalize
    q = ReviewQueue()
    product = {"colors_raw": ["Navy", "noir", "Sage"]}  # Navy·Sage 매칭, noir 미매칭
    out = normalize(fields.color_field(), product, brand="b", queue=q, overrides={})
    assert out == ["블루·네이비", "그린"]           # 매칭 canon만, 순서유지
    assert q.get("color", "b", "noir") is not None    # 미매칭은 큐로


def test_extract_materials_still_matches_standalone_keyword():
    mats = fields.extract_materials("Wool and Silk Blend", "", "")
    assert set(mats) == {"wool", "silk"}


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


def test_extract_item_or_queue_matches_without_queueing():
    q = ReviewQueue()
    item = fields.extract_item_or_queue("Sweater", "Cozy Knit", brand="b",
                                        queue=q, overrides={})
    assert item == "Sweater"
    assert q.entries() == []


def test_extract_item_or_queue_unmatched_queues_both_candidates():
    # AC fixture: SS26/70%Wool 류 진짜 비값 → None + 큐
    q = ReviewQueue()
    item = fields.extract_item_or_queue("SS26 - Seasonal", "Mystery Object",
                                        brand="lisayang", queue=q, overrides={})
    assert item is None
    raws = {e.raw_value for e in q.entries()}
    assert raws == {"SS26 - Seasonal", "Mystery Object"}
    assert all(e.field == "item" and e.brand == "lisayang" for e in q.entries())


def test_extract_item_or_queue_override_resolves_without_requeue():
    q = ReviewQueue()
    overrides = {"ss26 - seasonal": IGNORE}
    item = fields.extract_item_or_queue("SS26 - Seasonal", "The Alain Sweater",
                                        brand="lisayang", queue=q, overrides=overrides)
    assert item == "Sweater"  # product_type=IGNORE로 무시, title 키워드로 매칭
    assert q.entries() == []  # 어느 쪽도 큐에 안 올라감(재질문 X)


def test_extract_item_or_queue_learned_override_maps_directly():
    q = ReviewQueue()
    overrides = {"beret": "Hat"}
    item = fields.extract_item_or_queue("Beret", "Beret", brand="b",
                                        queue=q, overrides=overrides)
    assert item == "Hat"
    assert q.entries() == []


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


# ── MDA-5 Lisa Yang handle 색추출 ──
def test_extract_colors_from_handle_basic():
    # the-alain-sweater-navy − title슬러그 = navy
    assert fields.extract_colors_from_handle("the-alain-sweater-navy", "The Alain Sweater") == ["navy"]


def test_extract_colors_from_handle_multiword_poetic_preserved():
    # deep-cloud → "deep cloud" 한 색명으로 보존(토큰 쪼개지 않음) → MDA-8/큐가 판정
    assert fields.extract_colors_from_handle(
        "the-alayne-dress-deep-cloud", "The Alayne Dress") == ["deep cloud"]


def test_extract_colors_from_handle_excludes_material_token():
    # graphite-boucle: boucle(소재/기법)는 배제, graphite만
    assert fields.extract_colors_from_handle(
        "the-jayden-trousers-graphite-boucle", "The Jayden Trousers") == ["graphite"]


def test_extract_colors_from_handle_keeps_foreign_unknown():
    # noir(외국어 미지명)는 색후보로 보존 → colors_raw → MDA-7 큐
    assert fields.extract_colors_from_handle("the-caisa-sweater-noir", "The Caisa Sweater") == ["noir"]


def test_extract_colors_from_handle_empty_when_no_remainder():
    # handle이 title슬러그와 같음(변형 색 없음) → []
    assert fields.extract_colors_from_handle("the-plain-sweater", "The Plain Sweater") == []
    assert fields.extract_colors_from_handle("", "The Plain Sweater") == []


def test_extract_colors_ladder_uses_handle_when_no_structured():
    # 구조화 색 없고 handle 있으면 handle rung (Lisa Yang 경로)
    out = fields.extract_colors([], "The Alain Sweater", [], "raw",
                                handle="the-alain-sweater-navy")
    assert out == ["navy"]


def test_extract_colors_structured_still_wins_over_handle():
    opts = [{"name": "color", "values": ["Ivory"]}]
    out = fields.extract_colors(opts, "t", [], "raw", handle="t-navy")
    assert out == ["Ivory"]
