# Cashmere 브랜드 Retail source qualification

조사·교정일: 2026-07-22
상태: 해외 단일 30+ 포함 기준 오너 결정 반영; exact fixture·관찰 범위는 GitHub Issue [#17](https://github.com/bizarrecube/TPQT_AGENT/issues/17) 검토 중

이 문서는 2주 Trend Intelligence tracer의 **Retail 후보와 실제 관찰 fixture 판정**을 기록한다. 초기 검색 결과의 상품-card 수를 그대로 통과로 보지 않고, exact brand/product identity, market·locale·currency, 가격, option/stock, buy/cart 상태가 있는 category/PDP 전체 본문을 기준으로 재검증한 결과다.

Runway의 CFCL·ArdAzAei는 Retail 브랜드 fixture가 아니므로 이 문서 범위에 넣지 않는다. 해당 Vogue exact path는 manual-review-only이며, 계정 요구를 포함한 접근 조건과 source contract가 해소되기 전에는 unauthenticated/live 자동수집 대상으로 사용하지 않는다.

## 판정 기준

- 한국 우선 surface(W CONCEPT·MUSINSA·SSF)는 선호 leg지만 필수 조건은 아니다.
- 한국 current new-retail이 0이어도 해외 multi-brand retailer 한 곳의 exact-brand category full body에서 current buyable product card 30개 이상과 대표 buyable PDP를 확인하면 `included / overseas-only`로 편입한다. 한국 coverage는 `missing`으로 보존하고 한국 시장 주장에는 사용하지 않는다.
- 권장 관찰 채널은 브랜드당 3개다. 별도 market/operator 가치를 만드는 강한 4번째 채널만 최대 4개까지 둔다.
- SOLD OUT-only, USED/recommerce, 구매대행, 해외 사이트의 KR locale/한국 배송, lexical collision, snippet-only, stale PDP는 qualifier에서 제외한다.
- 검색 결과 수, category header 수, URL 존재는 discovery 정보다. exact identity와 current buyability를 full body에서 확인해야 통과한다.
- W CONCEPT·MUSINSA·SSF는 hybrid platform이다. Listing/Offer마다 operator, seller, shipper를 분리해 기록한다.
- Mytheresa와 NET-A-PORTER는 LuxExperience family다. Farfetch와 Browns도 같은 corporate family다. storefront가 달라도 독립 owner corroboration으로 중복 계산하지 않는다.
- Retail 관찰은 해당 retailer/market/date의 assortment·Listing·Offer와 source-text attribute만 지지한다. 판매량, sell-through, 수요 또는 trend direction은 지지하지 않는다.

## 판정 요약

| 역할 | 브랜드 | 판정 | 현재 결론 |
|---|---|---|---|
| Active 1 | Extreme Cashmere | PASS, 최대 4채널 | W CONCEPT·SSF SHOP·Mytheresa·Farfetch |
| Active 2 | Lisa Yang | PASS, 권장 3채널 | W CONCEPT·Mytheresa·Farfetch; SSF 3 current SKU는 support/monitor |
| Active 3 | Guest in Residence | PASS, 권장 3채널 | W CONCEPT·Bloomingdale's·Farfetch |
| Included 4 | ARCH4 | PASS, overseas-only 3채널 | NET-A-PORTER·SSENSE·Mytheresa; 한국 current new-retail 0 |
| Included 5 | &Daughter | PASS, overseas-only 3채널 | NET-A-PORTER·Shopbop·OPEN HOUSE; 한국 current new-retail 0 |
| Included 6 | Iris von Arnim | PASS, overseas-only 3채널 | LODENFREY·UNGER·Farfetch; 한국 current new-retail 0 |
| Included 7 | Cashmere in Love | PASS, overseas-only 1채널 30+ | Farfetch UK exact-brand category; 한국 current new-retail 0 |
| Warm reserve | LE17 SEPTEMBRE | PASS, 최대 4채널 | W CONCEPT·SSF SHOP·SSENSE·Merci Paris; adjacent style reference |
| Eligible fallback | COS | PASS, 최소 2채널 | SSF SHOP·Nordstrom; 권장 3채널 미충족으로 2주 workload 제외 |
| Monitor | Le Cashmere | FAIL | 한국 exact catalog는 non-buyable, 독립 해외 retailer leg 없음 |
| Monitor | Quince | FAIL | US DTC/Goody만 확인; 한국 결과는 name/color collision |
| Monitor | PLUSHMERE | FAIL | SSF/Kolon current, 독립 해외 retailer leg 없음 |

## Active 3 대표 fixture

최신 source-qualification synthesis가 권장한 primary는 같은 operator·locale 안의 category/PDP pair다. 아래 수량·가격·재고는 2026-07-22 관찰 snapshot이며 바뀔 수 있다.

| 브랜드 | Primary pair | 관찰 범위 | lineage와 최대 주장 |
|---|---|---|---|
| Extreme Cashmere | [Mytheresa category](https://www.mytheresa.com/us/en/women/designers/extreme-cashmere) · [N°267 Tina PDP](https://www.mytheresa.com/us/en/women/extreme-cashmere-ndeg267-tina-cotton-and-cashmere-t-shirt-red-p01217677) | US/USD; category 109 products; Tina $255, add-to-bag, one size/XS–S, tomato/red, 70% cotton/30% cashmere | `retail:luxexperience:mytheresa`; current assortment·Offer와 attribute 관찰만 허용 |
| Lisa Yang | [Mytheresa category](https://www.mytheresa.com/us/en/women/designers/lisa-yang) · [Mable PDP](https://www.mytheresa.com/us/en/women/lisa-yang-mable-cashmere-sweater-blue-p01134482) | US/USD; category 224 products; Mable $505, sizes 0/XS–2/M–L, add-to-bag, Misty Blue, 100% cashmere | Extreme과 같은 LuxExperience family; 두 브랜드는 panel observation이지 retailer-family 독립표가 아님 |
| Guest in Residence | [Bloomingdale's category](https://www.bloomingdales.com/buy/guest-in-residence) · [Marcella PDP](https://www.bloomingdales.com/shop/product/guest-in-residence-marcella-polo-sweater?ID=5917262) | US/USD; category 74 items. 최신 synthesis는 sale $98, original $245, 60% markdown, XS–XL, add-to-bag/buy-now를 기록 | earlier $245-only 관찰은 body/hash와 page-level time이 없어 price-change event로 연결하지 않음; seller/shipper unresolved |

### 한국 수동 확인 backup

세 브랜드 모두 W CONCEPT/신세계 한 source family다. 세 브랜드 panel observation이지 세 개의 독립 market signal이 아니다. 실제 baseline으로 쓰기 직전에 승인된 human browser에서 같은 timestamp로 다시 열어 count, option, buy control과 seller를 확인해야 한다.

| 브랜드 | Category / PDP | 2026-07-22 관찰 snapshot | 주의점 |
|---|---|---|---|
| Extreme Cashmere | [W CONCEPT category](https://display.wconcept.co.kr/rn/brand/111192) · [PDP 308346386](https://m.wconcept.co.kr/Product/308346386) | 352 catalog / 47 buyable; SS26 cardigan, ₩276,701, OLEANDER-TU, buy/cart | seller MXN Korea; W CONCEPT는 intermediary; authorization unproven |
| Lisa Yang | [W CONCEPT category](https://display.wconcept.co.kr/rn/brand/114718) · [PDP 308797578](https://m.wconcept.co.kr/Product/308797578) | 561 catalog / 218 buyable; FW26 tank, ₩247,850, SEA, buy/cart | 국내 primary; seller MXN Korea; authorization unproven |
| Guest in Residence | [W CONCEPT category](https://display.wconcept.co.kr/rn/brand/114268) · [PDP 308809474](https://m.wconcept.co.kr/Product/308809474) | 381 catalog / 114 buyable; FW26 scarf, ₩190,688, options, buy/cart | seller MXN Korea; authorization unproven |

### 별도 market/operator PDP fallback

| 브랜드 | PDP | 역할과 제약 |
|---|---|---|
| Extreme Cashmere | [Farfetch JP N°477 Mimi](https://www.farfetch.com/jp/shopping/women/extreme-cashmere-n477-mimi-item-34771256.aspx) | JP/JPY buyable last-one Offer; partner boutique 미노출 |
| Lisa Yang | [Farfetch JP Cristine](https://www.farfetch.com/jp/shopping/women/lisa-yang-cristine-item-33915653.aspx) | JP/JPY exact buyable Offer; synchronized category denominator와 partner seller 미확인 |
| Guest in Residence | [Farfetch UK cashmere sweater](https://www.farfetch.com/uk/shopping/women/guest-in-residence-cashmere-sweater-item-27378815.aspx) | UK/GBP buyable last-one Offer; partner seller 미확인 |

## Overseas-only 포함 4

한국 current new-retail 부재를 실패 조건으로 쓰지 않고, 해외 retailer 한 곳이라도 exact-brand current buyable 30+ depth가 있으면 포함한다는 2026-07-22 오너 결정을 반영했다. 한국 coverage가 생긴 것으로 간주하거나 해외 시장 관찰을 한국 market signal로 변환하지 않는다.

| 브랜드 | Current 해외 채널 | 대표 full-body evidence | 역할과 제약 |
|---|---|---|---|
| ARCH4 | NET-A-PORTER US · SSENSE US · Mytheresa US | [NAP Marisol](https://www.net-a-porter.com/en-us/shop/product/arch4/clothing/v-neck/marisol-cashmere-cardigan/46376663163064116) · [SSENSE Boston](https://www.ssense.com/en-us/women/product/arch4/brown-boston-v-neck-sweater/18536601) · [Mytheresa sweater](https://www.mytheresa.com/us/en/men/arch4-cashmere-sweater-beige-p01144525) | NAP/Mytheresa는 LuxExperience family라 owner-family 한 표로 dedup. Mytheresa 예시는 menswear이므로 gender scope를 분리 |
| &Daughter | NET-A-PORTER US · Shopbop · OPEN HOUSE Canada | [NAP Slim](https://www.net-a-porter.com/en-us/shop/product/daughter/clothing/v-neck/slim-cashmere-and-cotton-blend-sweater/46376663163039856) · [Shopbop Enya](https://www.shopbop.com/enya-cardigan-daughter/vp/v%3D1/1521607805.htm) · [OPEN HOUSE Ava](https://shop-openhouse.com/collections/daughter/products/and-daughter-ava-cardigan-dark-natural) | Shopbop의 KR/ko 표시는 해외 operator의 locale이며 한국 retailer가 아님. OPEN HOUSE의 `$`는 currency label 미노출 |
| Iris von Arnim | LODENFREY Germany · UNGER Germany · Farfetch UK | [LODENFREY Fallou](https://www.lodenfrey.com/Iris-von-Arnim-Fallou-Cashmere-Pullover-22.html) · [UNGER category](https://www.unger.de/en/designer/iris-von-arnim/sweater/) · [Farfetch Capri](https://www.farfetch.com/uk/shopping/women/iris-von-arnim-capri-sweater-item-24709822.aspx) | heritage-luxury ceiling 역할을 core-peer 가격 분모와 분리. Farfetch partner seller는 unresolved |
| Cashmere in Love | Farfetch UK | [Farfetch category](https://www.farfetch.com/uk/shopping/women/cashmere-in-love/items.aspx) · [Blake PDP](https://www.farfetch.com/om/shopping/women/cashmere-in-love-blake-cashmere-jumper-item-23062325.aspx) | category 첫 페이지에서 30개를 넘는 exact-brand current available cards와 3-page pagination 확인. Blake PDP는 size, Add to Bag, delivery, 100% cashmere를 노출; partner seller는 unresolved |

확대된 2주 owner-review workload는 기존 domestic-backed 10개에 overseas-only 10개를 더한 총 **20개 channel observation**이다. 동일 owner family와 locale variant는 독립 corroboration으로 중복 계산하지 않는다.

## Warm reserve와 fallback

| 역할 | 브랜드 | 한국 채널 | 해외 채널 | 대표 evidence와 경계 |
|---|---|---|---|---|
| Warm reserve | LE17 SEPTEMBRE | [W BINDING TOP](https://m.wconcept.co.kr/Product/308554052) · [SSF Millie](https://www.ssfshop.com/LE17SEPTEMBRE/GM0026041565411/good) | [SSENSE dress](https://www.ssense.com/en-us/women/product/le17septembre/black-asymmetrical-draped-midi-dress/19051431) · [Merci knit](https://merci-merci.com/en/products/le-17-septembre-maille-ouverte-bleu) | 최대 4채널 PASS. Cashmere specialist가 아닌 adjacent style reference라 Active 3와 역할이 다름 |
| Eligible fallback | COS | [SSF cashmere](https://www.ssfshop.com/COS/GRKL25120584584/good) | [Nordstrom cashmere](https://www.nordstrom.com/s/cashmere-crew-neck-sweater/9037605) | 최소 2채널 PASS. 권장 3 미충족으로 현재 workload에는 넣지 않음 |

## 제외 / monitor

| 브랜드 | 판정 | 현재 빠진 leg 또는 제외 사유 |
|---|---|---|
| Le Cashmere | FAIL/monitor | W CONCEPT exact catalog 400건은 모두 non-buyable이고 SSF sampled PDP도 stale이다. 기존 `1,208` 검색 수를 current qualifier로 쓰지 않는다. Kolon/Circular Library owner commerce는 있지만 current independent overseas retailer 0이며 US shop은 closed다. |
| Quince | FAIL/monitor | US DTC/Goody만 확인. 한국 결과는 name/color collision이다. |
| PLUSHMERE | FAIL/monitor | SSF/Kolon current, 독립 해외 retailer 0. |

## 플랫폼별 재검증 결론

- **W CONCEPT**: Lisa Yang과 Guest in Residence의 가장 강한 국내 full-body surface다. Extreme Cashmere와 LE17도 30+ buyable depth가 있다. Le Cashmere는 exact catalog identity가 있어도 400개 모두 non-buyable이라 current qualifier가 아니다.
- **MUSINSA**: 조사한 12개 브랜드 모두 direct official/current-new brand shop 0이다. Extreme·LE17·COS·PLUSHMERE는 USED 위주이고 Le Cashmere는 collaboration/USED라 qualifier로 쓰지 않는다. 다만 한국 leg가 0이라는 사실만으로 강한 overseas-only 브랜드를 제외하지 않는다.
- **SSF SHOP**: Extreme Cashmere·LE17·COS·PLUSHMERE가 current다. Lisa Yang도 current PDP가 있지만 W CONCEPT를 국내 primary로 둔다. BEAKER와 10 Corso Como sub-shop은 SSF/Samsung C&T family 하나로 센다.
- **LuxExperience**: Mytheresa와 NET-A-PORTER를 별도 storefront로 관찰할 수 있지만 independent corroboration으로 중복 계산하지 않는다.
- **Farfetch**: 별도 platform/market Offer는 보존하되 partner boutique가 노출되지 않으면 seller provenance는 unresolved다. Cashmere in Love는 exact-brand current available 30+ category depth로 포함하지만 Farfetch 한 family의 관찰이라는 한계는 유지한다.

## 수집·저장 권리 gate

이번 조사로 확인한 것은 **공개 full-body 관찰 가능성과 POC source 후보**다. 공개 페이지, HTTP 200 또는 성공한 parse만으로 production 장기수집·원문보존·재배포 권한이 생기는 것은 아니지만, 이를 이유로 bounded POC 자동수집까지 일괄 금지하지 않는다.

- 현재 production 지속수집 계약이 확정된 source는 0개다.
- 공개·비로그인 페이지가 robots와 명시적 사이트 제한을 위반하지 않으면 Scrapling 기반 opt-in POC collector를 작은 request/page/product cap과 deadline으로 활성화할 수 있다.
- POC raw HTML/JSON은 메모리에서 파싱하고 장기 artifact로 보존하지 않는다. URL, 구조화 사실, 짧은 evidence anchor와 hash는 저장할 수 있으며 image는 기본 `link_only`다.
- adapter 실패 또는 `manual_only` source는 정상 브라우저의 수동 URL-linked observation으로 보완한다.
- fixture에는 Offer별 `retailer_operator`, `seller`, `shipper`, `market`, `locale`, `currency`, `observed_at`, `availability_state`, `source_family_id`를 기록한다.
- 2주 tracer는 acquisition, provenance, normalization, missingness, replay, review cost와 source-contract stability만 검증한다. trend usefulness, demand, lead value 또는 performance correlation은 검증하지 않는다.

## 근거

- `.omo/ulw-research/20260722-trend-source-qualification/SYNTHESIS.md`
- `.omo/ulw-research/20260722-retail-channel-revalidation/SYNTHESIS.md`
- `.omo/teams/team-e766f7a8/artifacts/retail-fixtures.md`
- `.omo/teams/team-e766f7a8/artifacts/cohort-composition-wave2.md`
- `.omo/teams/team-c0e35f0a/artifacts/lisa-arch4-channels.md`
- `.omo/teams/team-c0e35f0a/artifacts/daughter-iris-channels.md`
- GitHub Issue [#17](https://github.com/bizarrecube/TPQT_AGENT/issues/17)
