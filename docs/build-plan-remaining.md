# TraLuat — Build plan: phần còn lại (partial + chưa làm)

> 7 work-package, dependency-ordered. Mỗi WP: mục tiêu · task · file · dep · test · 🔌 cần-ngoài.
> Nguyên tắc giữ: dựng trên nền sẵn (reference-data-plane · gateway · ground · workflows · graph), port + stub ready-to-plug, test trước commit. "được chậm, không được sai".

---

## WP1 — Hoàn thiện data-plane: calculators (FR-35) + directory/geo (FR-39/40)
**Mục tiêu:** 14 tiện ích tính + danh bạ LS/cơ quan, hiệu-lực-aware, RULE tier (không LLM).
- **T1.1 Calculator registry** (`w1/calculators.py`): mỗi calc = hàm RULE trên `lookup_reference` (thuế/lương vùng/mức phạt/lệ phí/mã HS/ngành…) + số học; trả kết quả **kèm `source_eid`** (calculator-có-nguồn-luật). `classify_tier`→RULE route tới đây.
- **T1.2 PostGIS geo** (FR-39): model `Directory(kind, name, address, geom POINT, phone, …)` + `nearby(lat,lon,radius)` KNN (`<->`). FR-40 danh bạ cơ quan (bảng thường).
- **T1.3 Adapter + PII gate**: `upsert_reference`/`DocumentSource` cho dataset danh bạ (danh-bạ có liên hệ → `pii_check=True`).
- **Test:** calc tax/penalty@as_of ra đúng số + source · nearby trả đúng bán kính · PII quarantine danh bạ.
- **🔌 Cần-ngoài:** image Postgres có **cả pgvector + PostGIS** (đổi `pgvector/pgvector:pg16` → image gộp, hoặc cài postgis vào container) · **data thật** từ đội data (thuế suất/lương/mức phạt/danh bạ).

## WP2 — Drafting & Templates: soạn đơn (FR-34) · biểu mẫu (FR-38) · Draft/Petition service (L9)
**Mục tiêu:** sinh đơn từ/biểu mẫu từ template, grounded, có nhãn AI.
- **T2.1 Template store (TES)** (`w?/templates.py`): model `Template(kind, title, body, slots jsonb, embedding)` + retrieve (pgvector) theo loại việc. "Học từ template" = lưu exemplar đã duyệt (nối L14).
- **T2.2 DraftService / PetitionDraftService** (`w6/workflows`): retrieve template phù hợp → `gateway.generate` điền slot **chỉ-từ-template + điều luật truy xuất** → `ground` (cite-or-abstain) → nhãn AI. Egress: dữ liệu khách → local.
- **T2.3 Forms (FR-38)**: định nghĩa biểu mẫu có cấu trúc (slot + validation) + điền.
- **Test:** retrieve đúng template theo loại · draft điền slot + có trích dẫn · abstain khi thiếu căn cứ · form validate.
- **🔌 Cần-ngoài:** API key (draft chất lượng cần Claude/local-LLM; stub Echo test luồng) · **template thật** (đội data/chuyên gia).

## WP3 — Tam ngữ VN-EN-ZH (cross-lingual)
**Mục tiêu:** câu hỏi EN/ZH → đúng luật VN + trích dẫn cùng eId; trả lời render EN/ZH.
- **T3.1 Cross-lingual retrieval**: bge-m3 **đã đa ngữ** → EN/ZH query vào cùng vector space, retrieve VN. Thêm **route embedding theo ngôn ngữ** + test cell "EN query → đúng điều VN".
- **T3.2 Termbank** (dataset reference): cặp thuật ngữ VN-EN-ZH **neo điều–khoản** (alignment offline theo lô) → pgvector.
- **T3.3 Presentation cache** (§6.2): tách **legal-conclusion cache** (language-neutral, vẫn keyed tenant/as_of/version) vs **translation cache** (+language) → suy luận 1 lần, render lại EN/ZH qua gateway.
- **Test:** EN query retrieve đúng eId VN · termbank lookup · conclusion-cache tái dùng, chỉ render đổi ngôn ngữ.
- **🔌 Cần-ngoài:** termbank data · API key (render EN/ZH). ZH eval defer cùng ZH corpus.

## WP4 — Experience/UI: review-UI · song-ngữ · điều hướng trích dẫn
**Mục tiêu:** luật sư *tiêu thụ* "việc đã xong" — trang phục vụ (single-file như `/graph`, hoặc SPA sau).
- **T4.1 Review UI** (`/review`): upload/paste hợp đồng → `ReviewService` → **highlight điều khoản bỏ sót** (màu) + findings.
- **T4.2 Citation navigation** (`/doc/{frbr}?as_of=`): click điều → **văn bản tại ngày T** (`document_as_of`) + effect_status badge.
- **T4.3 Song-ngữ view**: đối chiếu VN | EN side-by-side (dùng WP3).
- **T4.4 HITL console** (`/review-queue`): duyệt `pending_relations` (approve/reject → materialize).
- **Test:** `/review` 200 + render findings · `/doc` trả văn bản@T · `/review-queue` list+approve.
- **🔌 Cần-ngoài (tuỳ chọn):** nâng lên React/Next nếu cần UX sâu (hiện single-file HTML/JS đủ demo).

## WP5 — Observability đầy đủ (OTel) + Security (HSM)
- **T5.1 OTel tracing** (`w5/tracing.py`): OpenTelemetry SDK + span trên API/service/gateway + OTLP exporter (env) + propagate `trace_id`. Compose: otel-collector (profile obs).
- **T5.2 HSM provider**: `KMSProvider` **đã là port** → thêm `CloudKMS`/`HSMProvider` impl (AWS KMS/Vault Transit). `SoftwareKMS` giữ cho dev.
- **Test:** span tạo ra (in-memory exporter) · HSM provider wrap/unwrap (mock) roundtrip.
- **🔌 Cần-ngoài:** OTel collector/Jaeger chạy · HSM/KMS thật (Vault/AWS).

## WP6 — OCR full-page (detector + recognizer)
**Mục tiêu:** ảnh trang luật đầy đủ → text (hiện mới recognizer dòng).
- **T6.1 Text detector** (`w1/ocr_detect.py`): CRAFT/PaddleOCR detection → cắt dòng → `VietOCREngine.extract_lines` (đã có) → ghép. Hoặc PaddleOCR end-to-end (det+rec VN).
- **T6.2 Wire**: `ingest_source(ocr=FullPageOCR)` xử lý ảnh trang.
- **Test:** render ảnh 2–3 dòng → detect+OCR ra đủ dòng (so với VietOCR dòng-đơn hiện tại).
- **🔌 Cần-ngoài:** dep `paddleocr`/CRAFT + model download (safetensors) · ảnh mẫu thật.

## WP7 — FR-09 Alert luật mới (gửi thông báo) ✅ XONG
**Mục tiêu:** phát hiện (đã có) → **gửi** cho người theo dõi.
- **T7.1 Subscription model** ✅: `alert_subscription(tenant_id, frbr_uri, channel, target)` + `alert(tenant_id, frbr_uri, change, delivered)` — bảng khách FORCE RLS (migration `0012_alerts`).
- **T7.2 Alert pipeline** ✅: `w5/alerts.py` — `Deliverer` port (Recording/Webhook) + `fan_out` + `enable_alert_sync()` đăng ký **post-materialize hook** (như Neo4j sync); repeals/replaces/amends đã duyệt → `Alert(tenant, frbr, change)` + deliver.
- **API** ✅: `POST /alerts/subscribe` (lawyer/reviewer/owner) + `GET /alerts` (hộp thư, RLS cô lập).
- **Test** ✅: `test_pg_alerts.py` (subscribe→repeal→alert+deliver · không subscriber→im · cites không sinh alert) · `test_pg_w5_api.py` (subscribe+list roundtrip · viewer 403).
- **🔌 Cần-ngoài:** SMTP (email thật) · endpoint webhook khách (`WebhookDeliverer` đã có skeleton `post_fn`).

---

## Thứ tự đề xuất (value × codeability)
```
WP1 calculators (code ngay, cần image PostGIS cho geo + data)  →  WP2 drafting/templates (core product)
  →  WP4 UI (làm usable)  →  WP3 tam ngữ  →  WP7 alert  →  WP5 OTel/HSM  →  WP6 OCR full-page
```
**Code được NGAY (không chờ ngoài):** WP1 calculator registry (stub data) · WP2 Draft service luồng (Echo) · WP4 UI pages · WP3 cross-lingual retrieval test · WP5 OTel · WP7 subscription+pipeline (webhook stub).
**Cần stack/data/dep ngoài:** PostGIS image · template/termbank/directory data · paddleocr model · SMTP · HSM · API key (chất lượng draft/render).

Mỗi WP commit riêng + test; cập nhật `status-audit.md` sau mỗi WP.
