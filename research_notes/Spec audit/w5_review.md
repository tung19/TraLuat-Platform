# W5 Backend — Adversarial Spec Review

> Target: `docs/specs/w5-backend.md` (FastAPI + multi-tenant + residency, lifted from PAKTON).
> Method: read-only. Cross-read: `docs/specs/deployment-infrastructure.md §3–4`, `docs/compliance-vn.md`, `docs/specs/w3-ai-retrieval-grounding.md`, PAKTON `PAKTON Framework/API/*` + `Archivist/.../agent.py`.
> Stance: skeptical — find fail-OPEN paths, tenant leaks, and foreign-egress of client data. Date 2026-11-05.

**Verdict:** The tenancy model is coherent on paper but leans on two enforcement assumptions that are false as written (RLS fail-closed; one shared RLS session var across stores), and it isolates only **three** stores while the lifted PAKTON architecture has **five** data-bearing stores. The single most compliance-critical invariant — client data never reaches Claude API — has **no classifier specified, no audit record, and no acceptance test**. Several items are Critical.

---

## CRITICAL

### C1 — Egress classifier for Claude API is undefined; the one guard that exists does NOT make the egress decision (★ compliance, NĐ 356 Điều 20)
**Where:** w5 §2.5 + §3.1; deployment §3 routing table; w3 §3 (`LLMGateway.generate`).
**Claim:** deployment §3 says "Gateway phải **phân loại prompt trước khi gọi**" and routes "Chỉ KB luật công" → Claude API (outside VN), "Dữ liệu khách nhạy cảm" → vLLM. w5 §2.5 says the gateway "từ chối khi context_chunks lẫn chunk của tenant khác (chỉ cho phép cùng `tenant:<id>` hoặc `kb`)".

**The hole:** these are two different checks, and the spec conflates them.
- The w5 §2.5 guard is a **cross-tenant** check (is this chunk mine or `kb`?). A contract Review legitimately carries the tenant's **own** chunks (namespace `tenant:<id>`) + KB chunks — this guard **passes**, yet the prompt is full of client contract text and must NOT go to Claude. The guard does not gate egress at all.
- deployment §3 keys routing on "data classification" but **no mechanism is specified** that classifies a prompt as KB-only. w3 §3.3 instead implies **per-tenant** routing (`endpoint_url`→vLLM "cho tenant nhạy cảm"). So three docs disagree: per-prompt (deployment §3) vs per-tenant (w3 §3.3) vs cross-tenant-only (w5 §2.5).

**Failure scenario:** Tenant not flagged "sensitive" runs `POST /v1/analysis/review` on a contract. If routing is per-tenant (w3 §3.3), the whole prompt (contract text) → Claude API outside VN → cross-border transfer of client personal data with no TIA → NĐ 356 Điều 20 / Luật 91/2025 Điều 20(6) violation (SaaS customer data is **not** exempt — compliance-vn.md §1). Penalty tier: up to 3 tỷ / 5% revenue (compliance-vn.md §1).

**Second hole — the query/document text is never classified at all.** Both §2.5 and the routing table reason about **retrieved chunks**. But the user's raw query in `/v1/query/sse` and the uploaded document text are not chunks. A user who pastes contract clauses into an "assistant" question that the system treats as KB-lookup → classified KB-only → egress to Claude. Few-shot exemplars and system prompts assembled by the gateway are likewise unclassified.

**Third hole — prompt-cache + logs egress.** w3 §3.3 requires "prompt-cache ngữ cảnh grounding lớn" and "log I/O cho audit". If Claude prompt-caching is used on the KB path, any client text that slipped into context is **retained at Anthropic abroad** (direct conflict with zero-retention tenants). If gateway I/O logs ship to a non-VN observability vendor, prompts egress there too. SSE error path streams `str(e)` (PAKTON `api.py:396`) and PAKTON logs full query text (`api.py:303`, `tasks.py:52,114`) — error/debug logs can carry client text.

**Fix:**
1. State a **fail-closed egress rule, not a classifier guess**: a request may route to Claude only if *every* context element is provably `kb`-sourced AND the user query/document is tagged `public_kb_only` at ingress; default = local vLLM. Derive "contains client data" from provenance (any `tenant:<id>` chunk, any uploaded-doc token, any transcript) — never from a text classifier that can false-negative.
2. Disable Anthropic prompt-cache and external prompt logging on anything but the pure-KB path; keep gateway I/O logs in-VN.
3. **Audit every routing decision** (see C5) and add an acceptance test (see C8).

### C2 — RLS is assumed fail-closed but is fail-OPEN as lifted (owner role + no FORCE RLS)
**Where:** w5 §2.3(1), §6 enforcement table ("query không set var → 0 dòng"), build task 3.
**Reality:** PAKTON connects with a single `DATABASE_URL` (`database/config.py:22-31`) and runs migrations as that role (`alembic`, `migrate.sh`). Postgres RLS is **silently bypassed** for (a) the table **owner** and (b) any role with `BYPASSRLS`. If the app role owns the tables (the default in PAKTON's single-URL setup), every `USING (tenant_id = current_setting('app.current_tenant'))` policy is ignored → **all tenants visible**, the exact opposite of the table's "fail-closed" claim. The spec never mentions `FORCE ROW LEVEL SECURITY` or a dedicated non-owner, non-BYPASSRLS application role.

**Failure scenario:** Migration creates tables as app role; RLS policies attached; everything "works" in the 2-tenant test *only because the app also sets the var* — but a single query path that forgets `SET LOCAL` (or any admin/debug path) returns **all tenants**, and the owner bypass means even the policy wouldn't have saved it.

**Fix:** dedicated app role that owns nothing / is not BYPASSRLS; `ALTER TABLE … FORCE ROW LEVEL SECURITY` on every client table; deny-by-default policy; make `current_setting('app.current_tenant', true)` → NULL → `tenant_id = NULL` (0 rows) the *only* unset behavior and test it. Add acceptance test that queries with no var set return 0 rows **as the app role**.

### C3 — Checkpointer RLS assumption is physically impossible: it uses a separate connection pool
**Where:** w5 §2.3(2) ("AsyncPostgresSaver chạy trong cùng RLS session var"), §1 three-store table, §10 note 2.
**Reality:** `AsyncPostgresSaver.from_conn_string(DATABASE_URL)` (PAKTON `Archivist/.../agent.py:122-129`) opens **its own psycopg connection/pool**, independent of SQLAlchemy's engine and of `get_tenant_db_session()`. There is no shared transaction, so `SET LOCAL app.current_tenant` issued on the SQLAlchemy session **does not propagate** to the checkpointer connection. The checkpoint tables are therefore **not** RLS-filtered as the spec asserts. langgraph's saver does not emit a per-op `SET LOCAL` on its own.

**Failure scenario:** Protection of conversation history collapses to the `thread_id` namespace `tenant:<id>:<thread>` only. That is security-by-UUID-guess unless *every* checkpointer read validates the `tenant:<id>` prefix against the authenticated tenant — which the spec does not require. A resume/timeline read by thread_id that trusts the id leaks tenant A's conversation state to tenant B.

**Fix:** either (a) run the checkpointer through a connection wrapper that issues `SET LOCAL app.current_tenant` + FORCE RLS on checkpoint tables, or (b) make the enforcement authoritative at the app layer: validate `thread_id` begins with the authenticated `tenant:<id>` on every checkpointer access and store `tenant_id` as a first-class checkpoint column with its own RLS/app-filter. Do not claim the SQLAlchemy session var covers it.

### C4 — Celery result backend (Redis) + broker (RabbitMQ) are unisolated, unencrypted stores the spec never counts; carry raw client content
**Where:** w5 §1 (lifts PAKTON Celery wiring), §6 flow, enforcement table (no row for result backend/broker); acceptance test 5 (zero-retention) checks only vector/checkpointer/temp.
**Reality:** `index_document` passes **`file_content: bytes`** (the raw contract) as a Celery task arg (`tasks.py:187`, `api.py:460-466`) → serialized through RabbitMQ (broker) and the result stored in Redis (`docker-compose.yml`: `redis://redis:6379/0`, no auth, no TLS). `task_status` returns `task_result.result` for any task_id (next finding). None of this is tenant-partitioned, RLS-covered, or DEK-encrypted. These are a **4th and 5th data store** absent from the "three kho" model (§1).

**Failure scenarios:**
- **Zero-retention breach:** a `retention_mode='zero'` analysis's input bytes and full result sit in RabbitMQ + Redis with default TTLs, untouched by the "no-persist" toggle. Acceptance test 5 passes (vector/checkpointer/temp clean) while the content lives on in Redis → compliance false-negative.
- **Cross-tenant:** Redis result + broker messages have no tenant key; anyone with Redis/broker access (or the task_id) reads tenant A's analysis.
- bytes-over-broker also forces the pickle/JSON serializer question — pickle results in broker-driven RCE exposure.

**Fix:** never put client bytes on the broker — upload to encrypted object store (MinIO, DEK-encrypted) and pass an opaque handle; set Redis result TTL≈0 and encrypt results with tenant DEK or store results in RLS'd Postgres; require Redis/RabbitMQ auth+TLS; add zero-retention assertions over Redis+broker to acceptance test 5.

### C5 — No audit record of the egress/routing decision; audit schema cannot prove client data stayed in VN
**Where:** w5 §3.3 audit schema `audit_log(... action, resource, trace_id ...)`; §4 cost accounting logs `(tenant_id, model, prompt_tokens, completion_tokens, cost_usd)`.
**Gap:** the most compliance-critical event — "prompt classified X → routed to endpoint Y (Claude/vLLM)" — is recorded **nowhere**. Cost accounting logs the model but not the data classification or the residency decision. compliance-vn.md §1 (NĐ 356 Điều 29) requires ≥5-year records; a cross-border-transfer audit trail is exactly what a BCA inspection or a breach investigation needs, and it does not exist. "Who audits this boundary?" — per the spec, no one.

**Fix:** add `llm_egress_log(tenant_id, trace_id, endpoint, region, data_class, chunk_provenance_hash, consent/TIA_ref, ts)` written on every gateway call, append-only, 5-year. This is also the evidence artifact for the high-risk-AI logging duty (compliance-vn.md §2).

### C6 — `task_status` / result retrieval is a cross-tenant IDOR; lifted unchanged
**Where:** w5 §5 `GET /v1/tasks/{task_id}` ("lift api.py:558"); enforcement table has no row for task results.
**Reality:** PAKTON `get_task_status` (`api.py:558-605`) does `AsyncResult(task_id)` and returns `task_result.result` with **no ownership/tenant check** — authentication only. The result is the full analysis of a contract. The spec lifts it and never adds a tenant guard; RLS does not apply (Redis, not Postgres). Task ids are emitted to clients (202 responses), logs, and SSE — guessable/leakable.

**Failure scenario:** Tenant B obtains/guesses tenant A's `task_id` (from a shared link, a log, a proxy) → `GET /v1/tasks/{id}` → reads A's contract analysis. Acceptance test 2 tests documents/conversations/SSE isolation but **not** task-result isolation.

**Fix:** persist a `task → tenant_id, owner` binding (RLS'd Postgres) at enqueue; `/v1/tasks/{id}` must resolve via that binding under the tenant session and 403/404 on mismatch; never serve `AsyncResult.result` directly. Add to acceptance test 2.

---

## HIGH

### H1 — `ENABLE_AUTHENTICATION` kill-switch is retained; with auth off there is no tenant → undefined fail direction
**Where:** w5 §5 ("toggle `ENABLE_AUTHENTICATION` — giữ auth.py:92-101,164-198"), steal-list row.
**Reality:** PAKTON `get_current_user` returns `None` when auth is disabled (`auth.py:194-196`). The entire tenancy model derives `tenant_id` from the JWT (`app_metadata.tenant_id`). With auth off there is no JWT and no tenant. The spec does not state whether `get_tenant_context()` then 403s (closed) or falls back to a default tenant (open). A prod misconfiguration (`ENABLE_AUTHENTICATION=false`) silently removes all tenant isolation.
**Fix:** forbid the toggle in staging/prod (config assert: if not dev → must be true); `get_tenant_context` must hard-fail when user/tenant unresolved regardless of toggle.

### H2 — Supabase JWT: single shared HS256 secret for all tenants; `verify_aud=False`; residency of auth PII
**Where:** w5 §5 (keeps Supabase auth), §2.1 (`tenant_id` from `app_metadata.tenant_id`); PAKTON `auth.py:92-101`, `config.py:31`.
**Issues:**
- One `SUPABASE_JWT_SECRET` (symmetric) signs every tenant's tokens. Secret leak = forge a token for **any** tenant_id → total cross-tenant compromise. No per-tenant signing / asymmetric verification.
- `verify_aud: False` (`auth.py:99`) — audience unchecked; a token minted for another Supabase audience is accepted.
- Tenancy rests entirely on the `app_metadata.tenant_id` claim being server-set. The spec must assert it comes from `app_metadata` (server-controlled), never `user_metadata` (user-editable in Supabase) — it says `app_metadata` (good) but doesn't call out the trap, and doesn't validate the claim against the `tenant_user` table.
- Supabase is a hosted service (outside VN). User PII (emails, auth records) living at Supabase is itself cross-border personal-data processing — contradicts deployment §4 "mọi kho … đặt tại VN". Not addressed.
**Fix:** validate `tenant_id` claim by joining `tenant_user` on every request (don't trust the claim as authorization); enable `verify_aud`; move to asymmetric (RS256/JWKS) or self-hosted VN auth; assess Supabase residency explicitly or self-host GoTrue in VN.

### H3 — Intra-tenant isolation is absent: tenancy is firm-level, but legal work needs matter/user walls
**Where:** w5 §2 (isolation keyed on `tenant_id` only); RBAC roles are tenant-wide.
**Reality:** RLS filters by `tenant_id`, so **any** user in a firm can retrieve any other user's documents/conversations/analyses. PAKTON's own per-user checks are inconsistent (delete has `user_email` check at `api.py:848`; `get_by_thread_id` at `conversation_repository.py:65-76` has none; `task_status` has none) — the spec discards all of them in favor of tenant-only RLS. For a law firm this breaks ethical walls / conflict-of-interest segregation between matters and lawyers.
**Fix:** decide the confidentiality unit (matter/user), add `owner_id`/`matter_id` scoping + policies, or document explicitly that intra-firm sharing is intended and get that into the product/compliance contract.

### H4 — Zero-retention conflicts with the high-risk-AI record-keeping duty for Judgment Analysis
**Where:** w5 §3.2 (`retention_mode='zero'`), compliance-vn.md §2 (litigation AI = high risk, QĐ 33/2026: logging + human oversight + records).
**Tension:** compliance-vn.md §2 flags Judgment Analysis as likely **high-risk AI**, which mandates operational logging/record-keeping to reconstruct how an output was produced. Zero-retention deletes exactly that substrate (content, checkpoints). The spec presents zero-retention as a clean per-tenant toggle without reconciling it against the high-risk logging obligation. A zero-retention tenant running Judgment Analysis may be legally un-serviceable, or the mandated logs may themselves become retained regulated data.
**Fix:** gate `retention_mode='zero'` off for high-risk analysis types, or define a minimal compliant decision-record (inputs hashed, citations, verifier gates, routing) that satisfies the logging duty without storing raw content — and prove it doesn't itself breach zero-retention.

### H5 — DELETE conversation / crypto-shred does not erase the content stores; right-to-erasure incomplete
**Where:** w5 §5 `DELETE /v1/conversations/{thread_id}` ("lift api.py:810"), §2.4 crypto-shred, §3.2 zero-retention.
**Reality:** PAKTON's delete "only deletes the conversation record, **not the actual messages in the checkpoint database**" (docstring `api.py:820-821`). Message content survives in the checkpointer. Crypto-shred (§2.4) deletes the tenant DEK — but the audit_log, Redis results (C4), broker messages, and (if used) Pinecone are not DEK-encrypted, so content/PII survives the shred. NĐ 356 right-to-erasure (compliance-vn.md §1) is only partially met.
**Fix:** delete must cascade to checkpoint rows, vector namespace, object store, and Redis result; enumerate every store touched by crypto-shred and confirm each is either DEK-encrypted or purged; keep audit PII-free (M2).

### H6 — Pinecone option contradicts data residency
**Where:** w5 §2.3(3) and steal-list offer "Pinecone namespace = `tenant:<id>`" as an isolation option for **client** embeddings; deployment §4/§6 says prod uses pgvector, everything in VN, "bỏ Chroma".
**Reality:** Pinecone is a non-VN managed service. Client-document embeddings (invertible to source text) in Pinecone = client data stored abroad → residency breach. The w5 spec presents Pinecone as a valid tenant-isolation backend without flagging it.
**Fix:** restrict client-data vectors to in-VN pgvector/self-hosted; if Pinecone is ever allowed, only for public KB, and say so.

---

## MEDIUM

### M1 — Append-only audit log: integrity mechanism unspecified; tamperable by app/tenant
**Where:** w5 §3.3 ("append-only"), compliance Điều 29 (≥5y).
The app connects with full DML rights; nothing prevents UPDATE/DELETE of `audit_log`. "Append-only" is asserted, not enforced. **Fix:** write-only DB role for audit, triggers blocking UPDATE/DELETE, hash-chain or external WORM; verify under the same FORCE-RLS regime as C2.

### M2 — Audit log may contain regulated PII; "no sensitive content" is unenforced
**Where:** w5 §3.3 (`actor`, `meta_jsonb`, "không chứa nội dung nhạy cảm").
`actor` is an email (PII); `meta_jsonb` easily captures query text / filenames (can contain client data). Then the audit log is itself regulated personal data kept ≥5y, surviving crypto-shred (not DEK-encrypted) → undermines H5 erasure. **Fix:** schema-level allowlist for `meta_jsonb`, PII-scrub/pseudonymize `actor`, or encrypt audit PII columns with a separable key.

### M3 — `SET LOCAL` + pooled connections: tenant bleed risk across requests
**Where:** w5 §2.3(1) wrapping `get_db_session`; PAKTON pool (`config.py:25-31`, pool_size 10 + overflow 20), `get_db()` yields a session not wrapped in one transaction.
`SET LOCAL` is transaction-scoped; if any code path runs outside an explicit transaction (PAKTON `get_db` autocommit-style reads) the var is unset or, worse, a plain `SET` would persist onto the pooled connection and bleed into the next tenant reusing it. **Fix:** mandate one transaction per request with `SET LOCAL` at its start; never plain `SET`; reset on checkin; assert var present before any client query.

### M4 — Warm-agent global vs per-request tenant state (partially addressed, under-tested)
**Where:** w5 §1 ("state per-request không dính vào instance warm"); PAKTON global `archivist` (`tasks.py:38-47`), concurrency=1.
The spec states the intent correctly, but PAKTON's Archivist holds the checkpointer/indexer config at construction (`agent.py:118-137`), so vector namespace and checkpointer binding are instance-level, not per-call. With the warm global, a per-request `tenant:<id>` namespace must be threaded into every retrieve/checkpoint call, not read from the warm instance. **Fix:** make namespace/DEK/as_of strictly call-arguments; add a test that two tenants' tasks on the **same** warm worker don't cross (concurrency=1 serializes them, masking bugs — test with interleaving/prefetch).

### M5 — Retry discipline can re-run partial side effects
**Where:** w5 §1 ("không retry 4xx/validation", keep 3× infra retry), PAKTON `self.retry` (`tasks.py:49,77,186,273`).
Good that validation/tenant-suspended won't retry. But engine tasks have side effects (vector writes, checkpoint writes, cost metering); blind infra-retry can double-write or double-bill, and a retry after a tenant is suspended mid-flight needs re-checking tenant status on each attempt. **Fix:** idempotency key per task; re-assert tenant.status==active at task start on every retry; make writes idempotent.

### M6 — SSE auth + error leakage
**Where:** w5 §5 `/v1/query/sse` (lift `api.py:247`), PAKTON event_stream `api.py:305-398`.
Browser `EventSource` cannot send `Authorization` headers; PAKTON's SSE is POST+header (works via fetch-streaming but needs the frontend to comply — note for W6). Error branch yields `str(e)` to the client (`api.py:396`) — can leak internals/content. SSE CORS is `Access-Control-Allow-Origin: *` (`api.py:405`) — tighten for a multi-tenant app. **Fix:** sanitized error events; locked CORS; confirm token transport with W6.

---

## LOW / NOTES

- **L1 — Celery header `tenant_id` fail-closed (§6):** good invariant, but must be a worker `task_prerun`/signature check, not left to each task body; and headers transit the broker in clear (see C4). Verify the check cannot be skipped by direct `send_task`.
- **L2 — KMS blast radius (§2.4):** per-tenant DEKs wrapped by KMS is sound, but if all wrapping keys live under one KMS master/instance, KMS compromise = all tenants. Spec should state key-hierarchy separation and rotation mechanics (rewrap DEK vs re-encrypt data). Shared KB left unencrypted is fine (public data) — but confirm KB store cannot be written by tenants (read-only enforced at DB grant, not just app).
- **L3 — Temp-file plaintext (§3.2 cites `tasks.py:231-245`):** zero-retention leans on `os.remove`, but the plaintext contract hits worker local disk first; a crash between write and remove leaves plaintext. Use encrypted tmpfs / in-memory + guaranteed cleanup in `finally` (PAKTON does use `finally`, but disk-plaintext window remains).
- **L4 — AI-label single choke point (§3.4, `response_template.py`):** sound to centralize, but SSE events are hand-built (`api.py:349,387`) outside the envelope — ensure the label is injected in the stream path too, as §6 step 4 requires; test 4 covers this.
- **Inherited-PAKTON honesty check (task item 7):** multi-tenancy/RBAC are genuinely designed, not hand-waved (tenant tables, namespaces, RLS intent). But three "lifts" are hand-waved as free when they are not: RLS fail-closed (C2), shared RLS var across stores (C3), and the three-store model omitting broker/Redis (C4). Supabase is **kept**, not replaced, carrying its shared-secret + residency problems (H2).

---

## Acceptance-test sufficiency (task item 8)
Current tests (w5 §7) are necessary but miss the highest-stakes invariants:
1. **No egress test** — nothing asserts client data never reaches Claude. Add: a sensitive-tenant Review must route to vLLM; a pasted-contract query must not classify KB-only; assert the egress audit record (C1, C5).
2. **No task-result IDOR test** — add cross-tenant `GET /v1/tasks/{id}` → 403/404 (C6).
3. **Zero-retention test is incomplete** — extend test 5 to Redis result backend + RabbitMQ + object store + (if present) Pinecone, and to checkpoint-row deletion on conversation delete (C4, H5).
4. **RLS fail-open not tested** — add: as the **app role**, a query with no `app.current_tenant` set returns 0 rows; verify FORCE RLS and that the app role is non-owner/non-BYPASSRLS (C2).
5. **Checkpointer isolation tested only by namespace** — test 2 says "kiểm … checkpointer" but add a direct read-by-foreign-thread_id → denied, proving the app-layer prefix check, since RLS won't cover it (C3).
6. **Auth-disabled behavior** — test that with `ENABLE_AUTHENTICATION=false` prod config is rejected / requests fail closed (H1).
7. Test 2's "đổi tenant_id trong JWT" is unrealistic against HS256 (attacker can't resign) — keep it, but add the realistic confused-deputy vectors (task_id/thread_id guessing) and a forged-`user_metadata` attempt (H2).

---

## What's fine / keep
- Lifting PAKTON's FastAPI+Celery+SQLAlchemy+Alembic+SSE skeleton is the right call; the topology verification (§1, §10) is accurate against source.
- Two-layer split (shared read-only KB vs isolated client data) and "never train on client data" (§2.2) is the correct spine.
- Per-tenant namespacing of vector store + the fail-closed intent table (§6) are the right shape — the gaps are in enforcement mechanics, not the goal.
- Envelope encryption + crypto-shred concept (§2.4), AI-label centralization (§3.4), OTel trace propagation API→Celery→LLM (§4), and "no retry on validation/tenant-suspended" (§1) are all sound.
- Correctly identifies the go-live legal-entity/BCA-certification gate as non-code (§3.1, compliance-vn.md §1 Điều 21–22).
- Accurately catalogs PAKTON's missing tenancy/effectivity (§10) — matches `w3_review.md` and source grep.
