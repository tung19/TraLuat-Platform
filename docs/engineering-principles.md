# TraLuat — Nguyên tắc kỹ thuật (rút từ audit phản biện)

> 15 nguyên tắc chắt từ việc review phản biện độc lập các spec. Mỗi cái sinh ra từ một lỗi *thật* đã suýt lọt. Dùng làm checklist khi code + review PR.
> Nguồn lỗi: `docs/specs/spec-audit-fixes.md`, `w2 §11`, `w3 §8`, `research_notes/Spec audit/`.

---

1. **Verify "có" ≠ đảm bảo "đủ".** Kiểm trích dẫn đã có không chặn được *sót* điều chi phối. → luôn có **sufficiency/recall floor** lúc chạy; thiếu phủ → hạ confidence/HITL. *(W3 C1, W6 C1)*

2. **Bất biến không có constraint DB thì không phải bất biến.** "Đúng một dòng", "cô lập tenant" nếu chỉ ở code sẽ gãy. → ép bằng **`EXCLUDE`/`UNIQUE`/`FORCE RLS`**. *(W2 C1, W5 C2)*

3. **Mọi thay đổi qua versioning, không UPDATE in-place.** Sửa tại chỗ phá tx-time/audit. → `tx_to=now` + row mới. *(W2 C2)*

4. **Filter cứng gạt mất ngoại lệ pháp lý.** Hiệu lực không phải boolean một-trục: điều chuyển tiếp/grandfathered, khoản con bị bãi bỏ, version bị trích sai, quy phạm tùy nghi — đều bị filter cứng loại nhầm. → **giữ + đánh dấu**, kiểm tới cấp version/khoản. *(W3 C3, W4 C3, W6 C2)*

5. **Đọc code ≠ hiểu ngữ nghĩa.** Nhiều "port" sai vì chép hình mà không hiểu: NLI entailment ≠ *hỗ trợ pháp lý*; `confidence 0.82` bịa (eyecite không có); "cross-provider min" là *eval reporting* không phải runtime; `temporally_invalid` của L-MARS là *web-search*; `align` cần structure-encoder; resolver eyecite match *tên đương sự* không dùng cho anaphora luật; `"true" in lower()` khớp cả "untrue". → **đọc để hiểu cơ chế, viết lại sạch, test.** *(W1 C2/H2, W3 H1/M2/M4, W4 C1/C2, W2 H5)*

6. **Quyết định pháp lý có thể SAI → escalate human.** Giải xung đột tự động (general-vs-special) và "bản án đúng/sai" (vs *tuỳ nghi xét xử*) không được auto-quyết. → trả **`unresolved → human`**; disclaimer/abstain chiều tuỳ nghi; không bao giờ auto "thẩm phán sai". *(W2 H4, W4 H3/H6)*

7. **Test dữ liệu sạch in-order là vô dụng.** Test happy-path pass trong khi dữ liệu sai. → **adversarial fixtures** (overlap/cùng-ngày/lệch-thứ-tự/empty-set/chuyển-tiếp/injection) + **đo precision/recall**; với quan hệ phá huỷ, **precision > recall** (một `repeals` giả tệ hơn bỏ sót). *(mọi spec §tests)*

8. **Mối nối liên-module phải có cổng.** W1 *sinh* dữ liệu, W2 *không được tin vô điều kiện*. Hai module đúng riêng vẫn sai chung nếu cái nối không gác. → gate `review_status='approved'` ở đường materialize. *(W1 C1)*

9. **Sửa một spec phải lan sang spec phụ thuộc.** W4 tái phạm đúng lỗi W2/W3 đã vá vì không kiểm chéo (còn tự chứng "no mismatch"). → trước khi dùng hàm của spec khác, **đọc mục audit của nó**; "Match check" phải soi cả *bug đã biết*, không chỉ *API khớp*. *(W4 C1/C3/H3)*

10. **Tenancy & compliance phải fail-closed, ép ở hạ tầng, và CÓ TEST.** "Cô lập trên giấy" chưa cô lập: RLS fail-open, checkpointer/broker/cache ngoài vòng, egress không classifier, IDOR. → fail-closed + mọi store (gồm Redis/RabbitMQ) + mọi egress + **test rò rỉ là acceptance bắt buộc**. *(W5 C1–C6)*

11. **Tính năng moat phải được ENGINEER, không ASSERT.** Omission & tuân thủ rủi-ro-cao không được "hô HITL/second-opinion" thay cho cơ chế (conformity assessment, logging, registration, sufficiency, obligation-type). → mỗi moat = cơ chế + test, không phải câu khẳng định. *(W6 C1/C4)*

12. **Phân biệt loại nghĩa vụ (bắt buộc vs tùy nghi/default).** Civil-law có **quy phạm tùy nghi** luật tự lấp — coi mọi "im lặng" là "thiếu" sẽ false-positive hàng loạt. → `obligation_type` là field hạng nhất. *(W6 C2)*

13. **Luật VN = RULE BASE khai báo, tách khỏi engine; migrate code KHÔNG migrate luật.** Thang bậc/xung đột/hồi tố/as_of là **tri thức pháp lý cố định, versioned, neo primary-text, người-pháp-chế quản trị** — không chôn trong code, không auto-rewrite, không điền từ trí nhớ. Engine chỉ ĐỌC (`in_force`/`authority_rank`/`resolve_as_of` single-source, call-don't-reimplement). Khi migrate repo: **bóc rule pháp lý hardcode ngoại (US/EU) → đọc từ rule base.** *(`legal-rule-base.md`; bug hardcode US CA §16600 trong fork)*

14. **Đa ngữ: suy luận neo BẢN GỐC CÓ THẨM QUYỀN, dịch chỉ để trình bày.** Suy luận pháp lý neo vào **luật VN gốc**; EN/ZH là bản dịch tham khảo, **KHÔNG reason như thể có thẩm quyền** (dịch sai = sai nghĩa luật). **NGOẠI LỆ (beachhead FDI):** điều ước quốc tế → **ngôn ngữ xác thực** (+ưu tiên Đ.58 K5); tài liệu khách → **controlling-language clause của chính nó** (hợp đồng EN = gốc EN). Hệ quả: citation EN/ZH cite cùng `eId` về điều–khoản VN; bản dịch gắn `equivalence_type` + disclaimer "bản VN ưu tiên"; **tách cache kết-luận (language-neutral) vs bản-dịch (per-language)**; eval cross-lingual. *(FR-04, `legal-rule-base`, stack-db §2)*

15. **Được CHẬM, không được SAI — tối ưu phải bảo toàn đúng-đắn (2 lớp).** Pháp lý: tốc độ không bao giờ đổi lấy đáp án sai.
    - **(A) Tối ưu TƯƠNG-ĐƯƠNG** (snapshot · cache · index · batching · precompute): **phải identical** với đường-không-tối-ưu → **CI parallel-path byte-identical**; **cache key gồm MỌI input ảnh hưởng output** (query/cands/as_of/law_version/tenant/model+prompt version) — thiếu một = serve stale sai.
    - **(B) Tối ưu XẤP-XỈ** (ANN/HNSW · bound-hop · top_k · rerank — recall<100% by design): **offline-calibrate recall-floor vs brute-force oracle** → **CI đo recall@k ≥ floor**; runtime dựa **sufficiency floor (R1) + abstain**, **cấm miss âm thầm** (không có ground-truth runtime → không gate theo recall thật, chỉ proxy sufficiency).
    - **Cổng runtime:** **no-skip-rerank / no-downgrade ở ca HIGH-STAKES** (Judgment/omission/conflict — risk-class QĐ 33); tối ưu tốc độ chỉ cho ca rẻ. *(performance.md §8, W3 §4, chaos R1)*

---

## Dùng thế nào
- **Khi code:** mỗi nguyên tắc là một câu hỏi tự vấn ("bất biến này có constraint DB chưa?", "cổng này có kiểm *đủ* không hay chỉ *có*?").
- **Khi review PR:** reviewer chạy qua 12 mục; đặc biệt #2/#7/#10 là **ship-blocker**.
- **Khi dùng hàm/dữ liệu của mảng khác:** áp #8, #9 — đọc mục audit của mảng đó trước.
- Một dòng: **"grounded, gated, versioned, fail-closed, human-escalated, và test bằng dữ liệu bẩn."**
