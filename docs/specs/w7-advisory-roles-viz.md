# W7 — Compliance-Advisory · Vai mở rộng · Loophole · Per-role Visualization

> Bổ sung kiến trúc cho 3 thứ user nêu: (1) **use case doanh nghiệp → vi phạm? → cách tránh + trích điều luật**; (2) **vai mở rộng** (thẩm phán/kiểm sát/**điều tra**/kiểm toán) + **tư vấn lỗ hổng luật**; (3) **visualization theo vai**.
> Nguồn: `research_notes/Compliance advisory and roles/{compliance_advisory,multirole_and_loophole,legal_visualization}.md` (deep-research GitHub + papers).

---

## 0. "Có ai làm chưa?" — câu trả lời thẳng: **gần như CHƯA (greenfield)**

| Tính năng user muốn | Có OSS làm chưa? | Gần nhất |
|---|---|---|
| Scenario doanh nghiệp → vi phạm + remediation + **trích điều luật** | ❌ gần như không | **ARCCS** (EMNLP'26, document-centric, **không** surface citation, **không** remediation; license placeholder) |
| **Đúng điều luật tại ngày X + jurisdiction** trong compliance | ❌ **không hệ nào** (open/academic/commercial) giải | chỉ symbolic (LegalRuleML norm-dynamics) + Deloitte DORA (cite nhưng khách tự cấp control) |
| Vai **điều tra viên** (chứng cứ→điều luật) | ❌ **không có OSS** | — (gap thật) |
| Vai **kiểm sát ra quyết định** (không chỉ tranh tụng) | 🟡 PDP-Bench (TQ, ra *lớp* quyết định, không map điều luật) | System 206 TQ (đóng) |
| Vai **kiểm toán/tuân thủ** neo điều luật | 🟡 research sớm (RAGulating Compliance, SINTEF EU-AI-Act) | thương mại đóng (CUBE/Regology) |
| **Phát hiện lỗ hổng luật** (toàn corpus) | 🟡 sớm + hẹp, **đều cần solver** | tax-loophole DSL · IRC§121 (LLM→Z3) · LegalSim |
| **Workbench theo vai** + viewer song ngữ VN | ❌ **không OSS** (toàn thương mại) | NCSC eBench, CoCounsel judicial mode (đóng) |

> **Và differentiator lớn nhất trùng đúng moat của TraLuat:** *trích dẫn điều luật + đúng ngày hiệu lực* là khoảng trống lớn — **chốt lại chính xác (H4): "first OSS / first VN"**, KHÔNG phải "chưa ai trên đời" (RegTech thương mại như Deloitte DORA đã cite production; Indigo đã làm point-in-time). Cơ hội thật, nhưng khó.

> 🔴 **Audit phản biện W7 — lỗi xác nhận & sửa** (`research_notes/Spec audit/w7_review.md`):
> - **C1 — W7 là *strategy memo*, chưa buildable** (thiếu acceptance/interface/build tasks/dependency) → bổ sung **§8**.
> - **C2/C3 — nguy cơ FALSE-CLEAR** ("không vi phạm" sai → doanh nghiệp cứ làm → phạt tới 3 tỷ/5% doanh thu/hình sự). Verify 3 cổng (W3) **KHÔNG** bắt recall-gap → **bắt buộc coverage/sufficiency floor** (kế thừa W6 §C1, W3 §8-C1); kế thừa luôn fix W3 C2/C3/H3 (silent-vs-missed, chuyển tiếp, in_force cấp khoản).
> - **C4 — vai điều tra/kiểm sát rủi ro CAO HƠN Judgment Analysis** (prospective, buộc tội, suy đoán vô tội) nhưng đang ít guardrail hơn → phải có **high-risk engineering (QĐ 33/2026) + chống over-charging/recall-inflation** (cảnh báo PDP), không chỉ integrity_note.
> - **C5 — posture loophole hiện là *nhãn, không phải control*** (output comply≡evade, HITL = luật sư của chính user) → §3 thêm control thật.
> - **H1 — AGPL (CourtListener): tách-service là TRIGGER (§13), KHÔNG phải lối thoát** — chỉ GPLv3 (Indigo) mới an toàn khi tách; **phải hỏi luật sư** (§4 sửa).
> - **H2** remediation chưa có cơ chế grounding (dễ bịa nhất); **H5** solver cho §1 là **nút thắt hand-formalization** (thứ giữ Regorous nhỏ — mọi thành công solver chỉ ở *một mục luật*) → KHÔNG phải quick-win; **M3** số 69–88% là hallucination *khi KHÔNG grounded* (ta grounded — đừng dùng sai ngữ cảnh).

---

## 1. ComplianceAdvisoryService (workflow MỚI — L9)

**Vào:** mô tả tự do hoạt động kinh doanh (+ `as_of`, lĩnh vực). **Ra:** có vi phạm không · điều luật bị vi phạm (cite + ngày) · cách khắc phục/tránh · (tùy chọn) cảnh báo vùng luật mờ.

**Reuse (pattern, không có engine sẵn):**
- **ARCCS** (`github.com/geofila/ARCCS`): kiến trúc 2 module **RPEM** (trích yêu cầu có cấu trúc từ quy định) + **CCM** (kiểm từng yêu cầu → COMPLIANT/NON_COMPLIANT/INSUFFICIENT/HUMAN_REQUIRED + evidence + confidence). ⚠️ **License placeholder → chỉ học pattern tới khi rõ.** Thiếu: scenario-centric, surface citation, remediation.
- **COLING 2025 RAG Compliance** (3 tầng static/dynamic/computational) — reference architecture.
- **Regorous/Governatori + LegalRuleML** (Defeasible Deontic Logic) — **truy vết cấp điều luật + norm-dynamics (temporal)** là thứ duy nhất đúng; nhưng đóng + phải formalize tay.

**Build (net-new, trên nền ta):**
1. **Scenario intake** → trích "hoạt động/nghĩa vụ" (deontic: phải/cấm/được) kiểu LegalRuleML-lite.
2. **Áp dụng obligation** qua W3 retrieval (hiệu lực-aware) + `required_clause_rule@T` (W6) — **dùng `obligation_type` mandatory/default** (W6 C2) để không báo nhầm.
3. **Per-obligation check** (pattern ARCCS) → COMPLIANT/VI_PHẠM/THIẾU_THÔNG_TIN/CẦN_NGƯỜI, **mỗi kết luận neo điều–khoản + ngày** (verify 3 cổng W3 — đây là chỗ ARCCS thiếu).
4. **Remediation generation:** cách tránh/khắc phục (grounded, không bịa; dạng second-opinion, HITL).
5. **Hybrid reliability:** LLM/RAG + **tầng solver/symbolic** cho quy phạm hình thức hoá được (LLM thuần ảo giác 69–88% — Dahl 2024).

**Guardrail:** **không tư vấn trực tiếp cho công chúng** (công cụ cho pháp chế); mọi kết luận "có vi phạm" phải HITL + cite; abstain khi không neo được.

---

## 2. Vai mở rộng (W4 reasoner — config-driven, thêm vai)

`JurisdictionPack.roles` thêm 2 vai **chưa ai làm OSS**:
- **Điều tra viên (investigator):** map **chứng cứ ↔ điều luật** (cấu thành), dựng giả thuyết vụ việc. **Net-new** (không OSS). Dùng `LinkingService` (W2) + Auditor element-wise (W4) với "chứng cứ" thay "tình tiết".
- **Kiểm sát ra quyết định (procuracy-decision):** đánh giá chứng cứ + subsumption + định khung truy tố. Tham chiếu **PDP-Bench** (TQ) cho *khung task*, nhưng ta xuất **map điều luật + lập luận có cite**, không chỉ lớp quyết định.
- **Kiểm toán/tuân thủ (auditor):** chạy checklist tuân thủ neo điều luật (nối §1).

**★ Bất biến LAW-TRUE + integrity-note (áp cho MỌI vai):** lập luận **mù với địa vị/chức vụ** đương sự (`party.position`); output kèm `integrity_note` *tách biệt* cảnh báo "loại vụ này thực tế có thể thiên vị — platform không điều chỉnh, kết luận là *đúng luật*". (Đã ghi ở `w6 §1.4`; nhắc lại cho vai kiểm sát/điều tra.)

---

## 3. Loophole/Gap Advisory (tư vấn lỗ hổng — defensive)

**Reuse (ý tưởng, repo hẹp + license phần lớn chưa rõ):** tax-loophole **DSL Prolog + mã điều luật** (`fratric/Rules2Lab`); **IRC§121** LLM→Prolog/**Z3** (bắt mơ hồ 100% vs 33% LLM-thuần; `martians-sheep/...`); **Clash-of-Leges** (dataset *xung đột* luật); **LegalSim** (chuỗi exploit, **khung dual-use phòng thủ tường minh**); **typology lỗ hổng** (Greek audit, arXiv:2606.00030).

**Build:**
- **Tầng solver BẮT BUỘC** (LLM thuần không đủ): hình thức hoá quy phạm → phát hiện **im lặng / mâu thuẫn / mơ hồ / xung đột thứ bậc** (nối `resolve_conflict` W2).
- **Truy vết tới điều luật** mọi phát hiện.
- ⚠️ **Posture PHÒNG THỦ tường minh (ethical, bắt buộc):** chỉ ra *chỗ luật mờ/im/mâu thuẫn để doanh nghiệp phòng ngừa & chuẩn bị* — **KHÔNG** hướng dẫn *cách khai thác để né luật*. Khung "cảnh báo rủi ro cho người soạn/kiểm toán", không "evasion playbook".
- **★ C5 — "pro-only / HITL / nhãn" là NHÃN, không phải CONTROL** (output comply≡evade; HITL là luật sư của chính user → không chặn lạm dụng). Cần **control thật**: (a) output **chỉ mô tả vùng bất định + rủi ro + hướng *tuân thủ an toàn hơn*** — **không sinh bước hành động khai thác**; (b) **từ chối** yêu cầu khung "làm sao để không bị phạt/không bị phát hiện khi làm X"; (c) **log + review** mọi truy vấn loophole (audit W5); (d) tham chiếu mitigations LegalSim (giới hạn phạm vi, không hướng dẫn jurisdiction-specific cách né). **Đây là lý do xây loophole SAU CÙNG** + cần rà đạo đức/pháp lý riêng trước khi bật.

---

## 4. Per-role Visualization / Workbench (L12 mở rộng)

**Reuse:**
- **Engine/data:** **Indigo** (point-in-time, **GPLv3**) — tách API service là ổn (GPLv3 không lan qua ranh giới tiến trình/mạng). **CourtListener** (citation, **AGPL**) — ⚠️ **H1 sửa: AGPL §13 kích hoạt KHI tương tác qua mạng → tách-service CHÍNH LÀ trigger, không phải lối thoát**; nếu dùng CourtListener có chỉnh sửa & cho người dùng tương tác qua mạng, nghĩa vụ mở nguồn *vẫn áp*. → hoặc dùng *không sửa đổi* qua API công khai của họ, hoặc thay bằng thành phần permissive, **hỏi luật sư trước khi tích hợp**.
- **UX chuẩn vàng "What Version + Timeline of Changes":** legislation.gov.uk — pattern để bắt chước.
- **Viz chung permissive (nhúng thẳng frontend):** **Cytoscape.js / Sigma.js** (đồ thị quy phạm/citation), **shadcn timeline** (dòng thời gian hiệu lực).

**Build (net-new — không OSS):**
- **Workbench theo vai:** thẩm phán (phán quyết + án lệ áp dụng) · kiểm sát (hành vi + cấu thành) · **điều tra (map chứng cứ↔điều luật)** · kiểm toán (checklist tuân thủ). Mỗi vai: view + quyền (RBAC W5) + thao tác riêng.
- **Mặt phẳng quyết định tích hợp "luật-tại-ngày-T + án lệ"** (không OSS nào gộp cả hai).
- **Viewer song ngữ VN** (Akoma Ntoso chuẩn hoá *data layer* + định danh language-version; **UI song ngữ là net-new**).
- Điều hướng cite → `reconstruct_as_of` (đã có ở `w6 §3`).

> **Khuyến nghị kiến trúc:** model luật VN bằng **Akoma Ntoso (Cobalt/Bluebell)** để *mở khoá* logic point-in-time của Indigo **và** định danh song ngữ chuẩn — đòn bẩy cao nhất.

---

## 5. Build-vs-reuse & cảnh báo license

| Thành phần | Verdict | License |
|---|---|---|
| ARCCS (pattern compliance 2-module) | **STUDY** (chưa reuse code) | ⚠️ **placeholder — chưa rõ** |
| COLING RAG framework / AIReg-Bench (eval) | STUDY / eval method | paper CC BY 4.0; data chưa rõ |
| Regorous/LegalRuleML (symbolic traceability) | **ADOPT ý tưởng** (solver + norm-dynamics) | đóng; LegalRuleML là chuẩn mở |
| Indigo (point-in-time engine) | **ADOPT làm service** | GPLv3 (copyleft → tách service) |
| CourtListener (citation) | ADOPT làm service | AGPL (copyleft → tách service) |
| Cytoscape.js / Sigma.js / shadcn | **ADOPT nhúng** | permissive |
| PDP / loophole repos (Rules2Lab, IRC§121, LegalSim) | **STUDY ý tưởng** | phần lớn **chưa nêu license** → không copy |

**Tất cả:** không có gì cho **tiếng Việt**; license nhiều repo **chưa rõ → kiểm trước khi dùng thương mại**; copyleft (Indigo/CourtListener) **tách API service** để không lây sang frontend proprietary.

---

## 5b. Law simulation — QUYẾT ĐỊNH (không mở rộng scope)

Research 5 nghĩa (`research_notes/.../law_simulation.md`). Verdict **dứt khoát để tránh lan man**:

| Nghĩa | Verdict | Vì sao |
|---|---|---|
| Tòa role-play / diễn lại phiên xử | **❌ KHÔNG (giờ)** | đông, repo no-LICENSE, **không neo ngày hiệu lực**, không dùng moat ta |
| Mô phỏng *kết quả* (win-probability) | **❌ KHÔNG** | chỉ là classification, **EU rủi-ro-cao**, VN đã có đối thủ prediction |
| Xã hội agent có chuẩn (generative agents) | **❌ KHÔNG** | chuẩn trừu tượng, reward-hack, không phải luật thật |
| **Mô phỏng *tác động khi luật đổi* (Change-Propagation)** | **🟡 CÂN NHẮC — SAU** | *không ai làm* + **dùng đúng moat** (versioned + ngày hiệu lực); nối W1→W2 Change-Propagation |
| Counterfactual "what-if" có ràng buộc | **🟡 SAU** | hướng L4M neuro-symbolic (SMT-verified) = bền; chỉ khi có solver |

**Phân biệt cốt lõi (đừng lẫn):** **đa vai (W4) như *cơ chế verify* để ra second-opinion grounded = GIỮ (core)**; **đa vai như *sản phẩm mô phỏng phiên xử* = HOÃN**. W4 bounded + có Auditor, phục vụ *kết quả đúng*; mô phỏng là theater, không cần/không dùng moat.

---

## 5c. Phạm vi & ưu tiên (chống lan man)

- **LÕI (xây trước — moat + bán được):** W1–W6 = engine hiệu lực-aware + Review/omission + Assistant + **Judgment Analysis (second-opinion)**.
- **EXTENSION (backlog, chỉ sau khi lõi vững + benchmark đạt):** W7 §1 ComplianceAdvisory → vai mở rộng/workbench (§2,§4) → **loophole (§3) sau cùng** (nhạy cảm) → **law-simulation Change-Propagation (§5b) sau nữa**.
- **Nguyên tắc:** không mở tính năng extension nào khi lõi chưa qua cổng benchmark 3 chiều (L13). Mỗi extension phải *dùng moat* (hiệu lực + grounding) — nếu không, là sân của đối thủ, bỏ.

---

## 6. Kết luận chiến lược
Ba thứ user muốn (**scenario→vi phạm+remediation+cite**, **vai điều tra/kiểm sát-quyết-định/kiểm toán**, **loophole toàn corpus**, **workbench theo vai song ngữ**) **gần như chưa ai làm mã nguồn mở** — vừa là **cơ hội** (first-mover, nhất là cho VN), vừa **khó** (cần solver, cần dữ liệu nhãn, cần người). Và **lợi thế quyết định của các thứ này trùng đúng moat TraLuat đã có nền: trích dẫn điều luật + đúng ngày hiệu lực** — khoảng trống lớn nhất mà *không hệ nào* (open/academic/commercial) giải. → Nên xây, theo thứ tự: **ComplianceAdvisory (§1) trước** (giá trị thương mại rõ, tái dùng pattern ARCCS/COLING), rồi vai mở rộng + workbench, loophole (§3) sau cùng (khó + nhạy cảm, cần solver + posture phòng thủ).
