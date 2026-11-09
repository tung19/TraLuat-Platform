# TraLuat — Security posture & threat model

> Gom từ **deep security audit** (3 nhánh: appsec/infra · untrusted-input/parser · supply-chain) + chaos adversarial. Repo đang design-stage → phần lớn là **requirement để spec/impl**, không phải lỗ code.
> Nguyên tắc: **moat-security (tenancy/residency/egress/PII) đã mạnh — tài liệu này vá PERIMETER (appsec/parser/supply-chain).**
> Đọc kèm: `w5-backend.md` (tenancy/egress), `compliance-vn.md` (pháp lý), `spec-audit-fixes.md` (Round 1-3).

---

## 0. Threat model (STRIDE, rút gọn)
| Mối đe doạ | Bề mặt chính | Trạng thái |
|---|---|---|
| **Spoofing** | auth token (HS256 mint-able), tenant_id claim | 🟠 (D §F) |
| **Tampering** | poisoned weights · poisoned lakehouse reference-data · poisoned KB doc | 🔴 (B, E) · ✅ (materialize gate) |
| **Repudiation** | audit log | ✅ append-only + write-ahead |
| **Info disclosure** | cross-tenant · egress ra ngoài VN · log nội dung nhạy cảm · backup | ✅ tenancy/egress · 🔴 (D) |
| **DoS** | zip-bomb/ReDoS/parser · cost-bomb LLM/GPU noisy-neighbor | 🔴 (A) · 🟠 (§F) |
| **Elevation** | tenant-owner = platform-operator → cross-tenant admin | 🔴 (C) |
| **RCE** | pickle model weights · native parser/OCR/VLM | 🔴 (A, B) |

---

## 1. Năm QUYẾT ĐỊNH THIẾT KẾ (phải spec — không phải control chuẩn)

### 🔴 A. Untrusted-intake chokepoint (1 cổng cho MỌI file untrusted)
Mở rộng **PII gate** thành cổng cứng, **trước mọi parse nặng**, áp cho cả 3 luồng (meta.json · template lakehouse · tenant upload `POST /v1/documents`):
```
magic-byte type-validate (reject mismatch) → AV scan (ClamAV) → size + decompression-ratio + page-count cap
  → extract an toàn (no zip-slip/symlink, dir rỗng/doc) → SANDBOX parse (gVisor/seccomp, non-root, RO-fs, NO creds, NO net, mem/CPU/wall-clock cap)
  → defusedxml MỌI XML (lxml/python-docx/cobalt: resolve_entities=False, no_network, forbid DTD, huge_tree=False)
  → citation-grammar bằng re2/regex LINEAR (hoặc timeout+length-cap) — chống ReDoS
  → PII backstop (đã có) → fail BẤT KỲ bước nào = QUARANTINE (không retry vô hạn) + HITL
```
*Vì sao design, không ops:* ta ingest PDF/ảnh untrusted ở scale (4TB + upload khách) → native-lib CVE = RCE trên GPU plane có cred DB/MinIO. Sandbox + defusedxml + re2 là **kiến trúc**, không phải cấu hình.

### 🔴 B. Model supply-chain policy (pickle-RCE + poisoned-weights CÙNG 1 control)
- **safetensors-ONLY**; cấm `torch.load` `.bin/.pt` + cấm pickle cache (LeSICiN/LegalGraphRAG → parquet/JSON/safetensors).
- `weights_only=True` nơi bất khả kháng · **`trust_remote_code=False`** (chặn custom modeling — Vintern/Qwen-VL).
- **Pin HF `revision=<commit-sha>`** (không tag/branch) + **SHA-256 mỗi file weight** verify trước load.
- **Mirror weight đã duyệt về MinIO VN**; prod load từ mirror, **không pull HF live**.
- **L13 benchmark = tripwire** mỗi lần bump model (swap xấu → điểm tụt).
- Load model chỉ trong **sandboxed GPU worker**, không trong API process.

### 🔴 C. Platform-vs-tenant authz (chống cross-tenant admin escalation)
- `tenant_user.role ∈ {owner, lawyer, reviewer, viewer}` = **chỉ trong tenant**. Thêm **`platform_operator`** (identity riêng, ngoài tenant_user) cho `POST /v1/admin/tenants` + mọi op cross-tenant.
- `/v1/admin/tenants/{id}/*`: **ép `{id} == caller.tenant_id`** trừ platform_operator (tránh tenant A rotate key tenant B = **crypto-shred DoS**).
- **Dual-control + audit** cho key-rotation & retention-flip.
- Acceptance: tenant A owner → **403** trên route admin của tenant B.

### 🔴 D. Logging / retention reconcile (sửa MÂU THUẪN nội bộ spec)
- **Gateway log = METADATA-ONLY** (hash, token count, data_class, destination) — **KHÔNG body prompt/response**. (Hiện "log I/O audit" phá zero-retention + đá audit_log "no sensitive content".)
- Content-capture debug (nếu cần) = opt-in, DEK-encrypt, in-VN, short-TTL, **tắt cứng cho zero-retention tenant**.
- **Backup + WAL archive MÃ HOÁ** (key riêng, in-VN).
- **PITR vs right-to-erasure/zero-retention:** cơ chế xoá = **crypto-shred (huỷ DEK ở KMS)** → ciphertext trong backup thành bất-khả-giải; checkpointer/standard content phải DEK-encrypt để backup thừa hưởng.
- Acceptance: telemetry-no-content (mở rộng zero-retention test).

### 🔴/🟠 E. Lakehouse integrity (rẻ trước, nặng sau)
- **Làm ngay (rẻ, giá trị cao):** validate mọi row theo `schemas/<dataset>.schema.json` + **range/sanity** số pháp lý (tax/wage/penalty) · **cross-check `source_eid` vs W2** (claim derive từ eid không tồn tại → quarantine) · **anomaly-diff** version bump (delta lớn ở tax/authority_rank → HITL).
- **Defer (nặng, infra):** mTLS + **ký dataset version** (producer ký, adapter verify) — chống insider/compromise lakehouse. *(data team nội bộ tin cậy → defense-in-depth sau.)*

---

## 2. Control CHUẨN cần ENUMERATE (standard ops — ghi để không quên, không phải hố thiết kế)
| Control | Yêu cầu |
|---|---|
| **TLS/mTLS nội cụm** | mọi hop app↔vLLM/PG/MinIO/broker/checkpointer; `endpoint_url` TLS-only; pin cert (sensitive text không cleartext trên wire) |
| **Token lifecycle** | **RS256/ES256 + verify JWKS** (app không mint được); short TTL + refresh + revocation (`jti` denylist) trên user-remove/role-change/tenant-suspend; **`verify_aud`+`verify_iss`**; **bỏ `ENABLE_AUTHENTICATION` kill-switch** khỏi prod (fail-closed); coi `tenant_id` claim là untrusted trừ khi app_metadata chỉ-platform-ghi |
| **Rate-limit / quota / DoS** | per-tenant+per-user rate limit · max concurrent async analysis · token/cost budget → 429 (no-retry) · **GPU fair-share per tenant** (chống noisy-neighbor trên local pool residency) |
| **SCA / SBOM / deps** | lockfile + `--require-hashes` · **pip-audit/Trivy/Dependabot fail-closed CI** (cạnh L13) · SBOM CycloneDX (gồm weights + dataset version) · allowlist deps repo port |
| **Migrate security-pass** | thêm vào CONTRIBUTING port-checklist: pin upstream commit + diff + grep `eval/exec/subprocess/os.system/dynamic-import/network/cred` + SCA trước merge |
| **Dev hygiene** | `python -I` cho tool chạy trên `refs/`/weights/data untrusted; extract archive vào dir rỗng; không `cd` vào dir untrusted để chạy interpreter |
| **KMS** | scope decrypt grant hẹp nhất (per-tenant grant/short-lived) · HSM-back master key · runbook key-compromise + master-rotation *(giới hạn thật: app vẫn decrypt-được-mọi-tenant để serve — document blast-radius, không giả vờ fix hết)* |
| **Container** | non-root · read-only rootfs · secret qua Vault/CSI mount (không env) · image pin-by-digest + Trivy scan + cosign verify |
| **Code-level (verify khi code)** | `set_config('app.current_tenant', :val, true)` bound param (không f-string) — chống SQLi/search_path · scrub PII khỏi `meta_jsonb`/exception log · CORS allowlist |

---

## 3. Đã SOLID (đừng regress)
- **Egress provenance-based fail-closed + write-ahead audit** · **FORCE RLS triad + non-owner role + leak test** · checkpointer prefix · **worker no-egress (SSRF thấp)** · append-only audit + **crypto-shred** + 72h breach hook · XSS discipline (textContent, URL scheme-check) · **adapter anti-corruption** (blast-radius) · **PII quarantine gate 3 luồng** · derived-index **rebuildable từ SoR** · secrets→KMS/Vault · network segmentation (chỉ Gateway egress) · materialize gate (chặn fake-repeal poisoning).

## 4. IOU / defer (có cổng)
mTLS+ký lakehouse (E-nặng) · HSM master key · model mirror infra · second local model (cross-provider) · pentest trước GA.

## 5. Checklist pentest trước GA
- [ ] Cross-tenant: A truy B (query/cache/vector/checkpointer/admin-route/key-rotate) → chặn.
- [ ] Upload độc: zip-bomb · PDF-exploit · XXE DOCX/AKN · polyglot · ReDoS input → quarantine, không RCE/DoS.
- [ ] Model: load `.bin` pickle → bị từ chối; swap weight → L13 tụt + hash fail.
- [ ] Lakehouse: poisoned tax/authority_rank → range-check/source_eid chặn.
- [ ] Egress: client text qua misclassify/local-down → KHÔNG ra Claude (deny/queue).
- [ ] Auth: token hết hạn/revoke/sai aud → 401; kill-switch không tồn tại prod.
- [ ] Zero-retention: không còn vết ở log/trace/backup/temp sau task.

---

> Một câu: **đúng chỗ quan trọng nhất (data/tenancy/residency/PII) đã chắc; tài liệu này đóng perimeter — 5 quyết định (A intake-sandbox · B safetensors/pin · C platform-authz · D log/backup reconcile · E lakehouse-integrity) + checklist control chuẩn. Đúng-đắn & an-toàn đứng trên tốc độ & tiện lợi.**
