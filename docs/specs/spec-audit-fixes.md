# TraLuat — Spec audit: lỗi xác nhận & sửa (W1 · W4 · W5 · W6)

> Kết quả review phản biện độc lập (reviewer *không* được mớm kết luận). Ghi chú đầy đủ: `research_notes/Spec audit/w{1,4,5,6}_review.md`. W2/W3 đã có mục sửa *inline* (w2 §11, w3 §8).
> ⚠️ **Các lỗi Critical dưới đây là ship-blocker — phải sửa spec trước khi code mảng đó chạm SoR/khách.** Đọc kèm `docs/engineering-principles.md`.

---

## W1 — Data pipeline (garbage-in đầu độc moat #1)
**🔴 Critical**
- **C1 — Không có cổng giữa W1 (trích) và W2 (materialize).** W2 R3/R4 áp vô điều kiện, không đọc `confidence/review_status` → một quan hệ "được thay thế bởi" giả **viết lại version mà `in_force()`/W3 rồi tin**. **Fix:** W2 R3/R4 **từ chối relation trừ khi `review_status='approved'`** (hoặc `confidence≥θ` cho tập loại auto-safe); hàng chờ duyệt = deliverable W1 + acceptance test. *(precision > recall: một `repeals` giả tệ hơn một cái bỏ sót.)*
- **C2 — `confidence:0.82` là BỊA** (eyecite không có model confidence). **Fix:** định nghĩa confidence tính ra sao; mặc định `needs_review`.
- **C3 — Bản án không ẩn danh không bị chặn** (pipeline không có xử lý ẩn danh; field chỉ ở meta giả định). **Fix:** cổng cách ly ở stage 1 + backstop PII + test (NQ 03/2017).

**🟠 High:** Branch A **shadow-verify** (đừng tin meta.json mù); anaphora VN ("điều này/nêu trên") giải theo **eId cấu trúc**, *không* dùng resolver eyecite (nó match tên đương sự — code mới, không phải reuse); **structure-sanity gate** (parser "không từ chối" = mis-tree âm thầm); **commencement từng phần** (đừng sập về một ngày cấp văn bản — feed đúng W2 H3); regex ngày hiệu lforce neo vào "…*này* có hiệu lực", loại span trong trích dẫn văn bản khác.
**🟡 Medium:** validate field-level ngày (OCR 2021→2071); idempotency key = `(source_hash, schema_version, tool_version)` (nếu không, nâng cấp OCR bỏ qua doc cũ mãi); văn bản hợp nhất/phụ lục mis-tree; bilingual renumber/omit.

---

## W4 — Reasoning engine (hard-gate + đa vai)
**🔴 Critical**
- **C1 — Copy bug `"true" in lower()`** (W3 §8 H1 đã cờ) → "untrue" khớp "true" → điều không áp dụng được *accept*. **Fix:** parse bool chặt (ranh giới từ / structured output), **không substring**.
- **C2 — `lang="vi"` nhưng phân loại bằng `true/false` tiếng Anh** → đáp án VN rơi im lặng. **Fix:** phân loại tiếng Việt / structured output.
- **C3 — Cổng ngày hiệu lực là filter CỨNG** (nghịch W3 §8 C3). **Fix:** **giữ+đánh dấu** điều chuyển tiếp/grandfathered; `in_force` tới cấp **version + khoản/điểm** (sửa W3 H3/W2 H3).
- **C4 — Hard gate một chiều, non-deterministic, không đường cứu.** **Fix:** ép **temp=0 + cache**; thêm đường phục hồi/HITL cho false-reject.

**🟠 High:** empty verified set → **abstain, không bịa phán quyết**; transfer dân-sự phải mô hình **nghĩa vụ chứng minh** + với tới **affirmative defense** (thời hiệu…); dùng `resolve_conflict` (W2 H4 hỏng) → **HITL escalation**; đa vai: **trần chi phí + memoize audit + verifier model KHÁC** (cùng model = tự vọng, không kiểm độc lập); stop-condition phải đo **đồng thuận kết quả**, không chỉ ổn định tập verified; **H6 — phân biệt *sai luật* vs *tuỳ nghi xét xử*** + disclaimer/abstain chiều tuỳ nghi, **không bao giờ auto "thẩm phán sai"**.
**🟡 Medium:** **M3 sửa lỗi kiến thức:** án lệ VN theo **NQ 04/2019 là ràng buộc trên thực tế** (phải áp dụng, muốn khác phải nêu lý do), *không* "persuasive".

---

## W5 — Backend (tenancy + compliance) — nguy hiểm nhất
**🔴 Critical**
- **C1 — Classifier egress chưa định nghĩa + 3 doc mâu thuẫn route.** Prompt Review mang chunk tenant + KB qua guard nhưng **không được ra Claude**; query/văn bản khách thô không được phân loại; Claude cache/log giữ text ngoài VN. **Fix:** một quy tắc route **fail-closed theo provenance**, mặc định **vLLM local**, phân loại cả input thô, tắt cache/log ngoại trên nhánh KB. (NĐ 356 Đ20)
- **C2 — RLS fail-OPEN** (app role owner/BYPASSRLS bỏ qua policy). **Fix:** `FORCE ROW LEVEL SECURITY` + **app role non-owner**.
- **C3 — RLS cho checkpointer bất khả thi** (pool riêng). **Fix:** validate prefix `tenant:<id>` **mỗi read**.
- **C4 — Redis/RabbitMQ không cô lập/mã hoá**, raw bytes hợp đồng qua broker. **Fix:** **không truyền bytes qua Celery** (để object store, truyền ref); mã hoá/cô lập broker+cache; zero-retention phải chạm tới chúng.
- **C5 — Không audit quyết định route/egress** (NĐ 356 Đ29 ≥5 năm). **Fix:** ghi log phân-loại-dữ-liệu + residency.
- **C6 — `task_status` IDOR xuyên tenant.** **Fix:** check sở hữu task theo tenant.

**🟠 High:** kill-switch auth phải fail-closed; Supabase (thay/siết: `verify_aud`, tenant-join, host VN); **ethical-wall theo matter/user** (không chỉ firm); reconcile zero-retention vs logging rủi-ro-cao; quyền xoá phủ *mọi* store; **bỏ Pinecone cho embedding khách** (residency).

---

## W6 — Platform (omission + tuân thủ rủi-ro-cao)
**🔴 Critical**
- **C1 — Pass-B omission "xác nhận vắng mặt" không ground được** (không thể trích bằng chứng cho một phủ định; W3 C1/C2). **Fix:** omission = **checklist-coverage** ("không thấy trong tập đã truy xuất *đủ-rộng*" + sufficiency floor), không phải "trích dẫn cái không có"; đánh dấu độ tin.
- **C2 — `required_clause_rule` thiếu field *loại nghĩa vụ*** → lẫn **quy phạm tùy nghi (luật tự lấp)** với **bắt buộc** → false-positive "Missing 🔴" trên chỗ luật đã lấp. Và recall đo *per rule* = vòng tròn (100% vẫn sót nửa luật). **Fix:** thêm `obligation_type` (mandatory/default); định nghĩa nguồn/coverage/currency/sign-off của ruleset.
- **C3 — Flywheel mang nguyên văn hợp đồng khách vào train/eval** (finding block trích hợp đồng) — đúng đường §5.4 *cấm*. **Fix:** scrub/consent/cô lập, hoặc **không dùng dữ liệu khách**; hợp đồng cần ẩn danh; khách *không* được miễn TIA.
- **C4 — Judgment Analysis "đạt rủi-ro-cao" bằng *framing*** (HITL), chưa **engineer**: conformity assessment, logging rủi-ro-cao, đăng ký cổng, đầu mối VN (**đụng NĐ 356 Đ21-22: phải pháp nhân VN + chứng nhận BCA**). **Fix:** thiết kế cơ chế thật; hạ rủi ro khi QĐ 33/2026 còn [cần primary-text].

**🟠 High:** W6 cưỡi `in_force`/`verify_answer` *đang hỏng* (kế thừa fix W2/W3); `as_of` Review = **ngày ký**, không phải hôm nay; Draft sinh **văn bản pháp lý không verify được** + thiếu **chỉ định ngôn ngữ kiểm soát (VN controlling)** + thiếu kiểm nhất quán song ngữ cấp điều khoản; bước model-reasoning (liability-cap 4-dim, redline) **nghịch "grounded-or-abstain"**; JurisdictionPack `authority_hierarchy` phẳng tái tạo đúng mô hình W2 H4 bảo bất khả thi; eval-gate đo trên engine-hỏng + gold-set *cùng tác giả hệ thống*; thêm acceptance test cho Draft/Assistant/ComplianceDiff; định nghĩa **precedence playbook vs luật bắt buộc VN**.
**🟡 Medium:** equivalence_type=none phải **abstain**, không chỉ badge UI; đừng lift "gần nguyên" phần privilege US; HITL Edit phải **re-verify** trước khi vào flywheel; test prompt-injection (text hợp đồng tới LLM).

---

## Round 2 — Audit data-platform + AI-system (2 reviewer độc lập, Nov 2026)

> Phần lớn là **hệ quả bậc-2 của chính các fix Round 1** + 2 lỗ mới tạo khi thêm model/đa-ngữ. ✅ = đã sửa trong round này.

**🔴 Critical (đã sửa)**
- **A — `as_of` scalar phá lex-mitior/hồi tố/đa-mốc.** `resolve_as_of` nói 2 mốc nhưng `resolve_conflict`/`in_force` nhận 1 scalar; `unit_version` thiếu `applies_from` (hồi tố). ✅ **Fix:** `unit_version.applies_from` (W2 §2); `resolve_conflict(unit_eids, anchors[], question_type)` + `as_of_map` (W2 §6, legal-rule-base §4⑦⑧⑨, W3 §2/§1b, W6 §7); lex-mitior chạy NGOÀI cổng in_force.
- **B1 — W3 §1 vẫn hard-filter "loại chunk".** ✅ **Fix:** keep-and-MARK `effect_status` (W3 §1), không drop transitional/expired-citable.
- **B2 — W6 §7 WorkflowContext `as_of mặc định today`** (fix Round-1 chỉ landed §1.3, sót §7 — đúng ng.tắc #9). ✅ **Fix:** `as_of_map` không default; batch mơ hồ→FAIL→HITL.
- **B3 — `in_force()->bool` quá hẹp.** ✅ **Fix:** `effect_status → {in_force|expired_citable|transitional_applies|not_yet}` (W2 §2/§6); W3 gate2 dùng enum.
- **E — route embedding theo ngôn ngữ phá cross-lingual** (VN=AITeamVN, query EN=bge-m3 → 2 không gian). ✅ **Fix:** **DUAL-INDEX** (embed corpus bằng cả 2, query match đúng index); `chunk.embedding_model` (W2 §2, stack-db §2).

**🟠 High (đã sửa)**
- **G3 — `norm_relation` chỉ unit↔unit** → không model thay-thế-toàn-bộ-VB. ✅ endpoint doc-OR-unit (W2 §2).
- **G4 — sửa cùng-ngày không có khóa thứ tự.** ✅ `order_key` (date_issued, gazette) + fold theo thứ tự (W2 §2).
- **G13 — `chunk` thiếu `valid_from/to`+`tenant`** → tối ưu ANN bất khả. ✅ denormalize + index (W2 §2).
- **G7 — phased-commencement bị drop ở W1→W2.** ✅ `valid_from = unit.effective_date` nếu có (W1 §6).
- **D — precision-first NGƯỢC cho hiệu lực** (sót repeal=điều chết served live). ✅ recall-gated detection + flag human (stack-db §2).
- **F8 — element-subsumption LLM thô** (bước pháp lý nặng nhất, không neo). ✅ bắt neo span + HITL low-agreement (W4 §3).
- **F9 — gate3 không bắt sai-số (15≠30 ngày); "citation-F1 tất định" overclaim.** ✅ `exactness_check` + ghi rõ gate3 ngữ nghĩa không tất định (W3 §2).
- **F10 — conf chưa định nghĩa → Brier bất khả; gold-set moat chưa gate.** ✅ conf = xác suất hiệu chỉnh (W3 §2); gold-set = cổng go-live per-feature.
- **F4 — tenant local 1 model → cross-provider thành self-verify.** ✅ model local thứ-2 khác họ, HOẶC chế-độ-suy-giảm (deterministic+HITL) (stack-db §3).

**🟡 Wording/IOU**
- **F14** weak-label bằng **Qwen local** không Claude (ToS). ✅ (stack-db §2). · **F13** JurisdictionPack ví dụ align rule base (abstain specialis + rank-ref versioned). ✅ (W6 §2). · **F5** PII gate dùng-chung mọi luồng. ✅ (reference-data §0.7). · cache language-neutral ≠ tenant-neutral (làm rõ). ✅ (reference-data §6.2). · **FR-41** scope = "giải cái đã-flag"; detection = IOU có deliverable riêng. ✅ (registry).

**❌ Pushed back (overstate do agent không đọc W2/W5/integration-adapters)**
- "cache bỏ tenant→rò" — SAI, tenant vẫn trong base key; chỉ bỏ ngôn ngữ. · "không có RLS" — SAI, W5 §2.3 đã FORCE RLS. · "template bypass PII" — MỘT PHẦN SAI, template có gate ở integration-adapters §8b.

**IOU còn lại (sequencing, không fix bằng text được):** conflict **DETECTION** model+gold-set · effectivity/omission/conflict **gold eval set** (chuyên gia) · model local **thứ-2** (provision) · precedent recall. → gắn cổng trong roadmap.

---

## Round 3 — CHAOS validation (3 reviewer: failure/concurrency · data/temporal · adversarial/abstention, Nov 2026)

> Reviewer **chạy code thật** (validate_meta.py) + dựng kịch bản hỗn loạn. ✅ = đã sửa round này.

**🔥 TIER 0 — bug trong artifact ĐÃ SHIP đội data (empirical). ✅ fixed + repackage zip:**
- **S1** `anonymization_status: null` PASS → bản án chưa ẩn danh lọt. ✅ bỏ null khỏi enum + ban_an yêu cầu ∈ {source_anonymized, verified} (meta.schema.json).
- **S2** ngày rác (`2071-13-45`) PASS. ✅ validate_meta.py kiểm **ngày lịch thật + năm [1945..nay+5]**.
- **S3** NFC không check. ✅ validate_meta.py báo chuỗi non-NFC. *(relation null-date → gate ở W2, không phải validator.)*

**🔴 TIER 1 — runtime FAIL-OPEN. ✅ spec gate:**
- **R1** sufficiency floor chỉ eval-offline → thiếu luật = trả sai qua hết cổng + bug L3 (rỗng-cite→Answer). ✅ runtime sufficiency floor + empty→abstain + insufficient_retrieval≠no_governing (W3 §2). *(impl = IOU.)*
- **R2** local-model down → fail-open Claude = breach residency. ✅ circuit-breaker: local down→abstain/queue, cấm failover; provenance-based; audit write-ahead; prompt-cache per-tenant (W5 §3.1b).
- **R3** review-queue tắc → repeal chưa duyệt served live. ✅ query-time: cited unit có destructive-relation pending → caveat/needs_review (W3 §2).

**🟠 TIER 2 — concurrency/atomicity. ✅ spec invariant:**
- **C1** R3/R4 atomicity+idempotency (crash→luật mất; replay→double-apply). ✅ SERIALIZABLE tx + applied-ledger (W2 §3).
- **C2** ghi đồng-thời cùng unit. ✅ SELECT FOR UPDATE/serialize (W2 §3).
- **C3** norm_relation+chunk thiếu dedupe key. ✅ UNIQUE keys (W2 §2).
- **C4** Redis hot-cache không version/TTL. ✅ version-stamp key + TTL (reference-data §6.2).
- **C5** replication mode + read-skew. ✅ sync replication + pin law_version/query (W2 §3).

**🟠 TIER 3 — security residual. ✅ spec:**
- **X1** injection = control thật (delimiting+provenance+wrapper, áp W4 verdict). ✅ (W3 §3).
- **X2** spoofing định tính → exactness+span bắt buộc. ✅ (W3 §2).
- **X4** VERIFY-OFFICIAL = load-gate (`verification_status`, loader từ chối provisional). ✅ (legal-rule-base §6).
- **X3** advisory misuse/evasion — **IOU** (chưa có intent/refusal gate defensive-only). · **X5** zero-retention temp bytes crash → tmpfs+reaper (IOU) · **X6** egress audit write-ahead ✅ (W5) · **X7** poisoned doc body shadow-verify↑Critical + TES provenance (IOU) · **X8** checkpointer app-guard (đã có §2.3, siết wrapper — IOU).

**❌ Pushed back:** lỗi trong `src/traluat/temporal.py` (materialize vô điều kiện, no applies_from, crash-overlap…) = **bản SKETCH superseded, KHÔNG phải design hole** — spec đã có fix Round-1/2. Hành động: **XÓA sketch** kẻo copy nhầm. · Concurrency "hinge on unspecified tx boundary" = spec chưa-nói, nay đã bổ sung (C1/C5).

**IOU còn lại (code/data phase):** sufficiency-floor impl · injection-boundary impl · misuse/defensive-only policy (X3) · 2nd local model (F4) · zero-retention tmpfs+reaper (X5) · TES provenance gate (X7) · conflict-detection model+gold · effectivity/omission/conflict gold set.

---

## Round 4 — SECURITY audit (appsec/infra · parser/untrusted-input · supply-chain, Nov 2026)

> Deep audit 3 nhánh. **Kết luận: moat-security (tenancy/residency/egress/PII) MẠNH; perimeter mỏng.** Sau push-back/right-size: ~20 finding = **5 quyết-định-thiết-kế thật (A–E) + checklist control chuẩn**. Toàn bộ ở **`docs/security.md`** (threat model STRIDE + requirement + pentest).
- **🔴 A** untrusted-intake chokepoint (sandbox+AV+defusedxml+re2+bomb-cap+quarantine) · **B** model safetensors-only+pin+hash+mirror (pickle-RCE+poisoned-weights) · **C** platform-vs-tenant authz (cross-tenant key-rotate=crypto-shred DoS) · **D** log metadata-only + backup-encrypt + PITR-vs-erasure (mâu thuẫn nội bộ) · **E** lakehouse integrity (range/source_eid cross-check rẻ-ngay; mTLS/ký defer).
- **Standard controls** (enumerate, không phải hố mới): mTLS nội cụm · RS256/JWKS+token-lifecycle · rate-limit/quota/GPU-fair-share · SBOM/SCA fail-closed CI · migrate security-pass · `-I` · container hygiene · SQLi-safe SET LOCAL · log PII scrub.
- **Pushed back:** nhiều "lỗ" = control chuẩn chưa-viết-ra (không phải thiết-kế-sai); lakehouse mTLS/ký = defer (data team nội bộ); KMS blast-radius = document-giới-hạn (không fix-hết-được).
- **IOU:** mTLS+ký lakehouse · HSM · model-mirror infra · 2nd local model · pentest trước GA.

---

## Thứ tự sửa (ship order)
1. **W5 C1–C6** (rò tenant/egress = vi phạm pháp luật) + **W1 C1/C3** (gate materialize + ẩn danh) — *trước khi bất kỳ dữ liệu khách/bản án nào chạm hệ.*
2. **W2 C1/C2 + W4 C1–C3** (bitemporal invariant + hard-gate đúng) — *trước khi tin kết quả truy xuất/suy luận.*
3. **W3 C1–C3 + W6 C1–C4** (sufficiency + omission + compliance thật) — *trước khi phát hành tính năng.*
4. Mọi spec: thêm **adversarial acceptance tests** + **đo precision/recall** trước khi cho ghi SoR.
