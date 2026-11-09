# W6 — Knowledge Platform & Ops (L9, L10, L12–L14) — Đặc tả triển khai

> Module brief cho member nhận mảng **W6 / L9 Workflow + L10 Jurisdiction Config + L12 Experience + L13 eval-gate + L14 Knowledge-Ops**. Phụ thuộc W3 (RetrievalService/GroundingService/LLMGateway) + W5 (FastAPI/tenant/nhãn AI) + W2 (effectivity/graph/linking).
> Nguồn pattern: **Claude for Legal** (`refs/claude-for-legal`, Apache-2.0) cho khung workflow; legalbenchrag cho eval-gate (qua W3.4). Đọc kèm `docs/implementation-architecture.md §W6`, `docs/compliance-vn.md`.
> **Nguyên tắc vàng (đã xác nhận bằng cách đọc code):** Claude for Legal là **marketplace prompt/config 100%, KHÔNG có engine** — mọi câu trả lời pháp lý là *kiến thức model gắn thẻ `[model knowledge — verify]`*. W6 **fork cái khung** (thứ tự bước, hình dạng finding, bậc triage, template output, ma trận escalation, guardrails) và **thay ruột "model tự trả lời"** bằng gọi W3 (retrieval hiệu lực-aware + citation-verify) + W2 (effectivity/án lệ) + song ngữ. Lift *structure & good taste*, re-host runtime sang FastAPI.

---

## 0. Module này giao ra cái gì (deliverables)

1. **Năm workflow service (L9):** `ReviewService` (+ omission 2-pass), `DraftService` (song ngữ), `AssistantService`, `JudgmentAnalysisService`, `ComplianceDiffService` — mỗi cái = khung fork từ Claude for Legal + lõi grounding của ta.
2. **`JurisdictionPack` (L10):** cấu hình khai báo (declarative) → portability; VN không hardcode.
3. **Đặc tả Experience/UI (L12):** highlight rủi ro/bỏ sót theo màu, đối chiếu song ngữ side-by-side, điều hướng trích dẫn → văn bản tại-ngày-T, màn hình HITL.
4. **eval-gate (L13):** nối benchmark 3 chiều của W3.4 thành **cổng CI** pass/fail.
5. **Knowledge-Ops flywheel (L14):** công cụ gold-set, tuyển/cập nhật án lệ, viết `required_clause_rule`/playbook, duyệt HITL → feed fine-tune.

**Bất biến W6 (kế thừa toàn hệ):** mọi output có **trích dẫn + ngày hiệu lực + confidence + nhãn AI + HITL**; mọi khẳng định pháp lý phải qua verify 3 cổng hoặc **abstain**; không tin kiến thức tham số model; **Judgment Analysis = rủi ro cao → human-in-the-loop bắt buộc** (xem §1.4).

> 🔴 **Audit fixes Critical ĐÃ ÁP** (chi tiết `docs/specs/spec-audit-fixes.md` W6): **(C1)** omission = **checklist-coverage + sufficiency floor** ("không thấy trong tập truy xuất *đủ-rộng*"), KHÔNG "trích dẫn một phủ định"; **(C2)** `required_clause_rule` thêm **`obligation_type` (mandatory vs default/tùy nghi)** — tránh false-positive trên chỗ luật tự lấp; định nghĩa nguồn/coverage/sign-off; **(C3)** flywheel **không được mang nguyên văn hợp đồng khách** vào train (finding block trích HĐ) → scrub/ẩn danh hoặc chỉ nhãn trên KB công; **(C4)** rủi-ro-cao phải **ENGINEER** (conformity assessment, logging, registration) — không chỉ "hô HITL".

---

## 1. L9 — Năm workflow service

**Hình dạng chung của một workflow (fork từ SKILL.md):** mỗi SKILL.md của Claude for Legal = YAML frontmatter (`name`/`description`/`argument-hint`/`user-invocable`) + body `## Instructions`/`## Workflow` đánh số + template output trong fenced markdown + `## Quality checks` (xác nhận: `commercial-legal/skills/review/SKILL.md:1-11`, `vendor-agreement-review/SKILL.md`). W6 giữ **thứ tự bước + template output**, nhưng mỗi bước "đọc playbook rồi model tự so" đổi thành **gọi `RetrievalService.retrieve(as_of)` + `GroundingService.verify_answer`**. Runtime không phải slash-command; là **FastAPI endpoint + Celery task + SSE streaming** (từ W5), đọc **tenant config từ DB** (không phải `~/.claude/plugins/config/...`).

### 1.1 `ReviewService` — rà soát hợp đồng + bỏ sót (omission) 2-pass

Fork **router** `review/SKILL.md` (title-first routing + `confirm_routing`) + **finding** `vendor-agreement-review/SKILL.md`.

- **Pass A — present clauses (có mặt):** với mỗi điều khoản trong hợp đồng → tìm `required_clause_rule` áp dụng tại `as_of` (W2) + điều luật nền (W3 retrieval) → sinh **finding block** (§1.6).
- **Pass B — omission (bỏ sót):** duyệt **tập `required_clause_rule`** của `(jurisdiction, contract_type)` còn hiệu lực tại `as_of` (W2) → điều khoản **bắt buộc theo luật mà hợp đồng KHÔNG có** → finding `Gap: Missing term` kèm cite + ngày. *(Đây là moat #2 — "bắt bỏ sót theo luật", khác hẳn review "so với playbook" của repo.)* Recall của Pass B đo bằng tag `catch-omission` của eval harness (W3.4).
  - **★ Critical C1 — "vắng mặt" KHÔNG ground được bằng cách trích một phủ định.** Omission = **checklist-coverage**: với mỗi `required_clause_rule`, chạy retrieval **đủ-rộng** trên hợp đồng; "thiếu" = *không tìm thấy điều khoản phủ sau khi đã truy xuất đủ* + **sufficiency floor** (nếu retrieval yếu → không khẳng định "thiếu", gắn `needs_review`). Mỗi finding Missing mang **confidence** + liệt kê *đã tìm những gì*. (Nối W3 §8 C1/C2: phân biệt "luật đòi nhưng HĐ im" vs "ta tìm sót".)
  - **★ Critical C2 — chỉ flag Missing cho `obligation_type='mandatory'`.** Civil-law có **quy phạm tùy nghi (default luật tự lấp)** — nếu HĐ im thì *luật điền*, KHÔNG phải thiếu. `required_clause_rule.obligation_type ∈ {mandatory, default}`: `default` → finding mức *thông tin* ("luật sẽ áp X nếu không thoả thuận"), **không** 🔴 Missing. Nếu không phân biệt → false-positive hàng loạt.
- **2-pass** vì present-check và omission-check quét theo hai trục khác nhau (theo-hợp-đồng vs theo-luật); gộp 1 lượt sẽ sót điều luật không xuất hiện trong text hợp đồng.
- Giữ nguyên: **deal-breaker-first gate** (`## ⛔ DEAL-BREAKER PRESENT` rồi stop — `vendor-agreement-review/SKILL.md` Step 2), **liability-cap 4-dimension** (lines 150–160), **redline granularity** (word>phrase>subclause). **Thay:** "jurisdiction delta check" (lines 162–172, hiện hardcode US: CA §16600, auto-renewal, UCTA) → **query effectivity VN**: "điều khoản X có hiệu lực/hợp pháp theo bản luật áp dụng tại ngày hợp đồng?" qua `TemporalRepository.in_force` + `required_clause_rule`.

### 1.2 `DraftService` — soạn thảo song ngữ

Fork template output + "no silent supplement" + redline granularity. Sinh điều khoản/văn bản theo **statutory default VN** (không phải Delaware). Mọi mệnh đề pháp lý sinh ra phải neo về điều–khoản (cite + `valid_from`). **Song ngữ:** sinh vi + en, bám `concept/term/concept_alignment` (W2) để thuật ngữ nhất quán; đánh dấu `equivalence_type=partial|none` khi khái niệm EN không khớp VN (cảnh báo dịch).

### 1.2b `PetitionDraftService` — soạn ĐƠN TỪ pháp lý theo mẫu (FR-34, mở rộng DraftService)

**Nhu cầu (từ Legal Director):** soạn **đơn tố tụng/hành chính** — đơn khởi kiện, đơn khiếu nại, đơn tố giác tội phạm… **và "học từ những đơn đã được viết".** Khác hợp đồng: mỗi loại đơn có **cấu trúc/nội dung bắt buộc theo luật tố tụng** (vd đơn khởi kiện ⇒ nội dung bắt buộc **BLTTDS Điều 189**).

**Làm "học từ đơn cũ" đúng cách = RAG trên kho mẫu, KHÔNG fine-tune.** (Tránh bẫy residency/flywheel.) Kho mẫu do **data-eng** đổ vào **lakehouse** (đã curated + ẩn danh) → trigger kéo lên index.

> 🟠 **AUDIT — ĐỌC TRƯỚC KHI CODE (đây là mở rộng NHÓM-2, KHÔNG phải mũi moat lõi):**
> - **Vì sao NHÓM-2:** chất lượng một đơn ~80% nằm ở lập luận từ **tình tiết + chứng cứ + yêu cầu**, ~20% ở trích dẫn đúng. Moat (hiệu lực/omission/citation) chỉ chạm ~20% đó → đây là **drafting hạng parity có moat trang trí**, không phải beachhead. Xếp sau lõi W1–W6 qua cổng.
> - **3 CÂU PHẢI CHỐT trước khi build (nếu không chốt → dừng):**
>   1. **Kho mẫu là đơn TRỐNG hay đơn ĐÃ ĐIỀN?** Mẫu trống → chỉ cần **DTP + guided-fill** (kiểu docassemble), **KHÔNG cần RAG/TES nặng** (đừng over-engineer). Đơn đã-điền chất lượng → RAG mới đáng (học lập luận/hành văn). *Chốt cái này quyết định có cần TES không.*
>   2. **Audience: trợ lý cho LUẬT SƯ hay self-service cho DÂN?** Dân tự soạn đơn khởi kiện/tố giác = sát **hành nghề luật trái phép** + đụng ràng buộc "không tư vấn trực tiếp công chúng". Mặc định: **luật-sư-assist + HITL**, không bật public.
>   3. **Bao nhiêu loại đơn ở v1?** Mỗi loại cần người **mã hoá DTP thủ công** (trường bắt buộc theo luật, vd Điều 189 BLTTDS) — lao động pháp lý thật, không tự động. Chốt scope nhỏ (3–5 loại) trước.
> - **★ Risk-posture (cứng — đơn NỘP THẲNG RA TOÀ, hậu quả không kém bản án):** **HITL bắt buộc** (luật sư duyệt trước khi nộp) · **citation-gate mạnh + abstain** nếu không ground được căn cứ · nhãn AI. Posture gần §1.4, KHÔNG để nhẹ như draft hợp đồng.

**3 thành phần:**
1. **`DocumentTypePack` (DTP)** — mở rộng `JurisdictionPack` (§2, L10): mỗi `doc_type` đơn khai báo `governing_law` (frbr_uri), `required_fields[]` (mỗi field gắn `mandated_by` = eid điều–khoản + `obligation_type`), `optional_fields[]`, `output_template`. Versioned + **as_of-aware** (luật tố tụng đổi → trường đổi, bám W2 `TemporalRepository`). → biến "trường bắt buộc của đơn" thành **rule máy quét được** (tái dùng engine omission §1.1).
2. **`TemplateExemplarStore` (TES)** — index từ lakehouse (pgvector+BM25, W3). Template = **kho curated dùng chung, KHÔNG phải data tenant** → không RLS, nhưng giữ `provenance` + `license`. Fed qua **ingestion adapter** (anti-corruption, `integration-adapters`): lakehouse schema → canonical `TemplateDoc`; **idempotent upsert** theo `(template_id, version)`.
3. **`PetitionDraftService`** — orchestrate:
   - input: `doc_type` + `facts` + `parties` *(tenant-scoped, ở VN)*.
   - `load DTP(as_of)` → `retrieve exemplars TES(doc_type, facts, as_of)` → draft điền required+optional → **⚡ omission-gate (§1.1 / FR-02):** mỗi `required_field` thiếu → finding `Gap: Missing` + cite điều mandate (áp C1 sufficiency-floor + C2 chỉ `mandatory`) → **⚡ citation-verify (W3 §2 / FR-05):** căn cứ pháp lý trong đơn đúng điều–khoản + còn hiệu lực@as_of → **bilingual (FR-04)** → **HITL + nhãn AI** → **abstain** nếu không ground được.

**★ Ranh giới dữ liệu (cứng):** template (lakehouse/TES) = dùng chung; **`facts`/`parties` của vụ (PII)** = tenant-scoped, residency VN, **không bao giờ** ghi vào TES hay rời VN. (Nối W5 §2.2 hai-lớp-dữ-liệu + CN-01.)

**Trigger (seam data-eng → mình):** lakehouse phát **CDC event** hoặc **scheduled sync** → ingestion adapter. Data-eng sở hữu lakehouse + curation + ẩn danh template; mình sở hữu adapter→TES→service. Chi tiết seam: `integration-adapters §8b` + W1 §2 (intake).

**Prior-art & steal-list (đã search — `docs/competitive-landscape.md` mạch FR-34):**
- **Verdict:** từng nửa KHÔNG mới (exemplar-RAG đã chuẩn **thương mại** — Spellbook/Henchman/Harvey, nhưng proprietary + common-law/hợp đồng; required-field đã giải **OSS** — docassemble). **TỔ HỢP thì greenfield:** *DTP trường-bắt-buộc-neo-luật + exemplar-RAG + cổng `in_force@as_of` + civil-law VN + song ngữ* — **không repo/sản phẩm nào ship.** Đây là phần thủ được.
- **Tái dùng (học, không fork nguyên — US-centric):**
  - **docassemble / Suffolk Assembly Line (MIT)** — mô hình thu-field + validation + conditional assembly + xuất PDF. Prior-art cho tầng DTP field-collection.
  - **`refs/claude-for-legal` (Apache-2.0)** — fork **flow cổng `litigation-legal/skills/demand-draft`** + `references/element-templates.md` + **`cold-start` seed-doc delta-learning** (trích playbook từ 5–20 mẫu). ⚠️ *không có RAG/vector — chỉ cho structure/phrasing.* **Bỏ** `external_plugins/cocounsel-legal` (cần Westlaw).
  - **ARCCS** — pattern omission/"Insufficient Information" classifier (nối §1.1 C1).
- **Đo:** **InsufficiencyBench (ICML 2026)** — đo khả năng bắt "thiếu dữ kiện pháp lý trọng yếu"; model hiện yếu (F2≈0.46) → baseline cho omission-gate.
- **Pattern trigger đã xác nhận đúng chuẩn:** Delta **Change Data Feed** + scheduled sync (Airflow/dbt) + idempotent upsert `(template_id,version)`; corpus mẫu chậm → **scheduled sync đủ**, chưa cần Debezium/Kafka. (Lưu ý: bước embed→ANN index luôn là code ứng dụng, không standard nào lo.)
- ⚠️ **License chưa verify:** legal-draft-agent, Judicex, Lawgorithm, ARCCS — kiểm LICENSE trước khi dùng.

### 1.3 `AssistantService` — hỏi–đáp pháp lý

Fork khối **"Ad-hoc questions in this domain"** + **"Proportionality"** (phân loại legal/business/branding/CX/policy trước khi trả lời) từ `commercial-legal/CLAUDE.md`. Ruột = **vòng lặp grounding của W3/W4**: **`resolve_as_of(input, question_type)`** (gọi component dùng-chung ở `legal-rule-base §4` — **KHÔNG mặc định "hôm nay"**: ưu tiên **ngày sự việc**, propose-then-confirm, hỏi nếu mơ hồ) → retrieve → generate chỉ từ cands → verify 3 cổng → abstain nếu yếu. Trả kèm cite + ngày + **as_of đã dùng** + confidence + nhãn AI.

### 1.4 `JudgmentAnalysisService` — phân tích bản án (⚠️ RỦI RO CAO)

"Bản án vào → đúng/sai + căn cứ + án lệ áp dụng." Fork posture **Auditor hard-gate** (W4) + finding shape. Luồng: `LinkingService.link_judgment(facts, as_of)` (W2) lấy điều luật áp dụng **tại ngày vụ việc** → `match_precedents` lấy án lệ còn hiệu lực → `verify_article` kiểm **từng yếu tố cấu thành** (không yes/no tổng thể) → Auditor loại điều/án lệ hết điểm tựa.

**Compliance posture (bắt buộc — `docs/compliance-vn.md §2`):** AI hỗ trợ tố tụng được liệt **hệ thống rủi ro cao** trong **QĐ 33/2026/QĐ-TTg** (hiệu lực 15/8/2026). Hệ quả thiết kế **cứng**:
- **Human-in-the-loop bắt buộc:** output KHÔNG bao giờ là phán quyết tự động; luôn đi qua màn hình HITL (§3) để luật sư/thẩm phán duyệt trước khi dùng.
- **Second-opinion framing:** ngôn ngữ output định khung "ý kiến thứ hai / phân tích tham khảo", không "xử thay / kết luận đúng-sai thay toà" (giảm gánh tuân thủ + đúng đạo đức — `compliance-vn.md §2` hệ quả định vị).
- **★ LAW-TRUE + ghi chú thiên vị (integrity, bất biến):** kết luận pháp lý tính **chỉ theo luật + án lệ, BLIND với địa vị/chức vụ** của đương sự — không nâng/hạ vì thân thế. **Tách biệt**, output kèm một `integrity_note` *chỉ-để-lưu-ý*: nếu đương sự có địa vị/chức vụ (field `party.position`), ghi chú "loại vụ này thực tế có thể có thiên vị; **platform KHÔNG điều chỉnh** — kết luận trên là *đúng luật*". Ghi chú này **không bao giờ** chạm lập luận/kết quả; nó là *cảnh báo khoảng cách luật↔thực tiễn* cho user. Data: `party.position` là metadata; `integrity_note` là trường riêng, không trộn vào `legal_conclusion`.
- **Nhãn AI** (Luật 71/2025 Điều 44 + NĐ 142/2026): mọi output gắn thẻ máy-đọc-được tạo bởi AI (cắm ở LLMGateway W3/API W5).
- **Logging + hồ sơ — ★ Critical C4: phải ENGINEER, không "hô HITL".** Nghĩa vụ rủi-ro-cao là *cơ chế có thật*, là deliverable: (a) **high-risk logging spec** (I/O + quyết định + người duyệt, bất biến, ≥ thời hạn luật); (b) **hồ sơ đánh giá hợp chuẩn (conformity assessment)**; (c) **đăng ký cổng**; (d) **đầu mối liên hệ tại VN** — *đụng* ràng buộc NĐ 356 Đ21-22 (phải **pháp nhân VN + chứng nhận BCA**), nối cổng go-live W5 §3.1. Khi QĐ 33/2026 còn `[cần primary-text]` → **hạ phạm vi/để ở chế độ hạn chế**, không bật rộng.

### 1.5 `ComplianceDiffService` — đối chiếu tuân thủ khi luật đổi

Fork pattern **regulatory-legal** (reg-feed watch → diff rule vs policy library). Khi `norm_relation(amends|repeals)` mới vào KB (W1→W2): tính **delta** giữa `document_as_of(T_cũ)` và `document_as_of(T_mới)` (W2) → với mỗi hợp đồng/chính sách khách đang neo điều bị đổi → sinh finding "điều X đổi hiệu lực [ngày] → điều khoản của bạn cần rà lại". Trục ngày là của W2; repo không có.

**Legal-change watch (FR-09) = đầu vào của service này**, không phải trụ riêng: VB mới (W1 nạp hằng ngày) → `norm_relation` (W2) → trigger diff này → thông báo theo tenant. Cái "mới" chỉ là: (a) subscription theo tenant, (b) nạp dự thảo, (c) kênh thông báo. Phần diff/neo điều đã có sẵn.

> 🔴 **★ Critical — DỰ THẢO KHÔNG PHẢI LUẬT (bất biến, đụng moat #1):** dự thảo **chưa có hiệu lực** → **TUYỆT ĐỐI KHÔNG** sinh finding tuân thủ ("bạn vi phạm/thiếu X") từ dự thảo. Dự thảo đi **kênh riêng = "dự báo/heads-up"** ("điều X *có thể* đổi khi dự thảo [tên] thông qua — theo dõi"), gắn `status=draft`, **không `legal_basis` ràng buộc**, không trộn vào finding in-force. (Đây là họ hàng W7 §5b law-sim, không phải compliance finding.) Nếu để dự thảo thành finding ràng buộc = vi phạm chính nguyên tắc "không cite luật chưa in-force".
> 🟡 **Chống ngập thông báo (alert fatigue):** chỉ báo khi norm đổi **thật sự neo** một điều khoản của khách (đã có cơ chế neo) **+ ngưỡng severity** (vd chỉ 🔴/🟠 mới push ngay; 🟡/🟢 gom vào digest). Không quét-mù mọi hợp đồng cho mọi VB mới.

### 1.6 Finding block canonical (fork + mở rộng)

Giữ **đúng** template `vendor-agreement-review/SKILL.md:116–137` và **dual severity** emoji (`CLAUDE.md → Shared guardrails → Dual severity`): `Legal risk 🔴 Blocking/🟠 High/🟡 Medium/🟢 Low` + `Business friction 🔴 Blocks deals/🟠 Slows/🟡 Confuses/🟢 Invisible`; **cross-skill severity floor, round UP** khi mơ hồ.

```markdown
### [Điều X.X]: [Tên vấn đề]
**Playbook/Luật yêu cầu:**
  - (a) Playbook tenant: [vị trí chuẩn của khách]
  - (b) Luật VN tại ngày T: [required_clause_rule / điều–khoản] — cite `<frbr_uri>#<eid>` @<valid_from>   ← MỚI: thay "[model knowledge — verify]"
**Hợp đồng ghi:**
> "[trích nguyên văn hợp đồng]"
**Gap:** [Missing term | Weaker than standard | Weaker than fallback | Non-standard | Unacceptable]
**Legal risk:** 🔴/🟠/🟡/🟢    **Business friction:** 🔴/🟠/🟡/🟢
**Vì sao quan trọng:** [1–2 câu]
**Redline đề xuất:**
> "[ngôn ngữ thay thế — theo statutory default VN]"
**Nếu họ không nhượng:** [fallback từ playbook, hoặc "escalate tới [người]"]
**Trích dẫn & hiệu lực:** <eid> @valid_from..valid_to · confidence · 🤖 AI-generated
```

**Playbook = markdown prose, KHÔNG phải JSON** (xác nhận: playbook nằm trong `commercial-legal/CLAUDE.md` dạng prose + bảng; checklist là *thủ tục* trong SKILL.md, không phải bảng rule JSON). → W6 giữ playbook tenant dạng prose sửa được, **nhưng** phần "luật VN yêu cầu" đổi sang **`required_clause_rule` có cấu trúc (W2, có `valid_from/valid_to/source_unit_eid/severity`)** để máy quét omission + neo hiệu lực.

---

## 2. L10 — `JurisdictionPack` (cấu hình khai báo, portability)

Thiết kế từ đầu để VN không bị hardcode — tách *dữ-liệu-vùng-tài-phán* khỏi *engine*. Một `JurisdictionPack` (YAML/JSON trong DB, versioned) khai báo:

```yaml
jurisdiction: VN
legal_family: civil-law
authority_rank_ref: legal-rule-base.md §1   # ★ F13-fix: KHÔNG hardcode ở đây. Thang bậc = (cơ-quan+loại), VERSIONED 4 thời kỳ (as_of), 15 loại — đọc từ rule base. Ví dụ phẳng 4-dòng dưới chỉ MINH HOẠ, KHÔNG phải nguồn:
  # (minh hoạ) Hiến pháp > Luật > Nghị định > Thông tư — bản THẬT xem authority_rank @as_of
conflict_rules:               # ★ F13-fix: lex_superior/posterior = codified (Đ.156/Đ.58); lex_specialis = HEURISTIC chưa-codified; posterior⟂specialis → ABSTAIN→human (KHÔNG "thuần logic auto")
  codified: [lex_superior, lex_posterior, treaty_priority]
  heuristic: [lex_specialis]   # abstain khi đụng posterior
citation_grammar:             # cho W1 trích quan hệ: "Điều X Khoản Y của {Luật/NĐ/TT} số…/năm…", "án lệ số…/AL"
  patterns: [...]
sources: [vbpl.vn, congbobanan.toaan.gov.vn, anle.toaan.gov.vn]   # quyền dùng: compliance-vn §4
term_base_ref: concept/term (vi,en)      # song ngữ W2
contract_types: [hợp đồng dịch vụ, thỏa thuận bảo mật/NDA, SaaS, ...]   # routing key workflow
required_clause_rule_set_ref: <tenant/jurisdiction>
work_product_header:          # KHÔNG dùng doctrine "attorney work product" (US); xem Match-check
  note: "work-product là học thuyết US; VN khác — dùng nhãn bảo mật + 'không phải tư vấn pháp lý'"
```

Workflow L9 đọc `JurisdictionPack` thay cho hằng số US nhúng trong skill. Thêm vùng tài phán mới = thêm một pack, không sửa engine. `cold-start-interview` (fork) ghi ra pack + tenant playbook thay vì file `~/.claude/...`.

---

## 3. L12 — Experience / UI (đặc tả nhu cầu)

1. **Highlight rủi ro/bỏ sót theo màu:** render finding theo dual-severity emoji→màu (🔴/🟠/🟡/🟢); omission (Pass B) tô màu riêng (điều luật thiếu). Reuse **"Dashboard offer for data-heavy outputs"** + bảng sortable của repo.
2. **Đối chiếu song ngữ side-by-side:** hai cột vi | en khoá theo `concept`; badge `equivalence_type` khi partial/none.
3. **Điều hướng trích dẫn → văn bản tại-ngày-T:** click cite trong finding → mở `TemporalRepository.reconstruct_as_of(eid, as_of)` hiển thị **đúng nguyên văn điều khoản tại ngày áp dụng** (neo span zero-drift từ W3 chunk). Đây là tính năng mà không công cụ nào có.
4. **Màn hình HITL:** mọi output (đặc biệt Judgment Analysis) đi qua queue duyệt: hiện cite + ngày + confidence + nhãn AI; luật sư Approve/Edit/Reject → ghi quyết định (feed L14 flywheel §5).
5. **Bảo mật render (giữ nguyên verbatim từ repo):** **"Dashboard outputs escape untrusted input"** — HTML-escape mọi giá trị ô có gốc ngoài session (text hợp đồng đối tác, tên bên), set `textContent` không `innerHTML`, scheme-check URL (`http/https/mailto`). Liên quan trực tiếp vì ta render text đối tác cung cấp.

---

## 4. L13 — eval-gate (nối CI)

Port **benchmark 3 chiều** của W3.4 (legalbenchrag) thành **cổng CI** — repo chỉ xuất CSV, ta thêm threshold pass/fail:
- `correct-article` (P/R cấp ký tự) · `correct-effectivity` (as-of trả đúng điều còn hiệu lực) · `catch-omission` (recall per `required_clause_rule` — đo chính Pass B §1.1).
- **Cổng CI:** build fail nếu bất kỳ chiều nào dưới threshold hoặc tụt so baseline LLM. Gắn vào pipeline W5.
- Gold-set do L14 (§5) nuôi; eval chạy trên gold-set đó.

---

## 5. L14 — Human Knowledge-Ops (flywheel)

Công cụ cho đội tri thức, biến vận hành thành dữ liệu cải thiện:
1. **Gán gold-set:** chọn truy vấn/hợp đồng mẫu + span đáp án đúng (định dạng span rời-nhau của W3.4) → nuôi eval-gate L13.
2. **Tuyển/cập nhật án lệ:** curate 90 án lệ (`compliance-vn §3`; nhỏ, tuyển chọn → đúng thiết kế curated-KB + matching) — nhập `precedent` (situation/solution/`interpreted_unit_eids`/`date_adopted`/`date_annulled`) vào W2; xử lý TLS lỗi của `anle.toaan.gov.vn` ở W1.
3. **Viết `required_clause_rule`/playbook:** biên tập rule có cấu trúc (`valid_from/valid_to/source_unit_eid/severity` + **★C2 `obligation_type: mandatory|default`**) — nguồn cho omission-check §1.1 và finding (b) §1.6. **Quản trị ruleset là nghĩa vụ L14:** mỗi rule có **nguồn** (điều luật neo), **người viết + sign-off** (luật sư), **ngày rà lại (currency)**; **coverage** đo được (ruleset phủ bao nhiêu % nghĩa vụ bắt buộc của loại HĐ) — *recall omission không được đo vòng tròn chỉ trên rule đã mã hoá*. Fork ý tưởng **seed-doc delta-learning** của `cold-start-interview`.
4. **Duyệt HITL → training:** quyết định Approve/Edit/Reject ở màn hình HITL (§3) → **flywheel: output đã duyệt → gold-set → fine-tune extractor** (ViLegalBERT/Qwen, W3.3). **Ràng buộc:** chỉ train trên dữ liệu đã duyệt + được phép; **không train trên dữ liệu khách/tenant** (cô lập cứng, W5). Ý "experience-memory" học từ AgentCourt.
   - **★ Critical C3 — finding block TRÍCH NGUYÊN VĂN hợp đồng khách** ("Hợp đồng ghi: …") → output-đã-duyệt *mang theo* text khách vào gold-set/train = đúng đường §cấm. **Fix:** trước khi vào gold-set, **scrub/ẩn danh** phần trích hợp đồng (chỉ giữ nhãn + cite điều luật công), HOẶC chỉ lấy nhãn trên **KB công**, HOẶC cần **consent + TIA** rõ ràng. Hợp đồng khách KHÔNG được miễn TIA (`compliance-vn §1`). "được phép" phải là cơ chế, không khẩu hiệu.

---

## 6. Fork-plan (artifact → lift → đổi khi cắm engine)

| Artifact trong `refs/claude-for-legal` (path:line) | W6 lift (scaffolding) | Đổi khi cắm grounding/effectivity/song ngữ |
|---|---|---|
| `commercial-legal/skills/review/SKILL.md:1-11` + Step routing | Router title-first + `confirm_routing` + single-memo | Routing key → loại HĐ VN (dịch vụ/NDA/SaaS) từ `JurisdictionPack`; thêm **bước grounding bắt buộc** trước route |
| `commercial-legal/skills/vendor-agreement-review/SKILL.md:116-137` (finding block) | Template finding + Gap + dual severity + redline + "if they won't move" | "Playbook says" tách (a) playbook tenant + (b) **`required_clause_rule`@T + cite** (bỏ `[model knowledge — verify]`) |
| `vendor-agreement-review/SKILL.md:150-160` (liability-cap 4-dim), Step 2 deal-breaker, redline granularity | Giữ nguyên recipe bước | Chú US → giới hạn BLDS/Luật TM VN; enforceability lọc theo bản luật tại ngày HĐ |
| `vendor-agreement-review/SKILL.md:162-172` (jurisdiction delta, hardcode US) | Giữ **khái niệm** cổng enforceability-theo-vùng | **Thay** list US bằng query `in_force(eid, as_of)` + `required_clause_rule` VN — đây là slot cắm effectivity |
| `commercial-legal/skills/nda-review/SKILL.md:54-164` (GREEN/YELLOW/RED + "GREEN requires attorney-reviewed playbook, nếu thiếu → hạ YELLOW" + scope check + clean-NDA) | Toàn bộ máy-trạng-thái triage + template output | **GREEN** cần thêm: grounding VN pass + effectivity (điều khoản hợp pháp theo bản luật tại ngày) — không chỉ khớp playbook; tiêu chí từ playbook VN + `required_clause_rule`; output **song ngữ** |
| `corporate-legal/skills/tabular-review/references/ma-diligence-columns.md` (schema `verbatim/classify/date/duration/currency` + option enum + prompt/cột) | Schema trích xuất due-diligence có kiểu | enum localize sang taxonomy VN; **mỗi ô thêm `{cite, valid_from}`** + provenance (feed citation-verify) |
| `managed-agent-cookbooks/diligence-grid/agent.yaml` + `subagents/extractor.yaml:7,11,45-83` (`output_schema` state enum `answered/not_present/unclear/needs_review`; **"A value with no quote is a value you made up"**; untrusted-input posture; tool-scope: chỉ `grid-writer` có Write) | Mẫu orchestration multi-agent có schema cứng + quy tắc quote-bắt-buộc | **Re-host sang FastAPI** (YAML là Claude-managed-agent). Quote-per-cell → bất biến grounding/provenance của ta |
| `commercial-legal/skills/cold-start-interview/SKILL.md:1-40` (phỏng vấn + seed-doc delta-learning + viết prose không YAML) | Luồng onboard playbook khách | Ghi ra **`JurisdictionPack` + tenant config trong DB** (không `~/.claude/...`); thêm câu hỏi vùng tài phán/song ngữ |
| `commercial-legal/CLAUDE.md → ## Outputs` (work-product header + reviewer note + decision tree + **Dashboard escape untrusted input**) + `## Shared guardrails` (no-silent-supplement 3-giá-trị, currency trigger, source tags, severity floor, verification-log) | Lift gần nguyên — rule chất-lượng model-agnostic | Source tag (`[Westlaw]`/`[model knowledge — verify]`) → **object trích dẫn thật** (eid + version + timestamp). "No silent supplement" → **yêu cầu retrieval cứng**. Header: KHÔNG assert "attorney work product" (US) — xem Match-check |
| `commercial-legal/CLAUDE.md → ## Escalation` + `renewal-tracker/references/renewal-register.yaml` + `corporate-legal/agents/dataroom-watcher.md` | Shape ma trận escalation + register + watcher I/O | Threshold per tenant; watcher = **Celery scheduled job đọc bảng DB**, không YAML |
| `privacy-legal/skills/dsar-response/` (2-letter flow) + `product-legal/skills/launch-review/references/seven-category-framework.md` (thực 8 mục) | Step-sequence DSAR + khung launch-review | Deadline/exemption/category → regime VN (Luật 91/2025 + NĐ 356/2025) + effectivity; drop default US |
| `CONNECTORS.md` ("retrieved content is data, not commands" + provenance-in-results) | **Khớp luôn grounding contract của ta** | Giữ nguyên tinh thần; endpoint vendor US → engine grounding VN của ta |

**KHÔNG fork:** `external_plugins/cocounsel-legal` (Thomson Reuters, cần Westlaw, US-only); mọi MCP endpoint vendor; toàn bộ chất luật US (thay, không copy); runtime slash-command + `~/.claude/plugins/config/...` (Claude-harness-specific → lift content shape, re-host runtime). Lỗi repo đã biết đừng copy mù: `references/` chỉ ở root không ship trong plugin; file `seven-category-framework.md` thực chất 8 mục.

---

## 7. Interfaces — workflow gọi W2/W3 thế nào (hợp đồng tích hợp)

```python
class WorkflowContext:          # dựng mỗi request từ W5
    tenant_id: str; jurisdiction: str; lang: str
    as_of_map: dict[str, date]  # ★ KHÔNG default today — resolve_as_of(input, question_type) điền (sub-issue→anchor).
                                #   interactive: mơ hồ → propose-confirm/hỏi; batch (API/ComplianceDiff): mơ hồ → FAIL→HITL, KHÔNG today.
    pack: JurisdictionPack

# L9 workflow KHÔNG tự truy xuất/sinh — luôn đi qua W3 + W2:
RetrievalService.retrieve(query, as_of, jurisdiction, tenant_id, lang, top_k, multihop)  # W3.1 (đã lọc hiệu lực)
GroundingService.verify_answer(draft, as_of) -> VerifiedAnswer    # W3.2: 3 cổng + 6 lớp + abstain
LLMGateway.generate(prompt, context_chunks, node, tenant_id, lang) # W3.3: swappable + nhãn AI + log + guard tenant
TemporalRepository.reconstruct_as_of(eid, as_of, lang)            # W2: cho UI điều hướng cite (§3.3)
TemporalRepository.in_force(eid, as_of) -> bool                   # W2: cổng enforceability (thay jurisdiction-delta US)
LinkingService.link_judgment(facts, as_of) / match_precedents(situation, as_of)  # W2: Judgment Analysis §1.4
# omission (Pass B §1.1): truy required_clause_rule WHERE (jurisdiction, contract_type) AND valid tại as_of  (W2)
```

**Quy tắc:** workflow là *tầng điều phối + định dạng*; **mọi sự thật pháp lý đến từ W2/W3**. Không mệnh đề luật nào trong output W6 mà không có cite verify được (hoặc abstain). Output mọi service: `{finding[], citations[], as_of, confidence, ai_label=True, hitl_status}`.

---

## 8. Acceptance tests (phải xanh)

1. **Review present+omission:** 1 HĐ dịch vụ VN → Pass A sinh finding cho điều khoản có mặt (cite + ngày); Pass B phát hiện **điều khoản bắt buộc theo `required_clause_rule`@T mà HĐ thiếu** (Gap: Missing term). Đổi `as_of` qua mốc luật đổi → tập điều khoản bắt buộc đổi theo.
2. **Finding shape:** output bám đúng template §1.6, dual severity, mọi mệnh đề luật có cite; không còn thẻ `[model knowledge — verify]` trần.
3. **NDA triage:** NDA sạch + playbook đã-luật-sư-duyệt + grounding pass + effectivity pass → **GREEN**; playbook thiếu vị trí → **hạ YELLOW** (không GREEN trên default); điều khoản vi phạm bản luật tại ngày → **RED**. Output song ngữ.
4. **Judgment Analysis HITL:** bản án mẫu → điều luật + án lệ **tại ngày vụ việc** (loại điều/án lệ hết hiệu lực); output ở trạng thái **chờ HITL**, khung "second-opinion", gắn **nhãn AI**, có log; **không** phát ra phán quyết tự động.
5. **Điều hướng cite:** click cite trên UI → hiện đúng nguyên văn điều khoản tại `as_of` (khớp `reconstruct_as_of`).
6. **eval-gate:** harness in bảng 3 chiều vs baseline; CI **fail** khi 1 chiều dưới threshold.
7. **JurisdictionPack portability:** thêm pack thứ 2 (giả lập) → workflow chạy không sửa code engine.
8. **Flywheel:** 1 output duyệt HITL → vào gold-set → eval chạy lại dùng được; dữ liệu tenant không lọt vào tập train.
9. **★ omission default vs mandatory (C1/C2):** HĐ im về một điều luật tự lấp (`obligation_type=default`) → **KHÔNG** flag 🔴 Missing (chỉ thông tin); im về điều `mandatory` → flag Missing. Retrieval cố tình yếu → finding "thiếu" bị hạ `needs_review`, không khẳng định.
10. **★ flywheel không rò (C3):** output có trích nguyên văn hợp đồng khách → vào gold-set thì phần trích đã **scrub/ẩn danh**; kiểm tập train không chứa text hợp đồng khách thô.
11. **★ rủi-ro-cao engineered (C4):** Judgment Analysis sinh **bản ghi high-risk log** (I/O + người duyệt, bất biến) + trạng thái chờ HITL; khi thiếu điều kiện tuân thủ (go-live gate) → chạy **chế độ hạn chế**, không bật rộng.

---

## 9. Build tasks (thứ tự cho member)

1. `JurisdictionPack` (L10) + loader + tenant config DB (thay `~/.claude/...`). ← *làm trước, mọi workflow đọc nó.*
2. `ReviewService` 2-pass + finding block §1.6 (fork `vendor-agreement-review` + nối W2/W3) + acceptance 1–2. ← *chứng minh moat #2 (omission).*
3. `nda-review` triage state-machine + GREEN-gate (grounding+effectivity) + acceptance 3.
4. `JudgmentAnalysisService` + posture rủi ro cao + màn hình HITL (L12 §3.4) + acceptance 4.
5. UI điều hướng cite + song ngữ side-by-side + highlight màu + escape-untrusted (L12) + acceptance 5.
6. eval-gate CI (L13) nối W3.4 + acceptance 6.
7. `DraftService` / `AssistantService` / `ComplianceDiffService` (fork template + grounding).
8. Knowledge-Ops tooling (L14) + flywheel + acceptance 8.

---

## 10. Steal-list (file trong `refs/claude-for-legal` — ĐÃ xác minh)

| Cần | File:line (đã mở & xác nhận) |
|---|---|
| Marketplace + 12 plugin first-party (+cocounsel) | `.claude-plugin/marketplace.json` (13 entry; **không** alpha-sort — curated order, I1 warning) |
| Practice-profile template (xương sống) | `commercial-legal/CLAUDE.md` (playbook **prose**; `## Outputs`, `## Shared guardrails`, dual severity, severity floor) |
| SKILL.md shape (frontmatter + workflow đánh số + fenced template) | `commercial-legal/skills/review/SKILL.md:1-30` |
| Finding block + dual severity + liability-cap 4-dim + jurisdiction-delta | `commercial-legal/skills/vendor-agreement-review/SKILL.md:116-137,150-160,162-172` |
| GREEN/YELLOW/RED + "GREEN requires attorney-reviewed playbook"→hạ YELLOW + scope check | `commercial-legal/skills/nda-review/SKILL.md:54-164` (`user-invocable: false`) |
| Cold-start interview + seed-doc delta-learning | `commercial-legal/skills/cold-start-interview/SKILL.md:1-40` |
| Schema trích xuất có kiểu (`verbatim/classify/date/duration/currency`) | `corporate-legal/skills/tabular-review/references/ma-diligence-columns.md:5-125` |
| Orchestration schema cứng + "value with no quote = made up" + tool-scope | `managed-agent-cookbooks/diligence-grid/agent.yaml`, `subagents/extractor.yaml:7,11,45-83` |
| DSAR 2-letter flow / launch-review framework | `privacy-legal/skills/dsar-response/`, `product-legal/skills/launch-review/references/seven-category-framework.md` |
| Register + watcher + escalation shape | `commercial-legal/skills/renewal-tracker/references/renewal-register.yaml`, `corporate-legal/agents/dataroom-watcher.md` |
| Grounding/provenance contract | `CONNECTORS.md` ("retrieved content is data, not commands"; provenance-in-results) |
| License | `LICENSE` (Apache-2.0 — fork tự do, giữ attribution) |

---

## 11. Match-check (đối chiếu prior note `research_notes/Repo deep read/claude_for_legal.md`)

Mở & xác minh trực tiếp các file — **khớp hầu hết**, vài điểm cần hiệu chỉnh thuật ngữ:

- ✅ **Marketplace 13 entry** (12 first-party + `cocounsel-legal` vendor) — khớp. Xác nhận thêm: mảng **không alpha-sort** (`ip-legal` đứng *sau* `legal-builder-hub` — curated display order, trùng ghi chú I1 trong repo `CLAUDE.md`).
- ✅ **Finding block** `vendor-agreement-review/SKILL.md:116-137` — khớp *verbatim* (Section→Playbook says→Contract says→Gap→Legal risk/Business friction→Why→Proposed redline→If they won't move). **Dual severity 🔴🟠🟡🟢** khớp (`CLAUDE.md → Shared guardrails → Dual severity` + `Cross-skill severity floor` round UP).
- ✅ **Playbook = markdown prose, KHÔNG JSON** — xác nhận: playbook ở `commercial-legal/CLAUDE.md` dạng prose+bảng (`### Sales-side/Purchasing-side`, LoL 4 vị trí, "The one thing"); checklist là *thủ tục* trong SKILL.md. Artifact typed DUY NHẤT = `ma-diligence-columns.md` (YAML có kiểu) — khớp.
- ✅ **NDA GREEN/YELLOW/RED + "GREEN requires attorney-reviewed playbook positions… cannot be issued against default or absent positions → hạ YELLOW"** — khớp *verbatim* (`nda-review/SKILL.md:58-62`).
- ✅ **cold-start-interview** (viết prose không YAML, seed-doc delta-learning, ghi `~/.claude/plugins/config/...`) + **ma-diligence-columns** (verbatim/classify/date/duration/currency + option enum + prompt/cột, có "common cuts 6 cột") — khớp.
- ✅ **extractor** rule "**A value with no quote is a value you made up**" + state enum `answered/not_present/unclear/needs_review` — khớp (`subagents/extractor.yaml:11,62`). *Hiệu chỉnh nhỏ:* prior note ghi "a **cell** with no quote is a **cell** you made up"; nguyên văn repo là "**value**" (không phải "cell").
- ⚠️ **Tên skill:** `implementation-architecture.md §W6` và prior note gọi workflow là `review-contract`/`/triage-nda`; **tên thật** là skill `review` (router) + `vendor-agreement-review`/`nda-review`/`saas-msa-review` (loaded, `user-invocable:false`). Spec này dùng tên thật.
- ⚠️ **Work-product header:** repo `CLAUDE.md → ## Outputs` tự cảnh báo "attorney work product" là học thuyết **US (FRCP 26(b)(3))**, không tồn tại ở phần lớn hệ khác, và đã có nhánh non-US. → W6/`JurisdictionPack` cho VN **không assert** nhãn này; dùng nhãn bảo mật + "không phải tư vấn pháp lý" (khớp tinh thần prior note, nêu rõ ở §2/§6).
- ✅ **Không có engine** — xác nhận: 100% prompt/config. W6 fork *structure*, cắm grounding/effectivity/bilingual của ta.
