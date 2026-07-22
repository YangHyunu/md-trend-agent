# Trend Intelligence 자료 소스·수집 레퍼런스

기준 시각: 2026-07-22 UTC


범위: 2주 데이터 기반 tracer의 Retail, Runway, Editorial/context, NAVER 소스와 현재 허용된 수집 방식

## 1. 이 문서의 사용법

이 문서는 소스를 찾기 위한 링크 모음인 동시에 수집 전 preflight 기준이다. URL이 열리거나 `robots.txt`가 허용하더라도 자동수집·저장·재사용 권리가 생기는 것은 아니다.

현재 상태는 다음과 같다.

| 구분 | 내부 승인 | 현재 실행 가능 범위 | live 자동수집 |
|---|---|---|---|
| Retail | cohort와 POC collector 승인 | Scrapling bounded 자동 probe + 수동 URL-linked fallback | 공개·비로그인·robots/명시적 제한 preflight 통과 시 `POC_ALLOWED` |
| Runway | CFCL primary, ArdAzAei backup과 POC collector 승인 | 공식 공개 경로의 bounded 자동·수동 observation | source별 robots/명시적 제한에 따라 `POC_ALLOWED|MANUAL_ONLY|BLOCKED` |
| Editorial/context | 최종 cohort와 POC collector 승인 | 짧은 anchor를 위한 bounded 자동수집 + full-body 수동 검토 | source별 preflight 후 `POC_ALLOWED|MANUAL_ONLY|BLOCKED` |
| NAVER | 20개 concept와 공식 API collector 개발 승인 | offline fixture·registry 개발 | entitlement, credentials, Shopping Insight category breadcrumb 확인 후 활성화 |

상태 필드는 반드시 분리한다.

- `owner_approval_status`: 내부 cohort·개발 승인
- `external_rights_status`: 제3자 이용조건·license·source contract 상태
- `live_activation_status`: 실제 collector 실행 가능 상태
- `access_status`: `full | partial | metadata_only | paywalled | blocked`
- `retention_status`: 저장 가능한 원문·파생 데이터 범위

## 2. 공통 수집 원칙

### 현재 기본 수집 방식

1. 공개·비로그인 페이지는 robots와 명시적 사이트 제한을 preflight한 뒤 Scrapling bounded POC 자동수집을 우선한다.
2. 자동 adapter가 실패하거나 `manual_only`이면 사람에게 허용된 정상 브라우저로 URL 전체 본문을 확인한다.
3. exact identity, market, locale, currency, 날짜, 가격, option·stock·buy 상태와 lineage를 구조화해 기록한다.
4. 원문 전체를 장기 저장하지 않고 URL, 관찰 메타데이터, 짧은 evidence anchor, 파생 태그와 시각만 저장한다.
5. 검색 스니펫, OG 설명, 제목만 열린 페이지, 앞부분만 읽은 기사는 최종 근거로 사용하지 않는다.
6. 같은 retailer family, publisher owner, image provider 또는 underlying event는 독립 근거로 중복 계산하지 않는다.

### POC 자동수집 runtime 순서

1. plan의 domain/path, request/page/product cap, concurrency, deadline과 retention을 읽는다.
2. 정적 HTML·공식 JSON/API처럼 가장 단순한 공개 경로를 우선한다.
3. 허용된 페이지가 JavaScript 렌더링을 요구할 때만 browser runtime을 사용한다.
4. Scrapling `Fetcher` 요청 전 robots를 preflight하고 spider를 사용할 때 `robots_txt_obey=true`를 강제한다. engine·version·selector version·policy snapshot digest를 manifest에 남긴다.
5. exact brand/product ID, canonical container, market, currency, seller와 purchase-state invariant가 깨지면 `partial|failed`로 격리한다.
6. `403`, CAPTCHA, WAF challenge, login wall, robots denial, 명시적 중단 통보는 우회하지 않고 `blocked` 또는 `missing`으로 기록한다.
7. 자동 adapter 실패 후 정상 브라우저 관찰이 가능하면 수동 observation task로 전환한다.

금지 방식:

- Cloudflare·CAPTCHA·WAF 우회
- proxy rotation이나 stealth session으로 지역·접근 제한 회피
- 로그인·결제·private API·문서화되지 않은 endpoint 자동 접근
- POC에서 raw HTML, JSON, 기사 전문, 이미지를 장기 artifact로 저장하거나 재배포
- 오래된 마지막 정상값을 현재 관찰로 재사용

## 3. Retail active cohort: 7개 브랜드, 20 channel observations

Retail 관찰은 해당 retailer·market·관찰일의 assortment, Listing, Offer만 지지한다. 판매량, sell-through, 수요 또는 한국 시장 반응을 추론하지 않는다.

| 브랜드 | 채널 | 대표 URL | 현재 모드 | lineage·주의점 |
|---|---|---|---|---|
| Extreme Cashmere | W CONCEPT | [brand](https://display.wconcept.co.kr/rn/brand/111192) · [PDP](https://m.wconcept.co.kr/Product/308346386) | manual | W/SSG family; operator와 seller 분리 |
| Extreme Cashmere | SSF SHOP | [PDP](https://www.ssfshop.com/%5BBEAKER%5D-EXTREME-CASHMERE/GM0026071548787/good) | manual | SSF/Samsung C&T family |
| Extreme Cashmere | Mytheresa US | [brand](https://www.mytheresa.com/us/en/women/designers/extreme-cashmere) · [PDP](https://www.mytheresa.com/us/en/women/extreme-cashmere-ndeg267-tina-cotton-and-cashmere-t-shirt-red-p01217677) | manual | LuxExperience family |
| Extreme Cashmere | Farfetch JP | [PDP](https://www.farfetch.com/jp/shopping/women/extreme-cashmere-n477-mimi-item-34771256.aspx) | manual | partner seller가 미노출이면 `unresolved` |
| Lisa Yang | W CONCEPT | [brand](https://display.wconcept.co.kr/rn/brand/114718) · [PDP](https://www.wconcept.co.kr/Product/308807574) | manual | 국내 primary; seller MXN Korea |
| Lisa Yang | Mytheresa US | [brand](https://www.mytheresa.com/us/en/women/designers/lisa-yang) · [PDP](https://www.mytheresa.com/us/en/women/lisa-yang-mable-cashmere-sweater-green-p01210902) | manual | LuxExperience family |
| Lisa Yang | Farfetch JP | [PDP](https://www.farfetch.com/jp/shopping/women/lisa-yang-cristine-item-33915653.aspx) | manual | market·currency와 partner seller 분리 |
| Guest in Residence | W CONCEPT | [brand](https://display.wconcept.co.kr/rn/brand/114268) · [PDP](https://www.wconcept.co.kr/Product/308288673) | manual | W/SSG family; seller 별도 기록 |
| Guest in Residence | Bloomingdale's US | [PDP](https://www.bloomingdales.com/shop/product/guest-in-residence-marcella-polo-sweater?CategoryID=2910&ID=5917262) | manual | US-only Offer 제약 보존 |
| Guest in Residence | Farfetch UK | [PDP](https://www.farfetch.com/uk/shopping/women/guest-in-residence-cashmere-sweater-item-27378815.aspx) | manual | partner seller 미노출 가능 |
| ARCH4 | NET-A-PORTER US | [PDP](https://www.net-a-porter.com/en-us/shop/product/arch4/clothing/v-neck/marisol-cashmere-cardigan/46376663163064116) | manual | Mytheresa와 LuxExperience family로 dedup |
| ARCH4 | SSENSE US | [PDP](https://www.ssense.com/en-us/women/product/arch4/brown-boston-v-neck-sweater/18536601) | manual | exact Offer 상태만 사용 |
| ARCH4 | Mytheresa US | [PDP](https://www.mytheresa.com/us/en/men/arch4-cashmere-sweater-beige-p01144525) | manual | menswear 예시이므로 gender scope 분리 |
| &Daughter | NET-A-PORTER US | [PDP](https://www.net-a-porter.com/en-us/shop/product/daughter/clothing/v-neck/slim-cashmere-and-cotton-blend-sweater/46376663163039856) | manual | LuxExperience family |
| &Daughter | Shopbop | [PDP](https://www.shopbop.com/enya-cardigan-daughter/vp/v%3D1/1521607805.htm) | manual | KR locale은 한국 retailer identity가 아님 |
| &Daughter | OPEN HOUSE Canada | [PDP](https://shop-openhouse.com/collections/daughter/products/and-daughter-ava-cardigan-dark-natural) | manual | `$`만 보이면 currency를 추정하지 않음 |
| Iris von Arnim | LODENFREY Germany | [PDP](https://www.lodenfrey.com/Iris-von-Arnim-Fallou-Cashmere-Pullover-22.html) | manual | heritage-luxury ceiling 역할 |
| Iris von Arnim | UNGER Germany | [category](https://www.unger.de/en/designer/iris-von-arnim/sweater/) | manual | category와 대표 PDP를 같은 시각에 확인 |
| Iris von Arnim | Farfetch UK | [PDP](https://www.farfetch.com/uk/shopping/women/iris-von-arnim-capri-sweater-item-24709822.aspx) | manual | partner seller가 없으면 `unresolved` |
| Cashmere in Love | Farfetch UK | [category](https://www.farfetch.com/uk/shopping/women/cashmere-in-love/items.aspx) · [PDP](https://www.farfetch.com/om/shopping/women/cashmere-in-love-blake-cashmere-jumper-item-23062325.aspx) | manual | 단일 해외 retailer의 current buyable 30+ 기준으로 포함 |

한국 current new-retail이 없어도 해외 multi-brand retailer 한 곳에서 exact-brand current buyable card 30개 이상과 대표 buyable PDP가 확인되면 `included/overseas-only`로 포함한다. 한국 coverage는 계속 `missing`이다.

### Reserve·fallback·monitor

| 역할 | 브랜드 | 채널·대표 URL | 처리 |
|---|---|---|---|
| Warm reserve | LE17 SEPTEMBRE | [W CONCEPT](https://m.wconcept.co.kr/Product/308554052) · [SSF](https://www.ssfshop.com/LE17SEPTEMBRE/GM0026041565411/good) · [SSENSE](https://www.ssense.com/en-us/women/product/le17septembre/black-asymmetrical-draped-midi-dress/19051431) · [Merci](https://merci-merci.com/en/products/le-17-septembre-maille-ouverte-bleu) | adjacent style reference, active denominator 제외 |
| Eligible fallback | COS | [SSF](https://www.ssfshop.com/COS/GRKL25120584584/good) · [Nordstrom](https://www.nordstrom.com/s/cashmere-crew-neck-sweater/9037605) | minimum 2, 권장 3 미충족 |
| Monitor | Le Cashmere | W exact catalog non-buyable; US shop closed | current independent overseas retailer가 생길 때 재검토 |
| Monitor | Quince | US DTC/Goody만 확인 | 한국 검색 collision, active 제외 |
| Monitor | PLUSHMERE | SSF/Kolon current | 독립 해외 retailer 0, active 제외 |

## 4. Runway cohort: 공식 공개 경로 2개

| 역할 | Collection event | 공식 경로 | bounded coverage | 현재 모드 |
|---|---|---|---|---|
| Primary | CFCL Fall/Winter 2026 `VOL.12` | [CFCL official collection](https://cfcl.jp/en/pages/collection-vol-12) | 공식 gallery의 관찰 source-position 수는 48이나 개별 Look 전체 번호가 선언되지 않아 `official_total=null` | manual URL-linked observation |
| Backup | ArdAzAei Autumn Winter 2026 RTW | [official sitemap](https://www.ardazaei.com/sitemap.xml) · [Look 1](https://www.ardazaei.com/products/tfs-02) · [Look 38](https://www.ardazaei.com/products/look-38) | sitemap의 연속 `Look 1..38`, `official_total=38` | manual URL-linked observation |

Vogue의 [CFCL FW26](https://www.vogue.com/fashion-shows/fall-2026-ready-to-wear/cfcl)과 [ArdAzAei FW26](https://www.vogue.com/fashion-shows/fall-2026-ready-to-wear/ardazaei)은 review/discovery lineage로만 둔다. 로그인 또는 Start free trial 경로를 active fixture로 사용하지 않는다. Vogue review와 gallery, 공식 브랜드 페이지, 다른 매체가 같은 collection을 다뤄도 `underlying_event_id`는 하나다.

수집 grain은 `Collection → Look → Appearance`다. 이미지에서 보이는 color, silhouette, neckline, pattern, visual texture는 검토 후 태깅할 수 있지만 캐시미어·정확한 혼용률은 공식 텍스트가 특정 Appearance에 연결될 때만 확정한다. Runway Appearance를 Retail product/Offer와 병합하지 않는다.

자동화 경계:

- CFCL 공식 공개 경로는 POC preflight 후 bounded 자동 probe 또는 수동 observation으로 검증한다. 예약·반복 production 수집과 장기보존은 별도 계약 대상으로 둔다.
- ArdAzAei 이용조건이 spider/crawl/scrape를 제한하는 범위는 자동수집하지 않고 공식 [press room](https://www.ardazaei.com/en/page/press)을 통한 계약 또는 수동 관찰 가능 범위를 검토한다.
- 상용 대안은 [Launchmetrics Spotlight](https://www.launchmetrics.com/spotlight/)이지만 내부 분석, 파생 metadata와 automated delivery 권리를 계약서에 명시해야 한다.

## 5. Editorial/context cohort

| 역할 | 소스 | 대표 URL | 허용 주장 | 현재 모드 |
|---|---|---|---|---|
| Active | Fashionista | [NYFW FW26](https://fashionista.com/2026/02/new-york-fashion-week-fall-2026-trends) · [Milan FW26](https://fashionista.com/2026/03/milan-fashion-week-fall-2026-trends) | named collection의 dated qualitative theme | manual full-body |
| Active | Marie Claire US | [Fall 2026 Fashion Trends](https://www.marieclaire.com/fashion/fall-fashion/fall-2026-fashion-trends/) | multi-city FW26 knit·texture·layering 맥락 | manual full-body |
| Active locale context | Marie Claire Korea | [Paris FW26 trend](https://www.marieclairekorea.com/fashion/2026/03/paris-fashionweek/) | 한국어 editorial 해석; 한국 수요 주장은 금지 | manual full-body |
| Active upstream context | Woolmark | [AW26/27 Knit It All](https://www.woolmark.com/industry/source-wool/the-wool-lab/themes/knit-it-all/) | 소재·편직 방향; runway vote가 아님 | manual full-body |
| Monitor/context-only | Highsnobiety | [Argyle article](https://www.highsnobiety.com/p/argyle-pattern-trend/) | 2024 문화·스타일 recurrence framing | manual; active corroboration 제외 |
| Optional supplement | Vogue Korea | FW26 개별 기사 | 특정 look·collection 해석 | article-level manual only |

Editorial은 단독으로 prevalence, velocity, demand 또는 sales를 증명하지 않는다. Fashionista의 여러 기사는 Breaking Media family 하나이며, Marie Claire US/Korea도 licensing lineage가 확정되기 전 독립 trend vote로 합산하지 않는다. Woolmark는 upstream material direction으로 별도 분류한다. affiliate, sponsored, commerce module은 organic editorial assertion과 분리한다.

승인 전 저장 가능 필드:

- URL, publisher·owner family, author, publication/modification date
- article type, affiliate·sponsored·licensed state
- `underlying_event_id`, `provider_family_id`, `article_origin_id`
- 접근 상태, reviewer-derived tags, 짧은 evidence anchor, `observed_at`

기사 전문, raw HTML·JSON과 이미지는 저장하지 않는다.

## 6. NAVER 공식 API cohort

NAVER 20개 concept identity와 공식 API collector 개발은 owner-approved다. 정확한 keyword bundle은 별도 MD 검토 후 `keyword_bundle_status=approved`로 승격한다. 현재 Shopping Insight `category_id`는 공식 breadcrumb 확인 전 `null`이다.

| 서비스 | Method·endpoint | 역할 |
|---|---|---|
| Search Trend | `POST https://naverapihub.apigw.ntruss.com/search-trend/v1/search` | 같은 response snapshot 안의 상대 검색 관심 변화 |
| Shopping Insight Category | `POST https://naverapihub.apigw.ntruss.com/shopping/v1/categories` | 승인 category의 상대 click-interest |
| Shopping Insight Keyword | `POST https://naverapihub.apigw.ntruss.com/shopping/v1/category/keywords` | category 안에서 승인 concept의 상대 관심 |

인증 헤더는 `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`이며 값은 로그·fixture·오류·커밋에 남기지 않는다.

승인 concept 20개:

1. `cashmere_cardigan`
2. `cashmere_pullover`
3. `fine_gauge_knit`
4. `chunky_knit`
5. `brushed_fuzzy_knit`
6. `polo_knit`
7. `cashmere_hoodie`
8. `knit_dress`
9. `knit_pants`
10. `knit_skirt`
11. `poncho_cape`
12. `cashmere_scarf`
13. `balaclava_hooded_scarf`
14. `beanie_bonnet`
15. `twinset_layering`
16. `burgundy_knit`
17. `grey_knit`
18. `lilac_purple_knit`
19. `colorblock_knit`
20. `striped_knit`

운영 기본값:

- concept당 keyword 1~5개, bare `니트` 금지
- 요청당 group 5개, 전체 4개 batch
- 주 1회 시작, `<=1 RPS`
- 서로 다른 response·기간·query version의 ratio를 직접 비교하지 않음
- 응답에 없는 값은 0이 아니라 `provider_missing`
- legacy category `50000805`와 임의의 `cashmere` category 금지
- normalized observation과 response hash만 저장하고 raw response body는 provider contract 검토 전 `none`

공식 문서:

- [API HUB 개요](https://guide.ncloud-docs.com/docs/apihub-overview)
- [Search Trend](https://api.ncloud-docs.com/docs/naver-api-hub-search-trend)
- [Shopping Insight Category](https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-categories)
- [Shopping Insight Keyword](https://api.ncloud-docs.com/docs/naver-api-hub-shopping-insight-keywords)

## 7. 관찰 레코드 최소 필드

모든 소스 공통:

- `source_id`, canonical URL, source contract version·digest
- `observed_at`, `effective_from`, `effective_to`, `ingested_at`
- `market`, `locale`, `currency`
- `access_status`, `coverage_status`, expected·observed count
- `owner_approval_status`, `external_rights_status`, `live_activation_status`
- `publisher_family_id`, `provider_family_id`, `underlying_event_id`
- content hash를 합법적으로 계산할 수 있을 때의 hash와 collector/reviewer version

Retail Offer 추가 필드:

- `retailer_operator`, `retailer_family_id`, `seller`, `shipper`
- `source_product_id`, `source_style_id`, `variant_id`
- price, markdown, option, availability, buy/cart state

## 8. 실행 전 체크리스트

- [ ] URL과 source identity를 full body에서 다시 확인했다.
- [ ] 관찰 시각, market, locale, currency를 고정했다.
- [ ] owner approval과 external rights를 별도 상태로 기록했다.
- [ ] 자동수집이면 allowed path·field·frequency·TTL·retention 계약이 있다.
- [ ] publisher/provider/retailer/event family 중복을 제거했다.
- [ ] raw body·image를 저장할 권리가 없으면 retention을 `none`으로 설정했다.
- [ ] `blocked`, `partial`, `missing`, `zero`를 서로 바꾸지 않았다.
- [ ] 결과의 허용 주장과 금지 주장을 함께 기록했다.

## 9. 근거 우선순위

1. `AGENTS.md`
2. [Brand.md](../../Brand.md)


이 문서의 URL과 availability는 2026-07-22 관찰 snapshot이다. 실제 tracer 실행 직전에 같은 계약 버전으로 재확인하며, 변동은 기존 값을 덮어쓰지 않고 새로운 observation으로 남긴다.
