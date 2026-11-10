# Deep audit #3 — findings (sau L9 expose + FR-35.13/14 + geo)

Rà soát đối-nghịch code mới (L9 endpoints, deadlines/calendar, geo, alerts). Mức: ✅ đã sửa · ⚠️ đã ghi nhận (chưa sửa, rủi ro thấp).

## ✅ F1 (compliance — ĐÃ SỬA): `/judgment` & `/draft` không ghi audit
- **Lỗi thật**: `/judgment` (FR-03) và `/draft` (FR-34) bỏ qua `svc.audit` — khác `/analyze`·`/lookup`. Comment của `/judgment` còn hứa "CN-03 → HITL + audit" nhưng KHÔNG gọi audit. Vi phạm **CN-03** (QĐ 33/2026: high-risk judgment → HITL **+ logging**) và NĐ356 Đ29 (ghi xử-lý dữ-liệu khách cho `/draft`).
- **Sửa**: helper `audited()` ghi write-ahead `intent` + `confirm` quanh 2 endpoint (judgment: `data_class=case-review, dest=none`; draft: `client-sensitive, dest=local`; draft local-down → `confirm("denied")`). Trả `trace_id` cho client. Test: `test_judgment_writes_audit_trail`, `test_draft_writes_audit_trail` (kiểm intent+done qua `by_trace`).

## ✅ F2 (test-fragility — ĐÃ SỬA): seed-data commit vào DB test → test giả định "bảng rỗng" vỡ
- **Lỗi thật**: `seed_deadlines.py`/`seed_directory.py` `commit()` vào DB dev = DB test. `test_pg_reference` (`_count` đếm TOÀN bảng) và `test_pg_directory` (kind-filter) giả định bảng rỗng → vỡ khi có seed.
- **Sửa**: `_count` scope theo (dataset,key); kind-filter assert "mọi hit đúng loại". Robust với seed-data đã commit, vẫn chứng minh idempotent/filter.

## ✅ F6 (correctness — ĐÃ SỬA): bitemporal read trộn đồng-hồ host↔DB (clock skew)
- **Lỗi thật**: `reconstruct_as_of`/`effect_status`/`document_as_of`/`correct_valid_from` đặt `known` (mốc transaction-time "hiện tại") = `datetime.now()` của **host**, trong khi `tx_from` = `now()` của **DB** (server-default). DB chạy trong container (đồng hồ lệch host ~chục ms, có lúc NHANH hơn) → `tx_from > known` → **dòng VỪA GHI bị ẩn** → reconstruct `None`. Biểu hiện: test đọc-ngay-sau-ghi (materialize) **flaky** khi DB-clock > host-clock. Đây là lỗi bitemporal thật (không chỉ test): bất kỳ lệch đồng-hồ app↔DB nào cũng ẩn bản vừa commit.
- **Sửa**: helper `_db_now(s)=SELECT now()` → `known`/`now` mặc định lấy ĐỒNG HỒ DB (cùng nguồn `tx_from`). 4 site trong `w2/repo.py`. Regression `test_just_written_row_visible_with_default_known`. Suite ổn định 5/5 lần.

## ✅ F7 (test-infra — ĐÃ LÀM): tách DB test riêng `traluat_test` (yêu cầu của F2/F3)
- `tests/conftest.py`: mỗi phiên drop+tạo `traluat_test` + **clone schema-only** từ dev (`pg_dump --schema-only`), set `DATABASE_URL`. Demo-seed đổ `traluat`, test chạy `traluat_test` → hết class seed-pollution.
- **F8 phát sinh (ĐÃ SỬA)**: chuỗi migration KHÔNG replay-được từ rỗng (0001 `create_all` dựng `document` đủ cột, 0005 `add_column source_hash` → trùng) — **lỗi fresh-deploy/CI**.

## ✅ F8 (migration — ĐÃ SỬA): squash 13 migration → baseline replay-được
- **Sửa**: thay 0001…0013 bằng MỘT `0001_baseline.py` dựng toàn schema đúng thứ tự (CREATE EXTENSION postgis → `create_all` mọi bảng [GiST/GIN/HNSW + extension qua event model] → role app + grants + FORCE RLS bảng khách). Diff schema baseline-vs-dev: **446/446 dòng khớp** (chỉ khác thứ-tự-cột `analysis_task.payload`, vô hại) → verified reproduce đúng.
- DB dev đang chạy → `alembic stamp 0001_baseline --purge` (giữ seed). Fresh `alembic upgrade head` trên DB rỗng → OK (verified 2×). `conftest` chuyển sang `alembic upgrade head` (bỏ phụ thuộc docker/pg_dump). `prepend_sys_path = . src`.

## ⚠️ F3 (latent — GHI NHẬN): 4 test khác vẫn đếm-toàn-bảng
- `test_pg_bitemporal`(UnitVersion) · `test_pg_w3_indexed`(Chunk) · `test_pg_w5_rls`(AuditLogRow) · `test_pg_phase_d_followup`(Document) dùng `count().select_from(...)` không `where`. Hiện XANH vì chưa seed các bảng đó. **Rủi ro**: seed sau này vào chúng → vỡ. Nên: DB test riêng, hoặc scope mọi count theo khoá. (Chưa sửa — không broken.)

## ✅ F4 (robustness — ĐÃ SỬA): parse ngày ISO lỗi → 500 thay vì 400
- **Lỗi**: `dt.date.fromisoformat(...)` thẳng trong handler (/lookup,/compare,/deadline,/analyze,/doc,/draft,/judgment) → ngày sai/thiếu → ValueError → **500** (lẽ ra lỗi client → 4xx). Gây alert on-call nhầm + client không biết mình sai.
- **Sửa**: helper `parse_date(s, *, default)` → `HTTPException(422)` cho ngày sai; field bắt buộc thiếu → 422; field tuỳ chọn bỏ trống → default (today/None). Thay 9 call-site. Test `test_bad_date_returns_422_not_500` + `test_optional_date_omitted_still_ok`.

## ⚠️ F5 (edge — GHI NHẬN): deadline lùi qua ranh giới NĂM
- `compute_deadline` nạp `ngay_nghi` chỉ cho `raw.year`. Nếu hạn rơi 31/12 rồi lùi sang năm sau → lễ âm năm sau không có trong set (lễ dương built-in vẫn đúng). Edge hiếm. (Chưa sửa.)

## Đã kiểm — KHÔNG phải lỗi
- **Deadline math hợp luật**: ngày (X+N, "ngày bắt đầu không tính" khớp khi mốc=ngày sự kiện) · tháng/năm (ngày tương ứng, kẹp cuối tháng) — đúng BLTTDS Đ.182-184, BLDS Đ.147-148.
- **CCCD gate** `\b\d{12}\b`: MST 10/13 số không false-positive (word-boundary).
- **`/draft` residency**: dùng `svc.local_gateway` + `healthy()` → tình tiết khách không rời VN; local down → abstain (R2 no-failover). Đúng.
- **`/compare`,`/deadline` tenant**: thuần KB công, không chạm dữ-liệu-khách/RLS.
- **alerts fan_out**: 1 alert/subscriber, delivered-flag sau deliver. OK.
