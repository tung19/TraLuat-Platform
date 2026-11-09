# W7 Adversarial Review — Compliance-Advisory · Expanded Roles · Loophole · Per-role Viz

> Target: `docs/specs/w7-advisory-roles-viz.md` (reviewed 2026-11-05).
> Posture: skeptical. Goal is to find what is wrong/overstated/under-specified/risky/unethical, not to confirm.
> Sources read: the spec; `research_notes/Compliance advisory and roles/{compliance_advisory,multirole_and_loophole,legal_visualization}.md`; `docs/specs/w2-knowledge-graph.md §11`; `w3-ai-retrieval-grounding.md §8`; `w6-platform.md`; `docs/compliance-vn.md`.
> I did not run/build anything.

---

## TL;DR — severity ranking

| # | Finding | Severity | Spec locus |
|---|---|---|---|
| C1 | W7 has **no acceptance tests, no build tasks, no interface contract, no integration of the W2/W3/W6 audit fixes** — it is a pitch deck bolted onto a hardened spec stack | **Critical** | whole doc; cf. W6 §7–§8 |
| C2 | Compliance "**no violation**" (false-clear) is the highest-liability output and is unguarded; the guardrail only covers "có vi phạm" | **Critical** | §1 line 40 |
| C3 | It inherits W3 **C1 recall-gap** while claiming the 3 gates are the differentiator — the exact gate W3 flagged as insufficient | **Critical** | §1 step 3 (line 36) |
| C4 | Investigator + procuracy-decision roles carry **more** legal exposure than Judgment Analysis but inherit **less** of its hard compliance engineering | **Critical** | §2, §4 |
| C5 | Loophole "defensive posture" controls (pro-only / HITL / labeled) are **stated intent, not enforceable**; weaker than LegalSim's actual mitigations | **Critical** | §3 line 62 |
| H1 | "Separate service → copyleft doesn't spread" is **wrong for AGPL** (CourtListener); AGPL §13 reaches network use | High | §4 line 70, §5 |
| H2 | "Remediation generation (grounded)" has **no grounding mechanism**; nothing verifies a cure actually cures | High | §1 step 4 |
| H3 | Free-text scenario intake has **no fact-sufficiency / clarification loop** | High | §1 step 1 |
| H4 | "Greenfield / nobody has done this" + "effective-date unsolved by any system" is **overstated and self-contradictory** | High | §0, §6 vs §4 |
| H5 | Solver is declared **mandatory** for §1 yet §1 is scheduled **first "quick commercial win"** — internally inconsistent; the hand-formalization bottleneck is hand-waved | High | §1 step 5, §3, §6 |
| M1 | "Model VN law in Akoma Ntoso → unlock Indigo" ignores the **W2 data-model conflict** and corpus-conversion cost | Medium | §4 line 79 |
| M2 | AI-suggests-charges **liability / high-risk scoping** never addressed for the new roles | Medium | §2, §4 |
| M3 | **Dahl 69–88%** hallucination stat used out of context (it is the *ungrounded* number; TraLuat is grounded) | Medium | §1 step 5 |
| M4 | Silent inheritance of unresolved **W2 in_force/partial-commencement and conflict-resolution** gaps on which every compliance verdict depends | Medium | §1 step 2 |
| L1 | Uncritical echo of **unverified secondhand claims** (System-206 ">97%", L4M "solver-backed", future-dated arXiv IDs) | Low | §0, §3 |

What is genuinely fine is collected at the end.

---

## CRITICAL

### C1 — W7 is a strategy memo wearing a spec's clothes; it drops the engineering discipline every sibling spec enforces
W2, W3, W6 each end with hard artifacts: W6 has an **Interfaces contract** (§7), **11 acceptance tests** (§8), **ordered build tasks** (§9); W2/W3 carry adversarial audit sections (`§11`/`§8`) with Critical fixes that were folded back into the design. W7 has **none of these**. It is sections 0–6 of prose, verdict tables, and reuse lists — zero testable acceptance criteria, zero interface signatures, zero build sequencing beyond one sentence in §6.

Failure scenario: a member implements `ComplianceAdvisoryService` from §1. There is no "acceptance test 1" telling them what a correct false-clear/abstain looks like, no `WorkflowContext`/`RetrievalService` signature to call, no statement of which W3 gate state maps to `THIẾU_THÔNG_TIN`. They wire it to W3 as if W3 were un-audited, and silently re-introduce W3 C1/C2/C3 (below). The spec that is supposed to be "built on our foundation" never names a single fix from that foundation's audit.

Fix: W7 is not implementable until it gains (a) an Interfaces section reusing W6 §7 signatures (`RetrievalService.retrieve(... as_of ...)`, `GroundingService.verify_answer`, `in_force`, `required_clause_rule`), (b) acceptance tests in the W6 §8 style — specifically false-clear, abstain-on-low-coverage, accusatory-role abstention, loophole-gating — and (c) an explicit "inherits W3 §8 C1–C3 / W2 §11 H3–H4" clause. Until then treat §1–§4 as a research brief, not a build target.

### C2 — The asymmetric-risk output ("you are compliant") is the one the spec forgets to guard
§1's guardrail (line 40) protects only the **positive** finding: *"mọi kết luận 'có vi phạm' phải HITL + cite; abstain khi không neo được."* The dangerous output in compliance advisory is the **negative**: "no violation." A "có vi phạm" that is wrong wastes a lawyer's time; a "không vi phạm" that is wrong puts a business into a breach carrying (per `compliance-vn §1`) up to **3 billion VND / 5% revenue / criminal liability**. W6 §1.1-C1 already established the governing principle for the sibling service: *absence cannot be grounded by retrieving a negative; you need a coverage floor and `needs_review` on weak retrieval.* W7 does not carry that principle to the no-violation case at all.

Failure scenario: SME describes a cross-border data flow; retrieval misses NĐ 356 Điều 21–22 (VN-legal-entity + BCA certification requirement — `compliance-vn §1`). All obligations that *were* retrieved check COMPLIANT. Service outputs "no violation found." The business proceeds; it is in fact operating an uncertified cross-border processing arrangement. Confident, cited, wrong, and catastrophic.

Fix: make "no violation" the explicitly asymmetric case. Never emit "compliant/không vi phạm"; emit at most "no violation found among the obligations retrieved as of T — this is not a compliance clearance," gated behind an obligation-type coverage floor (did we retrieve across the mandatory obligation classes for this sector?) and forced to `needs_review`/abstain when coverage is low. Add an acceptance test: scenario with a deliberately omitted controlling obligation → service must NOT assert compliant.

### C3 — It markets the W3 3-gate verifier as the differentiator, but W3's own audit says those gates miss exactly this
§1 step 3 (line 36): *"mỗi kết luận neo điều–khoản + ngày (verify 3 cổng W3 — đây là chỗ ARCCS thiếu)."* W3 `§8-C1` (read directly) says in plain terms: **the 3 gates only verify citations that are already present; they do NOT check that retrieval was sufficient. A controlling provision missed → the LLM answers from general rules → all 3 gates pass → wrong but uncaught.** So the one capability W7 brags about as its edge over ARCCS is the capability W3 flagged as *not fixing the false-clear problem*. W7 cites the gates as if they close the gap they explicitly do not close.

This is the mechanism behind C2. It also drags in W3 C2 (no distinction between "law is silent" and "retrieval missed"), C3 (hard `as_of` filter wrongly discards transitional/grandfathered provisions that still govern — directly relevant to "was this activity compliant as of event date"), and H3 (`in_force` is boolean at eId level, so a repealed sub-clause inside a live article slips through). None are mentioned in W7.

Fix: §1 must require the W3 **recall/sufficiency floor at runtime** (not offline eval only), must consume the `insufficient_retrieval` vs `no_governing_provision` distinction, and must not hard-filter transitional provisions. Drop the claim that "verify 3 cổng" is the differentiator; the differentiator has to be the sufficiency floor, which W7 never names.

### C4 — The two new accusatory roles are higher-risk than Judgment Analysis yet get weaker guardrails
W6 §1.4 treats `JudgmentAnalysisService` as **high-risk** and engineers it: QĐ 33/2026 posture, mandatory HITL, second-opinion framing, **high-risk logging spec, conformity-assessment dossier, portal registration, VN contact point** (its "Critical C4"), plus LAW-TRUE + integrity_note. Judgment Analysis is *retrospective* — it analyses an already-decided `bản án`.

W7 §2/§4 adds **investigator** (evidence→statute, builds a case theory) and **procuracy-decision** (evaluates evidence, frames charges). These are *prospective and accusatory against a living, not-yet-convicted person*. Their guardrail in W7 is **only** LAW-TRUE + integrity_note (§2 line 51: "nhắc lại cho vai kiểm sát/điều tra"). The integrity_note addresses bias-by-status — the wrong axis. It does nothing about:
- **Presumption of innocence / burden of proof:** a tool that maps evidence → "constitutes crime X" and "drafts charges" produces an inculpatory artifact. Nothing requires it to surface exculpatory evidence symmetrically, to abstain more readily, or to refuse to assert guilt.
- **Over-reach / fabrication:** `multirole_and_loophole.md` warns that PDP-style outcome-only training caused **"recall inflation / precision collapse"** — i.e., systematic over-charging. W7 adopts PDP's task framing (§2) without adopting that warning.
- **High-risk compliance scoping:** these roles almost certainly fall under QĐ 33/2026 litigation-support high-risk (same basis as §1.4, arguably stronger), yet W7 never claims them as high-risk systems and never attaches the §1.4 logging/conformity/registration/contact-point obligations.

Failure scenario: investigator role maps a thin evidence set to Điều X cấu thành, drafts a chargeable theory, omits the one fact that negates intent. A procurator relies on the "second opinion," the labeled-AI artifact enters the file, a person is charged. The platform produced an accusatory legal instrument with less compliance machinery than it applies to analysing a closed case.

Fix: the accusatory roles need **stronger** guardrails than Judgment Analysis, not the same: (a) explicitly scope them as QĐ 33/2026 high-risk and attach the full §1.4-C4 engineering (immutable logging, conformity dossier, registration, VN entity/BCA); (b) a hard invariant that the system never asserts guilt/"has committed," only "evidence E, if accepted, maps to element e of Điều X" with mandatory surfacing of contrary/exculpatory evidence; (c) higher abstention thresholds; (d) acceptance tests for exculpatory-symmetry and no-guilt-assertion. Alternatively, defer these roles until the compliance machinery is built — do not ship accusatory output on an integrity_note alone.

### C5 — "Defensive posture" for loophole advisory is a label, not a control; the named controls don't bind
§3 line 62 states the right *intent* (point out where the law is unclear/silent/contradictory for prevention, NOT an evasion playbook) and names three controls: **for professionals, HITL, labeled.** None of these constrains the payload:
- The **output is identical** whether the reader wants to comply or to evade — "here is where NĐ X is silent / contradicts TT Y, traceable to these provisions" is a map; the map does not change with the user's intent.
- **"For professionals"**: no verification mechanism is specified; and the professional (e.g. the company's own tax counsel) is typically *aligned with the client's avoidance goal*, so gating to professionals does not gate against misuse.
- **HITL**: the human in the loop is the user, not an adversarial reviewer. HITL protects against the model being wrong, not against the human using a correct answer to evade.
- **"Labeled"**: a label on an evasion roadmap is still an evasion roadmap.

Compare LegalSim's *actual* mitigations (from `multirole_and_loophole.md`, the note the spec itself cites as the strongest dual-use treatment): **confine analysis to simulation; avoid jurisdiction-specific guidance; findings not grounded in real judicial data; inform not replace governance.** TraLuat's loophole feature is designed to do the *opposite of every one of those*: it is **grounded in real VN statutes, jurisdiction-specific, provision-traceable, point-in-time accurate** — i.e., maximally actionable. The spec imports LegalSim's defensive *framing* while discarding the constraints that made that framing meaningful. The note even flags that the tax-loophole paper's dual-use handling was "weak/implicit" — W7 lands closer to that weak end than to LegalSim.

Failure scenario: a user asks "where is the 91/2025 PDP regime silent/contradictory about cross-border employee-vs-customer data?" The tool returns a provision-anchored silence/conflict map. The user uses it to structure data flows into the gap. The platform facilitated avoidance; the "defensive" label is on the output.

Fix: either (a) accept that output parity means framing is not a control and impose *structural* constraints LegalSim-style — e.g. restrict to the drafter/regulator/audit perspective by withholding actor-specific "how to position yourself" synthesis, require the output to be addressed to closing the gap (findings formatted as "drafting defect for the legislator/auditor to fix") with the exploit-direction synthesis suppressed; or (b) gate loophole output behind an identity/role regime that is actually adversarial to misuse (e.g. regulator/compliance-officer tenants only, audited), not "professionals." If neither is enforceable, the honest move is to **not ship corpus-wide loophole discovery** — consistent with §6 already ranking it last. The current controls should not be described as sufficient.

---

## HIGH

### H1 — The copyleft "separate service" mitigation is sound for GPLv3 and wrong for AGPL
§4 (line 70) and §5 both treat Indigo (GPLv3) and CourtListener (**AGPL**) with the same remedy: "tách API service." For **GPLv3 (Indigo)** that is reasonable — GPL's copyleft triggers on *distribution* of linked code, so a separate process behind an API genuinely insulates a proprietary frontend. For **AGPL (CourtListener)** it is wrong: AGPL §13 was written precisely to defeat the "run it as a network service" escape — the trigger is *interacting with the program remotely through a computer network.* If TraLuat modifies CourtListener and runs it as its backend, it must offer that modified source to users who interact with it over the network. "Separate service" does not avoid the obligation; it is the obligation's trigger. The visualization note itself said "the license must be cleared with counsel" — the spec dropped that caveat and asserted the boundary suffices.

(Nuance in TraLuat's favour, which the spec should state: if it only consumes CourtListener's *bulk data exports / citation data* and runs none of its code, AGPL does not attach — but §5 lists CourtListener as "ADOPT làm service," i.e. run the code.)

Fix: split the two licenses. For CourtListener, either (a) use data only, run no modified code, and say so, or (b) accept AGPL source-disclosure for that service, or (c) reimplement the citation layer. Restore the "clear with counsel" caveat for both.

### H2 — "Grounded remediation" has no grounding; it is the most fabrication-prone output and has no gate
§1 step 4: *"Remediation generation: cách tránh/khắc phục (grounded, không bịa)."* Grounding mechanisms in this stack verify **which provision applies** (retrieve + the 3 citation gates). Remediation is a **prescriptive, forward-looking recommendation** ("restructure as X / add clause Y / obtain certificate Z") — that text is *not present verbatim in any statute*, so the citation verifier cannot support it. `compliance_advisory.md` confirms: **no benchmark scores remediation quality or citation correctness for advisory**, and commercial tools that do remediation are closed/self-reported. So the single most generative, most prescriptive output is asserted "grounded" with no mechanism and no eval.

This is also where "how to avoid the violation" (§1) blurs into C5's evasion concern: "how to cure a violation" and "how to restructure so the obligation doesn't bite" are a hair apart, and the spec draws no line.

Fix: downgrade remediation to clearly-labeled, non-authoritative, HITL-mandatory suggestions; forbid the "grounded" claim for the prescriptive part; add an eval dimension for remediation (even human-rated) before it is user-facing; and separate "cure a breach" from "restructure around an obligation," suppressing the latter.

### H3 — Free-text scenario intake has no completeness check; incompleteness silently produces confident verdicts
§1 step 1 extracts obligations from a free-text business description. A free-text scenario is *more* underspecified than ARCCS's target-document input, yet W7 provides no fact-sufficiency gate. If the user omits a material fact (volume of data subjects, whether minors, whether the counterparty is overseas), the deontic extraction silently proceeds on the stated facts and returns a verdict. ARCCS at least has `INSUFFICIENT_INFORMATION`/`HUMAN_REQUIRED` labels (per note); W7 maps these to `THIẾU_THÔNG_TIN`/`CẦN_NGƯỜI` (§1 step 3) but never defines **when they fire** — there is no "the determination depends on fact F which the scenario does not state → ask/abstain" loop.

Fix: add a materiality/clarification pass before any verdict — identify facts the obligation set is sensitive to, and if unstated, ask or return `THIẾU_THÔNG_TIN` rather than guess. Make it an acceptance test.

### H4 — "Greenfield / nobody solves effective-date" is overstated and contradicts the spec's own §4
Two problems:
1. **OSS-absence ≠ absolute novelty.** The research notes are careful ("no *open-source* full pipeline," "largely greenfield"). The spec's prose escalates to first-mover / "gần như CHƯA ai làm." But §0's own table concedes commercial RegTech (Deloitte DORA **cites provisions**; Corlytics, Ascent, CUBE, Regology) does scenario→obligation→gap→remediation-with-citation **in production**. The true claim is "first in OSS / first for Vietnam," which is still a good claim — the spec should stop implying first-ever.
2. **Internal contradiction on effective-date.** §0 line 13 and §6 assert *no system (open/academic/commercial) solves "correct provision at date X + jurisdiction."* But §4 **adopts Indigo specifically because it implements point-in-time "law as of T,"** and the viz note says legislation.gov.uk + Indigo are the production gold standard for exactly this, and commercial RegTech does temporal change-management. So the spec simultaneously says point-in-time is unsolved by anyone and that it will reuse the tool that solves it. The defensible, narrower claim: *effective-date-aware **citation grounding inside compliance advisory**, for **Vietnamese**, is unsolved* — not "point-in-time is unsolved."

Fix: restate as "first OSS / first VN," and scope the effective-date gap to "compliance-advisory citation grounding for VN," removing the contradiction with §4.

### H5 — Solver is "mandatory" yet §1 is scheduled as the quick first win: pick one
§1 step 5 and §3 both declare a **solver/symbolic layer mandatory** ("tầng solver BẮT BUỘC," LLM-only unreliable). §6 then recommends building **§1 first** as the clear-commercial-value, pattern-reusable quick win. These are inconsistent: if reliable compliance *requires* hand-formalizing VN norms into Prolog/Z3, then §1 is blocked on the exact bottleneck that kept Regorous niche. `compliance_advisory.md` is explicit that the symbolic tradition "requires hand-formalizing both the law AND the process... heavy, no Vietnamese LegalRuleML corpus exists," and `multirole_and_loophole.md` notes every solver success is a **single statute section** (IRC §121, one scheme) — not a corpus. The spec compresses this unbounded manual effort into one architecture bullet ("Hybrid LLM+solver") with no answer to *who formalizes which VN provisions, in what formalism, to what coverage, at what cost.* That is the central honesty gap the review brief asked about — and the spec hand-waves it.

Fix: decide explicitly. Either (a) solver is a **later, narrow** add-on for a handful of high-value formalizable obligations (then §1 ships LLM+RAG+grounding first, and the spec must be honest that §1's reliability rests on grounding, not a solver), or (b) solver is truly mandatory (then §1 is **not** a quick first win and §6's ordering is wrong). Add an explicit statement of the formalization cost and coverage target, or state that §1 v1 ships without a solver and carries the residual reliability risk.

---

## MEDIUM

### M1 — "Model VN law in Akoma Ntoso to unlock Indigo" ignores the W2 data-model conflict and the conversion cost
§4 line 79 calls Akoma Ntoso modelling "đòn bẩy cao nhất." But (a) W2 already defines its **own** URN/bitemporal schema and `apply_amendment`/`reconstruct_as_of` logic (W2 §2–§3, with the §11 audit fixes) — it is **not** stated to be Akoma Ntoso. "Unlock Indigo's point-in-time" therefore means either adopting Indigo's data model wholesale (which collides with W2's custom temporal design and its hard-won C1/C2/H1–H4 fixes) or building a lossy bridge. (b) Cobalt/Bluebell parsers are tuned to African/Anglo drafting conventions; VN structure (Điều/Khoản/Điểm, VBHN consolidation, partial commencement) may not map cleanly. The spec presents this as a free "unlock" and hides the W2 integration cost and the corpus-conversion effort.

Fix: state whether W2 becomes Akoma Ntoso-native or bridges to it, reconcile with the W2 §11 temporal design, and budget the VN-corpus conversion as real work, not a leverage freebie.

### M2 — Liability for AI-suggested charges, and high-risk scoping of the new roles, are unaddressed
Beyond C4's guardrails: the spec never names *who is legally responsible* when an investigator/procuracy output contributes to a wrongful charge, nor does it scope these roles under QĐ 33/2026 / NĐ 356 Đ21-22 (VN entity + BCA cert) the way W6 §1.4 does for Judgment Analysis. Compliance scoping for the most exposed feature is simply missing.

Fix: add a compliance-posture subsection for the accusatory roles mirroring W6 §1.4, and a liability/role-boundary statement (the tool assists a human officer who remains the decision-maker and the responsible party).

### M3 — The Dahl 69–88% hallucination figure is used out of context to justify the solver
§1 step 5 cites "LLM thuần ảo giác 69–88% — Dahl 2024" as the argument for a mandatory solver. Per `multirole_and_loophole.md`, that figure is for LLMs answering **without retrieval grounding.** TraLuat is a grounded (W3 retrieval + 3-gate) system, so the number does not describe TraLuat's baseline and does not, by itself, license "therefore we must add a solver." The solver may still be justified for *conflict/ambiguity detection* (a different argument), but the stat as deployed is misleading.

Fix: cite the ungrounded caveat, and justify the solver on conflict/temporal-logic grounds rather than on a hallucination rate that applies to a system TraLuat is not.

### M4 — Every compliance verdict rides on W2 in_force correctness, whose gaps are unresolved and unmentioned
A "violation / no violation at date T" turns entirely on whether a provision was in force at clause level on T. W2 §11 flags **H3 partial commencement not modelled** (`valid_from` conflated with document-level `date_effective`, which "phá `in_force()`"), and W3 §8 **H3** flags `in_force` is boolean at eId level (repealed sub-clause in a live article slips). W2 §11 **H4** flags conflict-resolution defaulting to "later-general overrides earlier-special" (usually wrong) unless escalated to human. W7 §1 depends on all three and mentions none.

Fix: add an explicit dependency note that §1 cannot be correct until W2 H3/H4 and W3 H3 land, and that compliance verdicts must degrade to `needs_review` when commencement/conflict state is `unresolved`.

### L1 — Uncritical echo of unverified secondhand claims
§0/§3 reproduce claims the notes marked unverified: System-206 ">97% accuracy" (note: closed prototype, test-phase, no rollout verified), L4M "solver-backed adjudication with formal guarantees" (note: "primary paper not located, treat as unverified"), and several future-/recently-dated arXiv IDs (2605.x, 2606.x, 2608.x, 2601.x) carried without the notes' "license/claim not verified" hedges. Minor, but a spec that sells itself on citation rigour should not launder unverified marketing numbers.

Fix: carry the notes' hedges into the spec, or drop the numbers.

---

## What is genuinely fine (credit where due)

- **obligation_type mandatory/default reuse** (§1 step 2, from W6 §1.1-C2) is a correct, load-bearing insight that prevents mass false-positive "violations" for civil-law default rules. Keep it.
- **License hygiene posture** (§5): flagging ARCCS's placeholder license as "STUDY, don't reuse," marking unverified repo licenses, and separating copyleft services is better practice than most specs — the *GPLv3* reasoning is sound (only the AGPL case, H1, is wrong).
- **Building loophole last** (§6, "khó + nhạy cảm") is the right call; the problem is that §3 oversells the controls, not the sequencing.
- **LAW-TRUE + integrity_note** is a thoughtful mechanism for status-bias — it is just the wrong/insufficient axis for accusatory roles (C4), not a bad idea in itself.
- **Citation + effective-date as the moat**, scoped to open-source / Vietnamese compliance advisory, is a real and defensible differentiator (once H4's overstatement is trimmed).
- The underlying **research notes are careful and well-caveated**; most of the spec's overstatement comes from compressing those hedged notes into confident prose, not from bad research.

---

## One-line verdict
The research is solid; the spec over-sells it and under-engineers it. W7 is currently a persuasive strategy memo that (1) lacks the acceptance tests / interfaces / audit-inheritance its siblings have, (2) forgets to guard its highest-liability output (false-clear) and its highest-liability feature (accusatory roles + loophole), and (3) hand-waves the solver bottleneck that is the crux of whether any of this is buildable. Do not treat §1–§4 as implementable until C1–C5 are resolved.
