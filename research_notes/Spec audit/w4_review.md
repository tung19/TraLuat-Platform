# W4 — Reasoning engine + Auditor hard-gate — Adversarial review

> Independent skeptical review of `docs/specs/w4-reasoning-engine.md`.
> Method: read the spec against the real source it ports (`refs/LegalGraphRAG`, `refs/PAKTON`, `refs/L-MARS`) and against the already-documented upstream defects it inherits (`w2-knowledge-graph.md §11`, `w3-ai-retrieval-grounding.md §8`). Files read only; nothing executed.
> Verdict up front: the spec is well-structured and the two-gate framing is sound, but **the hard-gate's core accept/reject primitive is literally a bug that W3's own audit already flagged, the temporal gate re-introduces a hard-filter that W3's audit told the team to remove, and the whole thing is a one-directional hard gate with no recovery path built on a non-deterministic LLM classifier.** For a product that tells a user "a real judge got it wrong", several of these are ship-blockers.

---

## CRITICAL

### C1 — The element verdict parser is the exact `"true" in lower()` bug W3 already flagged as a defect
Spec §3 reproduces LegalGraphRAG verbatim:
- `w4 §3` line 112: `if "true" in r.text.lower(): satisfied.append(element)` / `elif "false" in r.text.lower(): unsatisfied.append(element)`
- `w4 §3` line 120: `return ("true" in agg.text.lower()), agg.text`

Source confirmed: `refs/LegalGraphRAG/core/judge/judge_law.py:24-27` and `:31-32`.

**Failure scenario.** Aggregator (gate-2 final verdict) returns "This article does **not** apply; it would be **untrue** to say the elements are met." `"true" in "...untrue..."` → `True` → the inapplicable article is **accepted into `verified_articles`** and drives the judgment. At element level, "Not true" / "This is untrue" → matches `"true"` first (checked before `"false"`) → element wrongly marked *satisfied*. The bias is systematically toward *applicable*, which is the exact opposite of what a gate whose job is to *exclude* law should do — the moat leaks inward.

**This is not a new discovery for this repo.** `w3-ai-retrieval-grounding.md §8 H1` already says: *"Port LegalGraphRAG `"true" in lower()` khớp cả 'untrue' (bug) … Sửa: parse bool chặt (ranh giới từ, không substring)."* W4 §10 "Match check" claims *"mọi điểm khớp … Không có mismatch"* and does **not** flag that it is porting a known-defective matcher into the highest-stakes gate in the system. Reviewer-grade inconsistency: the spec copied the bug and certified it clean.

**Fix.** Do not substring-match. Require the model to return a single structured token (JSON `{"verdict":"applies"|"not_applies"|"uncertain"}`), parse with word-boundary/exact equality, and treat unparseable/uncertain as **reject** (fail-closed for a hard gate), not accept. Add an acceptance test whose fixture model output literally contains "untrue"/"not true" and assert the article is rejected.

### C2 — Gate 2 matches English `true`/`false` while running `lang="vi"` → silent element drop
Same `verify_article` loop, `w4 §3` lines 108-113, calls `LLMGateway.generate(..., lang="vi")` but classifies the response by English `"true"`/`"false"` substrings.

**Failure scenario.** A Vietnamese-prompted model answers in Vietnamese ("Điều kiện này **được thỏa mãn**" / "**không** thỏa mãn") or "Đúng"/"Sai". The response contains **neither** `"true"` nor `"false"` → the element lands in **neither** `satisfied` nor `unsatisfied`. The element is silently dropped from the checklist. The aggregate call then receives a *partial* checklist and can still return applicable on the surviving elements → an article that fails an un-evaluated constitutive element passes the gate. This is strictly worse than the holistic yes/no the spec disparages, because the omission is invisible.

**Fix.** Constrain output to a fixed enum regardless of `lang`; assert every element produced a parseable verdict; if any element verdict is missing/uncertain, fail the article closed and record which element could not be evaluated in the trail. Add test: 3-element article, one element returns Vietnamese prose → article must reject, not pass on 2/3.

### C3 — Gate 3 is a hard temporal filter — directly re-introduces the bug W3's audit removed, and inherits W2/W3's eid-granular `in_force` hole
`w4 §3` lines 88-89: `if not TemporalRepository.in_force(art.unit_eid, as_of): reject(gate=3, "temporally_invalid")`.

Two compounding problems:

**(a) Hard filter contradicts W3 C3.** `w3 §8 C3` explicitly: *"KHÔNG filter cứng — giữ điều hết hiệu lực nhưng đánh dấu + áp quy tắc chuyển tiếp (điều khoản chuyển tiếp là dữ liệu, không bị gạt)."* W4 gate 3 is precisely a hard filter: not-in-force-at-`as_of` ⇒ dropped before gate 2 even runs. **Failure scenario:** a contract formed under the old Civil Code, dispute adjudicated with a grandfather/transitional clause — the governing old provision is *not* `in_force` at `as_of` yet still controls. Gate 3 hard-rejects it; the Adjudicator (narrowing contract, no re-retrieval) can never see it; the engine renders a judgment on the wrong law and, in second-opinion mode, may declare a *correct* judgment "wrong." A boolean `in_force(eid, as_of)` cannot represent "repealed but still governs pre-repeal facts."

**(b) eid-granular boolean inherits W3 H3 + W2 H3.** `w3 §8 H3`: `in_force` at eid-boolean level lets through (i) a sub-clause repealed inside a still-living article and (ii) the correct article but *old version text* — and mandates *"Cổng 2 phải assert cited_version == version-at-as_of"*. W4 gate 3 calls only `in_force(art.unit_eid, as_of)`; it never asserts `art.version_date == version-at-as_of`, even though `Article.version_date` exists (`w4 §2`). So W4 does inherit the hole the task asked about. Worse upstream, `w2 §8 H3`: partial commencement is unmodeled and `valid_from` is conflated with document-level `date_effective`, which that audit says *"phá in_force()"* — i.e., the very function gate 3 leans on is known-broken for per-provision commencement. W4 cites `in_force` as if it were sound and adds no guard.

**Fix.** (1) Replace the hard reject with a *tri-state*: `in_force` / `superseded-but-transitional(keep+flag)` / `not-yet-or-void`; route transitional provisions through to gate 2 with a flag, don't drop them. (2) Add the version-equality assertion `art.version_date == version_at(as_of)` to gate 3 (or a new gate 3b) per W3 H3. (3) Record W2 H3 (partial commencement) as an explicit blocking dependency — gate 3 cannot be correct until W2 models commencement at provision level.

### C4 — A hard gate with no recovery path, driven by a non-deterministic LLM, is unrecoverable on any false-negative
The narrowing contract (`w4 §2`, §4.2) is the stated invariant: each layer only shrinks the set, Adjudicator cannot re-retrieve. Combined with gate 2 being an LLM call (`verify_article`), this means **any false-negative at gate 2 is terminal**: an article that actually governs but that the (buggy per C1/C2, or merely wrong) element classifier rejects can never re-enter. The Adjudicator then either renders the wrong result or abstains, and in multi-role mode no role can rescue it because every role's citations pass through the same gate.

Two multipliers:
- **Non-determinism.** Gate 2 is LLM-based; the spec never pins temperature=0 or mandates caching of audit verdicts. So the *same case re-run produces different `verified_articles`* → different judgments. `w3 §8 M3` already warns determinism holds *"chỉ … nhờ cache."* For a tool asserting a judge erred, run-to-run instability of the accept/reject set is a reliability defect, not a nuance.
- **Direction of the bug.** C1 biases toward false-*accept* (leaks bad law in); the underlying NLI errors also produce false-*reject* (drops good law out). A hard gate amplifies both because there is no downstream correction — W3's post-draft `verify_answer` can catch an *unsupported sentence*, but it cannot resurrect an article the gate wrongly dropped.

**Fix.** For gate 2 specifically: temperature=0 + mandatory memoized cache keyed on `(unit_eid, version_date, as_of, hash(party_facts))`; consider k-sample majority vote at the gate; and crucially, make the gate **advisory-with-escalation rather than silently terminal** — a rejected-but-high-retrieval-score article should raise an HITL flag, not vanish. Document that the narrowing invariant is in tension with recall and that the resolution is human escalation, not pure pruning.

---

## HIGH

### H1 — Empty verified set → Adjudicator still synthesizes (hallucinated judgment)
Source `refs/LegalGraphRAG/core/agents/adjudicator.py:5-12` calls `synthesize_judgment` unconditionally; `refs/.../judge_crime.py:48-55` falls back to a *criminal* default (`{"charge_name":"无罪", ... "death_penalty":False}`) on parse error. W4 §4.2 says the Adjudicator "nhận **chỉ** `verified_articles`" but specifies **no abstain-on-empty behavior**. If every candidate article fails applicability (or is wrongly rejected per C1-C4), `verified_articles=[]` and the Adjudicator is handed nothing — nothing in the spec stops it from producing a confident civil judgment from the bare `party_facts`. The post-draft W3 gate may eventually abstain, but only after the LLM has drafted an ungrounded opinion, and only if the draft's sentences carry citations to catch.

**Fix.** Explicit precondition: `verified_articles == [] ⇒ abstain` ("không đủ căn cứ pháp lý đã xác minh"), emit the audit trail explaining why each candidate was dropped, and never call the drafting LLM. Add an acceptance test for it (currently absent from §7).

### H2 — Civil-law model does not transfer: facts-as-given + no burden of proof + claim-anchored retrieval misses defenses
The spec (§3, §4.1) ports a *criminal charge-prediction* machine and swaps only the output schema (§10 note). The deeper assumptions do not survive the move to VN civil litigation:
- **Facts are treated as established.** `verify_article` runs element NLI over `party_facts` as if the facts were true. In civil disputes the facts *are* the dispute, allocated by **burden of proof** (nghĩa vụ chứng minh). The engine has no fact-finding or burden model; it answers "is element X present in this party's narrative," which is one-sided by construction. Per-party segmentation (`segment_case_text_withname`, `refs/.../util.py:55`) runs each side independently but nothing reconciles conflicting factual assertions or assigns who must prove what.
- **Defenses are unreachable.** Researcher `R_chg` (§4.1) is *cause-of-action anchored* (`GraphQuery.multihop(src, ["guides","cites"], …)`). Affirmative defenses that *defeat* a claim — e.g. **thời hiệu** (limitation), **miễn trừ**, contributory fault — are not causes of action and will not be reached by claim-anchored multihop. They therefore never reach the Auditor or Adjudicator → the engine is structurally biased toward the claimant. This is W3 C1 (recall/sufficiency floor) resurfacing at the reasoning layer; W4 inherits it and adds nothing.
- `judge_dep` → "điều kiện áp dụng": the spec hand-waves that the offline-frozen checklist is "sinh lại từ điều kiện áp dụng của quy phạm VN" (§2, §10) but gives no method, owner, or validation for producing civil constitutive-element checklists, and no handling of elements whose truth depends on which party bears the burden.

**Honesty verdict:** the spec acknowledges the *schema* swap but **does not honestly handle** that the applicability/charge model itself is criminal. It should state plainly that element-wise applicability over one party's facts is not adjudication, and add (a) a sufficiency/recall floor that pulls defense provisions, (b) a burden-of-proof annotation on elements, (c) HITL for contested facts.

### H3 — Adjudicator conflict resolution depends on `GraphQuery.resolve_conflict`, which W2's own audit says is broken and should escalate to human
`w4 §6` table: `GraphQuery.resolve_conflict(eids, as_of)` used "khi hai điều verify xung đột." But `w2 §8 H4` lists four defects in exactly this: `guides` treated as conflict, no `scope` column so lex specialis is impossible, hierarchy by `rank_level` mis-ranks same-authority different doc types, and a hard cascade that *"âm thầm chọn luật chung mới đè luật riêng cũ (thường SAI)"* — with the prescribed fix being *"trả `unresolved → human`."* W4 consumes this function as if sound, provides **no HITL escalation path for unresolved conflicts**, and provides no fallback when two verified articles genuinely conflict. **Failure scenario:** a later general provision and an earlier special provision both pass the gate; `resolve_conflict` silently picks the later-general (wrong under lex specialis); the Adjudicator builds the judgment on it; in review mode it declares a correct judgment wrong.

**Fix.** Treat `resolve_conflict` as returning possibly-`unresolved`; on unresolved or low-confidence, abstain + HITL, never auto-pick. Gate this on W2 H4 being fixed (scope column, doc_type hierarchy, `guides` exclusion).

### H4 — Multi-role: cost/latency explosion, no bound, no dedup, and the "debate" is one model echoing itself
§5 runs the full §3 Auditor **on every utterance**. Order-of-magnitude per case:
`parties P × roles R(4) × rounds N × articles-per-utterance A × (elements E + 1)` LLM calls for gating alone, **plus** each role's drafting call, plus Researcher, plus the post-draft W3 verify (itself multi-call per W3 M2). With P=2, R=4, N=3, A=3, E=4 that is ~2·4·3·3·5 ≈ **360 gating LLM calls** before drafting/verification — per case. The spec sets **no cost ceiling**, specifies **no memoization** (the same `(unit_eid, as_of, party_facts)` is re-audited every time any role cites it — an obvious dedup the spec omits), and `w3 §8 M2` already warns to *"tính chi phí/độ trễ pipeline nhiều-call."*

Two further design problems the spec does not confront:
- **Collusion / echo, not independent review.** All roles call the *same* `LLMGateway` model with only a role-prompt difference. A single model role-playing four parties is not an adversarial check; consensus among them is an echo of one model's prior, not corroboration. No model/temperature diversity is specified. This undercuts the entire §7 test-6 premise that "đa vai > một-lượt."
- **Over-deliberation drift.** The L-MARS/academic warning the spec cites elsewhere applies here: more rounds tend to converge on *confident* consensus, which for a single echoing model can be confidently wrong. The only guard offered — "Auditor on every utterance" — polices *citation validity*, not *reasoning correctness*, so it does nothing against drift toward a wrong-but-grounded consensus.

**Fix.** Hard per-case LLM-call budget; memoize gate verdicts; require genuine diversity (different models or ≥2 independent samples) before claiming debate adds signal; and redefine test 6 against a labelled gold set with a stated metric and significance test (currently unfalsifiable — see H5).

### H5 — Stop-condition measures the wrong quantity and its "determinism" rests on non-deterministic inputs
§5.2 stops when `verified_articles` is set-stable over a round, or at `max_rounds`. Confirmed PAKTON weakness it replaces (`refs/.../router.py:29` budget, `:35` sentinel-or-`similarity_check`). But:
- **Wrong quantity.** In an adversarial debate the roles fight over *interpretation* of the *same* articles. The verified-article **set** can be stable from round 1 while the roles still disagree on outcome forever. Set-stability therefore fires an **early stop while the dispute is unresolved**, handing `synthesize` a disagreement it must paper over — or, if a role keeps introducing fresh passing articles, it never stabilizes and only `max_rounds` ends it. Either way the criterion does not track opinion convergence, which is what a debate is for.
- **"Deterministic" is overclaimed.** Set-equality is a deterministic *test*, but its operands are non-deterministic LLM utterances, so the number of rounds (and the final set) is non-deterministic unless temp=0 + cache are mandated (they are not — see C4). §7 test 7 asserts determinism; it will be flaky.

**Fix.** Add an explicit convergence signal on the *positions* (e.g. each role's accept/reject of each claim stable, or a bounded-disagreement measure), not just the evidence set; mandate temp=0+cache so "deterministic stop" is true; keep `max_rounds` as the hard backstop.

### H6 — "Bản án đúng/sai": the engine cannot distinguish legal error from judicial discretion, and nothing addresses the liability of asserting a named judge erred
The product framing (second opinion on whether a judgment is right/wrong) requires separating *"the court misapplied the law"* from *"the court exercised discretion I'd have used differently"* — quantum of damages, witness credibility, discretionary remedies, apportionment. The Adjudicator (§4.2) produces **its own** civil judgment and implicitly compares; there is **no module** that (a) ingests the actual judgment, (b) classifies each divergence as legal-error vs discretion-within-bounds, or (c) applies a standard of review. Element-wise applicability + citation grounding can only ever check the legal-premise layer, not discretion. **Failure scenario:** the engine's damages figure differs from the court's and it reports the judgment "sai," when the court was within its lawful discretion — a defamation/liability exposure against a named judge/court, and a correctness error.

**Fix.** Make the output assert only what the gates can support: "the cited legal basis is/are verified and in force; the engine's analysis diverges on X" with an explicit discretion carve-out and a mandatory hedge that divergence ≠ error. Add a discretion-zone classifier or, minimally, a disclaimer-and-abstain on discretionary dimensions. Legal review of the framing before any "bản án sai" string ships.

---

## MEDIUM

### M1 — Fabricated citations in role utterances: the text→eid resolution step (where hallucination enters) is unspecified
Gate 1 (`w4 §3` line 83) checks `TemporalRepository.versions(art.unit_eid)` — existence of an **eid**. For single-pass mode candidates arrive as structured `Article` objects from retrieval, so eids are real. But in §5 a **role (LLM) drafts an utterance "viện dẫn"** articles as free text ("Điều 999 BLDS"). The step that parses an utterance's free-text citations into `unit_eid`s — the exact point a hallucinated citation would be injected — is not specified. If a hallucinated string fails to resolve, is that `citation_unreachable` (good) or silently dropped (bad)? Undefined.

**Fix.** Specify citation-resolution: unresolvable free-text citation → explicit `fabricated_citation` reject in the trail (not silent), and the utterance containing it is flagged. Add a test with a role citing a non-existent article.

### M2 — Under-prune and empty-citation precedents in `prune_unsupported`
`w4 §3` lines 123-127 keep a precedent if **any** cited eid survives — matches `refs/LegalGraphRAG/core/agents/auditor.py:20-23` (keep-if-≥1). So the task's over-prune concern is a non-issue: a precedent citing {A,B,C} with only A rejected is correctly **kept**. Two residual issues, though:
- **Under-prune / analogy drift.** A precedent whose actual *ratio* rested on rejected articles {A,B} is kept because an incidental citation C survived, and is then fed to the Adjudicator as live support — the very analogy drift the prune claims to prevent. Set-membership on citations is a coarse proxy for "the precedent still supports this."
- **Empty-citation precedents vanish.** `any(... for eid in p.cited_unit_eids)` over an empty list is `False` → a precedent with no extracted citations is silently dropped. If W2 linking failed to extract citations for an otherwise on-point án lệ, it is lost.

**Fix.** Keep the ≥1 rule but (a) down-weight / flag precedents whose *primary* cited articles were rejected rather than treating all survivors equally, and (b) decide explicitly how no-citation precedents are handled (route to situation-similarity matching, not silent drop).

### M3 — Legal-accuracy error in the domain note: VN published án lệ are effectively binding, not merely persuasive
§10 asserts *"án lệ VN là thuyết phục, không ràng buộc như guiding cases TQ."* This is questionable: under Nghị quyết 04/2019/NQ-HĐTP, published án lệ **must be studied and applied** by courts, and departure must be reasoned — closer to binding-with-escape than "merely persuasive." Mischaracterizing their force could lead the engine to under-weight a controlling án lệ and wrongly conclude a judgment erred (or failed to err).

**Fix.** Correct the note; model án lệ as presumptively-controlling with a reasoned-departure exception, and reflect that weight in the Adjudicator.

### M4 — Acceptance tests insufficient for the failure modes above
§7 covers element-wise, the temporal gate happy-path, prune, narrowing, two-gate handoff, a (weak) multi-role claim, and stop. **Missing:** the "untrue"/Vietnamese-output parser tests (C1/C2); empty-verified-set abstain (H1); run-to-run stability of the gate (C4); transitional/grandfathered provision must-not-be-hard-dropped (C3); version-equality at gate 3 (C3b); fabricated citation in a role utterance (M1); unresolved conflict → HITL (H3); one-sided-facts/defense-retrieval (H2); discretion-vs-error (H6); and a cost ceiling in multi-role (H4). Test 6 ("đa vai > một-lượt") has **no gold set, no metric definition, no significance test** → unfalsifiable as written.

**Fix.** Add the above as explicit red tests; replace test 6 with a labelled benchmark + metric + CI bound.

---

## LOW

### L1 — L-MARS `_temporally_invalid` in the steal-list is US-web logic, not a port target
§9 line 251 lists `L-MARS/.../router.py::_temporally_invalid` for "re-search giới hạn ngày." Confirmed `refs/L-MARS/lmars/faith_search/router.py:101-122`: it appends `"current 2026"`, `"<year> effective"`, and `site:.gov/uscourts.gov` filters — US federal web search. `w3 §8 M4` already classifies this as *"net-new, không phải port."* Harmless because W4 delegates re-search to W3, but the steal-list entry is misleading.

**Fix.** Mark the entry "reference only — not portable to KB temporal re-search."

### L2 — Minor: gate-2 aggregate relies solely on `"true" in agg` so an empty/uncertain aggregate silently rejects (fail-closed), but the asymmetry is undocumented
`w4 §3` line 120 returns `False` when `"true"` absent. For a hard gate, fail-closed is the right default — but combined with C1's false-accept-on-"untrue" the behavior is incoherent (accepts on "untrue", rejects on silence). Document the intended failure direction once C1 is fixed.

---

## What's fine (keep)
- **Two-gate framing** (pre-output Auditor vs post-draft `verify_answer`, §1) is a genuine improvement over LegalGraphRAG, which has no temporal or post-draft gate — correctly attributed.
- **Gate ordering for cost** (deterministic gates 1 & 3 before the `|elements|+1` LLM calls of gate 2, §3) is sound *as cost optimization* (the correctness problems are in the gates themselves, not their order).
- **Element-wise over holistic** applicability is faithful to `refs/.../judge_law.py:17-30` and is the right shape (the defects are in the *parser* and the *facts-as-given* assumption, not the element decomposition).
- **`prune_unsupported` ≥1-rule** matches the source (`auditor.py:20-23`); not an over-pruner.
- **Narrowing contract as an invariant** is a good discipline — provided C4's escalation path is added so it is not silently lossy.
- **Audit trail keeps rejected articles** (§3, unlike LegalGraphRAG which keeps only accepted) — good for HITL/eval.
- **Stop-condition hardening intent** (set-equality over PAKTON's sentinel/`similarity_check`, confirmed fragile at `refs/.../router.py:35`) is directionally right; it just measures the wrong set (H5).
- **tenant+case `thread_id`** instead of PAKTON's timestamp (§5.3) is a correct fix.

---

## Priority for the W4 member
1. **C1, C2** (parser) — one afternoon, unblocks the entire gate's trustworthiness; add the red tests first.
2. **C3** (hard temporal filter + version equality) — blocked on W2 H3; coordinate, do not ship gate 3 as hard-reject.
3. **C4 + H1** (determinism, escalation, abstain-on-empty) — design the gate as advisory-with-HITL, not silently terminal.
4. **H2** (civil model: sufficiency floor for defenses, burden of proof) — needs design, not a patch.
5. **H3** (conflict → HITL), **H6** (discretion vs error + liability framing) — legal review required before any "bản án sai" output.
6. **H4, H5** (multi-role cost/echo/stop) — before Phase 4; may conclude multi-role needs model diversity to earn its cost.
