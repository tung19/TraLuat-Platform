# Multi-Agent / Role-Based Legal Reasoning — Prior Art Inventory

> Scope: open-source + academic systems where multiple AI agents play distinct legal
> roles (lawyer, judge, prosecutor, regulator, auditor) and argue/deliberate, incl.
> adversarial "court simulation". Emphasis on real GitHub repos, maturity, licenses,
> and commercial usability. Compiled 2026-11-05.

> **LICENSE BOTTOM LINE (read first):** Of the directly relevant multi-agent legal
> repos, **only PAKTON (Apache-2.0) is safely usable in a commercial product.** The
> two flagship court-simulation repos (AgentCourt, AgentsCourt) and the
> Researcher/Auditor repo (LegalGraphRAG), plus L-MARS and ACAL, ship with **NO
> LICENSE FILE** — under default copyright law that means "all rights reserved" and
> they are **not legally reusable in a commercial product** without written
> permission from the authors. They are reference/research material only.

## Verify & deep-dive AgentCourt (github.com/relic-yuexi/AgentCourt)

### Takeaway
AgentCourt is a real, confirmed repo: an LLM-driven adversarial civil-court simulator whose two lawyer agents "evolve" by accumulating experience across ~1000 simulated cases. It is a low-maturity research demo (98 stars, no commits since Sep 2024) and ships with **no license**, so it is not commercially reusable as-is.

### Cited Findings
- Paper: "AgentCourt: Simulating Court with Adversarial Evolvable Lawyer Agents", arXiv:2408.08089 (Aug 2024; v2 revised Jun 2025). Authors: Guhong Chen, Liyang Fan, Zihan Gong, Nan Xie, Zixuan Li, Ziqiang Liu, Chengming Li, Qiang Qu, Shiwen Ni, Min Yang — [arXiv](https://arxiv.org/abs/2408.08089v2); [HTML](https://arxiv.org/html/2408.08089v1)
- Roles: judge, plaintiff's lawyer, defense lawyer, plus other courtroom participants — all autonomous LLM agents simulating full civil-court proceedings — [arXiv HTML](https://arxiv.org/html/2408.08089v1)
- Learning/evolution mechanism: lawyer agents improve through adversarial repetition; README states the system "simulated 1000 adversarial legal cases" and evolved agents "showed consistent improvement" in responsiveness, expertise, and logical rigor. Training is `python main.py`; testing disables `reflect_and_summary()`, indicating a reflection step drives learning — [GitHub README](https://github.com/relic-yuexi/AgentCourt)
- Memory: repo contains an `EMDB/` folder (likely an experience/memory DB) and `agent.py`, `main.py`, `LLM/`, `example_role_config.json`; README says agents "accumulate experience" but does not document the memory mechanism in detail — [GitHub](https://github.com/relic-yuexi/AgentCourt)
- LLM orchestration: models configured per-role in `example_role_config.json`; authors used Baidu ERNIE-Speed-128K; `llm_type` can be set to `offline` for a local model — [GitHub](https://github.com/relic-yuexi/AgentCourt)
- Claimed result: evolved agents reach performance comparable to GPT-4o on dynamic courtroom tasks while outperforming specialized legal models; paper also introduces CourtBench benchmark — [arXiv abstract](https://arxiv.org/abs/2408.08089v2)
- Maturity: **98 stars, 21 forks, 67 commits, last push 2024-09-05** (abandoned/dormant for ~14 months). README notes code "is currently being organized and refined." — [GitHub API, verified 2026-11-05]
- **License: NONE** — no LICENSE file present (GitHub API `/license` returns Not Found). — [GitHub API, verified 2026-11-05]

### Inferences
- With no license and no maintenance since 2024, AgentCourt is best treated as an architectural reference (role config + reflection-based "evolution" loop + experience DB), not as code to vendor into a product.
- The ERNIE/Chinese-law orientation means its prompts and any bundled data are tuned to Chinese civil procedure, limiting direct reuse for other jurisdictions.

### Gaps
- Exact contents/schema of `EMDB/` memory store not documented in README; would require reading source.
- No stated data license for any bundled case data.

## LegalGraphRAG and Researcher/Auditor multi-agent patterns

### Takeaway
"LegalGraphRAG" IS a real, named repo (XMUDeepLIT/LegalGraphRAG, ACL 2026 Main) — it is the clearest real implementation of a Researcher → Auditor → Adjudicator legal pattern, pairing a hierarchical legal knowledge graph with citation-grounded multi-agent retrieval. It has no license (not commercially reusable). L-MARS (boqiny/L-MARS) is a second real implementation of the same pattern with an explicit "Citation-Faithfulness Audit."

### Cited Findings
- **LegalGraphRAG** — "Multi-Agent Graph Retrieval-Augmented Generation for Reliable Legal Reasoning", arXiv:2605.28120 (posted ~May 2026), accepted **ACL 2026 Main** (aclanthology 2026.acl-long.1738). Authors from Xiamen University + Hong Kong Polytechnic — [arXiv HTML](https://arxiv.org/html/2605.28120); [ACL](https://aclanthology.org/2026.acl-long.1738/)
- Role structure: **Researcher** runs parallel retrieval (semantic matching, community expansion, charge anchoring) to maximize evidence coverage; **Auditor** verifies candidate statutory articles against case facts using diagnostic checklists + judicial interpretations (not surface similarity), prunes inapplicable evidence; **Adjudicator** synthesizes the validated subgraph into charges + statutory basis with explicit citations — [arXiv HTML](https://arxiv.org/html/2605.28120)
- Hierarchical graph (HierarGraph) has 3 layers: **Fact Graph** (cases→articles→offenses), **Ontology Graph** (abstract case features in 4 dimensions; communities via k-NN + Leiden), **Rule Graph** (articles→judicial interpretations + a diagnostic checklist per article) — [arXiv HTML](https://arxiv.org/html/2605.28120)
- Grounding: judgments carry "explicit citations to the statutory articles and judicial interpretations" used, traceable to the graph; the Auditor is the cross-role citation/applicability verification step — [arXiv HTML](https://arxiv.org/html/2605.28120)
- Datasets: CAIL2018, CMDL (Chinese criminal law); ethics statement also cites JuDGE, LeCaRDv2. Jurisdiction = Chinese criminal law — [arXiv HTML](https://arxiv.org/html/2605.28120)
- Results: with Qwen3-8B backbone, avg 49.5 (ACC/F1) vs 43.1 for strongest RAG baselines (RAPTOR, HippoRAG2); claims 6.3%–19.1% gains; up to 78.7% on CMDL with stronger backbones; ablations show removing Researcher −4.0%, removing Auditor −3.4%, removing HierarGraph drops CAIL 40.9→33.7 — [arXiv HTML](https://arxiv.org/html/2605.28120)
- Maturity: **70 stars, 9 forks, last push 2026-10-31** (actively maintained). Desc: "[ACL'26 Main] Official code." — [GitHub API, verified 2026-11-05]
- **License: NONE** (no LICENSE file; arXiv paper is CC BY 4.0 but that covers the paper, not the code; datasets keep original providers' licenses) — [GitHub](https://github.com/XMUDeepLIT/LegalGraphRAG); [GitHub API, verified 2026-11-05]
- **L-MARS** — "Legal Multi-Agent Workflow with Orchestrated Reasoning and Agentic Search", arXiv:2509.00761, **ICML 2026 AI4Law**. Code: github.com/boqiny/L-MARS (desc: "Legal Multi-Agent System with Agentic Search and **Citation-Faithfulness Audit**"). Agents do structured query decomposition, agentic web search, evidence filtering, cited-answer synthesis; a judge/verifier agent checks jurisdiction + date of authorities before answering. Retrieval via Serper API (web), BM25 (offline), CourtListener API (US case law). Reports 96.0% on LegalSearchQA (+38 pts over zero-shot). **15 stars, last push 2026-07-20, License: NONE** — [arXiv HTML](https://arxiv.org/html/2509.00761v2); [GitHub API, verified 2026-11-05]

### Inferences
- LegalGraphRAG is the strongest existing blueprint for a verification-enforcing legal multi-agent pipeline (Auditor = hard citation/applicability gate between retrieval and judgment). Its design is reusable as a pattern even though the code license blocks direct commercial copying.
- L-MARS + LegalGraphRAG together show two independent 2026 teams converging on an explicit "audit/verify citations across roles" step — this is now an established pattern, not a one-off.

### Gaps
- Whether LegalGraphRAG's Auditor does literal text-level verification against original source documents vs. checklist-based applicability judgment is ambiguous in the paper body (abstract says "against source documents"; body emphasizes diagnostic checklists).

## Other multi-agent legal frameworks (court sim, debate, deliberation, negotiation, contracts)

### Takeaway
There is a dense 2024–2026 ecosystem of multi-agent legal systems, almost all Chinese-law-oriented research demos from academic labs; most either have no public code or no license. The one clearly production-permissive, code-complete option is PAKTON (Apache-2.0) for contract QA.

### Cited Findings
- **AgentsCourt (a.k.a. SimuCourt)** — "AgentsCourt: Building Judicial Decision-Making Agents with Court Debate Simulation and Legal Knowledge Augmentation", arXiv:2403.02959, **EMNLP 2024 Findings**. Simulates judge decision-making via court-debate simulation (judge + plaintiff + defendant agents), legal-resource retrieval, and decision refinement. SimuCourt benchmark = 420 Chinese judgment docs (criminal/civil/administrative, 1st + 2nd instance); +8.6%/+9.1% F1 on generating legal grounds. Repo github.com/Zhitao-He/SimuCourt redirects to **github.com/Zhitao-He/AgentsCourt: 19 stars, last push 2024-12-30, License: NONE** — [arXiv](https://arxiv.org/abs/2403.02959); [GitHub API, verified 2026-11-05]
- **PAKTON** — "A Multi-Agent Framework for Question Answering in Long Legal Agreements", arXiv:2506.00608, **EMNLP 2025 (Oral)**. Collaborative agent workflow + multi-stage RAG for contract review/QA (not negotiation). **46 stars, Apache-2.0 (COMMERCIALLY USABLE), last push 2025-12-08** — [arXiv](https://arxiv.org/abs/2506.00608); [GitHub](https://github.com/petrosrapto/PAKTON); [GitHub API, verified 2026-11-05]
- **AgentsBench** — "Agents on the Bench: LLM-Based Multi-Agent Framework for Trustworthy Digital Justice", arXiv:2412.18697. Role-based judicial agents mimic a collegial bench: independent reasoning then discussion toward consensus (judgment prediction) — [arXiv HTML](https://arxiv.org/html/2412.18697v1)
- **SAMVAD** — "Multi-Agent System for Simulating Judicial Deliberation Dynamics in India", arXiv:2509.03793 (PES University, Bengaluru, Sep 2025). Roles: Judge, Prosecution Counsel, Defense Counsel, multiple Adjudicators (bench); RAG over landmark Indian legal docs (IPC, Constitution); multi-round deliberation + consensus checking. **No public GitHub repo found** (notable: one of the few non-Chinese-law systems) — [arXiv](https://arxiv.org/abs/2509.03793); [arXiv HTML](https://arxiv.org/html/2509.03793v1)
- **L-MAD** — "A Systematic Evaluation of Multi-Agent Debate Structures in Legal Reasoning", arXiv:2607.09099, **ICML 2026**. Studies debate structures on Legal Textual Entailment; finds more agents reduce inconsistency/improve accuracy but more discussion rounds cause "over-deliberation drift." No GitHub link found in results — [arXiv PDF](https://arxiv.org/pdf/2607.09099); [alphaXiv](https://www.alphaxiv.org/abs/2607.09099)
- **ACAL** — "Adaptive Collaboration of Arena-Based Argumentative LLMs for Explainable and Contestable Legal Reasoning." Neuro-symbolic multi-agent argumentation. **9 stars, last push 2026-07-05, License: NONE** — [GitHub](https://github.com/loc110504/ACAL); [GitHub API, verified 2026-11-05]
- Additional named systems catalogued by the 2026 survey "LLM Agents in Law" (arXiv:2601.06216) — roles/purpose per survey table:
  - **MASER** (Yue et al. 2025): client / lawyer / supervisor — synthetic legal scenario data generation
  - **Simcourt** (Zhang et al. 2025; see also "Chinese Court Simulation", arXiv:2508.17322): agent per trial stage — simulates Chinese criminal trial procedure
  - **LegalSim** (Badhe 2025): agents in a simulated legal system — stress-tests procedures for harmful-but-procedurally-valid strategies
  - **AgentMediation** (Chen et al. 2025): configurable mediation roles — 5-stage civil mediation; surfaces group polarization
  - **Debate-Feedback** (Chen et al. 2025): debating agents + reliability evaluator — stabilizes debate for judgment prediction
  - **MALR / ChatLaw** (Yuan 2024 / Cui 2023): theory-extraction, fact-analysis, synthesis agents; ChatLaw uses role-specialized agents + knowledge graph to cut hallucinations in consultations
  - **LawLuo** (Sun et al. 2024): role-based consultation agents — multi-round query clarification + structured consultation reports
  - **Law in Silico / Law in Silico** (Wang et al. 2025): individual + institutional agents — simulates lawmaking, adjudication, enforcement
  - **NegotiationGym** (Mangla et al. 2025): self-optimizing negotiating agents — iterative negotiation dynamics (closest to contract negotiation; no code link found)
  - **Rawlsian Agents** (Ferro et al. 2025): fairness-oriented negotiating agents — evaluate/draft bilateral agreements
  - **Benchmarks**: MASLegalBench (deductive reasoning across multi-agent setups), LegalAgentBench, MASCA, MARS — [survey arXiv HTML](https://arxiv.org/html/2601.06216v1)

### Inferences
- The field is heavily skewed to Chinese legal data (CAIL, CMDL, SimuCourt) and to judgment prediction / court simulation; genuine multi-role *contract negotiation* with debate is barely represented (NegotiationGym/Rawlsian Agents are the nearest, both negotiation-only, no production code).
- For a commercial product, the realistic reuse path is: adopt PAKTON (Apache-2.0) for contract QA, and reimplement the Researcher/Auditor/Adjudicator and court-debate *patterns* from the no-license papers in your own code rather than copying their repos.

### Gaps
- Could not confirm licenses for AgentsBench, Simcourt (2508.17322), MASER, LawLuo, NegotiationGym (repos not located or not checked within call budget).
- No GitHub repo located for SAMVAD, L-MAD, or NegotiationGym.

## Grounding in law / citation verification across roles

### Takeaway
A clear 2025–2026 trend: the better multi-agent legal systems ground arguments via external retrieval (statutes, case law, KBs) and increasingly add a dedicated verification/audit agent that checks citations and jurisdiction/date before a judgment is issued. LegalGraphRAG (Auditor) and L-MARS (Citation-Faithfulness Audit) are the two clearest examples that enforce cross-role citation verification.

### Cited Findings
- LegalGraphRAG's **Auditor** is a dedicated verification role between retrieval and adjudication: it checks each candidate statutory article's applicability against case facts via diagnostic checklists + judicial interpretations and prunes non-applicable evidence; final judgment carries explicit statutory/interpretation citations — [arXiv HTML](https://arxiv.org/html/2605.28120)
- L-MARS enforces **citation faithfulness** explicitly (repo tagline) and has agents verify that cited authorities apply to the correct jurisdiction and date before answering; retrieval grounded in CourtListener (US case law), BM25, and web search — [arXiv HTML](https://arxiv.org/html/2509.00761v2); [GitHub](https://github.com/boqiny/L-MARS)
- Survey ("LLM Agents in Law") summarizes grounding mechanisms used across systems: external retrieval of statutes/case law; jurisdiction + time checks (cites L-MARS); neural-symbolic verification (formalize statutes, use symbolic solvers for machine-checkable support); knowledge-graph augmentation (ChatLaw, AgentsCourt); peer-style cross-examination between agents; and evaluators that score citation quality + check outputs against source documents — [survey arXiv HTML](https://arxiv.org/html/2601.06216v1)

### Inferences
- "Dedicated Auditor/verifier agent that validates citations and jurisdiction/date across roles" is the most directly transferable, product-relevant design idea in this prior art — it is exactly the piece that mitigates hallucinated-citation liability in a commercial legal product.

### Gaps
- None of the surveyed systems were shown to do end-to-end *literal text-match* verification of every citation against the authoritative source text; most verify applicability/relevance rather than quote-level fidelity.

## Reusable vs. research-demo-only (production fitness)

### Takeaway
Nearly all of this prior art is research-demo quality and/or license-blocked for commercial use. PAKTON is the only directly reusable commercial-grade component; everything else is best mined for architectural patterns.

### Cited Findings
- **Commercially reusable (permissive license):** PAKTON — Apache-2.0, EMNLP 2025 Oral, maintained to Dec 2025 — [GitHub](https://github.com/petrosrapto/PAKTON)
- **Pattern-reference only (NO license → not commercially reusable):** AgentCourt, AgentsCourt, LegalGraphRAG, L-MARS, ACAL — all confirmed to have no LICENSE file via GitHub API (2026-11-05)
- **Abandoned/dormant demos:** AgentCourt (no commits since 2024-09), AgentsCourt (since 2024-12). Maintained: LegalGraphRAG (2026-10), PAKTON (2025-12), L-MARS (2026-07) — [GitHub API, verified 2026-11-05]
- Survey-stated production limitations of multi-agent legal systems: brittleness when facts change (surface-pattern reliance), procedural competence gaps, weak/underdeveloped law-specific evaluation (procedural compliance, fairness), unvalidated role-play realism/reproducibility, prompt sensitivity, narrow (mostly Chinese) jurisdictional coverage, and underexplored alignment with professional-conduct rules; the survey explicitly calls for human lawyer review/sign-off before deployment — [survey arXiv HTML](https://arxiv.org/html/2601.06216v1)

### Inferences
- For TraLuat (a commercial legal platform): treat AgentCourt / AgentsCourt / LegalGraphRAG / L-MARS as design references to reimplement cleanly in-house (role graph, reflection/experience memory, Researcher→Auditor→Adjudicator, citation-faithfulness audit). Only PAKTON can be vendored directly, and even then verify the Apache-2.0 NOTICE/attribution obligations and any model/data dependencies it pulls in.
- A "no LICENSE file" repo should be assumed off-limits for commercial copying unless the authors are contacted and grant a license in writing.

### Gaps
- Did not audit transitive dependencies/model weights of PAKTON for their own licenses (e.g., any GPL deps or non-commercial model checkpoints) — needs a code-level check before adoption.
- Licenses for several survey-listed systems (MASER, Simcourt, LawLuo, AgentsBench, NegotiationGym) remain unconfirmed.
