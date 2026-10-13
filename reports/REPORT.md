# Lab 25 ? Circuit Breakers, Caching & Reliability

**H? t?n / nh?m:** Nguy?n Minh Th?nh ? **MSV:** 2A202602556  
**Commit:** s? c?p nh?t b?ng commit tri?n khai tr??c khi n?p  
**?i?m t? ??ng:** 84 / 88; ??t to?n b? 84 ?i?m ki?m tra c?ng khai. 4 ?i?m SLO ?n ch? gi?ng vi?n; report ch?m tay /12.

K?t qu? d??i ??y d?ng seed 25. `reports/scoreboard.json` x?c nh?n m?i ki?m tra Game Day, workflow v? cache ??u pass tr?n seed 25, 26, 27. Kh?ng s?a simulator, test, k?ch b?n ho?c d?ch v? ???c cung c?p; kh?ng d?ng th?i gian th?c hay hard-code b?ng s? c? trong client/cache.

## 1. K?t qu? Game Day (naive vs resilient)

Ngu?n: [naive.json](gameday/naive.json), [resilient.json](gameday/resilient.json). `cost/turn` l? chi ph? m?i l??t **th?nh c?ng**; recovery `?` ngh?a l? k?ch b?n kh?ng ??nh ngh?a m?c h?i ph?c.

| B?ng | Client | availability | p95 (s) | amplification | retry_ratio | cost/turn | recovery (s) | PASS? |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| G1 | naive | 0.7194 | 7.157 | 7.738 | 6.738 | 2.163 | 4.0 | FAIL |
| G1 | resilient | 1.0 | 4.78 | 1.063 | 0.001 | 2.104 | 0.0 | PASS |
| G2 | naive | 0.456 | 15.034 | 9.904 | 8.904 | 4.627 | 155.0 | FAIL |
| G2 | resilient | 1.0 | 9.922 | 1.035 | 0.004 | 2.106 | 0.0 | PASS |
| G3 | naive | 1.0 | 4.768 | 1.164 | 0.164 | 2.328 | 0.0 | FAIL |
| G3 | resilient | 1.0 | 4.642 | 1.076 | 0.049 | 2.167 | 0.0 | PASS |
| G4 | naive | 1.0 | 13.764 | 1.004 | 0.004 | 2.008 | 0.0 | FAIL |
| G4 | resilient | 1.0 | 5.626 | 1.014 | 0.002 | 2.072 | 0.0 | PASS |
| G5 | naive | 0.3699 | 5.359 | 17.03 | 16.03 | 2.124 | ? | FAIL |
| G5 | resilient | 0.8179 | 5.477 | 1.003 | 0.002 | 2.504 | ? | PASS |
| G6 | naive | 0.517 | 4.836 | 12.344 | 11.344 | 2.009 | 0.0 | FAIL |
| G6 | resilient | 1.0 | 5.949 | 1.052 | 0.017 | 2.21 | 0.0 | PASS |

G1 c? 0 vi ph?m retry-after; G5 c? 0 retry l?i 400, 0 failover kh?ng c?n thi?t. G6 c? 0 route kh?ng t??ng th?ch. Traffic quay l?i alpha sau ph?c h?i: G2/G4/G6 ??u 100%; G1 90,4%.

## 2. C?u h?nh client v? l? do

| Tham s? | Gi? tr? | V? sao, b?ng ch?ng |
|---|---:|---|
| attempt_timeout_s | 8 s | G6 availability 100%, p95 5,949 s; timeout 30 s l?m availability c?n 94,88%. C? th?i gian failover trong deadline 30 s. |
| max_attempts_per_provider | 2 | M?t retry transient; G2 amplification 1,035 v? G3 retry_ratio 0,049. Th? 5 attempt khi breaker v? hi?u l?m G2 p95 19,208 s ngay c? khi c? budget. |
| min_time_left_s | 1 s | Ch? g?i attempt ?? th?i gian h?u ?ch; G6 m?c ??nh kh?ng c? GiveUp, test deadline pass. Timeout lu?n ???c ch?n b?i deadline c?n l?i. |
| backoff_base_s / cap_s | 0,25 / 4 s | Full jitter gi?m ??ng b? retry; G3 100% availability v?i retry_ratio 0,049. Test x?c minh kho?ng jitter, retry-after lu?n ???c t?n tr?ng. |
| retry_budget_ratio | 0,1 | G3 retry_ratio 0,049 ? 0,10; khi breaker h?ng, c? budget G3 0,068, kh?ng budget 0,163. |
| retry_budget_min_per_s / max_tokens | 0,5 / 20 | Cho retry l?c ?t traffic v? burst ng?n; kh?ng ph?i tr?n tuy?t ??i 10% v? c?n refill theo th?i gian v? token ban ??u. G2 budget-on retry_ratio 0,057. |
| quota_cooldown_s | 300 s | G5 ch? 2 l?i quota (hai deployment account A), 0 retry 400, availability 81,79%; kh?ng ch? cooldown quota. |
| breaker.window_size / min_calls | 20 / 10 | ?? m?u tr??c khi trip, qu?n k?t qu? c?; G2 100% availability, recovery 0 s; test sliding-window pass. |
| breaker.failure_rate_threshold | 0,5 | Trip l?i s?c kh?e, kh?ng t?nh 400/429 v?o failure rate; G5 c? 413 request sai nh?ng 0 failover v? ?ch. |
| breaker.slow_call_s / slow_rate_threshold | 5 s / 0,6 | Nh?n bi?t brown-out kh?ng l?i; G4 p95 gi?m 13,764 ? 5,626 s, availability 100%. |
| breaker.open_duration_s | 10 s | Fail fast r?i probe ??nh k?; G2 recovery 0 s, 100% traffic quay l?i alpha sau s? c?. Recovery n?y l? metric c?a to?n d?ch v?, kh?ng ph?i th?i ?i?m breaker ??ng. |
| breaker.half_open_max_probes / successes | 2 / 2 | Ch? 2 probe ?ang bay, 2 probe nhanh th?nh c?ng m?i ??ng; unit test concurrency v? generation pass. G2 amplification 1,035. |

S? ?? quy?t ??nh `on_error`:

| Lo?i l?i | Breaker | Retry c?ng provider | Failover | Cooldown |
|---|---|---|---|---|
| 400/401/403/404/422 v? l?i client kh?c | release permit | Kh?ng | Kh?ng, GiveUp client_error | Kh?ng |
| 429 insufficient_quota | release | Kh?ng | Ngay | 300 s theo deployment |
| 429 rate limit | release | Kh?ng ngay | Ngay | ?t nh?t retry-after; chia s? gi?a c?c call |
| 529/503, 5xx, timeout 0/408 | ghi failure | Ch? n?u s? attempt, token budget, breaker v? deadline cho ph?p; full jitter | Khi retry kh?ng ???c ph?p ho?c provider kh?ng d?ng ???c | Breaker OPEN |

M?i call m?i ?i t? primary, l?c tool capability. Khi h?t ladder, ch? ch? cooldown **rate limit** ? 5 s, breaker kh?ng OPEN v? c?n deadline. M?i Permit mang generation; k?t qu? t? th? h? c? b? b? qua, tr?nh ??ng/m? breaker do request c? ?ang bay. Simulator ch?y callback tu?n t?, concurrency ? ??y l? nhi?u request ?ang bay, kh?ng ph?i cam k?t thread-safety cho callback ?a lu?ng.

## 3. Ba th? nghi?m

C? th? ch?y l?i: `python scripts/run_experiments.py`. S? ??y ??: [experiments.json](experiments.json). Control d?ng b?n sao c?u h?nh v? subclass ch? trong script; kh?ng s?a client production ho?c b?ng s? c?.

### 3.1. Retry budget l? l?p ph?ng th? cu?i

Breaker `min_calls=1000000000`, `max_attempts_per_provider=5`; budget-off d?ng ratio=100, max_tokens=1e9, min_per_s=1e6.

| B?ng | Budget | availability | amplification | retry_ratio | recovery (s) | p95 (s) |
|---|---|---:|---:|---:|---:|---:|
| G2 | on | 0.9996 | 1.38 | 0.057 | 0.0 | 19.208 |
| G2 | off | 0.9674 | 1.595 | 0.392 | 35.0 | 21.935 |
| G3 | on | 1.0 | 1.136 | 0.068 | 0.0 | 4.55 |
| G3 | off | 1.0 | 1.164 | 0.163 | 0.0 | 4.768 |

? G2, budget ng?n l??ng retry t?ng t? 0,057 l?n 0,392; recovery gi?m t? 35 s xu?ng 0 s v? availability t?ng 96,74% ? 99,96%. G3 v?n 100% availability ? c? hai c?ch nh?ng budget gi?m retry_ratio 0,163 ? 0,068, gi?m chi ph? 2,327 ? 2,271 m?i l??t t?t. Budget kh?ng ch?n m?i failover n?n amplification v?n l?n h?n 1 + retry_ratio. Khi breaker ho?t ??ng ??ng, G2 amplification ch? 1,035; v?n c?n budget v? l?i c?u h?nh breaker, m?u ch?a ?? ho?c nhi?u provider c?ng l?i c? th? cho ph?p nhi?u retry tr??c khi trip.

### 3.2. Timeout 30 gi?y v? survivorship bias

| B?ng | Timeout | availability | give_up_reasons | p95 l??t th?nh c?ng (s) |
|---|---|---:|---|---:|
| G6 | 8 s | 1,0 | {} | 5,949 |
| G6 | 30 s | 0,9488 | deadline: 109; no_provider_available: 13 | 5,304 |
| G4 | 8 s | 1,0 | {} | 5,626 |
| G4 | 30 s | 1,0 | {} | 5,608 |

G6 m?t 122 l??t khi timeout 30 s v? m?t region c? th? treo, d?ng h?t deadline tr??c khi failover. p95 gi?m d? availability x?u ?i: metric ch? l?y l??t th?nh c?ng, b? c?c l??t b? treo/h?t h?n. G4 th?m latency nh?ng v?n th??ng tr? l?i tr??c 8 s; slow-call breaker v?n trip n?n n?ng timeout g?n nh? kh?ng ??i k?t qu?. Ch?n timeout d?a tr?n p99 **attempt b?nh th??ng**, deadline user c?n l?i v? th?i gian d?nh cho ?t nh?t m?t failover; p99 l??t hai-call kh?ng ??ng nh?t v?i p99 attempt.

### 3.3. B? l?c tool calling

? G6, b? l?c t?o **230 incompatible_routes** v? 230 GiveUp `incompatible_model_output`; availability gi?m 100% ? 90,36%, cost/turn t?ng 2,210 ? 2,290. V?i product manager, ??y l? 230 l??t m? model v?n c? th? n?i chuy?n nh?ng kh?ng th? t?o thao t?c c?ng c? ?? ho?n t?t y?u c?u c?a kh?ch. Fallback gi? r? ch? h?u ?ch khi gi? kh? n?ng c?n thi?t cho b??c c?ng vi?c; tool call ph?i gi? ? alpha/alpha-eu/beta.

## 4. Workflow ho?n ti?n

Ngu?n: [workflows.json](workflows.json), 500 session seed 25.

| Executor | completion | crashes | duplicate refunds | duplicate emails | lost refunds | overpaid (cents) | wasted LLM / crash |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive | 1.0 | 81 | 128 | 81 | 0 | 1496700 | 1.123 |
| yours | 1.0 | 66 | 0 | 0 | 0 | 0 | 0.303 |

Idempotency key d?ng c?p `(session_id, step)` m? h?a JSON, ?n ??nh qua retry/restart v? kh?ng nh?p nh?ng b?i d?u ph?n c?ch. Ch? idempotency key b?o v? side effect, nh?ng worker v?n l?m l?i classify/lookup v? t?n LLM; checkpoint t?ng b??c gi? k?t qu? ?? resume. Ch? checkpoint kh?ng b?o v? kho?ng tr?ng payment ?? commit nh?ng response/checkpoint ch?a ???c ghi: ch?y l?i s? tr? ti?n tr?ng. Ghi checkpoint tr??c payment c? th? l?m worker ch?t r?i skip m?t kho?n ch?a h? ???c tr?, g?y m?t refund.

Checkpoint ???c ghi **sau** th?nh c?ng; retry ch? b?t ServiceError/ServiceTimeout, WorkerCrash tho?t t?i runner. Exactly-once effects d?a v?o DurableStore b?n v?ng v? payment/email th?c thi idempotency; kh?ng ph?i m?i request m?ng ch? xu?t hi?n m?t l?n. Executor m?i c? 2500 checkpoint cho 500 workflow, 0 duplicate/lost v? 0,303 wasted LLM/crash ? 0,6.

## 5. Alerting & error budget

Prefix sums t?nh m?i window O(1). Lu?t page: 14,4? tr?n 1 h **v?** 5 m, ho?c 6? tr?n 6 h **v?** 30 m; ticket: 1? tr?n 3 d **v?** 6 h. Episode l? ?o?n li?n t?c rule ?ang firing, k?t th?c exclusive.

Ngu?n: [slo.json](slo.json).

| S? c? | Mong ??i | Naive alerter | Burn-rate alerter | ?? tr? burn-rate (ph?t) |
|---|---|---|---|---:|
| checkout_bug | page | page, 1 ph?t | page | 27 |
| provider_outage | page | page, 0 ph?t | page | 4 |
| deploy_blip | none | false page | none | ? |
| slow_leak | ticket | b? s?t | ticket, kh?ng page | 1337 |
| degraded_evening | page | page, 214 ph?t | page | 291 |
| night_spike | none | false page | none | ? |
| small_bump | none | false page | none | ? |

Naive c? 7 page episode, 3 false page; burn-rate c? 3 page, 1 ticket, 0 false page v? t?t c? s? c? ??ng h?n. Trong 30 ng?y c? 25.901.755 request, 55.618 bad, ???c ph?p 129.508,8 bad; availability 99,7853%. Budget ti?u **42,95%**, c?n **57,05%**, kh?ng ??ng b?ng release v? ch?a h?t budget.

`small_bump` (20 ph?t ? 12% l?i) kh?ng v??t ??ng th?i hai c?a s? page: v?i traffic ??u, 1 h error ratio ch? kho?ng 4%, burn 8? < 14,4?, 6 h burn kho?ng 1,33? < 6?. D? li?u th?c t? c?ng cho 0 page tr?n s? c? n?y; page theo 5 ph?t ??n l? g?y ??nh th?c kh?ng c?n thi?t. ??y l? ki?m tra c?ng khai; ch?a th? kh?ng ??nh ?i?m d? li?u SLO ?n.

## 6. Postmortem ? G2 v?i naive (blameless)

### T?m t?t

Alpha m?t 75% n?ng l?c GPU t? t=120 ??n t=300, l?m request ch? r?i timeout. Retry ba t?ng kh?ng c? jitter, budget, breaker hay fallback khu?ch ??i t?i l?n 9,904 attempt/call, bi?n suy gi?m provider th?nh m?t d?ch v? k?o d?i. Trong 2362 l??t, ch? 1077 th?nh c?ng (45,60%); recovery ???c simulator ?o l? 155 s sau khi provider ph?c h?i, c?n client resilient ??t 100% availability v? recovery 0 s.

### ?nh h??ng

**1285 l??t th?t b?i**, cost/turn t?t 4,627 thay v? 2,106 ? resilient; 2737 timeout, 3194 overloaded error v? 26298 rate-limit error. Provider g?p s? c? 180 s; c?a s? th?nh c?ng call 10 s g?n 0 t? kho?ng t=150 v? ch? c?i thi?n r? quanh t=455, cho th?y t?c ??ng k?o d?i sau t=300. V?i gi? ??nh traffic th?ng c? ??nh 4 l??t/s trong 30 ng?y, 10.368.000 l??t v? SLO 99,5%, budget = 51.840 l??t; ri?ng 1285 l??t th?t b?i ti?u **2,48% budget th?ng**, ch?a l?m c?n budget. T? l? th?t b?i 54,40% trong m?u lab l? **108,8 l?n** error ratio cho ph?p 0,5%, kh?ng ???c nh?m v?i 108,8 l?n budget c?a c? th?ng.

### Timeline (gi?y ?o)

Ngu?n: [CSV naive](gameday/naive_G2_overload_storm_timeseries.csv). M?i d?ng d??i l?y c?a s? `[t, t+10)`; success ratio = t?ng calls_ok / t?ng calls_done (call, kh?ng ph?i user turn). T?i trung b?nh d?ng t?ng attempts_alpha / 10.

| t | S? ki?n | attempts alpha/s | calls_ok / calls_done | success ratio |
|---:|---|---:|---:|---:|
| 110 | Tr??c s? c?, ch?y b?nh th??ng | 9,1 | 92 / 92 | 1,000 |
| 120 | M?t 75% GPU, k?t qu? c? v?n tr? v? | 6,2 | 32 / 32 | 1,000 |
| 150 | Retry storm xu?t hi?n | 166,5 | 0 / 49 | 0,000 |
| 290 | G?n cu?i s? c?, retry v?n cao | 146,1 | 0 / 41 | 0,000 |
| 300 | GPU ph?c h?i nh?ng d?ch v? ch?a ph?c h?i | 38,8 | 0 / 18 | 0,000 |
| 350 | V?n c?n h?u qu? c?a h?ng ??i | 17,9 | 0 / 39 | 0,000 |
| 450 | B?t ??u x? l? ???c c?c call | 13,7 | 45 / 70 | 0,643 |
| 455 | Ph?c h?i d?n; metric recovery = 155 s | 13,0 | 90 / 105 | 0,857 |
| 480 | Call success tr? l?i 100% | 10,6 | 124 / 124 | 1,000 |

![T?i attempt v? t? l? call th?nh c?ng: naive vs resilient](gameday/G2_overload_storm.png)

### Trigger vs root cause

Trigger l? m?t GPU, kh?ng ph?i sai s?t c? nh?n. Root cause n?m trong ch?nh s?ch retry m?c ??nh ba t?ng (app ? gateway ? SDK, t?i ?a 36 attempt/call), delay c? ??nh, kh?ng nh?n bi?t lo?i l?i v? thi?u gi?i h?n t?i/fallback. Simulator kh?ng h?y c?ng vi?c server khi client timeout: request c? ti?p t?c chi?m slot, retry m?i n?i h?ng ??i, th?i gian ch? t?ng, l?i timeout v? t?o th?m retry. V?ng ph?n h?i n?y t? gi? overload ngay sau khi GPU ?? ph?c h?i ? metastable failure; recovery kh?ng th? suy ra ch? t? tr?ng th?i GPU.

### ?i?u g? gi?p / l?m t? h?n

CSV, m? ph?ng l?p l?i c?ng seed v? ph?n lo?i timeout/529/429 gi?p t?i d?ng s? c?. Retry delay c? ??nh l?m c?c wave d?n nhau; 28381 vi ph?m retry-after tr?n G2 l?m t?i t? h?n v? v1 ch? c? alpha ?? nh?n m?i retry. Resilient chia t?i sang alpha-eu/beta, d?ng g?i khi breaker OPEN, probe gi?i h?n v? ch? m?t t?ng retry; G2 gi?m 34475 ? 4891 attempt, gi? to?n b? 2362 l??t th?nh c?ng. Quy tr?nh tr??c ??y thi?u ph?p th? s? c? sau khi provider h?i ph?c v? ch?a theo d?i amplification, t?o kho?ng tr?ng h? th?ng c?n kh?c ph?c.

### Action items

| # | H?nh ??ng | Lo?i | Owner | C?ch ki?m ch?ng |
|---|---|---|---|---|
| 1 | Chu?n h?a m?t t?ng retry, t?t retry SDK/gateway, b?t bu?c budget v? capability filter | prevent | Nguy?n Minh Th?nh ? client | CI G2 amplification ? 1,2; G3 retry_ratio ? 0,10; G6 incompatible_routes = 0 tr?n 3 seed |
| 2 | ??a multi-window burn-rate c?ng attempt rate, timeout, retry amplification l?n dashboard | detect | Nh?m SRE ShopAgent | Replay SLI: 3 page, 1 ticket, 0 false page; hi?n th? c? provider errors khi cache ?ang gi? availability |
| 3 | Breaker c? slow-call detection, 2 probe HALF-OPEN v? fallback v?ng/provider | mitigate | Nh?m n?n t?ng | Replay G2 recovery ? 30 s, primary_share ? 80%; G4 p95 ? 10 s; test generation/cancel pass |
| 4 | B? sung game day v?o ki?m tra tr??c ph?t h?nh, bao g?m giai ?o?n sau restore | prevent | Nh?m QA | 6/6 b?ng pass ? seed 25/26/27; ghi CSV v? scoreboard cho m?i thay ??i client |

## 7. M?t ?i?m y?u c?n l?i

G2 d? 100% availability, p95 v?n **9,922 s**, p99 **15,250 s**, cao h?n G3 p95 4,642 s. M?t s? request ban ??u ph?i ??i g?n timeout tr??c khi failover; beta c? gi? 1,4 so v?i alpha 1,0 n?n chuy?n t?i l?u l?m t?ng cost. N?u c? b?n provider c?ng ch?m, breaker fail fast c? th? gi? t?i th?p nh?ng kh?ng t? t?o kh? n?ng x? l? m?i; FAQ cache ch? gi?p c?u c?ng khai, kh?ng c?u tool flow. H??ng c?i thi?n l? gi?i h?n concurrency theo deployment v? deadline, quan s?t queue latency, ?u ti?n chat sang model nh? khi ph? h?p r?i benchmark l?i latency/chi ph?; kh?ng retry song song side effect m?t c?ch v? ?i?u ki?n.

## 8. Cache (Part G)

Ngu?n: [kh?ng cache](cache/resilient.json), [c? cache](cache/cached.json).

| Client | availability | faq_availability | cache_hit_ratio | stale_served | wrong_answers | outdated_answers | cost/turn | PASS? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| resilient | 0.8373 | 0.8424 | 0.0 | 0 | 0 | 0 | 1.386 | FAIL |
| cached | 0.9124 | 0.9645 | 0.652 | 157 | 0 | 3 | 0.915 | PASS |

| Tham s? cache | Gi? tr? | V? sao |
|---|---:|---|
| similarity_threshold | 0,90 | 0 wrong answers, hit 65,2%; 0,80 g?y 157 other_question, 0,97 gi?m hit c?n 58,1% m? v?n 0 wrong. |
| ttl_s | 60 s | 3 outdated ? 15; TTL 300 s c? 95 outdated. TTL 30 s ch? 2 outdated nh?ng hit th?p h?n 59,2% v? cost cao h?n 0,955 so v?i 0,915. |
| max_stale_s | 300 s | Bao tr?m outage 120 s; 157 stale served gi?p FAQ availability 96,45%, thay v? 87,33% khi stale=0. |
| max_entries | 500 | LRU gi?i h?n b? nh?, test eviction pass; ??t hit 65,2% v? kh?ng c?n t?ng capacity cho workload c?ng khai. |

Cache ch? ch?n embedding t??ng ??ng trong c?ng prompt_version, lo?i c?u c? nh?n, gi?i h?n TTL/stale v? invalidate to?n b? answer c? source b? c?p nh?t. Fresh hit ???c Serve ngay; stale ch? ???c tr? sau GiveUp v? lookup l?i t?i th?i ?i?m ??, tr?nh gi? hit c? qua webhook. Kh?ng gia h?n stored_at khi lookup; ch? provider answer m?i m?i refresh tu?i entry.

### 8.1. Th? nghi?m ng??ng

| Threshold | hit ratio | wrong_answers | wrong_answers_by_reason | cost/turn |
|---:|---:|---:|---|---:|
| 0,80 | 0,666 | 157 | other_question: 157 | 0,965 |
| 0,90 | 0,652 | 0 | {} | 0,915 |
| 0,97 | 0,581 | 0 | {} | 0,964 |

Ng??ng 0,80 tr?n c?c c?u g?n ngh?a nh?ng kh?c m?c ??ch; catalog c? c?c c?p refund_policy/refund_time, exchange_size/exchange_color, shipping_fee_city/shipping_fee_province v? payment_methods/cod (centroid cosine 0,86). JSON ch? ghi t?ng theo reason, kh?ng ghi s? l?i t?ng c?p; oracle ghi 157 `other_question`, kh?ng ph?i `other_user` hay `old_prompt`. Ng??ng 0,90 gi? ???c paraphrase v? lo?i near-miss trong tape, ti?t ki?m chi ph? h?n 0,97. Cost l? m?i l??t t?t, n?n nhi?u cache hit sai ? 0,80 kh?ng l?m cost/turn t?t th?p h?n.

### 8.2. Th? nghi?m TTL

| TTL (s) | hit ratio | outdated_answers | wrong_answers | cost/turn |
|---:|---:|---:|---:|---:|
| 30 | 0,592 | 2 | 0 | 0,955 |
| 60 | 0,652 | 3 | 0 | 0,915 |
| 300 | 0,731 | 95 | 0 | 0,863 |

Webhook b?o thay ??i refund t?i t=150 n?n invalidate gi?p tr?nh `ignored_invalidation`; thay ??i shipping t?i t=480 kh?ng c? webhook n?n client kh?ng bi?t ?? x?a. TTL bu?c t?i l?y d? li?u khi provider kh?e, gi?i h?n th?i gian tr? answer c?; stale window v?n c? th? k?o d?i ?? c? n?u provider l?i. TTL 300 t?i ?u hit/cost nh?ng kh?ng ??t ti?u ch? outdated ? 15, n?n ch?n 60 s.

### 8.3. Stale-if-error

Stale=0 l?m FAQ availability t? 96,45% xu?ng **87,33%**, hit 65,2% ? 56,1%, GiveUp `no_provider_available` t? 246 l?n 403. Stale=300 ph?c v? 157 answer stale; wrong_answers v?n 0 v? outdated v?n 3 ? seed 25. Outage to?n provider kh?ng th? l?y answer m?i, n?n rung cache gi?p gi? ph?n FAQ c?ng khai, v?i gi?i h?n freshness r? r?ng.

### C?u tr? l?i c? nh?n v? alert khi cache gi? dashboard xanh

C?u nh? ???n #48213 c?a t?i ? ??u?? ph? thu?c tr?ng th?i hi?n t?i, quy?n truy c?p v? d? li?u bi?n ??ng, n?n cache theo user v?n c? th? tr? sai tr?ng th?i, refund hay s? d?. Lab lo?i h?n personal request kh?i cache ?? kh?ng tr?n d? li?u ng??i d?ng; production c?n c?n ki?m tra quy?n t?i th?i ?i?m d?ng d? li?u.

Theo d?i availability ph?a user **v?** provider success/error/timeout rate, breaker OPEN, t? l? Serve(stale), tu?i answer v? cache hit/miss. C1 user availability 91,24%, FAQ 96,45% nh?ng 157 stale served l? t?n hi?u vi?c ph?c v? ?ang d?a v?o n?i dung c? khi upstream kh?ng tr? l?i. Page theo burn-rate upstream/critical tool flow, alert k?o d?i breaker OPEN ho?c stale v??t ng??ng freshness, tr?nh coi cache hit l? b?ng ch?ng provider kh?e.

## Ki?m ch?ng v? chu?n b? n?p

Windows kh?ng c? `make` trong m?i tr??ng n?y; ch?y tr?c ti?p ??ng c?c script m? Makefile g?i:

```powershell
python -m pip install -e ".[dev,plot]"
python -m pytest -q -p no:cacheprovider
python scripts/run_gameday.py --client both
python scripts/run_gameday.py --scenarios configs/scenarios_cache.yaml --client resilient,cached --out reports/cache
python scripts/run_workflows.py --executor both
python scripts/run_slo.py --alerter both
python scripts/run_experiments.py
python scripts/plot_timeseries.py --scenario G2_overload_storm
python scripts/grade.py --seeds 25,26,27
```

82/82 test pass; 6/6 b?ng Game Day, C1 cache, workflow v? SLO public pass. [scoreboard.json](scoreboard.json) ghi 84/88, 4 ?i?m SLO ?n ch?a ch?m. Report, h?nh, CSV v? JSON l? artifact b?i n?p; kh?ng ch?y `make clean` sau khi chu?n b?.

