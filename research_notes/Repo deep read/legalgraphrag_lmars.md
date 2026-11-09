# LegalGraphRAG + L-MARS — deep read for TraLuat L6 (Grounding/Verify) & L8 (Reasoning/Orchestration)

Read-only extraction. All paths absolute. Two repos:
- `refs/LegalGraphRAG` — Chinese criminal-law judgment prediction; multi-agent graph RAG (ACL 2026). Maps best to **L8** (multi-role reasoner + Auditor hard-gate) and the applicability half of **L6**.
- `refs/L-MARS` — US-law QA with agentic search + claim-level citation-faithfulness audit (ICML 2026 AI4Law). Maps best to **L6** (claim-level verifier + repair loop).

---

# PART A — LegalGraphRAG

## A1. Directory map / where orchestration lives

```
refs/LegalGraphRAG/
├── core/
│   ├── LegalGraphRAG.py          # top-level class: config, model load, graph build/load
│   ├── utils/util.py             # ←★ THE ORCHESTRATOR: analyze_case() runs the 3-agent pipeline
│   ├── agents/
│   │   ├── researcher.py         # Researcher agent (retrieval)
│   │   ├── auditor.py            # ←★ Auditor agent (hard-gate: verify + prune)
│   │   └── adjudicator.py        # Adjudicator agent (final judgment)
│   ├── judge/
│   │   ├── judge_law.py          # ←★ verify_article() — per-article applicability check
│   │   └── judge_crime.py        # synthesize_judgment() / judge_crime()
│   ├── graph_construct/          # the 4-layer HierarGraph
│   │   ├── feature_graph.py      # HierarGraph construct + retrieve_evidence() orchestration
│   │   ├── fact_graph.py         # fact layer + charge_anchored_articles()
│   │   ├── ontology_graph.py     # ontology layer: kNN, communities, semantic/community retrieval
│   │   ├── rule_graph.py         # rule layer: judge_dep (checklist) + related_laws on Law nodes
│   │   ├── graph_db.py           # in-memory graph (networkx-style) + vector index
│   │   └── embedding.py          # bge-m3 embed via HTTP
│   ├── preprocess/
│   │   ├── case_seg.py           # split multi-defendant case into per-defendant narratives
│   │   ├── get_features.py       # LLM extracts 4 ontology dimensions from a case
│   │   └── preJudge.py           # candidate-charge prediction (pre_judge)
│   ├── prompt/{judge,retrieval,preprocess,graph}/__init__.py   # all prompts (EN + _ZH)
│   └── models/                   # qwen3/qwen2.5/gemma3/internlm3/glm4/deepseek_v3/gpt4o_mini
├── run.py                        # CLI, multi-GPU dispatch over cases
└── datas/main_experiment/        # 14,049-case graph corpus + CAIL/CMDL eval sets
```

The multi-agent control flow is NOT in a framework (no LangGraph). It is a plain function:
`core/utils/util.py::analyze_case()` — a linear Researcher → Auditor → Adjudicator pipeline per defendant.

## A2. The agent split Researcher → Auditor → Adjudicator

Orchestrator — `refs/LegalGraphRAG/core/utils/util.py` lines 54-73:

```python
def analyze_case(chatbot, case, law_to_crime, cases_db, retrieve_config):
    case_by_defendant = segment_case_text_withname(chatbot, case["fact"][:1024], case["name"])
    for item in case_by_defendant:
        evidence, retrieved_laws, retrieved_facts = research(chatbot, item, ...)      # RESEARCHER
        if not (retrieved_laws and retrieved_facts):
            continue
        verified_articles, verified_cases = audit(chatbot, item, retrieved_laws, retrieved_facts)  # AUDITOR
        judge_result = adjudicate(chatbot, item, verified_articles, verified_cases)  # ADJUDICATOR
        item["judge_result"] = judge_result
        ...
```

Key architectural fact: **the case is first segmented per-defendant** (`segment_case_text_withname`, prompt `CASE_SEG_PROMPT` in `core/prompt/preprocess/__init__.py`) so each defendant is reasoned about independently. Relevant for TraLuat multi-party civil disputes (each party's claims/defenses reasoned separately).

### Researcher — `core/agents/researcher.py`
Role: align the defendant narrative to ontology features, then retrieve candidate articles + precedent cases. No verification. Produces the evidence set.
- `research()` first calls `get_features()` (LLM → 4 ontology dimensions: `defendant_info`, `criminal_acts`, `victim_property_details`, `intent_remorse`; prompt `GET_FEATURES_PROMPT`).
- Then `gather_evidence()` runs the **union of three retrieval operators** `R(q) = R_sem ∪ R_com ∪ R_chg`:
  - R_sem = semantic match, R_com = community expansion (both in `feature_graph.retrieve_evidence`)
  - R_chg = **charge-anchored** (`charge_anchored_retrieval`): LLM predicts ≤3 charges (`RETRIEVE_LAW_PROMPT`), then graph-traverses charges→linked articles.
- Output passed downstream: `evidence` (raw retrieval trace), `retrieved_laws` (list of article dicts with `id`, `entry`, `description`, `crimes`, **`judge_dep`**, **`related_laws`**), `retrieved_facts` (precedent cases, each annotated with its `crime` and `law` id list by joining to `cases_db`).

### Auditor — `core/agents/auditor.py` (the hard-gate; see A3)
Role: verify each retrieved article for applicability; drop precedents whose only support was a rejected article. Produces `(verified_articles, verified_cases)`.

### Adjudicator — `core/agents/adjudicator.py` + `core/judge/judge_crime.py`
Role: synthesize the FINAL judgment **only from the verified set**. `adjudicate()` → `synthesize_judgment()` which calls the LLM with `JUDGE_CRIME_ALL_PROMPT` and returns strict JSON:
```json
{"charge_name": [...], "law_article": ["第232条", ...],
 "term_of_imprisonment": {"death_penalty": bool, "imprisonment": <months>, "life_imprisonment": bool}}
```
The adjudicator prompt bakes in doctrine: behavior-count determination, imaginative concurrence ("punish the heavier crime"), concurrent punishment for multiple crimes. This is the "judge" role; the verified article set is its only evidence (the gate strips everything unverified before it ever sees it).

**Data passed between agents** (clean hand-off contract):
`Researcher → {retrieved_laws[], retrieved_facts[]}` → `Auditor → {verified_articles[], verified_cases[]}` → `Adjudicator → judgment JSON`. Each stage strictly narrows the set. The adjudicator cannot reach around the gate.

## A3. ★ THE KEY PART — the Auditor hard-gate

Full `core/agents/auditor.py`:

```python
from core.judge.judge_law import verify_article

def prune_unsupported_cases(verified_articles, retrieved_facts):
    law_ids = {str(law['id']) for law in verified_articles}
    filtered_facts = [
        fact for fact in retrieved_facts
        if any(law_id in law_ids for law_id in fact.get('law', []))
    ]
    return filtered_facts

def audit(chatbot, item, retrieved_laws, retrieved_facts):
    verified_articles = []
    for article in retrieved_laws:
        applicable, _ = verify_article(
            chatbot, f"被告人：{item['name']}，描述：{item['description']}", article)
        if applicable:
            verified_articles.append(article)
    verified_cases = prune_unsupported_cases(verified_articles, retrieved_facts)
    return verified_articles, verified_cases
```

So the gate is two steps:
1. **Per-article applicability filter** — every retrieved article must independently pass `verify_article`; rejects are dropped.
2. **Precedent pruning** — a precedent case survives only if it cites at least one *surviving* article (set-membership on `law_ids`). If all of a precedent's articles were rejected, the precedent is dropped. This stops "analogy drift": you can't justify a result with a similar-looking case whose legal basis you just rejected.

### How applicability is decided — `core/judge/judge_law.py::verify_article`

```python
def verify_article(chatbot, case_description, article):
    if type(article) == str:                     # fallback: whole-article yes/no (JUDGE_LAW_PROMPT1)
        judge_res = chatbot.generate_response(JUDGE_LAW_PROMPT1.format(law=article, case=case_description), ...)
        return ("true" in judge_res.lower()), ""
    satisfied, unsatisfied = [], []
    diagnostic_checklist     = article["judge_dep"]       # rule-layer: per-element checklist
    judicial_interpretations = article["related_laws"]    # rule-layer: linked interpretations
    for diagnostic_item in diagnostic_checklist:
        judge_res = chatbot.generate_response(JUDGE_LAW_PROMPT.format(
            law_item=article["description"], related=judicial_interpretations,
            element=diagnostic_item, case=case_description), max_length=128)
        if   "true"  in judge_res.lower(): satisfied.append(diagnostic_item)
        elif "false" in judge_res.lower(): unsatisfied.append(diagnostic_item)
    res = chatbot.generate_response(JUDGE_LAW_PROMPT0.format(
        case=case_description, law=article["description"],
        true_list=satisfied, false_list=unsatisfied), max_length=1024)
    return ("true" in res.lower()), res
```

Mechanism — **element-wise constitutive-element checking**, not a single holistic yes/no:
- Each article carries a `judge_dep` **diagnostic checklist** (its constitutive elements, e.g. "intent", "harmful result") and `related_laws` (judicial interpretations) — both stored on the Law node by the rule layer.
- For EACH element, a tightly-scoped LLM NLI call (`JUDGE_LAW_PROMPT`, output constrained to `true`/`false`) decides whether the case facts satisfy that element, using the article text + judicial interpretations as context.
- A final aggregation call (`JUDGE_LAW_PROMPT0`) takes the satisfied/unsatisfied element lists + article text and emits the article-level `true`/`false`. The prompt explicitly warns the lists may be incomplete and tells the model to re-verify key elements itself.
- The checklist (`judge_dep`) is LLM-generated offline during data prep (`scripts/prepare_law_judge_dep.py`) and frozen on the graph — effectively a cached, structured "elements of the offense" per article.

This is the HARD-GATE TraLuat wants: an article is applicable only if its constitutive elements are individually satisfied against the facts, decomposed element-by-element with per-element true/false, then aggregated. Note: the current repo verifies **citation applicability** (does this article apply to these facts) but has **no explicit effective-date / temporal-validity check** — that is the gap TraLuat must add (L-MARS supplies the `temporally_invalid` idea, see B3).

## A4. The legal knowledge graph — 4-layer, charge-anchored

Confirmed 4 layers (one in-memory graph, four construction/traversal modules under `core/graph_construct/`):

| Layer | File | Nodes / edges | Role |
|---|---|---|---|
| **Fact** | `fact_graph.py` | Nodes: `Cases`, `Laws`, `Crimes`. Edges: `RELATES_TO_LAW` (case→article), `RELATED_CRIME` (article→charge, exact+fuzzy match) | ground truth facts: real precedent cases and their cited articles/charges |
| **Feature** | `feature_graph.py` (orchestrator) + case node `description` = the 4 ontology dims serialized; embedded with bge-m3 | feature-text embeddings per case; drives similarity | the retrievable surface |
| **Ontology** | `ontology_graph.py` | adds `SIMILAR_TO` (kNN top-3 over case embeddings, `run_knn`), `Cluster` nodes + `BELONGS_TO` (Leiden/community detection, `build_communities`), PageRank+degree centrality | groups cases into charge-themed communities; community summaries re-ranked by LLM |
| **Rule** | `rule_graph.py` | writes `judge_dep` (diagnostic checklist) + `related_laws` (judicial interpretations) + `insights` onto each `Laws` node | the verifiable legal logic the Auditor consumes |

Construction: `LegalGraphRAG._prepare_nodes_data()` builds case/law/crime node dicts → `feature_graph.construct_hierargraph()` embeds all, `store_nodes_with_embeddings()` writes nodes + `build_relationships()` wires fact-layer edges → `run_knn(top_k=3)` → `build_communities()`. (Articles with `entry <= 101`, i.e. the General Provisions, are deleted from the graph — only specific-offense articles are retrievable.)

**Charge-anchored retrieval** (`R_chg`) — the "predict charge → traverse to linked articles" path:
- `core/agents/researcher.py::charge_anchored_retrieval`: LLM predicts ≤3 charges from the facts (`RETRIEVE_LAW_PROMPT`: "you are a criminal judge, output ≤3 charges as a Python list, sorted by likelihood").
- `core/graph_construct/fact_graph.py::charge_anchored_articles(crime_list, top_k=1)`: embeds each predicted charge string, finds the top-k most similar `Crimes` nodes by cosine, then walks the `RELATED_CRIME` edges backward to every `Laws` node pointing at that crime; dedups and ranks by crime similarity.
- This is the graph-structured anchor: instead of trusting semantic article match alone, it grounds article retrieval in a predicted charge and the fact-layer charge→article edges built from real cases.

Three operators are then unioned in `researcher.gather_evidence()`: semantic match (`R_sem`, direct case-embedding kNN), community expansion (`R_com`, find similar cluster → cases in cluster → their articles via `laws_for_case`), and charge-anchored (`R_chg`). All toggled by `RetrieveConfig` (`community_expansion`, `semantic_match`, `charge_anchored`, top-k=5 each).

## A5. What TraLuat should reimplement (L8/L6) + transfer assessment

**Reimplement for L8 (Reasoning/Orchestration):**
1. The **per-party segmentation → Researcher → Auditor → Adjudicator linear pipeline** with a strict narrowing contract (each stage can only shrink the evidence set, adjudicator sees only verified set). This is exactly the "lawyer ⇄ prosecutor ⇄ judge" shape, and it is simpler/cheaper than a debate loop. The TraLuat Auditor HARD-GATE = `audit()`: nothing reaches the adjudicator unverified.
2. The **two-stage prune**: verify atoms (articles) individually, then prune dependent evidence (precedents) that lost all its support. Generalizes to: verify statutes → drop case-law/analogies that relied only on rejected statutes.
3. The **adjudicator doctrine prompt** pattern — encode the jurisdiction's charge/claim-selection doctrine (for VN civil: cause-of-action selection, concurrent vs. alternative claims) directly in the synthesis prompt, operating only over the verified set.

**Reimplement for L6 (Grounding/Verify):**
4. `verify_article`'s **element-wise constitutive-element checking**: each statutory article gets a frozen `judge_dep` checklist of its elements; applicability = per-element true/false NLI against facts + linked interpretations, then an aggregation call. For VN civil statutes this maps cleanly to "điều kiện áp dụng" / elements of a legal norm (e.g. conditions for a valid contract, elements of liability).
5. The **charge/claim-anchored graph traversal** to ground article retrieval in predicted cause-of-action and real-case article links, rather than embedding similarity alone.

**Transfer from Chinese criminal law → Vietnamese civil law + statutes:**
- **Transfers well (structure):** the agent topology, the hard-gate, element-wise verification, and the graph-anchored retrieval are all legal-system-agnostic. VN civil norms are also decomposable into elements/conditions, and VN relies heavily on codified statutes (good fit for a statute-article node graph). Linking norms to interpretations/guiding-decisions (án lệ, nghị quyết, thông tư) parallels `related_laws`.
- **Needs rework (domain):** (a) the output schema is criminal-specific (`charge_name` / `term_of_imprisonment` / death penalty) — replace with civil relief schema (claim upheld/rejected, remedy, damages, obligations). (b) The "predict charge" step becomes "predict cause of action / applicable statute group". (c) The precedent layer: VN is not precedent-binding the way CN uses guiding cases; `verified_cases` should become "guiding decisions / án lệ that cite a surviving article" and weighted as persuasive, not controlling. (d) **Critical gap:** no effective-date/temporal validity check — VN statutes are amended frequently; TraLuat must add an effective-date gate (combine with L-MARS `temporally_invalid`). (e) `judge_dep` checklists must be regenerated from VN legal doctrine, not reused.
- **Infra caveat:** graph is a bespoke in-memory store (`graph_db.py`) with bge-m3 embeddings over an Ollama HTTP endpoint; no Neo4j. Fine as a reference design; TraLuat would likely back it with a real graph/vector store at scale.

---

# PART B — L-MARS

## B1. Directory map + agent flow

```
refs/L-MARS/
├── lmars/
│   ├── workflow.py           # ←★ LMarsWorkflow: Query→Search→[Judge loop]→Summary
│   ├── agents.py             # ←★ QueryAgent, SearchAgent, JudgeAgent, SummaryAgent + is_blocked()
│   ├── verify_agent.py       # ←★★ VerifyAgent: 6-class claim-level citation audit + ALCE metrics
│   ├── faith_search/
│   │   ├── workflow.py       # ←★★ FaithSearchWorkflow: draft→decompose→verify→re-search→repair→abstain
│   │   ├── router.py         # ←★ FailureTypeRouter: failure_type → re-search query strategy
│   │   └── aggregator.py     # AbstentionAggregator: per-claim include/abstain
│   └── tools/                # serper, tavily, courtlistener, offline_rag (BM25)
├── prompts/
│   ├── faith_search_system_prompt.txt   # citation-aware answer prompt (mandatory inline url: cites)
│   ├── llm_judge.txt         # cross-provider usefulness judge (eval)
│   └── summary_template.txt
└── eval/                     # bar-exam + LegalSearchQA harness, baselines (cot/naive_rag/zero_shot)
```

Two orchestrations:
- **Simple / Multi-Turn** (`lmars/workflow.py`): `QueryAgent.build_query` → `SearchAgent.search` → (if `max_turns>1`) `JudgeAgent.evaluate` loop that decides sufficiency and proposes `next_query`, dedup by URL across turns → `SummaryAgent.generate_final_answer`. The JudgeAgent is a *retrieval-sufficiency* gate (does the evidence contain specific legal doctrine?), NOT a citation verifier.
- **Faith-Search** (`lmars/faith_search/workflow.py`): the citation-faithfulness repair pipeline — this is the L6 prior art. See B2/B3.

## B2. ★★ THE KEY PART — VerifyAgent / 6-class citation-faithfulness audit

File `refs/L-MARS/lmars/verify_agent.py`. The 6-class taxonomy (`SUPPORT_LEVELS`, lines 89-96):

```python
SUPPORT_LEVELS = ("supported", "partially_supported", "unsupported",
                  "citation_unreachable", "no_citation", "verifier_error")
```

Core design (from the module docstring): judge each **atomic claim against ONLY its own cited source**, never against the whole retrieved pool — this prevents "supported by some random snippet" leakage. Three phases, each one LLM call:
1. `decompose_claims(question, answer)` — LLM (`_DECOMPOSE_SYSTEM`) splits answer into atomic claims, each with the `cited_url`/`cited_snippet` the author attached. Skips rhetoric and general background.
2. `_find_cited_evidence()` — resolve the cite against the retrieved evidence pool: **strict URL match** (`_canonical_url` + `_urls_match`: host + normalized path, rejects the "parent-domain trap" where `irs.gov` matches any IRS page) then **snippet fallback** (≥50 chars, substring OR token-Jaccard ≥0.5).
3. `check_entailment()` / `check_entailment_batch()` — NLI judge (`_VERIFY_SYSTEM`) against only the cited text.

How each of the 6 classes is decided (`check_entailment`, lines 514-609):

```python
# Case 1 — no cite offered → no_citation
if not (cited_url or cited_snippet.strip()):
    return ClaimRecord(..., support_level="no_citation", failure_type="no_citation",
                        severity="major", confidence=1.0, ...)

# Case 2 — cite offered but not locatable in evidence pool → citation_unreachable
cited_evidence = _find_cited_evidence(cited_url, cited_snippet, evidence)
if cited_evidence is None:
    return ClaimRecord(..., support_level="citation_unreachable",
                        failure_type="fabricated_source", severity="critical",
                        confidence=0.95, ...)   # "fabricated or stale"

# Case 3 — cite resolved → LLM NLI against ONLY that source's text (bounded 4000 chars)
out = self._llm_json(_VERIFY_SYSTEM, user)   # returns support_level/failure_type/severity/confidence
# support ∈ {supported, partially_supported, unsupported}; failure ∈ {none, partially_relevant, unsupported, temporally_invalid}
# if LLM call throws → support_level="verifier_error", failure_type="verifier_error"
```

So the 6 classes split by *stage*: `no_citation` (decompose found no cite), `citation_unreachable` (resolution failed → fabricated/stale), `verifier_error` (judge threw / unparseable JSON), and the NLI judge produces the remaining three (`supported` = source entails claim in full; `partially_supported` = right topic, wrong scope/year/number; `unsupported` = source exists but off-topic). `_VERIFY_SYSTEM` also forces a parallel `failure_type` (`none`/`partially_relevant`/`unsupported`/`temporally_invalid`) and `severity` (`minor`/`major`/`critical`).

Why 6 classes matter (from docstring design notes, worth stealing verbatim for TraLuat): `no_citation` (no attempt) is kept separate from `citation_unreachable` (attempt that failed) because only the latter counts as a false positive in precision; `verifier_error` is tracked separately so judge instability does not silently inflate/deflate metrics.

**Metrics** (strict ALCE, module-level fns, lines 845-947):
- `citation_precision = supported / (supported + partially_supported + unsupported + unreachable)` — unreachable counts as a false positive; no_citation and verifier_error excluded.
- `citation_recall = supported / total_claims`.
- `citation_f1` = harmonic mean. Plus `citation_coverage`, `citation_precision_relaxed` (partial=0.5), `failure_type_distribution`, `verifier_error_rate`.

**Answer-side enforcement** (`prompts/faith_search_system_prompt.txt`): the draft prompt mandates every factual sentence end with inline `(url: <full URL>)` that appears VERBATIM in the evidence block; "Do NOT invent URLs." This is what makes claim→cite decomposition tractable.

## B3. ★ The Faith-Search repair loop

File `refs/L-MARS/lmars/faith_search/workflow.py::FaithSearchWorkflow.run()`. Pipeline:
1. Initial retrieval → evidence pool (dedup by URL).
2. `_draft_answer()` with citation-aware system prompt (inline `(url:)` cites).
3. `decompose_claims()`.
4. **Batched verify round 0** (`check_entailment_batch`, 1 LLM call for all claims).
5. **Per-question re-search loop** (budget `max_research_calls_per_question`, default 2):
   - Select failing claims whose `failure_type ∈ {fabricated_source, temporally_invalid, partially_relevant, unsupported}` (lines 331-336). `none`/`no_citation`/`verifier_error` are deliberately skipped (re-searching can't fix them).
   - Group by `failure_type`; order groups by claim-count desc; spend budget on biggest group first.
   - `FailureTypeRouter.route()` produces ONE targeted re-search query per group (see strategies below); run one search, add new evidence.
   - **URL repair**: for each claim in the group, `_best_repair_evidence()` picks the top-ranked, non-blocked, not-yet-used new result and REPLACES the claim's `cited_url`/`cited_snippet`. Original dead cite recorded in `history` for audit.
6. **Post-research batched re-verify** — re-judge all claims against the (repaired) cites.
7. `AbstentionAggregator.decide()` — include vs abstain per claim.
8. Optional `_final_synthesis()` — keep the answer letter, regenerate the rationale using ONLY included claims.

Router strategies (`faith_search/router.py::FailureTypeRouter.route`) — failure_type → how to re-search:
```
fabricated_source   → re-query with authoritative-domain filter (site:.gov OR site:supremecourt.gov OR site:law.cornell.edu ...)
temporally_invalid  → add date constraint: "<claim> <year> effective" or "<claim> current 2026"
partially_relevant  → expand with the specific missing element parsed from the verifier's explanation
unsupported         → reformulate around the verifier-identified evidence gap ("does not address X" → query X)
no_citation / none / verifier_error → None (no-op)
```
The router parses the verifier's free-text `explanation` with regexes (`_extract_missing_specifics`, `_extract_evidence_gap`) to steer the next query — the verifier's diagnosis directly drives repair. Budget is matched (no extra K), enforced by the workflow.

Abstention (`faith_search/aggregator.py`): a claim is **included** iff `support_level ∈ {supported, partially_supported}` AND `confidence ≥ min_confidence` (default 0.6); otherwise **abstained**. Deliberately a simple per-claim binary threshold, not a weighted score — the threshold drives a precision-coverage curve. This is the "drop it rather than keep a broken cite" behavior.

## B4. Cross-provider judging

Present and central. `verify_agent.py` docstring + `VerifyAgent.__init__(model_id=...)`: the evaluator must be a *different model family* from the system backbone to defuse "model grades its own output". Default config (`faith_search/workflow.py::FaithSearchConfig`): `llm_model="openai:gpt-5.4-mini"` (answerer) vs `evaluator_model="google_genai:gemini-3-flash-preview"` (verifier). The docstring prescribes running both crosswise (2×2) and reporting the **minimum** of the two crosswise scores as the headline, so a system can't benefit from a judge tuned to favor it. `_extract_text()` normalizes both OpenAI (string) and Gemini (list-of-blocks) response shapes. (Separately, `prompts/llm_judge.txt` is a coarse usefulness rater used only in `eval/`, not the citation audit.)

## B5. What TraLuat should reimplement for L6 + jurisdiction note

**Reimplement for L6 (claim-level verifier + repair):**
1. The **6-class taxonomy** verbatim as the claim-verification contract — especially the stage separation: `no_citation` (answer offered no cite) ≠ `citation_unreachable` (cite doesn't resolve to retrieved evidence = fabricated/stale) ≠ `verifier_error` (judge failed). This separation is what makes the metrics honest.
2. **Judge each claim against ONLY its cited source**, with strict URL/snippet resolution (`_canonical_url`/`_urls_match` to avoid parent-domain false matches, snippet token-Jaccard fallback). No cross-snippet leakage.
3. **Faith-Search repair loop**: decompose → verify → group failures by type → failure-type-aware re-search → **URL repair (replace dead cite)** → re-verify → **abstain** on still-failing claims. Keep the audit `history` per claim.
4. **Failure-type-aware routing** where the verifier's explanation steers the next query — and crucially the `temporally_invalid` strategy (date-bounded re-search), which is exactly the **effective-date** dimension LegalGraphRAG lacks.
5. **Cross-provider judging** (answerer ≠ verifier family; report min of crosswise) for any TraLuat self-eval of citation faithfulness.
6. Mandatory **inline-citation answer prompt** so decomposition is tractable.

**Jurisdiction note:** L-MARS is US-law, retrieval = CourtListener + Serper/Tavily web, cites = live URLs. But the **verifier logic is jurisdiction-neutral**: decompose → resolve cite → NLI-entail against only that source → classify into the 6 classes → abstain is domain-independent. For TraLuat the "cited source" is a VN statute article / guiding decision in TraLuat's own corpus (not a web URL), so `_find_cited_evidence` becomes a lookup into TraLuat's canonical article store (match on article id + version/effective-date) instead of URL canonicalization — strictly easier and more reliable than URL matching. The `temporally_invalid` class + date-bounded repair map directly onto VN statute amendment/effective-date checking. "Faithfulness = reachable + entails" is narrower than doctrinal validity (still good law); TraLuat's L6 should add the good-law/effective-date gate on top (where LegalGraphRAG's applicability check and L-MARS's temporal check combine).

---

# SYNTHESIS — a concrete design for TraLuat's Auditor hard-gate + claim-level citation verifier

Combine LegalGraphRAG's **pre-output applicability gate** (L8) with L-MARS's **post-draft claim-citation audit + repair** (L6). Two gates, bracketing the adjudicator.

### L8 — Researcher → Auditor(HARD-GATE) → Adjudicator (from LegalGraphRAG)
- **Researcher**: per-party segmentation; retrieve candidate statute articles via three operators — semantic, community/cluster, and **cause-of-action-anchored** (predict cause of action → graph-traverse to linked articles). Each article carries its frozen element checklist (`judge_dep` equivalent = "điều kiện áp dụng") + linked interpretations (án lệ / nghị quyết / thông tư) + **effective-date metadata**.
- **Auditor HARD-GATE** (`audit()` generalized), runs BEFORE any output, three checks per article — ALL must pass:
  1. **Citation check** — the article/interpretation actually exists in TraLuat's canonical corpus (exact id resolution).
  2. **Applicability check** — element-wise: for each constitutive element run a scoped true/false NLI against the facts (+ interpretations), then aggregate (`verify_article` pattern). Article applicable only if elements are satisfied.
  3. **Effective-date check** (NEW, borrowed from L-MARS `temporally_invalid`) — the article version is in force for the dispute's relevant date; superseded/not-yet-effective versions are rejected.
  Then **prune dependent evidence** (`prune_unsupported_cases`): drop any án lệ / analogy whose only support was a rejected article.
- **Adjudicator**: synthesizes relief/judgment over ONLY the verified-article set, with a VN-civil doctrine prompt (cause-of-action selection, concurrent vs alternative claims). Cannot reach around the gate.

### L6 — claim-level citation verifier + repair (from L-MARS), on the adjudicator's drafted reasoning
- Force the adjudicator to emit **inline citations** (article id + version) on every factual/legal sentence.
- **Decompose** the draft into atomic claims, each with its cited article.
- **Verify each claim against ONLY its cited article**, classify into the 6 classes (reuse verbatim; `citation_unreachable` = cite not in corpus/fabricated, `temporally_invalid` folded in via the effective-date check). Resolution is an id+version lookup into TraLuat's corpus, not URL matching.
- **Faith-Search repair loop** (budgeted): group failing claims by failure_type → failure-type-aware re-retrieval → **repair the cite** (swap to a correct surviving article) → re-verify → **abstain** on claims that still fail (confidence < threshold). Abstained claims are dropped from the final rationale (regenerate rationale from included claims only).
- **Cross-provider verifier**: the L6 verifier model is a different family from the adjudicator; report the min of crosswise faithfulness scores in TraLuat's internal eval.

### Why both, not one
- LegalGraphRAG's gate guarantees the adjudicator *starts* from only verified, in-force, element-satisfied law (prevents bad-premise reasoning). L-MARS's audit guarantees the *output's* every sentence is traceable to a reachable, entailing, in-force source and repairs or abstains otherwise (prevents citation hallucination in the final text). The first is a precondition gate; the second is a post-condition gate. Effective-date validity is enforced in BOTH places. Together they deliver TraLuat's requirement: an Auditor hard-gate that verifies citations + applicability + effective-date before any output, plus claim-level citation-faithfulness with a repair loop.

### Key source files to port
- Gate skeleton: `refs/LegalGraphRAG/core/utils/util.py`, `core/agents/auditor.py`, `core/judge/judge_law.py` (`verify_article`), `core/judge/judge_crime.py` (`synthesize_judgment`), prompts in `core/prompt/judge/__init__.py` (`JUDGE_LAW_PROMPT`, `JUDGE_LAW_PROMPT0`), charge-anchoring in `core/graph_construct/fact_graph.py` (`charge_anchored_articles`) + `core/agents/researcher.py`.
- Verifier + repair: `refs/L-MARS/lmars/verify_agent.py` (6-class, ALCE metrics, cite resolution), `lmars/faith_search/workflow.py` (repair loop), `lmars/faith_search/router.py` (failure-type routing incl. temporal), `lmars/faith_search/aggregator.py` (abstention), `prompts/faith_search_system_prompt.txt` (inline-cite enforcement).
