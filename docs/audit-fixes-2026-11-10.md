# Bản sửa sau audit — 10/11/2026

> Cập nhật tiếp ngày 11/11: đã nối indexed retrieval, Ollama và NLI vào runtime; mặc định không còn Echo. Xem [bản kết nối AI local](local-ai-wiring-2026-11-11.md) cho migration 0005 và bằng chứng mới. Nội dung dưới đây lưu trạng thái đợt sửa ngày 10/11.

Đã sửa các lỗi tái hiện trong audit A01–A30 và bổ sung regression test. Đây là bản sửa trên workspace, chưa commit/push, chưa áp migration vào database dev hoặc production. **Chưa đủ điều kiện phát hành production:** còn các phần scaffold và dữ liệu/hạ tầng chưa nghiệm thu ở cuối tài liệu.

Audit gốc tại commit `76c8dc4` được giữ nguyên làm bằng chứng: [audit-2026-11-10.md](../reports/audit-2026-11-10.md). Trạng thái tính năng hiện tại nằm trong [feature-registry.md](feature-registry.md).

## Phạm vi đã sửa

| Finding | Thay đổi và giới hạn |
|---|---|
| A01 | Bỏ secret mặc định; bắt buộc issuer, audience, subject, tenant UUID, iat/exp, thời hạn tối đa 1 giờ. Role, retention, residency và quyền platform lấy từ DB hiện tại, không tin claim phân quyền. |
| A02 | Provider thật kiểm login và membership role đặc quyền, dùng `traluat_app` non-owner, bind tenant/subject theo transaction. Test hai tenant và đọc KB bằng login runtime. |
| A03 | Commit khi request thành công, rollback khi lỗi; test subscription được đọc từ kết nối mới. |
| A04 | Audit metadata bền vững qua connection riêng; intent commit trước gateway và còn tồn tại khi gateway lỗi. Không ghi nội dung khách vào audit. |
| A05 | Migration thu hồi UPDATE/DELETE/TRUNCATE của app trên audit; test UPDATE/DELETE bị DB từ chối. |
| A06 | Duyệt KB đòi identity `platform_operator` riêng, không suy từ tenant owner. Kết nối ghi KB phải cấu hình riêng; có audit actor/intent/result. |
| A07 | Lookup/summarize coi raw input khách là sensitive, định tuyến local. |
| A08 | Sửa import Celery, kiểm runtime login, commit task; chỉ retry lỗi connection/operational phù hợp. Test wrapper thực. |
| A09 | Split và same-date fold đóng belief cũ rồi append belief mới, không ghi đè lịch sử; test cố định `known_as_of`. |
| A10 | Repeal áp toàn subtree và các ngôn ngữ; dựng văn bản giữ tiêu đề lịch sử và bỏ nội dung đã hết hiệu lực. |
| A11 | Điều đích chưa resolve giữ unresolved, không chuyển thành repeal toàn văn bản. |
| A12 | FRBR cho loại dễ trùng giữ hậu tố cơ quan; hash/identity khác yêu cầu review. Không tự phục hồi tài liệu đã bị bỏ sót trước đây. |
| A13 | Savepoint theo document; lỗi constraint ở giữa batch không làm mất document tốt trước/sau. |
| A14 | Tách `review_status` khỏi `materialized_at`. `amends` chưa có payload text được duyệt trả false, vẫn caveat và ở queue. Chưa có workflow nhập/apply payload amendment hoàn chỉnh. |
| A15 | Phân biệt mệnh đề hiệu lực toàn văn bản và ngoại lệ từng unit; không lấy ngoại lệ đầu tiên làm default. |
| A16 | Numeric gate dùng Decimal, giữ dấu, dấu phẩy thập phân, nhóm nghìn và biên khoảng. |
| A17 | Kiểm từng câu; trích nguyên câu nguồn có thể được chấp nhận. Paraphrase cần claim/quote đầy đủ và NLI thật trả PROMOTE; HOLD hoặc stub không đủ. Đây chưa phải nghiệm thu đủ 6 lớp citation verifier. |
| A18 | Giữ các ứng viên theo cả eid và anchor; nhiều mốc luật hoặc mốc bất định đưa về abstain/HITL, không tự chọn lex mitior. |
| A19 | Eval gate kiểm omission_recall thật; tập eval rỗng không pass. |
| A20 | Resume gắn facts, as_of, lang, checklist, judge/policy/version và fingerprint nội dung KB. Judge tùy biến không có version không được reuse. |
| A21 | Án lệ chưa hiệu lực hoặc thiếu ngày không được nâng thành binding verified. |
| A22 | Cache thêm language, model và prompt identity. |
| A23 | Mục được định danh theo Chương; giữ các dòng tiếp của Điểm. |
| A24 | Dedup giữ quyết định review cũ; PostgreSQL UNIQUE NULLS NOT DISTINCT. Migration gặp duplicate cũ sẽ dừng rõ ràng, không xóa evidence. |
| A25 | Replay amendment scope theo unit/lang/effective_date; khóa unit để serialize writer. |
| A26 | CI build PostgreSQL có vector + PostGIS, cài package editable từ lockfile và extra geo; migrate/test trên DB riêng. Lint hiện là bước bắt buộc. |
| A27 | Sửa import seed vào package tools; seed deadline yêu cầu bundle reviewed và nguồn hợp lệ. |
| A28 | Reference contract/range/finite/source gate; version bất biến; thay đổi chồng thời gian cần reviewed_change; khóa publication đồng thời; kiểm lại legacy payload lúc lookup. |
| A29 | Mẫu công bắt buộc public_reviewed/provenance và kiểm PII trước embedding. Regex PII cơ bản vẫn cần review con người, không phải bộ ẩn danh hoàn chỉnh. |
| A30 | Test chỉ dùng TEST_DATABASE_URL đã chỉ định, tên *_test/test_*; không DROP/CREATE hay fallback sang dev. CI thiếu DB thì fail. |

Bổ sung: graph traversal chỉ nhận cạnh approved và giới hạn hop; lex posterior yêu cầu cùng cơ quan và dùng ngày ban hành; form/directory từ chối số không hữu hạn và tọa độ/radius không hợp lệ. Các chỉnh lint còn lại chủ yếu sắp import, bỏ import/noqa dư và làm assertion lỗi mã hóa cụ thể hơn.

## Bằng chứng kiểm thử

| Kiểm tra | Kết quả |
|---|---|
| Cài mới bằng `uv sync --locked --extra geo` vào venv riêng | Thành công; import package và ASGI factory không cần PYTHONPATH |
| Migration từ database trắng | Tới `0004_data_integrity`, PostgreSQL 16 + vector + PostGIS |
| Core suite trên venv sạch, PostgreSQL riêng | 360 passed, 8 skipped; gồm migration từ chối duplicate legacy và giữ evidence |
| BGE embedding/retrieval + NLI model thật | 7 passed, chạy offline từ cache ở venv hiện có |
| Ruff `src tests scripts` | Pass, CI không còn bỏ qua lỗi lint |
| Lockfile offline và `git diff --check` | Pass |

Log tại [reports/fixes-2026-11-10](../reports/fixes-2026-11-10/). Core skip các extra models, Neo4j, Pillow/OCR và OpenTelemetry chưa cài trong venv sạch; BGE/NLI đã được chạy riêng. Chưa chạy OCR model thật, Neo4j/GDS live hoặc hạ tầng KMS. Có warning deprecation từ Starlette/httpx và Torch, không phải lỗi test.

Chỉ dùng database tạm trên container `traluat-fix-20261110`, localhost 55433, dữ liệu tmpfs. Không chạy test ghi vào PostgreSQL dev 5433 hay Neo4j đang có của người dùng. Container tạm được dọn khi kết thúc kiểm chứng.

## Áp dụng migration và khởi động

1. Dùng connection quản trị migration có quyền tạo extension/role và sửa schema để chạy `alembic upgrade head`. Không dùng credential này cho API/worker. Hai revision mới là `0003_runtime_security` và `0004_data_integrity`.
2. Nếu 0004 báo duplicate relation, đối soát các ID, evidence, quyết định review và `unit_version.source_relation_id` trước khi chạy lại. Migration cố ý không chọn/xóa duplicate hộ người vận hành. Không tự đánh dấu quan hệ cũ đã materialize khi chưa xác minh.
3. Tạo login runtime non-owner, không superuser/BYPASSRLS/CREATEDB/CREATEROLE/REPLICATION và không là member của role có các quyền đó. Cấp `traluat_app` cho login này. Ví dụ SQL quản trị: `CREATE ROLE traluat_runtime LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION; GRANT traluat_app TO traluat_runtime;`. Đặt mật khẩu riêng qua hệ thống secret hoặc `\password`, không lưu trong repo.
4. Provision `tenant_user.auth_subject` bằng subject từ issuer đáng tin cậy. Legacy NULL subject không được đoán từ email hoặc token role. Tenant phải active. Cấp `platform_operator` riêng cho người quản trị KB cần quyền này.
5. Cấu hình `JWT_SECRET` riêng ít nhất 32 byte; issuer/audience mặc định `traluat`/`traluat-api`. Token phải có `iss`, `aud`, `sub`, `tenant_id`, `iat`, `exp`; `0 < exp - iat <= 3600`. Runtime hiện dùng HS256, chưa có tích hợp JWKS/IdP hoàn chỉnh.
6. Chạy `uvicorn traluat.w5.asgi:app_from_env --factory` với `DATABASE_URL` của login runtime. Compose lấy URL này từ `APP_DATABASE_URL`; hostname bên trong là `postgres:5432`, phía host dev là `localhost:5433`. `.env.example` để trống các secret bắt buộc.
7. Nếu cần duyệt/ghi KB, provision `KNOWLEDGE_DATABASE_URL` riêng chỉ có quyền ghi KB cần thiết. Không cấu hình thì API approve trả 503. Chỉ identity platform được dùng đường này; thiếu text amendment vẫn giữ trạng thái chưa áp dụng.

Compose vẫn là cấu hình phát triển, chưa phải image production bất biến. Các bước trên chưa được thực hiện trên database dev/production trong đợt sửa này.

Chạy test với database test riêng đã tồn tại:

```bash
uv sync --locked --extra geo
TEST_DATABASE_URL="$ISOLATED_TEST_DATABASE_URL" REQUIRE_TEST_DATABASE=1 \
  uv run --locked --extra geo python -m pytest tests -q -ra
uv run --locked --extra geo ruff check src tests scripts
```

## Phần còn mở trước phát hành

- `core/legal_rule_base.py` vẫn provisional, chưa version đúng theo `as_of` và chưa có production gate hoàn chỉnh. Không coi kết quả conflict mặc định là kết luận pháp lý được nghiệm thu.
- Omission hiện là keyword/playbook, chưa xử lý đầy đủ phủ định hoặc luật bắt buộc theo ngày. Cần semantic/as-of implementation và gold được chuyên gia duyệt.
- ASGI mặc định vẫn Echo; chưa nối toàn bộ indexed hybrid retrieval, reranker, NLI và local model serving vào runtime. Paraphrase thiếu claim/quote hợp lệ sẽ abstain nhiều hơn; cần adapter sinh output theo hợp đồng mới.
- Sửa đổi dạng `amends` cần payload text được duyệt và workflow apply/reindex hoàn chỉnh. Fan-out alert runtime và projection Neo4j cần nối/kiểm tích hợp; hook ngoài PostgreSQL chưa phải outbox có bảo đảm exactly-once khi process lỗi.
- Fingerprint checkpoint đọc nội dung canonical tables để tránh reuse sai; cần revision service để giảm chi phí khi KB lớn.
- Dataset mới phải có contract; `lich_nop_thue` và `ma_nganh` chưa có contract riêng. Fixtures/seed minh họa không xác nhận mức thuế, thời hạn hoặc nội dung luật thật.
- Chưa nghiệm thu identity issuer/rotation, model supply-chain, KMS thật, residency vật lý, retention/backup, tải lớn hoặc pentest. Test này không chứng nhận tuân thủ pháp lý.
- Chưa phục hồi dữ liệu lịch sử bị ghi đè, FRBR đã va chạm hoặc quan hệ cũ bị áp sai. Cần đối soát với nguồn gốc đã duyệt trước khi dùng lại kho hiện hữu.

Ưu tiên tiếp theo: production gate cho rule base và serving, semantic/as-of omission, payload amendment cùng outbox/reindex, rồi acceptance trên gold/corpus thật và hạ tầng triển khai.
