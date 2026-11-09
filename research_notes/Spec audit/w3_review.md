# Adversarial Review — W3 Retrieval + Grounding Spec

Spec: `docs/specs/w3-ai-retrieval-grounding.md`
Reviewer stance: skeptical. Goal = find what breaks, is overstated, or is under-specified.
Refs read: `refs/L-MARS/lmars/verify_agent.py`, `refs/L-MARS/lmars/faith_search/{workflow,router,aggregator}.py`, `refs/legalbenchrag/legalbenchrag/{benchmark_types,benchmark,run_benchmark,methods/baseline}.py`, `refs/PAKTON/.../retrievers/base.py`, `refs/LegalGraphRAG/core/judge/judge_law.py`.

Bottom line: the invariant "LLM only answers from retrieved units + every citation passes 3 gates or abstain" (§0, §2) controls **citation fabrication** but does **not** control **answer correctness**. The whole design verifies the citations the draft *made* and never checks the provisions the draft *should have cited but missed*. Several "ported" mechanisms (L-MARS temporal routing, cross-provider min, legalbenchrag recall, span-preserving chunker) do not do in this spec what the source code actually does.

---

## CRITICAL

### C1. No recall floor — confident answer from an incomplete retrieval set (§1, §2)
The grounding loop (§2) iterates only over `draft.citations`. Every gate (`in KB`, `in_force`, `nli_supports`) is a *per-citation* check. Nothing checks whether the retrieved set `cands` actually contains all controlling in-force provisions.

Failure scenario: Question "Can the employer unilaterally terminate in case X?" The controlling exception lives in Điều 36 BLLĐ, but hybrid retrieval surfaces only the general rule Điều 35 (lexical/semantic near-miss; Điều 36 phrased differently). The LLM answers "yes" citing Điều 35. Gate1 passes (Điều 35 real), gate2 passes (in force), gate3 passes (text supports the general-rule claim). `conf` is high → answer returned confidently and **wrong**, because the dispositive provision was never retrieved. The 3 gates are structurally incapable of catching this: they can only reject a bad citation, never flag a missing one.

There is no "did we retrieve enough" signal anywhere at runtime. `catch-omission` exists only in the §4 benchmark (and depends on a `required_clause_rule` ground-truth that the spec never defines how to author). An offline benchmark tag is not a runtime guard.

Fix: add a runtime recall/sufficiency gate before answering — e.g. (a) retrieval-confidence floor (min rerank score / score-gap / coverage of the question's legal concepts), (b) a coverage check that the multi-hop expansion of each cited provision (dẫn chiếu, sửa đổi, hướng dẫn) was itself retrieved, (c) force abstain-with-escalation when the top-k scores are flat/low rather than answering. Treat "insufficient retrieval" as a first-class outcome distinct from "answered".

### C2. "No provision addresses this" (silence) is indistinguishable from "we failed to retrieve" (§1, §2, §4)
Nothing in the pipeline separates *true legal silence* from *retrieval miss*. Both produce the same symptom: few/weak candidates. The loop then either (a) hallucinates a loosely-related provision that happens to pass NLI, or (b) abstains — and the user cannot tell "the law is silent" from "the system gave up".

This is baked into the ported eval too: legalbenchrag's `recall` returns `0` when `total_relevant_len == 0` (`run_benchmark.py:52-54`), and every `QAGroundTruth` carries a non-empty `snippets` list. The ported harness has **no representation of a silence question**, so the §4 benchmark can never measure this failure. The spec inherits a blind spot and does not acknowledge it.

Fix: define a "no governing provision" answer class with its own evidence standard (e.g. must show the searched-but-empty authority set + why), and add silence cases to the benchmark with an explicit expected-abstain / expected-"no provision" label. Do not let silence collapse into generic abstain.

### C3. `as_of` default = today is wrong for most real tasks; hard effectivity filter drops still-relevant law (§1, §2)
§2 pseudocode: `as_of_date=default today`. §1: "sau retrieval, loại chunk có unit_version không thoả `in_force(eid, as_of)`" — a **hard** post-filter.

Failure scenarios:
- **Contract review.** The relevant date is the contract-signing date or the performance/breach date, not today. Default "today" silently applies current law to a 2019 contract and drops the 2015 Civil Code provisions that actually govern it. Wrong answer, no warning.
- **Future-effective law.** A law passed but effective 2026-07-01, asked on 2026-03. `in_force(today)` filters it out, so the system cannot answer "what will change" — yet that is a common legal question.
- **Transitional / grandfathered provisions (điều khoản chuyển tiếp).** New law in force today, but its transitional clause keeps old law applicable to matters begun before the cutover. A hard `in_force(as_of=today)` filter excludes the old provision that is *legally controlling* for the ongoing matter. The system answers from the new law and is wrong.

The spec treats effectivity as a single scalar `as_of` and a binary in/out filter. Real effectivity is: {status at date} × {which date matters for this question} × {transitional carve-outs}. None of the last two are modelled.

Fix: (a) `as_of` must be a required, explicit, per-matter input with task-type defaults (contract → signing/performance date, dispute → event date, advisory → today or user-chosen), surfaced in the answer. (b) Support a date *range* / "law in force at event + any transitional provisions that reach back." (c) Make the filter *annotate and down-rank* rather than hard-drop, so transitional/superseded-but-relevant provisions can still reach the LLM with a "not in force at as_of — check transitional rules" flag. A hard drop is unsafe.

---

## HIGH

### H1. Gate 3 `nli_supports` — textual entailment is the wrong test for legal support (§2)
Gate3 = `nli_supports(draft.claim, KB.text)`. The ported L-MARS verifier defines "supported" as *"the cited source's text entails the claim in full"* (`verify_agent.py:205`, `_VERIFY_SYSTEM`). Legal support is frequently **not** surface entailment:

- **False negatives (real support rejected).** A conclusion reached by interpretation/application ("a 30-day notice is required here") is supported by a provision stating a principle plus a definition elsewhere; neither sentence "entails the claim in full." The verifier returns `unsupported`/`partially_supported`, Faith-Search burns its 2 re-search calls, then abstains on a correct answer → over-abstention.
- **False positives (lexical overlap passes).** The LegalGraphRAG reference the spec cites for element-wise verify (`judge_law.py:9,31`) decides truth by `"true" in judge_res.lower()` — which also matches "untrue"/"not true". If gate3 is implemented in that style, superficial keyword overlap or a stray "true" passes a non-supporting citation.

Also the batch verifier truncates cited text to **1500 chars** (`verify_agent.py:653`; single-claim path 4000, line 559). A long Điều whose dispositive Khoản sits past char 1500 gets judged on a truncated text → spurious `unsupported`.

Fix: (a) do not frame the gate as strict NLI entailment; use a legal-support rubric (does the provision, read with its definitions/cross-refs, authorize the asserted legal conclusion?) and allow "supports via stated cross-reference." (b) Verify against the *full* cited unit (structure-aware chunking makes units bounded — pass the whole unit, not a 1500-char prefix). (c) Never decide support by substring match on the judge's prose; require structured output.

### H2. Abstain threshold is uncalibrated LLM self-confidence; confident-wrong passes (§2)
`conf < THRESHOLD → abstain`, and the ported value is `0.6` (`aggregator.py:42`, `FaithSearchConfig.abstention_threshold=0.6`). But `conf` is the **LLM judge's self-reported** `confidence` field (`verify_agent.py:596`), parsed by `_safe_float` with a **default of 0.5** on unparseable output (line 267). This number is not calibrated to empirical correctness anywhere; the L-MARS code itself says the threshold is "a hyperparameter … a sweep over thresholds drives the precision-coverage curve" (`aggregator.py` docstring) — i.e. it must be *measured*, and the spec never says it will be.

Failure scenario: judge confidently mis-reads an amended provision, emits `support_level="supported", confidence=0.9`. Passes gate and threshold. Confident-but-wrong answer ships. Conversely a cautious judge emitting 0.55 on a correct support triggers needless abstain.

The §5 acceptance tests contain **no calibration test** and no target for over-abstention vs under-abstention rate. Product risk: either hallucination leaks (threshold too low) or the product abstains so often it is useless (too high), with no measured operating point.

Fix: calibrate the threshold on a labelled dev set; report a precision–coverage curve and pick the operating point against an explicit max-hallucination-rate SLA; add both over-abstention and under-abstention (confident-wrong-pass) as CI-gated metrics. Treat judge confidence as a feature to calibrate, not a probability to threshold directly.

### H3. Gate 2 operates at `unit_eid` granularity — repealed sub-clause / wrong-version citations slip through (§2)
`gate2 = in_force(c.unit_eid, as_of)` is a boolean on one eid. Two misses:
- **Repealed sub-clause of a live article.** If `unit_eid` resolves at Điều level but Khoản 3 was repealed, a citation quoting Khoản 3 passes gate2 (the Điều is "in force"). Depends entirely on eid granularity, which the spec asserts is Điều/Khoản/Điểm but never guarantees the *citation* resolves to the leaf that was repealed.
- **Version mismatch.** gate2 only asks "is this eid in force at as_of"; it does **not** assert that the *quoted text* equals the as_of version's text. A provision amended (renumbered wording, changed figure) but still in force passes gate2 while the draft quotes the old wording. gate3 (NLI) may or may not catch it, and if semantics are close it won't.

Fix: gate2 must verify in-force **at the leaf unit the citation points to**, and the citation's `version` must equal the version returned by `in_force(as_of)` (reject or flag a version delta). The spec already carries `unit_version_id`/`version` on chunks — enforce it in the gate, not just store it.

---

## MEDIUM

### M1. Span "zero-drift" asserts contradict the `prepend struct_header` design (§1)
§1 says each chunk (a) prepends `struct_header` (số hiệu + đường dẫn điều-khoản) and (b) keeps legalbenchrag's two asserts `sum(len)==len(content)` and `"".join==content`. Those asserts hold in legalbenchrag only because its splitter has `chunk_overlap=0, strip_whitespace=False` so chunks concatenate back to the exact source (`baseline.py:117-120`). **Prepending a header breaks both asserts** and, worse, makes `chunk.content != text[span]`, breaking the §5.3 acceptance test (`chunk.content == text[span]`).

The two concepts must be separated: `embed_text = header + body` (what you embed/BM25) vs `span_text = body` (what the span/offset anchors to, what the citation quotes). The spec conflates them into one `content`. As written it is internally inconsistent.

Fix: store header and body separately; run the zero-drift asserts on the span-bearing body only; embed/rerank on `header + body`.

### M2. Cross-provider "lấy điểm thấp nhất" misreads the source + ignores cost/latency (§2, §6)
Spec §2: "answerer ≠ verifier … lấy điểm thấp nhất (take the minimum)." In the source, "minimum of the two crosswise scores" is an **eval-reporting** method — run both A→B and B→A and report the min so a system can't be accused of training its own judge (`verify_agent.py:36-46`). At **runtime**, Faith-Search uses exactly **one** verifier model, different family from the answerer (`FaithSearchConfig.evaluator_model`). If the team implements a runtime "min of two providers," that is a *third* LLM pass per answer (answerer + 2 verifiers) on top of claim-decomposition and re-search calls.

§6 build tasks and the spec generally **never mention cost or latency**. A single grounded answer already costs: 1 decompose + ≥1 batched verify + up to 2 re-search retrievals + up to 1 re-verify + optional synthesis (see `faith_search/workflow.py` phases). Adding cross-provider doubling of verify makes a single answer a many-LLM-call, multi-second operation. For self-hosted tenants under NĐ 356/2025 (§3) this is worse.

Fix: state explicitly that runtime uses a single cross-family verifier; reserve crosswise-min for offline eval. Add a latency/cost budget and per-answer call-count ceiling to the spec. If runtime min-of-two is really wanted, justify the 2× verify cost.

### M3. Verifier determinism is overstated (§4)
§4: "diskcache content-hash … chạy lại rẻ & tất định (deterministic)." Caching makes **re-runs of identical inputs** reproducible; it does not make the verifier deterministic. First-run judgments vary (provider updates, non-zero effective sampling, JSON-parse fallbacks → `_norm_enum` defaults to `unsupported`/`major`, `_safe_float`→0.5). Any prompt/model change invalidates the content-hash and silently re-queries. So "deterministic" is only "reproducible while the cache and model are frozen." CI gating (§4) on top of a non-deterministic judge can flake.

Fix: distinguish "cache-reproducible" from "deterministic"; pin verifier model+version in CI; record judge version in the content-hash key; add a verifier-stability check (same input re-judged N times) as a reported metric, as L-MARS already tracks `verifier_error_rate`.

### M4. Faith-Search `temporally_invalid` routing is web-search logic, inapplicable to a temporal KB (§2)
Spec §2 maps `temporally_invalid → truy vấn giới hạn ngày ★`. The ported router actually appends strings like `"{year} effective"` or `"current 2026"` to a **web** query and biases to `site:.gov`/`law.cornell.edu` (`router.py:101-122,33-40`). None of that applies to a Vietnamese KB with a `TemporalRepository`. The real temporal fix here is re-query `in_force(as_of)` / fetch the correct version — which the L-MARS router does not do. So "port L-MARS faith-search repair" undersells how much must be rebuilt: the temporal branch is essentially net-new, and `no_citation` is a deliberate no-op in the router (`router.py:66-67`) meaning a claim the LLM left uncited is never recovered by re-search.

Fix: replace the router's temporal/authority strategies with KB-native ones (re-ask `in_force`, pull the version at `as_of`, expand via `GraphQuery.multihop`). Don't present this as a straight port.

### M5. Chunk-level retrieval loses cross-provision context; multi-hop is off by default (§1)
A Khoản that says "theo quy định tại Điều 12" is meaningless without Điều 12. Retrieval is chunk-level and `multihop=False` by default (§1 signature). So the default path retrieves the referencing clause but not the referenced one; the LLM either answers from an incomplete unit or the verifier later can't support the claim.

Fix: default multi-hop on for queries whose top candidates contain internal cross-references; or always expand one hop along dẫn-chiếu edges before answering. Tie this to C1's sufficiency check.

---

## LOW

### L1. NFC normalization vs citation offsets (§1)
Normalizing to NFC before index and before `.find()` is consistent for *matching*, but if the canonical stored/display text the citation quotes is the raw (un-normalized) source, NFC can change length (combining diacritics) and offsets drift against the displayed source. Confirm the stored source and the offset basis are the *same* normalization. Low because it's an implementation discipline item, but it silently corrupts citations if missed.

### L2. Vietnamese BM25 analyzer hazards (§1)
Good that `.split()` is banned. Watch: (a) word-segmenters that underscore-join ("công_ty") break exact matching of legal numbers/abbreviations ("Điều 36", "NĐ 356/2025", "khoản 2"); (b) diacritic-folding analyzers collide distinct legal terms ("khoản" vs "khoan"); (c) cross-reference tokens as plain text. Specify analyzer behaviour for legal citations/abbreviations and keep a keyword/exact field for citation strings alongside the analyzed field. bge-m3 itself is fine for Vietnamese.

### L3. Grounding-loop pseudocode bugs (§2)
As written, `gate1/gate2/gate3` are reassigned each loop iteration and `conf = aggregate(gates)` sits after the loop — only the last citation's gates survive; there's no accumulation, no per-citation repair trigger inside the loop, and if `draft.citations` is empty the loop body never runs and `gates` is undefined (an uncited answer could fall through to "return Answer"). Likely just loose pseudocode, but it hides the real policy for multi-citation and zero-citation answers. Specify: aggregate over all citations, and define the zero-citation outcome (should be forced abstain, matching L-MARS `no_citation`).

---

## Things that are actually fine (brief)
- "PAKTON retriever lacks `as_of`/`tenant`" (§1 ref note): **correct** — `retrievers/base.py` `retrieve(query, **kwargs)` has no such params; adding them is justified.
- Structure-aware chunking on Điều/Khoản/Điểm boundaries instead of blind length cuts: sound and better than legalbenchrag's naive/rcts splitter.
- Separating `citation_unreachable` (fabricated/stale cite) from `no_citation` (no cite offered): genuinely useful distinction, correctly present in the ported verifier (`verify_agent.py:17-28`).
- Doing the eval harness first (§6.1) with a character-level P/R metric: good engineering order; the char-level overlap metric (`run_benchmark.py:22-54`) is a reasonable, well-defined retrieval metric.
- bge-m3 (1024d, MIT) as the dense model for Vietnamese: reasonable choice.

## Highest-leverage fixes
1. Add a **runtime retrieval-sufficiency / recall gate** and a distinct **"no governing provision"** outcome (C1, C2). Without these the invariant gives false assurance.
2. Make **`as_of` explicit + transitional-aware + non-hard-filter** (C3).
3. **Calibrate** the abstain threshold and CI-gate both over- and under-abstention (H2).
4. Reframe gate3 away from strict textual entailment and verify the **full leaf unit at the cited version** (H1, H3).
