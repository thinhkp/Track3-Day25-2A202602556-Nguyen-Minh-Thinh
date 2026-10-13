# Lab 25 — Circuit Breakers, Caching & Reliability

**Họ tên / nhóm:** Nguyễn Minh Thịnh — **MSV:** 2A202602556

**Commit:** `cb113b9b4e802d08e89e39a3ae027de546572918` (triển khai đã kiểm chứng; các commit tiếp theo chỉ hoàn thiện report).

**Điểm tự động:** 84 / 88. Đạt toàn bộ 84 điểm công khai; 4 điểm SLO ẩn chờ giảng viên, report chấm tay /12.

Các bảng dùng seed 25. [scoreboard.json](scoreboard.json) xác nhận Game Day, workflow, cache đều pass trên seed 25, 26, 27. Không sửa simulator, test, kịch bản hoặc dịch vụ được cung cấp; client/cache không dùng thời gian thực, không hard-code tên băng hay thời điểm sự cố.

## 1. Kết quả Game Day

Nguồn: [naive.json](gameday/naive.json), [resilient.json](gameday/resilient.json). Cost/turn là chi phí mỗi lượt **thành công**; recovery `—` nghĩa là kịch bản không định nghĩa mốc hồi phục.

| Băng | Client | availability | p95 (s) | amplification | retry_ratio | cost/turn | recovery (s) | PASS? |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| G1 | naive | 0,7194 | 7,157 | 7,738 | 6,738 | 2,163 | 4 | FAIL |
| G1 | resilient | 1,0000 | 4,780 | 1,063 | 0,001 | 2,104 | 0 | PASS |
| G2 | naive | 0,4560 | 15,034 | 9,904 | 8,904 | 4,627 | 155 | FAIL |
| G2 | resilient | 1,0000 | 9,922 | 1,035 | 0,004 | 2,106 | 0 | PASS |
| G3 | naive | 1,0000 | 4,768 | 1,164 | 0,164 | 2,328 | 0 | FAIL |
| G3 | resilient | 1,0000 | 4,642 | 1,076 | 0,049 | 2,167 | 0 | PASS |
| G4 | naive | 1,0000 | 13,764 | 1,004 | 0,004 | 2,008 | 0 | FAIL |
| G4 | resilient | 1,0000 | 5,626 | 1,014 | 0,002 | 2,072 | 0 | PASS |
| G5 | naive | 0,3699 | 5,359 | 17,030 | 16,030 | 2,124 | — | FAIL |
| G5 | resilient | 0,8179 | 5,477 | 1,003 | 0,002 | 2,504 | — | PASS |
| G6 | naive | 0,5170 | 4,836 | 12,344 | 11,344 | 2,009 | 0 | FAIL |
| G6 | resilient | 1,0000 | 5,949 | 1,052 | 0,017 | 2,210 | 0 | PASS |

G1 có 0 vi phạm retry-after; G5 có 0 retry lỗi 400, 0 failover không cần thiết; G6 có 0 route không tương thích. Traffic quay lại alpha sau phục hồi: G2/G4/G6 đều 100%, G1 90,4%. G5 không thể cứu request malformed nên availability thấp hơn các băng còn lại.

## 2. Cấu hình client và lý do

| Tham số | Giá trị | Lý do và bằng chứng |
|---|---:|---|
| attempt_timeout_s | 8 s | G6 availability 100%, p95 5,949 s; timeout 30 s làm availability còn 94,88%. Chừa thời gian failover trong deadline 30 s. |
| max_attempts_per_provider | 2 | Chỉ một retry transient; G2 amplification 1,035, G3 retry_ratio 0,049. Thử 5 attempt khi breaker hỏng làm G2 p95 19,208 s dù có budget. |
| min_time_left_s | 1 s | Không gửi attempt thiếu thời gian hữu ích; test deadline pass và G6 mặc định không GiveUp. Timeout bị chặn bởi deadline còn lại. |
| backoff_base_s / cap_s | 0,25 / 4 s | Full jitter tránh đồng bộ retry; G3 availability 100% với retry_ratio 0,049. Test xác minh khoảng jitter và retry-after. |
| retry_budget_ratio | 0,1 | G3 retry_ratio 0,049 ≤ 0,10; khi breaker hỏng, có budget là 0,068, không budget là 0,163. |
| retry_budget_min_per_s / max_tokens | 0,5 / 20 | Cho retry lúc ít traffic và burst ngắn; không phải trần tuyệt đối 10% vì có refill theo thời gian/token ban đầu. G2 budget-on retry_ratio 0,057. |
| quota_cooldown_s | 300 s | G5 chỉ 2 lỗi quota ở hai deployment account A, availability 81,79%. Không chờ cooldown quota. |
| breaker.window_size / min_calls | 20 / 10 | Đủ mẫu trước khi trip, quên kết quả cũ; G2 availability 100%, recovery 0 s; test sliding-window pass. |
| breaker.failure_rate_threshold | 0,5 | Trip theo lỗi sức khỏe; không tính 400/429. G5 có 413 request sai nhưng 0 failover vô ích. |
| breaker.slow_call_s / slow_rate_threshold | 5 s / 0,6 | Nhận biết chậm không lỗi; G4 p95 giảm 13,764 → 5,626 s, availability 100%. |
| breaker.open_duration_s | 10 s | Fail fast rồi probe định kỳ; G2 recovery 0 s, 100% traffic quay lại primary. Recovery là metric dịch vụ, không phải lúc breaker đóng. |
| breaker.half_open_max_probes / successes | 2 / 2 | Tối đa 2 probe đang bay, 2 probe nhanh thành công mới đóng; test concurrency/generation pass. G2 amplification 1,035. |

Sơ đồ quyết định `on_error`:

| Loại lỗi | Breaker | Retry cùng provider | Failover | Cooldown |
|---|---|---|---|---|
| 400/401/403/404/422 và lỗi client khác | release permit | Không | Không, GiveUp client_error | Không |
| 429 insufficient_quota | release | Không | Ngay | 300 s theo deployment |
| 429 rate limit | release | Không ngay | Ngay | Ít nhất retry-after, chia sẻ giữa các call |
| 529/503, 5xx, timeout 0/408 | ghi failure | Chỉ khi số attempt, budget, breaker, deadline cho phép; full jitter | Khi không được retry hoặc provider không dùng được | Breaker OPEN |

Mỗi call mới đi từ primary, lọc tool capability. Khi hết ladder, chỉ chờ cooldown **rate limit** ≤ 5 s, breaker không OPEN và còn deadline. Permit mang generation; kết quả cũ không được đổi trạng thái mới. Simulator chạy callback tuần tự với nhiều request đang bay; đây không phải cam kết thread-safety cho callback đa luồng trong hệ thống thật.

## 3. Ba thí nghiệm

Chạy lại bằng `python scripts/run_experiments.py`; số đầy đủ trong [experiments.json](experiments.json). Thí nghiệm dùng bản sao cấu hình và subclass trong script, không sửa client production hay băng sự cố.

### 3.1. Retry budget là lớp phòng thủ cuối

Breaker `min_calls=1000000000`, `max_attempts_per_provider=5`; budget-off đặt ratio=100, max_tokens=1e9, min_per_s=1e6.

| Băng | Budget | availability | amplification | retry_ratio | recovery (s) | p95 (s) |
|---|---|---:|---:|---:|---:|---:|
| G2 | on | 0,9996 | 1,380 | 0,057 | 0 | 19,208 |
| G2 | off | 0,9674 | 1,595 | 0,392 | 35 | 21,935 |
| G3 | on | 1,0000 | 1,136 | 0,068 | 0 | 4,550 |
| G3 | off | 1,0000 | 1,164 | 0,163 | 0 | 4,768 |

G2 có budget ngăn retry_ratio tăng 0,057 → 0,392; recovery giảm 35 → 0 s và availability tăng 96,74% → 99,96%. G3 vẫn availability 100% nhưng budget giảm retry_ratio 0,163 → 0,068, cost/turn 2,327 → 2,271. Budget không chặn mọi failover nên amplification vẫn lớn hơn 1 + retry_ratio. Khi breaker đúng, G2 amplification chỉ 1,035; vẫn cần budget vì cấu hình breaker sai, mẫu chưa đủ hoặc nhiều provider cùng lỗi có thể cho phép nhiều retry trước khi trip.

### 3.2. Timeout 30 giây và survivorship bias

| Băng | Timeout | availability | give_up_reasons | p95 lượt thành công (s) |
|---|---|---:|---|---:|
| G6 | 8 s | 1,0000 | {} | 5,949 |
| G6 | 30 s | 0,9488 | deadline: 109; no_provider_available: 13 | 5,304 |
| G4 | 8 s | 1,0000 | {} | 5,626 |
| G4 | 30 s | 1,0000 | {} | 5,608 |

G6 mất 122 lượt ở timeout 30 s vì region treo dùng hết deadline trước khi failover. p95 giảm dù availability xấu đi: metric chỉ lấy lượt thành công, bỏ các lượt treo/hết hạn. G4 thêm latency nhưng vẫn thường trả lời trước 8 s; slow-call breaker vẫn trip nên nâng timeout gần như không đổi kết quả. Chọn timeout theo p99 **attempt bình thường**, deadline user còn lại và thời gian dành cho một failover; p99 lượt hai-call không phải p99 attempt.

### 3.3. Bỏ lọc tool calling

G6 bỏ lọc có **230 incompatible_routes**, 230 GiveUp `incompatible_model_output`; availability giảm 100% → 90,36%, cost/turn tăng 2,210 → 2,290. Với product manager, đây là 230 lượt mà model có thể nói chuyện nhưng không thể tạo thao tác công cụ để hoàn tất yêu cầu khách hàng. Fallback chỉ hữu ích khi giữ khả năng cần thiết; tool call phải ở alpha/alpha-eu/beta.

## 4. Workflow hoàn tiền

Nguồn: [workflows.json](workflows.json), 500 session seed 25.

| Executor | completion | crashes | duplicate refunds | duplicate emails | lost refunds | overpaid (cents) | wasted LLM / crash |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive | 1,0 | 81 | 128 | 81 | 0 | 1496700 | 1,123 |
| yours | 1,0 | 66 | 0 | 0 | 0 | 0 | 0,303 |

Idempotency key mã hóa JSON cặp `(session_id, step)`, ổn định qua retry/restart, không nhập nhằng dấu phân cách. Chỉ key bảo vệ side effect nhưng worker vẫn làm lại classify/lookup, tốn LLM; checkpoint từng bước giữ kết quả để resume. Chỉ checkpoint không bảo vệ khoảng trống payment đã commit nhưng response/checkpoint chưa ghi: chạy lại sẽ trả tiền trùng. Ghi checkpoint trước payment có thể làm worker chết rồi skip khoản chưa được trả, gây mất refund.

Checkpoint ghi **sau** thành công; retry chỉ bắt ServiceError/ServiceTimeout, WorkerCrash thoát tới runner. Exactly-once effects dựa vào DurableStore bền vững và payment/email hỗ trợ idempotency, không có nghĩa mỗi request mạng chỉ xuất hiện một lần. Executor có 2500 checkpoint, 0 duplicate/lost và 0,303 wasted LLM/crash ≤ 0,6.

## 5. Alerting & error budget

Prefix sums cho mỗi window O(1). Luật page: 14,4× trên 1 h **và** 5 m, hoặc 6× trên 6 h **và** 30 m; ticket: 1× trên 3 d **và** 6 h. Episode là đoạn liên tục firing, end exclusive. Nguồn: [slo.json](slo.json).

| Sự cố | Mong đợi | Naive alerter | Burn-rate alerter | Độ trễ burn-rate (phút) |
|---|---|---|---|---:|
| checkout_bug | page | page, 1 phút | page | 27 |
| provider_outage | page | page, 0 phút | page | 4 |
| deploy_blip | none | false page | none | — |
| slow_leak | ticket | bỏ sót | ticket, không page | 1337 |
| degraded_evening | page | page, 214 phút | page | 291 |
| night_spike | none | false page | none | — |
| small_bump | none | false page | none | — |

Naive có 7 page episode, 3 false page; burn-rate có 3 page, 1 ticket, 0 false page, mọi sự cố đúng hạn. Trong 30 ngày có 25.901.755 request, 55.618 bad, được phép 129.508,8 bad; availability 99,7853%. Budget tiêu **42,95%**, còn **57,05%**; không freeze release vì chưa hết budget.

`small_bump` (20 phút ở 12% lỗi) không vượt đồng thời hai cửa sổ page: với traffic đều, 1 h error ratio khoảng 4%, burn 8× < 14,4×; 6 h burn khoảng 1,33× < 6×. Dữ liệu thực tế cũng cho 0 page; page theo 5 phút đơn lẻ gây đánh thức không cần thiết. Đây là kiểm tra công khai, chưa thể khẳng định điểm SLO ẩn.

## 6. Postmortem — G2 với naive (blameless)

### Tóm tắt

Alpha mất 75% năng lực GPU từ t=120 đến t=300, làm request chờ rồi timeout. Retry ba tầng không jitter/budget/breaker/fallback khuếch đại tải lên 9,904 attempt/call, biến suy giảm provider thành mất dịch vụ kéo dài. Trong 2362 lượt, 1077 thành công (45,60%), recovery 155 s sau khi provider phục hồi; resilient đạt 100% availability và recovery 0 s.

### Ảnh hưởng

**1285 lượt thất bại**, cost/turn tốt 4,627 so với 2,106 ở resilient; 2737 timeout, 3194 overloaded error, 26298 rate-limit error. Sự cố provider dài 180 s; call success cửa sổ 10 s gần 0 từ khoảng t=150 và chỉ cải thiện rõ quanh t=455. Giả định tháng 30 ngày, traffic cố định 4 lượt/s: 10.368.000 lượt, SLO 99,5%, budget = 51.840 lượt. Riêng 1285 lượt thất bại tiêu **2,48% budget tháng**, chưa làm cạn budget. Tỷ lệ thất bại 54,40% trong mẫu lab là **108,8 lần** error ratio cho phép 0,5%; không nhầm với 108,8 lần budget cả tháng.

### Timeline (giây ảo)

Nguồn: [CSV naive](gameday/naive_G2_overload_storm_timeseries.csv). Mỗi dòng lấy cửa sổ `[t,t+10)`; success ratio = tổng calls_ok / tổng calls_done, tính **call**, không phải user turn. Attempts/s = tổng attempts_alpha / 10.

| t | Sự kiện | attempts alpha/s | calls_ok / calls_done | success ratio |
|---:|---|---:|---:|---:|
| 110 | Trước sự cố, bình thường | 9,1 | 92 / 92 | 1,000 |
| 120 | Mất 75% GPU; kết quả cũ vẫn về | 6,2 | 32 / 32 | 1,000 |
| 150 | Retry storm xuất hiện | 166,5 | 0 / 49 | 0,000 |
| 290 | Gần cuối sự cố, retry vẫn cao | 146,1 | 0 / 41 | 0,000 |
| 300 | GPU phục hồi nhưng dịch vụ chưa hồi phục | 38,8 | 0 / 18 | 0,000 |
| 350 | Vẫn chịu hậu quả hàng đợi | 17,9 | 0 / 39 | 0,000 |
| 450 | Bắt đầu xử lý được call | 13,7 | 45 / 70 | 0,643 |
| 455 | Phục hồi dần; recovery metric = 155 s | 13,0 | 90 / 105 | 0,857 |
| 480 | Call success trở lại 100% | 10,6 | 124 / 124 | 1,000 |

![Tải attempt và tỷ lệ call thành công: naive vs resilient](gameday/G2_overload_storm.png)

### Trigger vs root cause

Trigger là mất GPU, không phải sai sót cá nhân. Root cause là chính sách retry mặc định ba tầng (app × gateway × SDK, tối đa 36 attempt/call), delay cố định, không phân loại lỗi, thiếu giới hạn tải và fallback. Simulator không hủy công việc server khi client timeout: request cũ tiếp tục chiếm slot, retry mới nối hàng đợi, thời gian chờ tăng, lại timeout và tạo thêm retry. Vòng phản hồi tự giữ overload sau khi GPU hồi phục — metastable failure; không thể suy ra dịch vụ hồi phục chỉ từ trạng thái GPU.

### Điều gì giúp / làm tệ hơn

CSV, replay cùng seed và phân loại timeout/529/429 giúp tái dựng sự cố. Delay cố định làm wave retry dồn nhau; 28381 vi phạm retry-after trên G2 làm tải tệ hơn, v1 chỉ có alpha nhận mọi retry. Resilient chia tải sang alpha-eu/beta, dừng gửi khi OPEN, probe giới hạn, dùng một tầng retry; G2 giảm 34475 → 4891 attempt, giữ toàn bộ 2362 lượt thành công. Quy trình trước đây chưa có phép thử giai đoạn sau provider restore và chưa theo dõi amplification, tạo khoảng trống hệ thống cần khắc phục.

### Action items

| # | Hành động | Loại | Owner | Cách kiểm chứng |
|---|---|---|---|---|
| 1 | Một tầng retry, tắt retry SDK/gateway, bắt buộc budget và capability filter | prevent | Nguyễn Minh Thịnh — client | CI G2 amplification ≤ 1,2; G3 retry_ratio ≤ 0,10; G6 incompatible_routes = 0 trên 3 seed |
| 2 | Dashboard burn-rate, attempt rate, timeout và amplification | detect | Nhóm SRE ShopAgent | Replay SLI: 3 page, 1 ticket, 0 false page; hiện upstream errors cả khi cache giữ availability |
| 3 | Breaker có slow-call detection, tối đa 2 probe và fallback vùng/provider | mitigate | Nhóm nền tảng | G2 recovery ≤ 30 s, primary_share ≥ 80%; G4 p95 ≤ 10 s; test generation/cancel pass |
| 4 | Game day trước release, kiểm tra cả giai đoạn sau restore | prevent | Nhóm QA | 6/6 băng pass seed 25/26/27; lưu CSV/scoreboard cho mỗi thay đổi client |

## 7. Một điểm yếu còn lại

G2 availability 100% nhưng p95 **9,922 s**, p99 **15,250 s**, cao hơn G3 p95 4,642 s. Một số request ban đầu đợi gần timeout trước failover; beta giá 1,4 so với alpha 1,0 nên chuyển tải lâu tăng cost. Nếu mọi provider cùng chậm, breaker giữ tải thấp nhưng không tạo năng lực mới; cache chỉ cứu FAQ công khai, không cứu tool flow. Hướng cải thiện: giới hạn concurrency theo deployment/deadline, quan sát queue latency, ưu tiên chat sang model nhỏ khi phù hợp, rồi benchmark lại latency/cost; không retry song song side effect vô điều kiện.

## 8. Cache (Part G)

Nguồn: [không cache](cache/resilient.json), [có cache](cache/cached.json).

| Client | availability | faq_availability | cache_hit_ratio | stale_served | wrong_answers | outdated_answers | cost/turn | PASS? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| resilient | 0,8373 | 0,8424 | 0 | 0 | 0 | 0 | 1,386 | FAIL |
| cached | 0,9124 | 0,9645 | 0,652 | 157 | 0 | 3 | 0,915 | PASS |

| Tham số cache | Giá trị | Lý do |
|---|---:|---|
| similarity_threshold | 0,90 | 0 wrong, hit 65,2%; 0,80 gây 157 other_question, 0,97 giảm hit còn 58,1% dù vẫn 0 wrong. |
| ttl_s | 60 s | 3 outdated ≤ 15; TTL 300 có 95 outdated. TTL 30 chỉ 2 outdated nhưng hit 59,2%, cost 0,955 cao hơn 0,915. |
| max_stale_s | 300 s | Bao trùm outage 120 s; 157 stale served giúp FAQ availability 96,45% thay vì 87,33% khi stale=0. |
| max_entries | 500 | LRU giới hạn bộ nhớ, test eviction pass; đạt hit 65,2%, không cần tăng capacity cho workload công khai. |

Cache tìm cosine trong cùng prompt_version, loại personal, có TTL/stale và invalidate mọi entry chứa source cập nhật. Fresh hit được Serve ngay; stale chỉ sau GiveUp, lookup lại lúc đó để tránh dùng hit cũ qua webhook. Lookup không gia hạn stored_at; chỉ provider answer mới refresh tuổi entry.

### 8.1. Thí nghiệm ngưỡng

| Threshold | hit ratio | wrong_answers | wrong_answers_by_reason | cost/turn |
|---:|---:|---:|---|---:|
| 0,80 | 0,666 | 157 | other_question: 157 | 0,965 |
| 0,90 | 0,652 | 0 | {} | 0,915 |
| 0,97 | 0,581 | 0 | {} | 0,964 |

Catalog có near-miss refund_policy/refund_time, exchange_size/exchange_color, shipping_fee_city/shipping_fee_province và payment_methods/cod, centroid cosine 0,86. Ngưỡng 0,80 trộn câu gần nhưng khác mục đích; oracle ghi 157 other_question, không có other_user/old_prompt. JSON không ghi số lỗi từng cặp nên không gán 157 lỗi cho riêng một cặp. Ngưỡng 0,90 giữ paraphrase và loại near-miss trong tape, cost thấp hơn 0,97; nhiều hit sai ở 0,80 làm giảm lượt tốt nên cost/turn tốt vẫn cao.

### 8.2. Thí nghiệm TTL

| TTL (s) | hit ratio | outdated_answers | wrong_answers | cost/turn |
|---:|---:|---:|---:|---:|
| 30 | 0,592 | 2 | 0 | 0,955 |
| 60 | 0,652 | 3 | 0 | 0,915 |
| 300 | 0,731 | 95 | 0 | 0,863 |

Webhook báo refund thay đổi t=150 nên invalidate ngăn ignored_invalidation; shipping đổi t=480 không webhook, client không biết để xóa. TTL buộc lấy dữ liệu mới khi provider khỏe, giới hạn thời gian trả answer cũ; stale window có thể kéo dài độ cũ nếu provider lỗi. TTL 300 tối ưu hit/cost nhưng vượt outdated ≤ 15, nên chọn 60 s.

### 8.3. Stale-if-error

Stale=0 làm FAQ availability 96,45% → **87,33%**, hit 65,2% → 56,1%, GiveUp no_provider_available 246 → 403. Stale=300 phục vụ 157 answer stale; wrong vẫn 0, outdated vẫn 3 ở seed 25. Khi mọi provider sập không thể lấy answer mới; rung cache giữ FAQ công khai với giới hạn freshness rõ ràng.

### Câu cá nhân và alert khi cache giữ dashboard xanh

“Đơn #48213 của tôi ở đâu?” phụ thuộc trạng thái hiện tại, quyền truy cập và dữ liệu biến động. Cache theo user vẫn có thể trả sai trạng thái/refund/số dư, nên lab loại hẳn personal; production còn phải kiểm tra quyền lúc dùng dữ liệu.

Theo dõi user availability **và** provider success/error/timeout rate, breaker OPEN, Serve(stale), tuổi answer và hit/miss. C1 FAQ availability 96,45% nhưng 157 stale served báo việc phục vụ đang dựa vào answer cũ khi upstream không trả lời. Page theo burn-rate upstream/critical tool flow; alert OPEN kéo dài hoặc stale vượt ngưỡng freshness, không coi cache hit là bằng chứng provider khỏe.

## Kiểm chứng và chuẩn bị nộp

Windows không có make, dùng đúng các script Makefile gọi. Đã cài thành công `.[dev,plot]` vào `.venv` mới và chạy lại test/grader trong môi trường đó:

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

82/82 test pass; 6/6 Game Day, C1, workflow, SLO public pass. Ruff trên các file thay đổi pass. Scoreboard 84/88; SLO ẩn 4 điểm chưa chấm. Hình postmortem đã được xem để kiểm tra; report, CSV và JSON được commit, không chạy make clean.

Repo public đúng quy tắc tên: https://github.com/thinhkp/Track3-Day25-2A202602556-Nguyen-Minh-Thinh — nhánh `main`. Link này dùng để nộp lên kênh của lớp; cần đường dẫn kênh nộp để thực hiện bước gửi bài.
