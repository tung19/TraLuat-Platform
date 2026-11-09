# No-License / Pattern-Study Repos for TraLuat — Architecture Reuse Decisions

Scope note (per coordinator update): This is a REFERENCE/LEARNING phase, not commercial yet. Verdicts below are based on **architectural / feature learning value**, NOT license. License is recorded as a one-line note per repo for later (when TraLuat commercializes). Legal boundary for later: reading a repo and reimplementing its design clean-room = OK; copying its source code into a commercial product with no license = NOT OK.

All 8 repos were verified live via the GitHub API on 2026-11-05 (metadata, license endpoint, recursive file tree, README, and key source files read directly).

## TL;DR verdict table

| Repo | Conf/Year | Jurisdiction | Maturity | License | Verdict |
|---|---|---|---|---|---|
| LegalGraphRAG (XMUDeepLIT) | ACL'26 Main | China, criminal (CAIL/CMDL) | Active, well-structured | NONE | **CLONE & STUDY — high** |
| L-MARS (boqiny) | ICML'26 AI4Law workshop (poster) | US, statutory QA | Active, clean, small | NONE | **CLONE & STUDY — high** |
| LeSICiN (Law-AI) | AAAI 2022 | India, IPC statutes | Dormant (2024) | NONE | **CLONE & STUDY — high** (for L3) |
| ACAL (loc110504) | Canadian AI 2026 | US, single-label legal QA | Active, demo-grade | NONE | **CLONE & STUDY — medium** |
| AgentsCourt / SimuCourt (Zhitao-He) | EMNLP'24 Findings | China, crim/civil/admin | Dormant (Dec 2024) | NONE | **READ PAPER + skim code** |
| CaseLink (yanran-tang) | SIGIR 2024 | COLIEE (common-law retrieval) | Semi-active | NONE | **READ PAPER ONLY** |
| AgentCourt (relic-yuexi) | arXiv Aug 2024 | China, civil | Dormant (Sep 2024) | NONE | **READ PAPER ONLY** (one idea: experience-memory loop) |
| AALawyer (theSleepyPig) | ACL 2026 Main | China, statutes+precedent | Active but very messy | NONE | **READ PAPER ONLY** (repo not worth cloning) |

---

## 1. LegalGraphRAG — github.com/XMUDeepLIT/LegalGraphRAG

**One-line license note:** No LICENSE file (GitHub license endpoint returns 404). Code reuse later = NO without a license; architecture study/reimplement = OK.

**Status/maturity:** Active — last push 2026-10-31, 70 stars. ACL'26 Main ("Official code"). Best-engineered repo in this set: clean `core/` package, config via `.env`, multi-model support (Qwen3, DeepSeek-V3, GPT-4o-mini, InternLM3, GLM4, Gemma3), bundled 14,049-case graph corpus + 568-case CAIL / 1,374-record CMDL eval sets with SHA256SUMS. Baselines included (HippoRAG2, LightRAG, RAPTOR, DIGIMON, naive).

**Jurisdiction skew:** Chinese **criminal** law (CAIL/CMDL; task = charge + law-article + imprisonment-term prediction). Prompts default `zh`. The *task* is Chinese-criminal, but the *architecture* is jurisdiction-agnostic.

**Architecture (read from source, not just README):**
- **3-agent pipeline** in `core/agents/`:
  - `researcher.py` — "Researcher" does ontology alignment + **three parallel retrieval operators**: `R(q) = R_sem (semantic) ∪ R_com (community) ∪ R_chg (charge-anchored)`. Charge-anchored retrieval predicts the likely charge first, then pulls the statute articles linked to that charge from the graph (`charge_anchored_articles`). Query text is built from 4 ontology dimensions: defendant_info, criminal_acts, victim/property details, intent/remorse.
  - `auditor.py` — **"Auditor" hard-gate.** `audit()` loops over every retrieved article and calls `verify_article()` (an LLM applicability check against the defendant facts); only articles that pass are kept. Then `prune_unsupported_cases()` **drops every retrieved precedent/fact that does not cite at least one surviving article.** This is a true verify-then-prune gate between retrieval and generation.
  - `adjudicator.py` — "Adjudicator" calls `synthesize_judgment()` over the *verified* article set + verified cases to produce charge/article/term. It never sees unverified evidence.
- **Multi-layer legal KG** in `core/graph_construct/`: `fact_graph.py`, `feature_graph.py`, `ontology_graph.py`, `rule_graph.py`, wired through `graph_db.py` (`GraphDBManager`). Note: the repo ships **4 graph layers** (fact / feature / ontology / rule), not the "3-layer" named in the task brief — flag this when planning.
- Data flow: preprocess (`case_seg`, `get_features`, `preJudge`) → build/load graph (`qwenX_graph_db.pkl`) → Researcher retrieves → Auditor verifies+prunes → Adjudicator synthesizes → `evaluation/` scores.

**Reusable design ideas for TraLuat:**
- **(L6 grounding/verify) The Auditor hard-gate** is the single highest-value pattern here: per-article applicability verification + "prune any precedent not supported by a surviving article." Direct analog for TraLuat: before any Vietnamese statute/precedent reaches the answer synthesizer, gate it through an applicability check and drop orphaned citations. Clean-room reimplement.
- **(L8 multi-role) Researcher→Auditor→Adjudicator** separation (retrieve / verify / decide) with the decider only seeing verified evidence.
- **(L3 linking) Charge-anchored retrieval** (`R_chg`): predict the legal category, then traverse the graph edge category→articles. For VN civil law, analog = predict the relationship/dispute type, then pull the governing Bộ luật / Nghị định articles linked to it.
- **(L3) The 4-layer graph split** (facts vs. case-features vs. ontology vs. rules) is a useful separation-of-concerns template for a VN statute+case KG.

**FINAL VERDICT: CLONE & STUDY — high learning value.** It is the closest architectural match to TraLuat's L8+L6+L3 stack, is actively maintained and cleanly structured, and the Auditor gate is directly reimplementable. Clean-room reimplement the agent split and the verify-then-prune gate; do not lift the Chinese-criminal prompts/data.

---

## 2. L-MARS — github.com/boqiny/L-MARS

**One-line license note:** No LICENSE file (404). Reuse NO later; study/reimplement OK.

**Status/maturity:** Active — last push 2026-07-20, 15 stars. ICML 2026 AI4Law **workshop poster** (not a main-conf paper — calibrate expectations). Paper arXiv 2509.00761 (Sep 2025, verified). Clean small package (`lmars/`, `eval/`, `prompts/`). Ships `LegalSearchQA` dataset (HF) + bar-exam QA.

**Jurisdiction skew:** US law. Evidence sources are **CourtListener** (US case law), Serper web search, Tavily, and local BM25 RAG. Not civil-law, but the verification machinery is jurisdiction-neutral.

**Architecture:**
- **4-agent pipeline** (`lmars/agents.py`, `workflow.py`): **Query Agent** (decompose question into intent + jurisdiction + date scope) → **Search Agent** (multi-source retrieval) → **Judge Agent** (sufficiency check: factual support, jurisdiction match, temporal specificity, contradiction; flags missing info) → **Summary Agent** (answer with inline citations). Two modes: Simple (single pass) and Multi-Turn (iterate until evidence sufficient or max iterations).
- **Citation-Faithfulness Audit** (`lmars/verify_agent.py`, `faith_search/`): a **VerifyAgent** decomposes the answer into atomic claims and labels each claim vs. its cited source with a **6-class taxonomy**: `supported / partially_supported / unsupported / citation_unreachable / no_citation / verifier_error`. Scored with strict-ALCE precision/recall under **cross-provider judging** (answerer and verifier from different model families so a model doesn't grade itself).
- **Faith-Search** (`faith_search/router.py`, `aggregator.py`, `workflow.py`): optional post-draft repair — re-verify each claim, then **repair an unreachable citation with a freshly retrieved source, or drop it** rather than keep a broken citation. Reported to push unreachable-citation rate below 1%.

**Reusable design ideas for TraLuat:**
- **(L6 grounding/verify) The claim-level citation audit + 6-class taxonomy** is the standout. TraLuat analog: decompose each answer into atomic legal claims, verify each against the cited VN statute/precedent, label with a reachability+entailment taxonomy, and gate/repair. This is more granular than LegalGraphRAG's article-level gate and complements it.
- **(L6) Faith-Search repair loop** — don't just flag a bad citation, re-retrieve or drop it.
- **(L8) Query Agent's jurisdiction + date-scope decomposition** — critical for VN law where "which law is currently in force / which amendment applies as of date X" matters a lot. Reimplement temporal/jurisdiction gating.
- **(verification methodology) Cross-provider judging** — use a different model family to verify than to generate, to avoid self-grading bias.

**FINAL VERDICT: CLONE & STUDY — high learning value.** Small, clean, and the citation-faithfulness audit + Faith-Search repair is the best-articulated grounding/verify pattern of the set and highly transferable to VN. Caveat: workshop-poster scale, US-only data; reimplement the verifier, don't expect a drop-in product.

---

## 3. LeSICiN — github.com/Law-AI/LeSICiN

**One-line license note:** No LICENSE file (404). Reuse NO later; study/reimplement OK. Dataset is separately on Zenodo (doi.org/10.5281/zenodo.6053791) — check its own terms before using data.

**Status/maturity:** Dormant — last push 2024-04-20, 25 stars. Paper: AAAI 2022 (Paul, Goyal, Ghosh). Compact PyTorch codebase (`model/` = basicmodules/submodules/model, `data_helper.py`, `helper.py`, `run.py`), config-driven. Not an LLM system — it's a trained heterogeneous-graph neural model.

**Jurisdiction skew:** Indian law, Indian Penal Code (IPC). India is technically common-law, BUT the **task** — Legal Statute Identification (map case facts → the statute sections that apply) — is exactly the statute-centric task that fits Vietnamese civil law better than any courtroom-simulation repo here.

**Architecture:**
- Task = multi-label **Legal Statute Identification (LSI)**: given fact text, predict which statute Sections apply.
- Models statutes + documents as a **heterogeneous graph** with node types Act / Chapter / Topic / Section / Fact, plus (a) a **label tree** (Act→Chapter→Topic→Section hierarchy) and (b) a **Fact↔Section citation network**.
- `submodules.py`: Text Encoder (LSTM+attention over sentences, optional sent2vec) + Graph Encoder + a **Matching Network** that correlates textual and graph features.
- Uses **metapath schemas** per node type (sampled metapath instances) to propagate structure — so a Section's representation is informed by its neighbors in both the label tree and the citation net.
- **Inductive link prediction**: can place a *new* test document (whose graph edges are unknown at train time) and predict links to existing Section nodes — i.e., classify unseen cases against the fixed statute graph.

**Reusable design ideas for TraLuat:**
- **(L3 case↔statute linking) The whole model is the reference design for L3.** The case↔statute citation graph + statute label tree (Act→Chapter→Topic→Section) maps almost 1:1 onto VN's hierarchical structure (Bộ luật → Phần → Chương → Mục → Điều → Khoản). Reimplement the "statute-hierarchy tree + fact→article citation graph" as TraLuat's L3 schema.
- **(L3) Inductive multi-label linking** — classify a brand-new case against the fixed statute graph without retraining. Exactly what a production VN legal engine needs.
- **(L6) Text+graph matching network** — fuse semantic similarity with graph-structural signal rather than relying on embeddings alone.

**FINAL VERDICT: CLONE & STUDY — high learning value (for L3 specifically).** Dormant and pre-LLM, so study it as a *data-model blueprint*, not a runnable component: it is the cleanest existing template for the case↔statute↔hierarchy graph TraLuat needs at L3. The statute-identification framing transfers to VN civil law better than any courtroom repo here.

---

## 4. ACAL — github.com/loc110504/ACAL

**One-line license note:** No LICENSE file (404). Reuse NO later; study/reimplement OK.

**Status/maturity:** Active — last push 2026-07-05, 9 stars. Paper: "Neuro-Symbolic Adaptive Collaboration of Arena-Based Argumentative LLMs for Contestable Legal Reasoning," **Canadian AI 2026 (PMLR)**, arXiv 2602.18916. NOTE: the task brief tagged ACAL "ACL 2026" and "neuro-symbolic argumentative" — the neuro-symbolic part is right, but it is Canadian AI 2026, not ACL (AALawyer is the ACL 2026 one). Demo-grade code: single-file modules, built on **LangGraph**. Authors are Vietnamese researchers (Cao/Nguyen et al.) — relevant for local collaboration, though the repo data is US (`data/hearsay/`, `data/learned_hands_courts/`).

**Jurisdiction skew:** US legal-QA datasets (hearsay, Learned Hands). Single-label classification tasks. Transfer is conceptual, not data-level.

**Architecture:**
- **A-QBAF** = Arena-based Quantitative Bipolar Argumentation Framework. `qbaf_scorer.py` builds a graph of `QBAFArgument` nodes (each: content, base_score 0–1 from an LLM, support/attack edges, parent option Yes/No) and computes **gradual-semantics argument strength** (e.g., weighted_sum = Σsupport − Σattack) to resolve conflicting claims into a scored Yes/No decision. This is the **neuro-symbolic** core: LLMs produce arguments + base scores, a symbolic argumentation calculus aggregates them.
- `legal_agents.py`: a registry of **10 legal-profession role personas** (Private Practice Lawyer, Corporate Counsel, Judge, Prosecutor, Public Defender, Paralegal, Law Clerk, Compliance Officer, IP Attorney, Legal Analyst), each with expertise_areas / focus_priorities / argument_style — used to generate diverse arguments.
- `graph.py` / `main.py`: a **LangGraph state machine**: rag_retrieval → (plan) → multi_agent_argument_generation → **human_review** (conditional loop-back edge) → argument_validation → final_answer_generation. `semantic_relation_analyzer.py` infers support/attack relations between arguments semantically.
- Explicit **human-in-the-loop** node and "contestable" design — the argument graph is inspectable and editable.

**Reusable design ideas for TraLuat:**
- **(L8 reasoning/multi-role) Explicit support/attack argument graph with numeric strengths** — instead of a single LLM verdict, generate pro/con arguments, score them, and aggregate symbolically. Gives an auditable, contestable rationale, valuable for a legal product that must justify answers.
- **(L8) Role-persona registry** to diversify argument generation (adversarial coverage without a full courtroom sim).
- **(explainability) Human-review loop + QBAF** make the reasoning inspectable — a strong UX/trust pattern for TraLuat's output layer.

**FINAL VERDICT: CLONE & STUDY — medium learning value.** The neuro-symbolic argument-scoring (A-QBAF) and the contestable/human-review design are genuinely novel and worth reimplementing for TraLuat's explainability story; but the repo is demo-grade (US data, single-file modules, commented-out nodes) so treat it as a concept reference. Local-author bonus for potential contact.

---

## 5. AgentsCourt / SimuCourt — github.com/Zhitao-He/AgentsCourt

**One-line license note:** No LICENSE file (404). Reuse NO later; study/reimplement OK.

**Status/maturity:** Dormant — last push 2024-12-30, 19 stars. EMNLP 2024 Findings, arXiv 2403.02959 (verified). Code is a loose collection of scripts under `AgentsCourt/` (not a packaged library): retrieval scripts (`retrieve_bm25.py`, `retrieve_pyserini.py`, `retrieve_rerank.py`), judge pipeline scripts (`judge_analysis_record.py`, `judge_case_refine.py`, `judge_final_once.py`), and a `role/` dir (chat_agent, role_playing, main_court) plus many `.txt` system prompts. Ships the SimuCourt dataset.

**Jurisdiction skew:** Chinese law — covers criminal, civil, AND administrative (separate extract prompts for each: `crimial_extract_prompt.txt`, `civial_extract_prompt.txt`, `administrative_extract_prompt.txt`). Civil + administrative coverage makes it more relevant to VN than purely criminal repos.

**Architecture:**
- **Court-debate simulation** for judicial decision-making: plaintiff / defendant agents (`plaintiff_message*.txt`, `defendant_message*.txt`) debate; a **judge agent** runs a multi-step analysis → record → refine → final pipeline (the `judge_*` scripts and `judge_analysis*.txt` prompts).
- **Legal-knowledge augmentation**: a retrieval stack (BM25 → Pyserini → rerank) over a legal-knowledge base + precedent documents, with law-matching (`macth_laws.py` [sic], `extract_laws_in_document.py`) feeding the judge's reasoning. Separate evaluation scripts for criminal / laws / other.

**Reusable design ideas for TraLuat:**
- **(L8) Judge multi-step refine loop** (analysis → record → refine → final) — a structured decision pipeline rather than one-shot generation.
- **(L6/L3) Retrieve→rerank→law-match grounding chain** before the judgment, with explicit statute extraction from precedent documents.
- **(coverage) The crim/civil/admin split by document type** is a useful reminder that VN needs per-domain extraction prompts.

**FINAL VERDICT: READ PAPER + skim code.** Strong, relevant ideas (civil/admin coverage, judge-refine loop, retrieve-rerank-match grounding) but the repo is dormant and script-soup rather than a reusable library — you'll learn the design faster from the paper + a skim of the prompt files than from trying to run it. Clone only to read the `.txt` prompts and the judge pipeline order.

---

## 6. CaseLink — github.com/yanran-tang/CaseLink

**One-line license note:** No LICENSE file (404). Reuse NO later; study/reimplement OK.

**Status/maturity:** Semi-active — last push 2026-08-17, 11 stars. SIGIR 2024, arXiv 2403.17780 (verified; authors Tang, Qiu, Yin, Li, Huang). Research code: shell-driven (`CaseLink2022_run.sh`, `Graph.sh`, `BM25_matrix_generation.sh`), `CaseLink_model.py`, `train.py`, `main.py`. Depends on a sibling repo **CaseGNN** for embeddings.

**Jurisdiction skew:** COLIEE 2022/2023 (Canadian/Japanese common-law case retrieval). Task = **case-to-case** legal retrieval, not case-to-statute. Weaker fit for VN statute-centric civil law.

**Architecture:**
- Builds a **case-association graph**: nodes = cases; edges from (a) BM25 ranking matrix (top-k textual neighbors, `--topk_neighbor` ∈ {3,5,10,20}) and (b) a **charge/legal-concept co-occurrence threshold** (`--charge_threshold` ∈ {0.85,0.9,0.95}, `federal_charges_coliee.txt`).
- Node features = CaseGNN embeddings. A GNN (`CaseLink_model.py`) learns **inductive** case representations over this graph for ranking candidate precedents (hard-negative mining via `hard_neg_top50_*.json`).

**Reusable design ideas for TraLuat:**
- **(L3 precedent linking) Case-case graph construction via textual (BM25) + legal-concept-overlap edges** — a concrete recipe for building TraLuat's precedent-similarity graph layer.
- **(L3) Inductive GNN ranking** so new cases can be placed into the precedent graph without retraining.

**FINAL VERDICT: READ PAPER ONLY, repo not worth cloning.** The two edge-construction ideas (textual + charge-overlap) are worth knowing for TraLuat's precedent layer, but it's case↔case retrieval on common-law data, requires the separate CaseGNN repo to run, and adds little beyond LeSICiN (which already gives the case↔statute graph TraLuat actually needs). Get the two ideas from the paper.

---

## 7. AgentCourt — github.com/relic-yuexi/AgentCourt

**One-line license note:** No LICENSE file (404). Reuse NO later; study/reimplement OK.

**Status/maturity:** Dormant — last push 2024-09-05, 98 stars (most-starred here, but stale). arXiv 2408.08089 (verified). Small repo: `agent.py`, `main.py`, `EMDB/db.py` (experience-memory DB), `LLM/` (many client wrappers incl. ERNIE/wenxin, zhipuai, offline), `example_role_config.json`. Dataset on HF (youzi517/AgentCourt). Built on ERNIE-Speed-128K.

**Jurisdiction skew:** Chinese civil law, evaluated by Chinese legal experts; auto-eval via LawBench. Chinese-skew.

**Architecture:**
- **Full adversarial courtroom simulation**: judge + plaintiff lawyer + defense lawyer (+ others) as autonomous LLM agents, configured via `example_role_config.json`.
- **Adversarial evolution via reflection + experience memory**: `reflect_and_summary()` after each simulated case writes distilled experience into an **experience-memory DB** (`EMDB/db.py`) spanning three databases; agents retrieve past experience to improve. They simulated ~1000 cases ("a decade of experience") and report measured improvement. (At test time, reflection/summary is disabled.)

**Reusable design ideas for TraLuat:**
- **(L8) The experience-memory reflection loop** — after handling a case, distill a reflection and persist it to a memory DB that future queries retrieve. This is the one idea worth lifting conceptually: a self-improving experience store for TraLuat.

**FINAL VERDICT: READ PAPER ONLY (repo not worth cloning).** Dormant since 2024, tied to ERNIE/Chinese-civil prompts, and the courtroom-sim framing is heavier than TraLuat needs. Extract exactly one pattern — the reflection + experience-memory loop — from the paper; the code adds little.

---

## 8. AALawyer — github.com/theSleepyPig/AALawyer

**One-line license note:** No LICENSE file at repo root (404). (It bundles an entire copy of LLaMA-Factory, which carries its *own* Apache-2.0 LICENSE — that covers LLaMA-Factory only, not AALawyer's own code.) Reuse of AALawyer's own code NO later; study/reimplement OK.

**Status/maturity:** Active — last push 2026-06-28, 6 stars. **ACL 2026 Main** (verified: aclanthology.org/2026.acl-long.633). BUT the repo is a **mess**: it vendors the whole LLaMA-Factory tree, has files like `Interface/app copy.py`, `index copy 2.html`, and an `a/` directory with dozens of ad-hoc scripts (`-eva31.py`, `evabqwen3.py`, `evafuzi.py`, `evawisdom.py`, `generateRAG1_v3.py`, …). Not organized for reuse.

**Jurisdiction skew:** Chinese law — backbone is "AA-LeLLM" built on DeepSeek-R1-Distill-Qwen-7B via IPT+SFT over Chinese articles/legal instruments; baselines are Chinese legal LLMs (fuzi, wisdom, lawllm, disc). Chinese-skew.

**Architecture (from paper/README):**
- Title: "Mitigating Legal Hallucinations via Symbolic Constraints and Analogical Precedents."
- **Dual-retriever framework**: **SCR = Symbolic Constrained Retrieval** (retrieve statutes under symbolic/structural constraints) + **APR = Analogical Precedent Retrieval** (retrieve precedents by analogy to the query facts). The two retrievers are complementary and feed a fine-tuned legal LLM (AA-LeLLM; LoRA IPT→SFT pipeline).

**Reusable design ideas for TraLuat:**
- **(L3 statute + precedent linking) The SCR + APR split** is the key idea: one retriever for *statutes under symbolic constraints* (e.g., jurisdiction/effective-date/article-type filters) and a separate one for *analogical precedents*. Maps cleanly onto TraLuat L3: a symbolic statute retriever (hard constraints on VN article validity/scope) + an analogical precedent retriever. Worth reimplementing the two-retriever separation.
- **(L6) Symbolic constraints on retrieval** as a hallucination guard — only return statutes satisfying structural constraints.

**FINAL VERDICT: READ PAPER ONLY, repo not worth cloning.** The SCR+APR dual-retriever concept is genuinely relevant to TraLuat's L3 and worth reimplementing, but the published code is disorganized (vendored LLaMA-Factory + scratch scripts) and Chinese-skewed — you'll get everything useful from the ACL 2026 paper (open PDF at aclanthology.org/2026.acl-long.633.pdf) far faster than from the repo.

---

## Cross-cutting notes & flags

- **License:** every one of the 8 repos has NO LICENSE file (confirmed via GitHub license endpoint 404 on each). For the current learning phase this doesn't block study. Record for commercialization: none of this code may be copied into a commercial product without obtaining a license from each author.
- **Jurisdiction skew:** 4 Chinese (LegalGraphRAG, AgentsCourt, AgentCourt, AALawyer), 2 US (L-MARS, ACAL), 1 Indian (LeSICiN), 1 COLIEE common-law (CaseLink). None are Vietnamese or civil-law-native. The **statute-centric** repos (LeSICiN, AALawyer's SCR, LegalGraphRAG's charge-anchored retrieval) transfer best to VN civil law; the **courtroom-simulation** repos (AgentCourt, AgentsCourt) transfer least.
- **Dormant/demo flags:** AgentCourt (Sep 2024), AgentsCourt (Dec 2024), LeSICiN (Apr 2024, pre-LLM) are dormant. ACAL and AALawyer are active but demo/scratch-grade. Only LegalGraphRAG and L-MARS are both active AND cleanly engineered.
- **arXiv / venue flags to double-check:**
  - LegalGraphRAG: GitHub homepage field points to **arXiv 2605.28120** (would be May 2026). The README itself *comments out* the paper link and references a ResearchGate entry instead. Treat the exact arXiv ID as **unverified** — confirm before citing.
  - ACAL brief said "ACL 2026"; it is actually **Canadian AI 2026 (PMLR)**, arXiv 2602.18916. The "ACL 2026 Main" repo is **AALawyer**, not ACAL.
  - L-MARS is an ICML 2026 AI4Law **workshop poster**, not a main-conference paper — calibrate weight accordingly.
  - Verified-valid IDs: AgentCourt 2408.08089, AgentsCourt 2403.02959, CaseLink 2403.17780, L-MARS 2509.00761, ACAL 2602.18916, AALawyer aclanthology 2026.acl-long.633.
- **Highest-leverage reimplementations for TraLuat (ranked):**
  1. LegalGraphRAG Auditor verify-then-prune gate (L6) + Researcher/Auditor/Adjudicator split (L8).
  2. L-MARS claim-level citation-faithfulness audit + Faith-Search repair + cross-provider judging (L6).
  3. LeSICiN case↔statute heterogeneous graph + statute hierarchy tree + inductive multi-label linking (L3).
  4. AALawyer SCR+APR dual-retriever separation (L3/L6) — from paper.
  5. ACAL A-QBAF argument-strength scoring + contestable/human-review (L8/explainability).
