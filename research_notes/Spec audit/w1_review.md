# W1 Data Pipeline — Adversarial Review

> Target: `docs/specs/w1-data-pipeline.md` (L1 Acquisition + L2 Ingestion).
> Lens: **garbage-in silently poisons moat #1** — one wrong extracted date or one false amendment relation materializes a wrong version that `in_force()` / the W3 Citation Verifier then trust as truth.
> Method: read-only. Spec cross-checked against `refs/eyecite`, `refs/bluebell` (Rust crates + Python), `refs/cobalt`, and `docs/specs/{w2-knowledge-graph,meta-json-assumed-schema}.md`.
> Verdict up front: the "steal-list" code citations are accurate, but the spec **systematically overstates what the stolen engine gives it** (eyecite has no confidence model, its resolver is case-law-specific) and **has no quality gate anywhere between extraction and materialization**. The golden rule "W1 không phát minh chân lý" is quietly violated: W1 *does* invent a `confidence` number and an `effective_date`, and W2 trusts them unconditionally.

---

## CRITICAL

### C1 — No confidence/HITL gate exists between relation extraction (W1 stage 5) and version materialization (W2 R3/R4). A single false relation silently creates a wrong version.
**Spec:** W1 §5/stage 5 emits `norm_relation` with `confidence:0.82, review_status:"auto"` (line 136); §3 stage 5 says "W2 mới áp qua R3/R4 để materialize" (line 139); §6 restates the hand-off (lines 217–220).
**W2 side:** `apply_amendment` (R3, `w2-knowledge-graph.md:102–105`) and `repeal` (R4, `:107`) apply **unconditionally** — they take `new_text, effective_date, src_unit` and mutate the bitemporal table. Nowhere do they read `confidence` or `review_status`. W2's own audit only lists "định nghĩa filter projection (confidence/review_status)" as an *unresolved* item (`w2-knowledge-graph.md:224`, M2). So the gate is a TODO on both sides — it belongs to neither.
**Failure scenario:** Stage 5 extracts, from a "Căn cứ …" preamble, a relation `replaces(TT-X → NĐ-99/2015)` with confidence 0.6. Nothing blocks it. W2 R3 closes the live version of NĐ-99's Điều 3 Khoản 2 at that date and inserts a tombstone/new text. `in_force(NĐ-99, dieu_3__khoan_2, today)` now returns the wrong version; W3's Citation Verifier reports the real, in-force clause as repealed. No human ever saw it.
**Fix:** Make materialization gated by contract. W2 R3/R4 must refuse any relation whose `review_status != 'approved'` (or `confidence >= θ` AND type ∈ auto-safe set). Define θ and the approval queue as a W1 *deliverable*, not a W2 afterthought. Add an acceptance test: a relation with `review_status='auto'` must NOT change any `unit_version` until approved.

### C2 — `confidence` is fabricated: the ported engine (eyecite) has no confidence model at all.
**Spec:** stage 5 output and §6 both carry a numeric `confidence` (lines 136, 218), presented as if it falls out of the ported 4-stage eyecite engine.
**Reality (verified):** `grep confidence` over all of `refs/eyecite/eyecite/` returns **nothing**. eyecite is deterministic regex/token matching with a binary outcome: a citation either resolves to a `Resource` or is **dropped** (`resolve.py` docstring: "If a citation cannot be definitively resolved to a resource, it is dropped and not resolved"). There is no probability anywhere in `find.py`/`models.py`/`resolve.py`.
**Why it matters:** the spec leans on `confidence` as the safety valve (C1, §4 "văn bản OCR nặng → review_status ưu tiên HITL"), but that number has no principled source. A hand-rolled heuristic score (regex tier × OCR conf × resolver certainty) is fine — but the spec must *say so* and define it, because right now reviewers will assume the engine produces calibrated confidence and set a threshold against noise.
**Fix:** Specify exactly how `confidence` is computed, and treat it as a heuristic, not a probability. Until defined, do NOT let any threshold on it gate materialization (see C1) — default everything to `needs_review`.

### C3 — Non-anonymized judgments (bản án) are never detected or blocked. Legal-risk (NQ 03/2017).
**Spec:** the 8-stage pipeline (W1 §3) has **no anonymization stage**. `grep -ni "anonym|ẩn danh|NQ 03|bản án"` over `w1-data-pipeline.md` returns **zero hits**. The `anonymization_status` field exists only in the *assumed* meta schema (`meta-json-assumed-schema.md:76`) and as a checklist line (`:106`) — nothing in W1 reads or enforces it.
**Failure scenario:** a crawled `ban_an` PDF with real litigant names (or `anonymization_status` absent/`"raw"`) flows through stages 1→8 and lands in the SoR, then into W3 chunks (stage 8) and the retrieval index. The platform now serves personal data in violation of NQ 03/2017/NQ-HĐTP. OCR'd scans are the worst case: the status field is likely missing entirely.
**Fix:** Add a gate in stage 1 (and a re-check post-OCR in stage 2) for any `doc_type ∈ {ban_an}`: if `anonymization_status != 'anonymized'`, quarantine — do not emit records, do not index. Add a PII detector (names, addresses, CMND/CCCD numbers) as a backstop for documents where the meta flag lies or is absent. Add acceptance test: a non-anonymized judgment must be blocked, not ingested.

---

## HIGH

### H1 — Branch A trusts `meta.json` blindly: a wrong `date_effective` or `relations[]` in the source is copied straight into the moat with zero cross-check.
**Spec:** §2 Nhánh A (lines 59, 221): "meta.json GIÀU cấu trúc → bỏ stage 2–3, map thẳng"; mapping table §2 marks `date_effective` as ✅ taken from meta when present. The whole premise (line 37) is "field nào có sẵn → bỏ qua stage tương ứng." Plus the meta schema itself is an **assumption** — `meta-json-assumed-schema.md:1` "GIẢ ĐỊNH — chờ meta thật," and W1 §2 is a "PLACEHOLDER — chốt tuần 1." So the entire intake contract, and every acceptance test built on it, rests on a schema that does not exist.
**Failure scenario:** vbpl.vn metadata lists `date_effective:"2021-01-01"` but the document body actually says "có hiệu lực từ 01/7/2021" (data-entry error, common in aggregated sources). Branch A copies the wrong date; `unit_version.valid_from` is wrong by six months; every as-of query in that window returns the wrong law. Same for a `relations[]` entry pointing at the wrong `target_doc`.
**Fix:** Even in Branch A, run the stage-4/stage-5 extractors in **shadow/verify mode** and flag `review_status=needs_review` on any disagreement between meta and extracted value (especially `date_effective` and each relation target). Trust-but-verify, not trust. Do not close the §2 contract or the acceptance tests until the real schema is in hand.

### H2 — The eyecite resolver the spec plans to "reuse" for Vietnamese back-references does not transfer. `antecedent_guess` is case-name matching; legislative anaphora has no plaintiff/defendant.
**Spec:** §5.3 (line 194): "'điều này', 'khoản trên', 'nêu trên', 'cùng điều' … → resolve về công cụ đầy đủ gần nhất (dùng lại logic `antecedent_guess` + `last_resolution` của resolve.py)."
**Reality (verified, `resolve.py`):** `_resolve_supra_citation` / `_resolve_shortcase_citation` resolve by matching `antecedent_guess` against `full_citation.metadata.defendant` / `.plaintiff` (`_filter_by_matching_antecedent`), or by reporter+volume. These fields are **US case-law specific and do not exist for a Nghị định**. Only the `id.`-style `last_resolution` carry-forward (`_resolve_id_citation`) is genuinely reusable — and it is exactly the mechanism that *propagates a wrong antecedent*.
**Failure scenario:** "…quy định tại khoản 2. Khoản này được thay thế bởi…" — "Khoản này" must bind to the structurally enclosing khoản, not to the most recently *mentioned* citation. eyecite's `last_resolution` binds it to whatever full citation was parsed last in reading order. If a different document was cited one sentence earlier, "Khoản này" resolves to the wrong target → a false `amends` edge on the wrong unit → wrong version materialized (feeds C1).
**Fix:** Resolution of VN legislative anaphora ("điều này/khoản trên/cùng Nghị định") must use the **structural position of the reference** (which eId contains the evidence span), not eyecite's citation-order heuristic. This is new code, not a reuse. Scope it explicitly and give it its own tests; the §5.3 "dùng lại" claim is misleading as written.

### H3 — "Forgiving parser" (Bluebell never rejects input) is sold as a feature but is the silent-mis-tree hazard. No structure-quality signal exists.
**Spec:** §3.1 (line 115): "Bluebell bảo chứng 'luôn sinh AKN hợp lệ, không bao giờ từ chối input lỗi' → copy tinh thần forgiving-parser (OCR tiếng Việt bẩn vẫn ra cây)." Branch B relies on this to build the unit tree from scratch.
**Reality:** a parser that never fails means **garbage OCR always yields a tree, and the tree is never flagged as wrong**. There is no confidence, no "did this parse look sane" check. Bluebell's eId generator (`eid.rs` clean_num, verified) will happily turn OCR noise into a stable-looking eId (e.g. a misread "Điều 3l" → `dieu_3l`), and amendments then point at a unit that is subtly wrong.
**Failure scenario:** two-column scanned PDF OCR'd in reading order interleaves the columns; indentation (which Bluebell uses as hierarchy, `grammar.pest:64`) is destroyed; Khoản 2 of Điều 5 gets attached under Điều 4. eId tree is internally consistent (passes acceptance test 3!) but structurally wrong. Every relation/chunk keyed to those eIds is now misfiled.
**Fix:** Add a structure-sanity gate for Branch B: expected-vs-found ordinal gaps (Điều 1,2,4 with no 3), orphan khoản, implausible depth, OCR `conf` aggregated per unit → `review_status=needs_review`. Acceptance test 3 (eId idempotent) proves *determinism*, not *correctness* — determinism on garbage is still garbage.

### H4 — Phased / per-article / conditional commencement collapses to one document-level `date_effective`, poisoning `valid_from`.
**Spec:** §2 maps a single `document.date_effective`; stage 6 (line 143) sets `unit_version.valid_from = date_effective` for **all** units. W2 already flagged this: H3 (`w2-knowledge-graph.md:220`) "Commencement từng phần chưa mô hình hoá; valid_from lẫn với date_effective cấp văn bản → phá in_force()." W1 feeds exactly the single-date input that breaks it.
**Failure scenario:** a Luật says "Luật này có hiệu lực từ 01/01/2021, riêng Điều 10 có hiệu lực từ 01/01/2023." W1 stamps every unit `valid_from=2021-01-01`. Điều 10 is reported in force two years early. Conditional commencement ("có hiệu lực khi Chính phủ quy định chi tiết") has no date at all and should be `needs_review`, not silently 2021.
**Fix:** Stage 4 must extract per-provision commencement (list of {unit scope, date|condition}), not a scalar. Where a provision has conditional/absent commencement, emit `needs_review` and do NOT default it to the document date. Align the output contract with W2's planned per-article `Commencement.provisions`.

### H5 — Effective-date regex cannot distinguish the document's own commencement from quoted/amended dates, nor hiệu lực from áp dụng (transitional applicability).
**Spec:** stage 4 (line 126): regex "có hiệu lực (thi hành) từ ngày…". Single pattern, first-match semantics implied.
**Failure scenario:** an amending Thông tư contains "Nghị định số 99/2015/NĐ-CP có hiệu lực từ ngày 10/12/2015" (describing its *target*) before stating its own "Thông tư này có hiệu lực thi hành kể từ ngày 01/7/2024." A naive first-match grabs 2015-12-10 as the Thông tư's own effective date. Also: "điều khoản chuyển tiếp" (transitional applicability) dates are not commencement dates; conflating them sets `valid_from` wrong.
**Fix:** Anchor the extraction to the self-referential subject ("… này có hiệu lực"), exclude spans that are inside a detected citation to another document, and separate `date_effective` (hiệu lực) from applicability/transitional provisions. On multiple ambiguous matches → `needs_review`, never guess (consistent with §2 line 48 intent, which stage-4 regex does not actually enforce).

---

## MEDIUM

### M1 — One wrong OCR digit in a date has unbounded blast radius and no digit-level validation gate.
**Spec:** stage 2 keeps per-block `conf` (line 83) and §4 routes OCR-heavy docs to HITL via `review_status`, but there is **no field-level confidence check** on the specific characters forming a date. A date can be extracted from a block with aggregate conf 0.97 while the single glyph "1"→"7" is the one error.
**Failure scenario:** "01/01/2021" OCR'd as "01/01/2071". Aggregate page conf is high, so no HITL. `date_effective=2071` → the law is "not yet in force" for 46 years; `in_force()` returns None; W3 reports a live law as non-existent. A "7"→"1" the other way back-dates amendments.
**Fix:** Validate every extracted date against the document's `date_issued` (effective ≥ issued, within a sane window, not in the far future), and against the OCR `conf` of the exact character span (not the block). Fail → `needs_review`. Cheap, high-value.

### M2 — Idempotency keyed solely on `source_hash` makes OCR/extractor improvements un-reprocessable (stale truth sticks).
**Spec:** §3 (line 68) "idempotent (key = `source_hash`)"; stage 1 (line 78) "cùng source_hash → skip"; acceptance test 6 (line 233) only checks same-hash → no dup. Provenance records `tool_version` (line 68) but the skip key ignores it.
**Failure scenario:** you upgrade Tesseract `vie` → VietOCR (explicitly planned, build task 6, line 245) to fix bad diacritics. Re-running the pipeline **skips every already-ingested doc** because `source_hash` (the PDF bytes) is unchanged. The corrected OCR never lands; the wrong dates/relations from the first pass stay in the SoR.
**Fix:** Idempotency key must be `(source_hash, stage_schema_version, tool_version)`. A tool/schema bump must trigger reprocessing of downstream stages. Extend acceptance test 6 to cover a `tool_version` bump forcing recompute.

### M3 — SHA-256 dedup confuses "same document, different scan/source" with "distinct documents," and cannot catch near-duplicates or revisions.
**Spec:** stage 1 (line 72) dedups on content hash of each file.
**Failure scenario (A):** the same Nghị định is crawled from vbpl.vn and from the issuing ministry as two different scans → two different hashes → two `document` records for one legal work. Amendments extracted from one copy don't attach to the other; as-of queries may hit the un-amended twin. **(B):** a consolidated re-issue (văn bản hợp nhất) vs the original are legitimately different documents but near-identical text — hashing treats them as unrelated, losing the consolidation relationship.
**Fix:** Dedup at the *work* level by canonical identity (doc_number + doc_type + authority) in addition to byte hash; when multiple byte-distinct files map to one work, pick a primary and record the others as provenance alternates. Add fuzzy near-dup detection (shingling/MinHash) to flag suspected same-work-different-source for review.

### M4 — Consolidated documents (văn bản hợp nhất), amended-in-place text, appendices (phụ lục) and forms (biểu mẫu) are not handled by Branch B's from-scratch parser; they silently mis-tree.
**Spec:** §2 line 56 mentions a "cờ consolidation" as optional meta, but no stage *processes* consolidation; §3.1 grammar only covers PHẦN/CHƯƠNG/MỤC/…/ĐIỂM. Phụ lục, biểu mẫu, and consolidated footnote markers ("được sửa đổi bởi khoản X Điều Y của …") are out of grammar.
**Failure scenario:** a consolidated law carries inline footnote markers showing which amending act changed each clause. Bluebell segments the hierarchy but ignores the markers → W1 treats consolidated (already-amended) text as the *original* `unit_version` with `valid_from=date_effective` of the consolidation, erasing the amendment history W2 is supposed to reconstruct. Phụ lục with its own "Mẫu số 01" numbering gets forced into the Điều/Khoản tree as garbage units.
**Fix:** Detect doc sub-types (consolidated, appendix, form) in stage 1/3 and route them: consolidated docs must either be parsed for their embedded amendment footnotes or explicitly excluded from version-origin ingestion and flagged; appendices/forms get a distinct `unit_type` and are excluded from the Điều/Khoản tree invariants.

### M5 — Bilingual alignment (stage 7) assumes EN and VN share the same eId tree and order; official VN→EN translations routinely renumber, merge, or omit.
**Spec:** stage 7 (line 148): "căn Điều↔Điều theo eId + thứ tự." §6 implies EN `unit_version` reuses the same `unit`.
**Failure scenario:** the EN translation omits a repealed article or merges two khoản. Position-based alignment then shifts: EN text for Điều 6 gets attached to VN Điều 5's unit for everything after the gap. Retrieval in EN now returns the wrong clause text under a correct-looking eId. Also: many VN laws have only *unofficial* translations — ingesting them as authoritative `unit_version(lang='en')` presents unofficial text as law.
**Fix:** Align by content/number matching with explicit gap handling, not raw ordinal zip; refuse to emit an EN unit_version when counts diverge and flag for review. Record translation provenance/authority (official vs unofficial) and never let an unofficial translation back a grounded legal answer without a disclaimer flag.

---

## LOW

### L1 — Acceptance tests are all happy-path; none exercise the failure modes that poison the moat.
**Spec:** §7 tests 1–7. Test 1 is a single clean amendment pair; test 3 proves eId *determinism* (not correctness, see H3); nothing tests: a false/low-confidence relation being blocked from materialization (C1), a wrong-digit OCR date (M1), a non-anonymized judgment being refused (C3), ambiguous back-reference resolution (H2), phased commencement (H4), consolidated docs (M4), or **precision/recall of relation extraction on a labeled set**. The relation extractor — the stated moat feeder — ships with no measured precision/recall.
**Fix:** Add negative/adversarial fixtures for each Critical/High above, and a labeled relation-extraction eval reporting precision/recall with a target (precision must dominate — a false `repeals` is worse than a missed one, given C1).

### L2 — `clean_text` / NFC normalization (§5.1) can shift offsets; evidence_span round-trip is asserted (test 5) but date/number mangling by cleaning is not.
**Spec:** §5.1 clean step "chuẩn hoá NFC, dọn artefact OCR, số/ký hiệu." SpanUpdater (verified, `annotate.py`) correctly remaps spans, so test 5 passes. But aggressive "dọn số/ký hiệu" cleaning could itself alter a digit or merge "01 . 01" handling before extraction.
**Fix:** Keep date/number extraction on lightly-cleaned text, or assert that cleaning is lossless for digit sequences; add a test that a date survives clean_text unchanged.

### L3 — `authority_rank` / rank_level is assumed present or "tra bảng thẩm quyền," but the rank table is undefined. lex-superior conflict resolution (W2) depends on it.
**Spec:** meta schema `authority_rank:80` is "giả định" (`meta-json-assumed-schema.md:28`); W1 §2 maps authority "qua registry" but the registry/rank mapping is not specified. W2 conflict ordering (lex superior/posterior, `w2-knowledge-graph.md:119`) needs correct ranks.
**Fix:** Specify the authority→rank registry as a W1 deliverable (it is the analogue of courts-db, which the spec correctly notes lives at `helpers.py:8`), and treat a missing/ambiguous authority as `needs_review`.

---

## What is genuinely fine (credit where due)

- **Code citations in the steal-list (§9) are accurate.** Verified: `eid.rs` `clean_num` starts line 5; `xml.rs:1994` `rewrite_all_eids`; `grammar.pest` `hier_element_block` at :64, keyword list :75–79, short aliases :80; eyecite `__init__.py` exports exactly the 4 pipeline functions; `annotate.py` `SpanUpdater` at :20. The §10 Match-check correction about `courts_db` living in `helpers.py:8` (not `tokenizers.py`) is correct and honest.
- **The data↔engine split (`vn-legal-db` vs `traluat-cite`) is the right lesson from eyecite** and is faithfully drawn.
- **`SpanUpdater` reuse for offset preservation is legitimate** — it genuinely does what the spec claims (diff-based O(log n) remap), and anchoring `evidence_span` to source text is sound.
- **The architectural boundary "W1 extracts, W2 materializes bitemporal"** is the correct separation of concerns — the problem is only the *missing gate* at the seam (C1), not the seam itself.
- **Stage 4's stated intent** "thiếu date_effective → `needs_review`, không bịa ngày" (line 127) is exactly right — it just isn't enforced for the harder cases (H1, H5, M1).
- **Measuring OCR ratio early (§4)** before investing in an OCR engine is good engineering discipline.

---

## One-paragraph bottom line
The spec's engineering scaffolding is solid and its references are honestly verified, but it has a structural safety hole: it manufactures a `confidence` number the ported engine cannot produce (C2), labels everything `auto`, and hands it to a W2 that materializes relations with **no gate** (C1) — so any false amendment/repeal silently rewrites the bitemporal truth the whole system trusts. Compounding this, Branch A trusts source metadata blind (H1), the "forgiving" parser guarantees a tree but never a *correct* one (H3), per-article commencement collapses to one date (H4), and non-anonymized judgments are never stopped (C3, a legal exposure). Fix order: C1/C3 first (both are "do not ship without"), then H1–H5. The acceptance suite must grow adversarial cases and a measured precision/recall for relation extraction before this pipeline is allowed to write to the SoR.
