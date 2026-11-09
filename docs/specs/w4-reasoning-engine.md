# W4 — Động cơ suy luận (Reasoning engine) — Đặc tả triển khai

> Module brief chi tiết cho member nhận mảng **W4 / L8** (orchestration + Auditor hard-gate).
> Nguồn pattern: LegalGraphRAG (3-agent pipeline + Auditor hard-gate element-wise), PAKTON (LangGraph loop + sub-agent-as-tool), L-MARS (Faith-Search repair + cổng `temporally_invalid`).
> Đọc kèm `docs/implementation-architecture.md §W4`, `research_notes/Repo deep read/{legalgraphrag_lmars,pakton}.md`.
> W4 **tiêu thụ** W2 (`TemporalRepository.in_force`, `GraphQuery`) và W3 (`RetrievalService`, `LLMGateway`, `GroundingService`) — không tự làm lại retrieval/verify cấp claim.

---

## 0. Module này giao ra cái gì (deliverables)

1. **Orchestrator một-lượt**: pipeline tuyến tính **Researcher → Auditor(HARD-GATE) → Adjudicator** theo từng *bên/yêu cầu* (per-party), hợp đồng thu hẹp nghiêm ngặt (mỗi tầng chỉ **co nhỏ** tập bằng chứng; Adjudicator không với tay qua cổng).
2. **Auditor HARD-GATE** (moat lõi của W4): với mỗi điều/khoản ứng viên chạy **3 cổng bắt buộc** — (1) trích dẫn có thật, (2) **áp dụng theo từng yếu tố cấu thành** (element-wise), (3) **ngày hiệu lực** (cổng LegalGraphRAG thiếu) — rồi **prune** án lệ mất hết điểm tựa.
3. **Reasoner đa vai** (Phase 4): vòng tranh biện Luật sư ⇄ Kiểm sát ⇄ Thẩm phán ⇄ Bộ ngành, trên nền LangGraph, với **Auditor chạy trên mọi phát ngôn** trước khi vào biên bản.
4. Hai **interface** cho W5/W6 tiêu thụ: `ReasoningEngine`, `Adjudication`; và các **điểm nối** đã định nghĩa tới W2/W3.

**Nguyên tắc:** W4 là *tầng điều phối*, không chứa logic retrieval hay NLI cấp claim. Mọi truy xuất đi qua `RetrievalService` (W3), mọi lời gọi LLM đi qua `LLMGateway` (W3), mọi kiểm "còn hiệu lực" đi qua `TemporalRepository.in_force` (W2), mọi verify cấp-khẳng-định cuối cùng đi qua `GroundingService.verify_answer` (W3). **Auditor hard-gate là của W4** vì nó là cổng *tiền-output* (áp dụng element-wise + ngày hiệu lực + prune), khác với cổng *hậu-draft* cấp claim của W3.

> 🔴 **Audit fixes Critical ĐÃ ÁP** (chi tiết `docs/specs/spec-audit-fixes.md` W4): **(C1)** bỏ `"true" in text.lower()` (khớp cả "untrue") → parse bool structured; **(C2)** phân loại *tiếng Việt*/structured, không `true/false` tiếng Anh khi `lang="vi"`; **(C3)** cổng ngày hiệu lực **KHÔNG filter cứng** — chuyển tiếp/grandfathered giữ+đánh dấu; + kiểm **version-match** & cấp khoản/điểm (H3); **(C4)** ép `temp=0`+cache (xác định) + đường HITL cho false-reject; **(H1)** verified-set rỗng → **abstain, không bịa**; **(H6)** phân biệt *sai luật* vs *tuỳ nghi xét xử*; **(M3)** án lệ VN **ràng buộc trên thực tế** (NQ 04/2019), *không* "thuyết phục".

---

## 1. Hai cổng bọc Adjudicator (định vị W4 vs W3)

TraLuat có **hai** cổng kiểm, đặt ở hai phía Adjudicator — đừng gộp:

```
                 ┌──────────────── W4 ────────────────┐
 Researcher ──▶ AUDITOR (cổng TIỀN-output) ──▶ Adjudicator ──▶ draft
   (W3 retrieve)   ├ (1) trích dẫn có thật              (LLMGateway)   │
                   ├ (2) element-wise applicability                    ▼
                   ├ (3) ngày hiệu lực (in_force)          GroundingService.verify_answer  ← W3
                   └ prune án lệ mất điểm tựa              (cổng HẬU-draft: 6 lớp + Faith-Search + abstain)
                 └─────────────────────────────────────┘
```

- **Cổng tiền-output (Auditor, W4):** đảm bảo Adjudicator *khởi đầu* chỉ từ điều luật đã verify, còn hiệu lực, thoả yếu tố cấu thành ⇒ chống suy luận trên tiền đề sai. Từ LegalGraphRAG.
- **Cổng hậu-draft (GroundingService, W3):** đảm bảo *mọi câu* trong draft truy vết được tới nguồn còn hiệu lực và được nguồn đó entail; không thì sửa trích dẫn hoặc abstain. Từ L-MARS. W4 chỉ **gọi** nó, không cài lại.
- **Ngày hiệu lực được chốt ở CẢ HAI** cổng (Auditor cổng 3 + verifier lớp `temporally_invalid`).

---

## 2. Hợp đồng dữ liệu giữa các agent (narrowing contract)

Bất biến: **mỗi tầng chỉ co nhỏ tập**, không thêm. Adjudicator không được truy xuất lại.

```
Researcher → { candidate_articles[], candidate_precedents[] }
Auditor    → { verified_articles[]  ⊆ candidate_articles,
               verified_precedents[] ⊆ candidate_precedents }   # + audit_trail per article
Adjudicator→ draft (chỉ đọc verified_*; emit trích dẫn inline bắt buộc)
```

Mỗi `candidate_article` mang sẵn (do W2/W3 nạp):
```python
Article = {
  "unit_eid": str,                 # khoá canonical (W2), vd "nd99__dieu_3__khoan_2"
  "version_date": date,            # version đang xét
  "text": str,                     # nguyên văn tại as_of (W2.reconstruct_as_of)
  "elements": list[str],           # ← "điều kiện áp dụng": checklist yếu tố cấu thành (tương đương judge_dep)
  "interpretations": list[str],    # án lệ / nghị quyết / thông tư hướng dẫn (tương đương related_laws)
}
Precedent = {
  "precedent_id": str,
  "cited_unit_eids": list[str],    # các điều mà án lệ này tựa vào
  "situation": str, "solution": str,
}
```
`elements` được sinh **offline** trong W1/W2 (như LegalGraphRAG sinh `judge_dep` ở `scripts/prepare_law_judge_dep.py`) và **đóng băng** trên node điều luật — không sinh lúc chạy.

---

## 3. Auditor HARD-GATE — thuật toán (đặc tả hành vi, pseudocode)

Port **LegalGraphRAG** `core/agents/auditor.py::audit` + `core/judge/judge_law.py::verify_article`, **THÊM cổng ngày hiệu lực** (LegalGraphRAG không có — xác nhận ở Match-check).

```python
def audit(engine, party_facts: str, as_of: date,
          candidate_articles: list[Article],
          candidate_precedents: list[Precedent]) -> AuditResult:
    verified = []
    trail = []                                    # audit trail cho mọi điều (kể cả bị loại)
    for art in candidate_articles:
        # ── CỔNG 1: trích dẫn có thật (citation) ──────────────────────────
        if not TemporalRepository.versions(art.unit_eid):        # eid không tồn tại trong KB
            trail.append(reject(art, gate=1, reason="citation_unreachable")); continue

        # ── CỔNG 3 (chạy SỚM, rẻ, deterministic): ngày hiệu lực ───────────
        #    LegalGraphRAG THIẾU cổng này; ta cắm in_force của W2 vào đây.
        #    ★ C3: KHÔNG filter cứng — điều chuyển tiếp/grandfathered VẪN có thể chi phối.
        #    ★ H3: kiểm tới cấp khoản/điểm + KHẲNG ĐỊNH version == version-at-as_of.
        st = TemporalRepository.in_force_detail(art.unit_eid, art.version_date, as_of)
        if not st.version_match:                       # trích đúng điều nhưng SAI phiên bản
            trail.append(reject(art, gate=3, reason="version_mismatch")); continue
        if not st.in_force:
            if st.transitional:                        # chuyển tiếp: GIỮ + đánh dấu, đưa xuống cổng 2
                art.flags.append("transitional")       # Adjudicator buộc xét quy tắc chuyển tiếp
            else:
                trail.append(reject(art, gate=3, reason="temporally_invalid")); continue

        # ── CỔNG 2: áp dụng theo TỪNG yếu tố cấu thành (element-wise) ──────
        ok, expl = verify_article(engine, party_facts, as_of, art)
        if ok:
            verified.append(art);  trail.append(accept(art, expl))
        else:
            trail.append(reject(art, gate=2, reason="not_applicable", detail=expl))

    # ── PRUNE: án lệ mất hết điểm tựa thì bỏ (chống "analogy drift") ───────
    verified_precedents = prune_unsupported(verified, candidate_precedents)
    return AuditResult(verified, verified_precedents, trail)


def verify_article(engine, party_facts: str, as_of: date, art: Article) -> (bool, str):
    """Element-wise, KHÔNG phải yes/no tổng thể (đây là điểm mấu chốt)."""
    satisfied, unsatisfied = [], []
    for element in art.elements:                       # mỗi yếu tố cấu thành MỘT lời gọi NLI gọn
        r = LLMGateway.generate(                        # ← mọi LLM đi qua gateway W3
                prompt=JUDGE_ELEMENT_PROMPT.format(
                    element=element, law=art.text,
                    interp=art.interpretations, case=party_facts),
                node="auditor.element", lang="vi")
        # ★ C1/C2 — KHÔNG `"true" in text.lower()` (khớp cả "untrue"/"not true"); KHÔNG tiếng Anh khi lang=vi.
        #   Ép structured output {"satisfied": true|false} + temp=0, parse chặt:
        v = parse_bool_strict(r)                        # None nếu không parse được
        if   v is True:  satisfied.append(element)
        elif v is False: unsatisfied.append(element)
        else: unsatisfied.append(element); trail_note(art, element, "verifier_unparsed→needs_review")  # KHÔNG im lặng bỏ
        # ★ F8-fix: verdict yếu-tố là LLM thô ở bước PHÁP LÝ NẶNG NHẤT (subsumption) → bắt NEO SPAN:
        #   prompt buộc trả {satisfied, span} = đoạn art.text nó tựa vào; span rỗng/không khớp → needs_review.
        #   disagreement cross-provider HOẶC confidence thấp → HITL. temp=0 = tái lập, KHÔNG phải đúng.
    # lời gọi tổng hợp: nhận hai danh sách + nguyên văn điều → true/false cấp điều
    agg = LLMGateway.generate(
            prompt=JUDGE_AGG_PROMPT.format(
                case=party_facts, law=art.text,
                true_list=satisfied, false_list=unsatisfied),
            node="auditor.aggregate", lang="vi")
    return (parse_bool_strict(agg) is True), agg.text   # ★ structured bool, không substring "true"


def prune_unsupported(verified_articles, candidate_precedents):
    """Giữ án lệ chỉ khi nó còn tựa vào ÍT NHẤT MỘT điều đã verify (set-membership)."""
    live = { a.unit_eid for a in verified_articles }
    return [ p for p in candidate_precedents
             if any(eid in live for eid in p.cited_unit_eids) ]
```

**Vì sao element-wise (không holistic):** một điều luật chỉ *áp dụng* khi **từng** yếu tố cấu thành của nó được thoả riêng rẽ với tình tiết — rồi mới tổng hợp. Đây đúng là cơ chế `verify_article` của LegalGraphRAG (vòng lặp qua `judge_dep`, mỗi phần tử một call `true`/`false`, rồi call tổng hợp `JUDGE_LAW_PROMPT0`). Dịch sang luật dân sự VN: "điều kiện áp dụng" của một quy phạm (vd điều kiện có hiệu lực của hợp đồng; các yếu tố cấu thành trách nhiệm bồi thường).

**Thứ tự cổng (tối ưu chi phí):** cổng 1 và 3 là **deterministic, không LLM** → chạy trước, loại sớm trước khi tốn `|elements|+1` lời gọi LLM ở cổng 2.

**Audit trail:** `trail` ghi *mọi* điều kèm lý do loại (gate nào, reason gì) — vào biên bản HITL và phục vụ L13 eval. Khác LegalGraphRAG (chỉ giữ điều được nhận), ta giữ cả điều bị loại để giải trình.

---

## 4. Researcher & Adjudicator (hai đầu pipeline)

### 4.1 Researcher — chỉ thu bằng chứng, không verify
Port `core/agents/researcher.py` + `util.py::analyze_case`:
1. **Phân mảnh theo bên** (`segment_case_text_withname` → `case_by_defendant`): mỗi bên/yêu cầu được suy luận độc lập. Hợp với tranh chấp dân sự đa bên VN (mỗi bên có yêu cầu/phản bác riêng).
2. **Trích đặc trưng** tình huống (tương đương `get_features`: 4 chiều ontology) để tạo query.
3. **Hợp ba toán tử truy xuất** `R = R_sem ∪ R_com ∪ R_chg`, nhưng **ủy quyền cho W3**:
   - `R_sem` + `R_com`: `RetrievalService.retrieve(query, as_of, jurisdiction, lang, top_k)` — đã lọc hiệu lực.
   - `R_chg` (vấn-đề-pháp-lý-anchored): LLM đoán ≤3 **vấn đề pháp lý / căn cứ khởi kiện** → `GraphQuery.multihop(src_eid, ["guides","cites"], hops, as_of)` (W2) để đi tới điều liên quan. Thay "predict charge → charge_anchored_articles" của LegalGraphRAG bằng cause-of-action VN.
   - án lệ: `GraphQuery`/W2 `LinkingService.match_precedents(situation, as_of)`.

### 4.2 Adjudicator — tổng hợp CHỈ trên tập đã verify
Port `core/agents/adjudicator.py` + `judge/judge_crime.py::synthesize_judgment`:
- Nhận **chỉ** `verified_articles` + `verified_precedents`. Không đọc tập ứng viên gốc.
- **★ H1 — verified-set RỖNG → ABSTAIN, không bịa:** nếu mọi điều bị loại (hết hiệu lực/không áp dụng) → trả `insufficient_basis` (phân biệt với "không điều nào điều chỉnh"), đẩy HITL. KHÔNG tổng hợp phán quyết từ `party_facts` trần (LegalGraphRAG `synthesize_judgment` gọi vô điều kiện — ta chặn).
- **★ H6 (Judgment Analysis) — phân biệt *sai luật* vs *tuỳ nghi xét xử*:** chỉ kết luận "bản án có điểm vênh" ở **chiều ràng buộc được** (điều luật/án lệ đúng tình huống không áp dụng mà không giải thích — doctrinal hook NQ 04/2019 Đ.8). Chiều **tuỳ nghi** (mức bồi thường, đánh giá chứng cứ, biện pháp tuỳ chọn) → **abstain + disclaimer**, KHÔNG bao giờ auto "thẩm phán sai". Định vị: second-opinion cho chuyên gia, người ký.
- **★ H2 — dân sự ≠ hình sự:** `party_facts` KHÔNG mặc nhiên là sự thật (có **nghĩa vụ chứng minh**); Researcher phải với tới **affirmative defense** (thời hiệu, miễn trừ…) — không chỉ `R_chg` anchored theo yêu cầu (dễ thiên về nguyên đơn).
- Prompt **bỏ doctrine hình sự TQ** (charge_name / term_of_imprisonment / tử hình) → thay **schema cứu trợ dân sự VN**: yêu cầu được chấp nhận/bác, biện pháp khắc phục, nghĩa vụ, bồi thường; doctrine chọn căn cứ khởi kiện, yêu cầu đồng thời vs thay thế.
- Emit **trích dẫn inline bắt buộc** (`unit_eid` + `version_date`) trên mọi câu pháp lý → làm cho cổng hậu-draft (W3 `verify_answer`) decompose được. (Khác LegalGraphRAG: nó trả JSON phán quyết; ta trả văn bản-có-trích-dẫn để nối verifier.)
- Output JSON nghiêm ngặt (như `synthesize_judgment` parse `{...}`), nhưng là schema dân sự.

---

## 5. Reasoner đa vai (Phase 4) — LangGraph + Auditor trên mọi phát ngôn

Nền từ **PAKTON** `Interrogator/.../graph/builder.py` (vòng LangGraph) + `Archivist/.../tools/interrogation_tool.py` (sub-agent-as-tool). **Viết lại sạch từ pattern, không copy** (PAKTON Apache-2.0 nhưng khác domain).

### 5.1 Hình học graph
```
START → draft_utterance(role)                      # một vai phát biểu (luật sư/kiểm sát/thẩm phán/bộ ngành)
draft_utterance → AUDITOR_GATE                     # §3 chạy trên CHÍNH phát ngôn đó
AUDITOR_GATE → (route) → { next_role | synthesize } # loại/giữ căn cứ trong phát ngôn trước khi nó vào biên bản
next_role → draft_utterance                         # luân phiên vai (loop)
synthesize → write_opinion → END
```
- **Auditor chạy trên MỌI phát ngôn** (yêu cầu W4): trước khi một vai được ghi vào biên bản tranh biện, mọi điều nó viện dẫn phải qua 3 cổng §3; căn cứ rớt bị gạch khỏi phát ngôn (ghi vào trail). ⇒ không vai nào "thắng" bằng điều đã hết hiệu lực / không áp dụng.
- Vai = cấu hình (role prompt + tool-scope), không hardcode: `lawyer`, `prosecutor`, `judge`, `ministry`. Lấy từ `JurisdictionPack` (W6 L10).
- **★ H4 — chặn bùng nổ chi phí + tự-vọng:** Auditor-mọi-phát-ngôn = ~`P×R×N×A×(|elements|+1)` lời gọi LLM → **đặt trần chi phí/vụ** + **memoize audit theo `(unit_eid, version, as_of, facts_hash)`** (một điều audit một lần/vụ). Và các vai **phải dùng model/họ KHÁC verifier** (cùng một model = "tranh biện" là tự vọng, không kiểm độc lập); chống **over-deliberation drift** bằng trần lượt + kiểm đồng thuận.

### 5.2 Stop-condition — SIẾT lại (PAKTON mong manh)
PAKTON dừng bằng: ngân sách lượt **HOẶC** chuỗi sentinel literal **HOẶC** `similarity_check` embedding (xác nhận ở `router.py` dòng 29/35). Ta thay bằng tiêu chí **deterministic + đo được**:
- **Ngân sách lượt cứng** (`max_rounds`, như `max_num_turns`) — giữ.
- **Hội tụ**: dừng khi tập `verified_articles` **ổn định** qua một lượt (không vai nào thêm/bớt căn cứ đã verify) → đo bằng set-equality, không bằng similarity văn bản.
- **Không dùng** sentinel-string/embedding làm điều kiện dừng chính (fragile; chỉ dùng như tín hiệu phụ).

### 5.3 Durable state
Dùng checkpointer Postgres theo `thread_id` (như PAKTON `AsyncPostgresSaver`), **nhưng** `thread_id` sinh từ `tenant_id + case_id` (không timestamp — PAKTON dùng timestamp, có risk va chạm/khó truy vết). Mọi state mang `tenant_id` (guard của W5).

---

## 6. Interface cho W5/W6 (hợp đồng tích hợp)

```python
class ReasoningEngine(Protocol):
    def analyze(case: CaseInput, as_of: date, mode: Literal["single","multi_role"]="single",
                tenant_id: str|None=None) -> Adjudication: ...
    # single  = Researcher→Auditor→Adjudicator (một lượt)
    # multi_role = §5 (Phase 4)

class Adjudication(TypedDict):
    parties: list[PartyResult]          # mỗi bên: kết luận + cứu trợ
    verified_articles: list[Article]    # tập đã qua hard-gate
    verified_precedents: list[Precedent]
    audit_trail: list[AuditEntry]       # mọi điều + lý do loại (gate, reason)  ← giải trình HITL/L13
    draft: str                          # văn bản có trích dẫn inline (unit_eid@version_date)
    verified_answer: VerifiedAnswer     # kết quả W3.verify_answer (6 lớp + abstain) trên draft
    ai_label: True
```

### Điểm nối tới W2/W3 (ký đúng chữ ký spec W2/W3)
| W4 gọi | Interface (nguồn) | Dùng ở đâu |
|---|---|---|
| `TemporalRepository.in_force(unit_eid, as_of) -> bool` | W2 §6 | Auditor **cổng 3** (ngày hiệu lực) |
| `TemporalRepository.versions(unit_eid) -> list` | W2 §6 | Auditor **cổng 1** (tồn tại) |
| `TemporalRepository.reconstruct_as_of(eid, as_of, lang)` | W2 §6 | nạp `Article.text` tại as_of cho element-wise |
| `GraphQuery.multihop(src, rels, hops, as_of)` | W2 §6 | Researcher `R_chg` (cause-of-action→điều) |
| `GraphQuery.resolve_conflict(eids, as_of)` | W2 §6 | Adjudicator khi hai điều verify xung đột — **★ H3: nếu trả `unresolved` (general-vs-special, thiếu scope…) → HITL, KHÔNG auto-chọn** (W2 §11 H4) |
| `RetrievalService.retrieve(query, as_of, …)` | W3 §1 | Researcher `R_sem`/`R_com` (đã lọc hiệu lực) |
| `LLMGateway.generate(prompt, ctx, node, tenant, lang)` | W3 §3 | **mọi** lời gọi LLM (element/aggregate/draft/role) |
| `GroundingService.verify_answer(draft, as_of)` | W3 §2 | **cổng hậu-draft** trên `draft` của Adjudicator |

**Bất biến tích hợp:** W4 **không** tự cài NLI cấp claim, repair, abstain — đó là `GroundingService.verify_answer` (W3). W4 **không** tự lọc hiệu lực ở retrieval — đó là W3 (và cổng 3 của Auditor dùng `in_force` của W2). Auditor **chỉ** điều phối ba cổng + prune.

---

## 7. Acceptance tests (phải xanh)

1. **Element-wise, không holistic:** một điều có 3 yếu tố cấu thành; tình tiết thoả 2/3 → `verify_article` trả `False` (điều không áp dụng), và `audit_trail` chỉ rõ yếu tố nào `unsatisfied`. (Chứng minh gate 2 là element-wise, không yes/no tổng thể.)
2. **Cổng ngày hiệu lực (điểm W4 thêm so với LegalGraphRAG):** một điều **áp dụng đúng** về nội dung nhưng `in_force(eid, as_of)=False` (đã bị bãi bỏ/chưa hiệu lực tại ngày vụ việc) → bị loại ở **cổng 3**, reason=`temporally_invalid`, **không** tốn lời gọi LLM cổng 2. Đổi `as_of` sang ngày điều còn hiệu lực → điều được nhận.
3. **Prune án lệ:** án lệ P tựa vào {điều A, điều B}; A,B đều bị loại (hết hiệu lực/không áp dụng) → P **không** nằm trong `verified_precedents`. Nếu A được giữ → P còn.
4. **Narrowing contract:** `verified_articles ⊆ candidate_articles` và Adjudicator chỉ đọc tập verified (test: chèn một điều "độc" vào candidate nhưng bị loại ⇒ không xuất hiện trong `draft`/trích dẫn).
5. **Hai cổng khớp nhau:** Adjudicator emit trích dẫn tới một điều đã-verify nhưng **diễn giải sai** (claim không được nguồn entail) → **cổng hậu-draft** (`verify_answer`) hạ lớp `unsupported` → Faith-Search sửa hoặc abstain (nối test W3 #2). Chứng minh cổng tiền + hậu bọc đúng hai phía.
6. **Đa vai > một-lượt, không tăng trích dẫn sai (acceptance §W4):** trên bộ tình huống mẫu, `mode="multi_role"` cho kết luận tốt hơn `mode="single"` **mà** tỉ lệ `citation_precision` (đo bởi W3/L13) không giảm — vì Auditor chạy trên mọi phát ngôn.
7. **Stop-condition deterministic:** vòng đa vai dừng khi `verified_articles` ổn định qua một lượt HOẶC chạm `max_rounds`; không phụ thuộc chuỗi sentinel.

---

## 8. Build tasks (thứ tự cho member)

1. **Auditor hard-gate** (`audit` + `verify_article` element-wise + `prune_unsupported`) với **3 cổng**, chạy stub `in_force`/`versions` trước → test 1,2,3. ← *chứng minh moat W4*.
2. Nối thật `TemporalRepository.in_force`/`versions`/`reconstruct_as_of` (W2) vào cổng 1 & 3 → test 2 với dữ liệu bitemporal thật.
3. **Orchestrator một-lượt** Researcher→Auditor→Adjudicator (per-party), nối `RetrievalService`/`GraphQuery`/`LLMGateway` → test 4.
4. Adjudicator schema dân sự + trích dẫn inline bắt buộc; nối `GroundingService.verify_answer` (cổng hậu-draft) → test 5.
5. **Reasoner đa vai** LangGraph (Auditor mọi phát ngôn) + stop-condition deterministic + checkpointer tenant-aware → test 6,7.

## 9. Steal-list (file trong `refs/` — ĐÃ VERIFY)
| Cần | File (dòng đã kiểm) |
|---|---|
| Orchestrator 3-agent tuyến tính + per-party seg | `LegalGraphRAG/core/utils/util.py::analyze_case` (dòng 54–73) |
| Auditor hard-gate: `audit` + `prune_unsupported_cases` | `LegalGraphRAG/core/agents/auditor.py` (dòng 5–37) |
| **verify_article element-wise** (vòng `judge_dep` → agg) | `LegalGraphRAG/core/judge/judge_law.py::verify_article` (dòng 4–33) |
| Researcher 3 toán tử + charge/cause-anchored | `LegalGraphRAG/core/agents/researcher.py` (dòng 22–75) |
| Adjudicator tổng hợp chỉ-trên-verified + JSON strict | `LegalGraphRAG/core/judge/judge_crime.py::synthesize_judgment` (dòng 41–56) |
| Vòng LangGraph (generate→answer→refine loop) | `PAKTON/.../Interrogator/src/Interrogator/graph/builder.py` (dòng 39–67) |
| Stop-condition (để SIẾT — tham chiếu điểm yếu) | `PAKTON/.../Interrogator/.../graph/nodes/router.py` (dòng 26–35) |
| Sub-agent-as-tool (ReAct gọi sub-graph) | `PAKTON/.../Archivist/src/Archivist/tools/interrogation_tool.py` |
| Faith-Search repair (gọi qua W3, không cài lại) | `L-MARS/lmars/faith_search/workflow.py::run` (dòng 256+; chọn claim lỗi dòng 333–336) |
| Cổng `temporally_invalid` (re-search giới hạn ngày) | `L-MARS/lmars/faith_search/router.py::_temporally_invalid` (dòng 102–117) |

---

## 10. Match check — đối chiếu repo thật vs prior notes

Đã **mở và xác nhận** các file; mọi điểm khớp với `research_notes/Repo deep read/{legalgraphrag_lmars,pakton}.md`. Không có mismatch. Chi tiết xác nhận:

- **`core/utils/util.py::analyze_case` (dòng 54–73):** ✔ đúng là orchestrator tuyến tính, **per-defendant** (`segment_case_text_withname` → loop `research` → `audit` → `adjudicate`), không framework (không LangGraph). Khớp note A1/A2.
- **`core/agents/auditor.py` (dòng 5–37):** ✔ `audit` lọc từng điều qua `verify_article` rồi gọi `prune_unsupported_cases`; `prune_unsupported_cases` giữ fact (án lệ) chỉ khi `fact['law']` có ít nhất một id ∈ tập id điều đã verify (dòng 17–24). Khớp note A3. → **prune drop đúng án lệ mà mọi điều viện dẫn đều bị loại.** ✔
- **`core/judge/judge_law.py::verify_article` (dòng 4–33):** ✔ **element-wise**: vòng `for diagnostic_item in article["judge_dep"]` (dòng 17), mỗi yếu tố một call `JUDGE_LAW_PROMPT` ràng buộc `true`/`false` (dòng 18–27), **rồi** call tổng hợp `JUDGE_LAW_PROMPT0` trên hai danh sách satisfied/unsatisfied (dòng 29–33). **KHÔNG** phải yes/no holistic (nhánh holistic chỉ là fallback khi `article` là `str`, dòng 6–12). Khớp note A3 ("element-wise constitutive-element checking, not a single holistic yes/no"). ✔
- **Thiếu cổng ngày hiệu lực:** ✔ xác nhận không có bất kỳ `in_force`/`valid_from`/`effective_date`/temporal check nào trong `auditor.py` hay `judge_law.py`. Đây đúng là **gap** mà W4 phải thêm (note A3 §gap, note B5 `temporally_invalid`). W4 cắm `TemporalRepository.in_force` (W2) làm cổng 3.
- **PAKTON `Interrogator/.../graph/builder.py` (dòng 39–67):** ✔ vòng LangGraph đúng như note: `START→generate_question→route→{get_answer|save_interrogation}`, `get_answer→refine_answer→generate_question` (loop), `save_interrogation→write_report→END`. Sub-agent-as-tool: `Archivist/.../tools/interrogation_tool.py` wrap Interrogator thành `@tool` (khớp note §2a/§8). ✔
- **Stop-condition mong manh:** ✔ `Interrogator/.../graph/nodes/router.py` (dòng 29 ngân sách lượt; dòng 35 chuỗi sentinel literal **hoặc** `similarity_check` embedding). Khớp note ("fragile soft stop") → W4 siết bằng tiêu chí hội tụ set-equality (§5.2).
- **L-MARS Faith-Search (`faith_search/`):** ✔ repair loop ở `lmars/faith_search/workflow.py::run` (dòng 256+); chọn claim lỗi để re-search theo `failure_type ∈ {fabricated_source, temporally_invalid, partially_relevant, unsupported}` (dòng 333–336); router `_temporally_invalid` re-search giới hạn ngày (dòng 102–117); abstention include iff `support_level ∈ {supported,partially_supported}` & `confidence ≥ 0.6` (`aggregator.py` dòng 49). Khớp note B2/B3. **W4 không cài lại** phần này — gọi qua `GroundingService.verify_answer` của W3.

**Lưu ý chuyển đổi domain (đã nêu ở note A5, nhắc lại để member nhớ khi code):** output schema hình sự TQ (`charge_name`/`term_of_imprisonment`) → **thay** bằng schema cứu trợ dân sự VN; "predict charge" → "predict căn cứ khởi kiện"; `judge_dep` checklist → **sinh lại** từ "điều kiện áp dụng" của quy phạm VN (không tái dùng checklist TQ).
- ⚠️ **Sửa M3 (lỗi kiến thức ở bản trước):** án lệ VN đã công bố là **RÀNG BUỘC TRÊN THỰC TẾ** — NQ 04/2019 Điều 8: Thẩm phán *phải* nghiên cứu, áp dụng; không áp dụng *phải nêu rõ lý do*. KHÔNG phải "thuyết phục/không ràng buộc". → không được *under-weight* án lệ đúng tình huống.
