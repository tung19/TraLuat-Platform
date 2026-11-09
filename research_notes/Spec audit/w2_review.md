# Adversarial review — W2 Knowledge-Graph spec (`docs/specs/w2-knowledge-graph.md`)

Reviewer stance: skeptical. Goal is to find what breaks, is overstated, or is under-specified.
Grounded against the reference sketch `src/traluat/temporal.py` (the spec's own R1–R5 reference impl),
`refs/indigo/indigo_api/models/{works,amendments}.py`, and `refs/LeSICiN/{helper.py,model/model.py}`.

Note on citations: the spec (line 138) cites `refs/LeSICiN/model/helper.py::generate_graph`.
The actual file is `refs/LeSICiN/helper.py` (not under `model/`). Minor, but the "steal-list" paths
should be fixed or a member will waste time.

---

## CRITICAL

### C1. The "exactly one row" invariant (§3 R1, test §8.4) is NOT enforced by the schema, and the R3 algorithm actively violates it under realistic ingestion.
The spec asserts (line 98) that for a given `(unit, lang, known_as_of, as_of)` the query returns **exactly 1 row (or 0)**,
and relegates violations to "a test must catch it". Nothing in the DDL (§2) prevents overlap — there is no exclusion
constraint. The invariant rests entirely on `apply_amendment` being well-behaved, and it is not. Three concrete inputs
that corrupt it:

- **Out-of-order / retroactive-middle amendment.** State: V0 `valid_from=2020-01-01, valid_to=NULL`.
  Apply amendment eff `2022-01-01` → `_open_version_at(2022)` returns V0, sets `V0.valid_to=2022`, inserts V1 `2022→NULL`.
  Now a *later-arriving* amendment eff `2021-01-01` (retroactive, or just ingested out of order):
  `_open_version_at(2021)` returns V0 (`valid_from 2020 ≤ 2021 < valid_to 2022`), sets `V0.valid_to=2021`, inserts
  V2 `2021→NULL`. Result: **V1 `2022→NULL` and V2 `2021→NULL` both open**. Query for `as_of=2023` matches *both*
  → `reconstruct_as_of`'s `.one_or_none()` (temporal.py:52) **raises `MultipleResultsFound`** = unhandled 500, not a
  graceful `None`. `_open_version_at` (temporal.py:71-80) splits/truncates but never creates the trailing segment, so
  retroactive inserts in the middle of a live interval always leave an overlapping open tail.

- **Amendment effective BEFORE the origin version.** Original V0 `valid_from=2020`. Amendment eff `2019`:
  `_open_version_at(2019)` finds nothing (`valid_from 2020 ≤ 2019` false) → `prev=None`, nothing closed, inserts
  `2019→NULL`. Now V0 `2020→NULL` and the new row `2019→NULL` overlap for all `t≥2020`. Same multi-row corruption.

- **Two amendments with the SAME `effective_date`** (common in VN: several decrees all commence Jan 1). First closes V0
  at T and inserts V1 `T→NULL`. Second: `_open_version_at(T)` now returns V1 (V0 excluded because `valid_to=T` not `>T`),
  sets `V1.valid_to=T` → a **zero-width `[T,T)` ghost row**, inserts V2 `T→NULL`. The read happens to return one row (V2),
  so **test §8.4 passes while the content is silently last-writer-wins** — two different amending documents with different
  text, and the one that "wins" is just whichever was ingested last. No conflict is raised.

**Fix:** add a Postgres exclusion constraint on the current-belief slice, e.g.
`EXCLUDE USING gist (unit_id WITH =, lang WITH =, daterange(valid_from, valid_to) WITH &&) WHERE (tx_to = 'infinity')`,
plus a partial unique index enforcing at most one open (`valid_to IS NULL`) row per `(unit_id, lang)` in current tx.
This turns all three corruptions into a **write-time rejection (fail loud)** instead of a silent read-time corruption.
Then `apply_amendment` must be rewritten to (a) reject or explicitly handle out-of-order/retroactive inserts and
(b) genuinely SPLIT an interval (close the pre-segment, insert the amended segment, re-open a trailing segment if the
original had a later `valid_to`) rather than blindly truncating `valid_to`.

### C2. `apply_amendment` (R3) mutates `valid_to` in place → it is NOT bitemporally correct, contradicting the R5 claim.
R5 (line 109) promises that transaction-time lets you recover "what the system believed at K". But R3/`apply_amendment`
(temporal.py:98) closes the previous version with `prev.valid_to = effective_date` — an **in-place UPDATE** that leaves
no tx-time trace. After an amendment, you can no longer reconstruct the *prior belief* of that unit's history
(`known_as_of` = before the amendment was entered), because the old `valid_to=NULL` fact was overwritten, not versioned.
So the system is bitemporal only for the narrow R5 correction path and single-temporal everywhere amendments flow.
This defeats the stated moat ("hệ thống tin tại thời điểm K").

**Fix:** every mutation of an existing `unit_version` (including closing it during an amendment) must go through
tx-versioning: set `tx_to=now` on the old row and insert a new row with the new `valid_to`. Decide and document this
once; right now R3 and R5 use two different, incompatible update disciplines.

---

## HIGH

### H1. `correct_amendment_date` (R5) can break the neighbour interval and re-introduce a 2-row overlap.
`correct_amendment_date` (temporal.py:133-155) tx-closes the wrong row and inserts a corrected row with the new
`valid_from`, but it touches **only that one row**. The *preceding* version was closed at the wrong date
(`prev.valid_to = wrong_from`) and is left untouched. Example: V1 `2020→2022` (wrong; should end 2021), V2 `2022→NULL`.
Correct V2's `valid_from` to `2021`. Now current belief = V1 `[2020,2022)` and corrected `[2021,∞)` → `as_of=2021-06`
matches both → overlap → the §8.4 invariant is violated by the very function that is supposed to demonstrate temporal
correctness. The function also hard-codes `lang="vi"` default instead of reading `wrong.lang`.
**Fix:** corrections must adjust the matching neighbour's `valid_to` in the same tx-versioned transaction, or be
expressed as a single "move boundary" operation over the affected pair; add a test (see M-tests).

### H2. No un-apply / revival path; `norm_relation` is not itself temporal → corrected or repealed amending docs cannot roll back.
Several real scenarios have no answer in the spec:
- **Amending document itself later repealed/annulled** ("does the amendment revert?"). VN law generally has *no automatic
  revival*, but the spec records only a `repeals` edge and provides no mechanism either way. There is no inverse of
  R3/R4. Contrast indigo, which has `AmendmentInstruction.apply()/unapply()` as an explicit FSM
  (`refs/indigo/indigo_api/models/amendments.py:145-157`).
- **W1 extracted a wrong `norm_relation`** (wrong target eId / wrong date). W2 has already materialized versions from it
  (`source_relation_id`). There is no cascade to de-materialize. Materialization is one-way.
- `norm_relation` (§2) has `effective_date` but **no tx-time and no valid_to** — relations are not bitemporal, so you
  cannot ask "what did we believe the amendment graph was at time K", even though that is the whole premise of the module.

Also an impl gap: the sketch creates the `norm_relation` *after* the version and never sets `new_v.source_relation_id`
(temporal.py:99-119), so provenance is not actually wired.
**Fix:** make `norm_relation` bitemporal (or at least tx-versioned + retractable); add `unapply`/`retract` that
de-materializes versions whose `source_relation_id` points at a retracted relation; define the revival policy explicitly
(default: no revival unless an express `revives` edge exists).

### H3. Partial / per-provision commencement is unmodelled; `valid_from` is conflated with document effective date.
VN laws routinely commence provisions on different dates, and a provision can be *published but not yet in force*
(`Điều X có hiệu lực từ ...`). Indigo models this explicitly: `Commencement.provisions` (a list of provision eIds),
`all_provisions` bool, `Work.all_commenceable_provisions(date)`, `all_uncommenced_provision_ids(date)`
(`refs/indigo/indigo_api/models/works.py:284-405`). The W2 schema has only a single `unit_version.valid_from` and a
`document.date_effective`. Test §8.1 even bakes in the conflation ("None khi `t < date_effective`"), which is only correct
if W1 stamps every unit's `valid_from` with the document's effective date — which is exactly what breaks for staggered
commencement. There is no field linking a version to its commencement event/scope.
**Fix:** add a commencement concept (per-unit commencement date and/or a `commencement` table with a provision scope),
and separate "exists in text" from "in force". `in_force()` (the W3 Citation-Verifier gate, §6) depends on getting this
right.

### H4. Conflict resolution (§4) will mis-handle guidance-vs-conflict, lacks the scope data it requires, and hard-codes a contestable doctrinal order.
- **Guidance treated as conflict.** A Thông tư that *hướng dẫn* (guides) a Nghị định is not in conflict, yet
  `resolve_conflict(candidate_units[], as_of)` receives a flat unit list with no relation context and will apply lex
  superior, discarding the guiding instrument's operative detail. The schema *has* a `guides` relation_type, but the
  resolver signature never consults `norm_relation` to exclude guidance pairs. Concrete wrong result: NĐ Art.5 + TT Art.3
  (TT guides NĐ) → resolver returns only NĐ, dropping the implementing detail the user actually needs.
- **`lex specialis` is undecidable with the given schema.** §4 step 3 says "đánh dấu phạm vi (scope metadata)" but **no
  scope column exists anywhere in §2** — no territorial (national/provincial), subject-matter, or personal scope. So
  specialis cannot be computed; and a provincial VBQPPL vs a national one is a scope distinction, not a pure rank contest.
  The claim "thuần logic, không LLM" hides a dependency: scope must be classified by *something* (annotation or a model).
- **`rank_level` on `authority` alone is insufficient.** The VN normative hierarchy (Luật Ban hành VBQPPL 2015/2020, Art.4)
  is largely *doc_type*-based. Two instruments from the *same* authority (e.g. a Luật vs a Nghị quyết of the National
  Assembly; a Luật vs a Pháp lệnh of the Standing Committee) can't be ordered by authority rank. Rank belongs partly on
  `doc_type`, not only `authority`.
- **Fixed cascade superior→posterior→specialis is a doctrinal choice presented as settled.** The hard case — a *later
  general* law vs an *earlier special* law — is genuinely unsettled; applying posterior before specialis will always pick
  the later general law, which is frequently the *wrong* legal answer (*lex specialis derogat legi generali*). A
  deterministic engine should return "unresolved → escalate to human" for this class rather than silently pick posterior.
**Fix:** (1) consult `norm_relation` and exclude `guides`/`hierarchy` pairs before ranking; (2) add explicit scope columns
(territorial/subject/personal) or specialis is non-functional; (3) move part of the ranking to `doc_type` and encode the
Art.4 order; (4) make posterior-vs-specialis return an explicit "conflict unresolved" state.

### H5. The "inductive linking" story is internally contradictory and drops LeSICiN's training machinery without replacement.
§5.2 says the dominant signal is **align (text↔structure)** and simultaneously proposes to *replace* the model with a
text **bi-encoder (bge-m3) + cross-encoder rerank**. But in LeSICiN the align signal is produced by the graph encoder
(`MetapathAggrNet`) over metapaths (`refs/LeSICiN/model/model.py:52-60`); a pure text bi-encoder **does not reproduce the
structural/align signal at all**. You cannot keep the "trội" signal while deleting the mechanism that generates it.
Also factually: at inference LeSICiN scores with only two signals — `scores = λ0·attr + λ2·align`, `struct_scores` is
unused for prediction (`model.py:80`) — so the "ba tín hiệu match" framing is imprecise about what actually scores.
Further gaps:
- **Negative sampling unspecified.** LeSICiN avoids it via BCE over *all* labels + class weights
  (`helper.py:67-73`, `tws` scheme). A bi-encoder/cross-encoder needs a hard-negative strategy (sibling articles in the
  same Điều/Chương, co-cited articles). Without it the matcher will prefer lexically-similar-but-wrong articles.
- **Threshold calibration unspecified.** LeSICiN uses one global `pthresh=0.65` (`model.py:5,18`). `link_judgment` exposes
  only `top_k=20`, no score threshold and no per-`matter_type` calibration → it will always emit 20 (poor precision) or
  truncate when >20 apply. Test §8.6 checks neither precision/recall nor threshold.
**Fix:** either retain a lightweight structural encoder (and accept that brand-new nodes only have hierarchy edges), or
drop the "align is dominant" claim; specify hard-negative mining and a calibrated (ideally per-type) threshold; add
precision/recall acceptance criteria.

---

## MEDIUM

### M1. The sample Cypher (§5.1) is wrong openCypher and misses temporal edge-filtering.
```cypher
MATCH (a:Unit {eid:$eid})-[r:guides|cites*1..3]->(b:Unit)
WHERE r.effective_date <= $as_of
```
In a variable-length path `*1..3`, `r` binds to a **list of relationships**, so `r.effective_date` is not a property
access — AGE/openCypher will error or not filter per hop. It must be `ALL(rel IN r WHERE rel.effective_date <= $as_of)`.
It also omits any filter for edges whose relation was later repealed/superseded and has no `valid_to`/upper bound — the
§5.2 "THÊM" note about filtering repealed edges is not applied to the norm-graph query itself.

### M2. Cycle risk in `norm_relation` for the "FK+CTE first" phase.
`A amends B` + `B cites A` (or any back-reference) is a real cycle. A naive `WITH RECURSIVE` over `norm_relation`
**infinite-loops / errors on depth** unless it uses `UNION` (dedupe) or a Postgres 14+ `CYCLE ... SET ... USING` clause or
a visited-set. The bounded Cypher `*1..3` is safer (bounded hops, no rel reuse per path), but the spec explicitly starts
with FK+CTE before AGE, and the CTE cycle handling is unspecified. Also unspecified: **which** `norm_relation` rows get
projected into the graph — projecting low-`confidence`/unreviewed edges yields garbage multi-hop results. Define a
projection filter (`review_status='approved' AND confidence >= τ`).

### M3. Linking date semantics are legally ambiguous and under-specified.
"Lọc theo ngày bản án (chỉ điều còn hiệu lực tại thời điểm vụ việc)" — but `link_judgment(facts, as_of, ...)` takes a
single `as_of`. The applicable law is usually the law in force **at the time of the act/conduct**, not the judgment date,
and criminal matters have retroactive-lenient application (hồi tố có lợi). Conflating these into one `as_of` will select
the wrong temporal slice. Also undefined: the **candidate-generation** step. For a brand-new, zero-citation law
(cold-start), if candidates are drawn from "articles seen in prior citations", the new article is invisible regardless of
how good the bi-encoder is; and its align/structure signal has only hierarchy edges, no citation edges. The spec claims
to "add" date filtering but doesn't address candidate recall for never-cited articles.

### M4. `reconstruct_as_of` repeal handling vs document_as_of ordering.
`reconstruct_as_of` returns `None` for `status='repealed'` or `text IS NULL` — fine. But `document_as_of`
(temporal.py:58-68) orders only by `Unit.ordinal` at the top level and ignores the recursive `parent_id` tree; a
hierarchical document (Điều → Khoản → Điểm) will be flattened/mis-ordered unless every unit shares one global ordinal
space. The §2 `unit` is explicitly a recursive tree, so top-level `ORDER BY ordinal` is insufficient for correct assembly.

---

## LOW

### L1. Steal-list path error: `refs/LeSICiN/model/helper.py` → actual `refs/LeSICiN/helper.py` (§5.2, §10).
### L2. `.one_or_none()` behaviour on >1 rows is an exception, not the graceful `None` the prose implies; the spec should state that the invariant breach surfaces as a raised error (which is fine if intentional, but should be documented and caught at the API boundary).
### L3. `TX_INF`/`tx_to='infinity'` sentinel and the half-open `[valid_from, valid_to)` convention are used consistently (good), but only the open-row partial index is mentioned; make the uniqueness/exclusion guarantees explicit in the DDL (see C1).

---

## Acceptance tests (§8) — insufficient to catch the above

The tests only exercise clean, in-order sample data and will pass while C1/C2/H1 corruptions exist. Add:
- **Overlap/invariant (adversarial), not just happy-path §8.4:** out-of-order amendment (eff date earlier than a
  previously-applied one); amendment eff before origin `valid_from`; two amendments same `effective_date` with different
  text (assert a conflict is raised, not last-writer-wins). Ideally enforce via the exclusion constraint and assert the
  write is rejected.
- **Interval split:** retroactive amendment landing strictly inside a live interval → assert exactly the pre-segment,
  amended segment, and (if applicable) trailing segment exist, non-overlapping.
- **Correction neighbour:** `correct_amendment_date` must not create an overlap with the adjacent version (H1).
- **Transaction-time under amendment:** after an amendment, `known_as_of` *before* the amendment entry must still return
  the prior belief (catches C2).
- **Revival:** repeal of a repealing document → assert the chosen (no-revival) policy.
- **Conflict:** guides-not-conflict (TT guiding NĐ must not be dropped); same-rank specialis with scope; later-general vs
  earlier-special returns "unresolved".
- **Linking:** precision/recall thresholds, cold-start brand-new (zero-citation) article, act-date vs judgment-date.
- **Graph:** cycle `A amends B, B cites A` terminates; per-hop temporal edge filter actually filters.

---

## Things that are actually fine (brief)
- Postgres-as-single-source-of-truth with AGE/pgvector as rebuildable derived indexes (§0) is a sound, defensible choice.
- Half-open valid-time interval `[valid_from, valid_to)` with `valid_to > as_of` strict comparison is internally
  consistent and matches indigo's `expression_date <= T` intent.
- Pointing amendments/commencement at a stable `eId` rather than an autoincrement id (§1) is correct and matches
  indigo's `AmendmentInstruction.provision_id` (eId) design.
- Separating `guides` from `conflicts`/`amends`/`repeals` as distinct relation_types is the right vocabulary — the gap is
  only that `resolve_conflict` doesn't consume it (H4).
- Making new *judgments* inductive via embedding+match (no retrain) is a genuine and correct improvement over LeSICiN's
  transductive fact nodes — the problem is only the contradictory claim about preserving the structural/align signal (H5),
  not the inductive direction itself.
