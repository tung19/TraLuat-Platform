# LAW / Legal Simulation — Landscape for TraLuat (Vietnam legal-AI engine)

Scope: map what "legal/law simulation" means in practice, the concrete systems per sense, their maturity/license/grounding, and relevance to TraLuat (Judgment Analysis, Compliance Diff / Change-Propagation, policy/loophole). Current as of late 2026. Note: almost none ground in real statutes with effective-dates, and none are Vietnamese — flagged throughout.

## Sense 1 — Courtroom / trial simulation (multi-agent judge / lawyer / prosecutor role-play)

### Takeaway
This is the most crowded and mature sense: a cluster of 2024–2026 academic multi-agent frameworks that role-play the full trial. They are research prototypes (China-heavy, plus India/US), mostly code-public but **license-absent** (= not safe for commercial reuse by default), and most do NOT ground in versioned statutes with effective-dates. None are Vietnamese.

### Cited Findings
- **AgentsCourt / SimuCourt** (arXiv 2403.02959, Mar 2024; ACL-family authors incl. Haitao Li). Multi-agent judicial decision-making: court-debate simulation + legal resource retrieval + decision refinement. Introduced the **SimuCourt benchmark = 420 real-world judgment documents** across criminal/civil/administrative. Uses a legal knowledge base (Legal-KB), BM25 + BGE-Large re-ranking. Reports F1 gains of 8.6% / 9.1% in first-/second-instance over prior methods. Jurisdiction: China. — [arXiv](https://arxiv.org/abs/2403.02959), [repo Zhitao-He/AgentsCourt](https://github.com/Zhitao-He/AgentsCourt)
- AgentsCourt repo: **public, ~19 stars, 4 forks, NO LICENSE stated**, 17 commits, contains code + data folder (benchmark/Legal-KB presence not confirmed on page). — [GitHub](https://github.com/Zhitao-He/AgentsCourt)
- **AgentCourt** (arXiv 2408.08089, Aug 2024, Chen et al.). Simulates the entire courtroom; judge, plaintiff lawyer, defense lawyer are autonomous LLM agents. Core novelty = **adversarial evolutionary approach**: lawyer agents "learn" to argue better across simulated cases (experience accumulation). Jurisdiction: China. — [arXiv](https://arxiv.org/html/2408.08089v1)
- AgentCourt repo (relic-yuexi/AgentCourt): **public, ~98 stars, 21 forks, NO LICENSE**, 67 commits; README says code "currently being organized and refined"; dataset on HF `youzi517/AgentCourt`. — [GitHub](https://github.com/relic-yuexi/AgentCourt)
- **SimCourt** ("Chinese Court Simulation with LLM-Based Agent System", arXiv 2508.17322, Aug 2025, Kaiyuan Zhang, Qingyao Ai, Yiqun Liu). Models Chinese **criminal** procedure: 5 stages, 5 roles (judge, prosecutor, attorney, defendant, stenographer), each an LLM agent w/ profile + memory + tools. Benchmark = 200 first-instance single-defendant cases from **LeCaRDv2**. Human experts pairwise-compared simulated vs real trials; reports agents often **outperformed human practitioners** on judge procedural control and prosecutor legal precision. Positioned for legal education / decision support. — [arXiv](https://arxiv.org/abs/2508.17322), [review](https://www.themoonlight.io/review/chinese-court-simulation-with-llm-based-agent-system)
- **SAMVAD** (arXiv 2509.03793, Sep 2025, PES University, India). Multi-agent sim of **Indian judicial bench deliberation**: Judge agent (issues impartial instructions), Prosecution + Defense counsel, multiple Adjudicator agents running multi-round deliberation to consensus verdict, coordinated by an Orchestrator. **Grounds via RAG over Indian legal texts (Indian Penal Code, Constitution)** — agents cite sources. v1 preprint; evaluation described as planned, not fully reported. — [arXiv](https://arxiv.org/abs/2509.03793)
- **LegalSim** (arXiv 2510.03405, Oct 2025, Sanket Badhe, Rutgers, sole author). See Sense 5 — it is a procedural-exploit/red-team simulation, not a trial-quality simulation. — [arXiv](https://arxiv.org/html/2510.03405v1)
- **BenCourt / Sim-Court** (repo Miracle-2001/Sim-Court): "A Benchmark and Framework for Court Simulation using LLM-based Agents" — separate effort. — [aggregator](https://awesome.ecosyste.ms/projects/github.com%2FMiracle-2001%2FSim-Court)
- **MASER** (arXiv 2502.06882, NAACL 2025, Yue et al.). "Multi-Agent Simulator Drives Language Models for Legal Intensive Interaction." Generates synthetic Lawyer–Client dialogues (Supervisor agent oversees) from real case data to produce **training data**; ships **MILE benchmark** (LLM-as-lawyer eval). Jurisdiction: China. — [arXiv](https://arxiv.org/pdf/2502.06882)
- **Civil Court Simulation with LLMs** (arXiv 2606.09632, 2026) — newer entrant extending court sim to civil cases. — [deeppaper](https://arxiv.deeppaper.ai/papers/2606.09632v1)
- A Korean repo (tagged agentcourt, updated May 2026) does Korean criminal sentencing sim, inspired by AgentCourt 2408.08089 — a distinct derivative. — [GitHub topic](https://github.com/topics/agentcourt)

### Inferences
- The field has converged on a standard pattern: role-typed LLM agents + procedure script + (sometimes) RAG. Reusable as architecture/prompting reference, but not as drop-in product due to missing licenses.
- Grounding quality ranks roughly: SAMVAD (RAG over statutes, best) > AgentsCourt (Legal-KB) > AgentCourt/SimCourt (dataset-grounded but not necessarily versioned statute + effective-date) > LegalSim (synthetic rules, no real statutes).

### Gaps
- Exact licenses for AgentCourt/AgentsCourt unconfirmed beyond "none shown on repo page" — must verify LICENSE file / contact authors before any reuse.
- None confirmed to track statute **effective-dates / version history** (critical for TraLuat Change-Propagation).

## Sense 2 — Legal OUTCOME / litigation simulation (decide THIS case, win-probability, settlement)

### Takeaway
Treated academically as **classification (judgment prediction)**, not true Monte-Carlo outcome simulation. LLMs do it moderately (AUC ~0.72–0.78 in one patent study; some report GPT-3.5 robust), but practitioner + regulatory consensus is that reliable calibrated win-probabilities do NOT exist and the use case is "strategy input, not forecast." EU AI Act flags it high-risk.

### Cited Findings
- **LawLLM** (arXiv 2407.21065, US legal system) frames outcome as 4-way label: plaintiff wins / defendant wins / settlement / dismissal. — [arXiv](https://arxiv.org/pdf/2407.21065)
- Patent-litigation master's thesis: staged prediction (survival/settlement/adjudication), best **AUC ~0.72–0.78**; patent text embeddings did NOT improve prediction. — [VU repository](https://epublications.vu.lt/object/elaba:277679252/)
- "Rethinking Legal Judgement Prediction in a Realistic Scenario in the Era of LLMs" (arXiv 2410.10542) reports GPT-3.5 Turbo robust in realistic judgment-prediction scenarios. — [arXiv](https://arxiv.org/html/2410.10542v1)
- Practitioner skepticism: LLMs lack nuanced judgment for precise win-probabilities; recommend quantile regression / prediction intervals for settlement ranges, not point estimates; **EU AI Act classifies legal outcome prediction as high-risk AI**. — [neuralbase guide](https://theneuralbase.com/ai-for-legal/learn/beginner/judicial-responses/)
- Law firms treat AI as a strategy tool, not reliable forecaster of litigation outcomes. — [pulse.bot summary of Ellen Bardash](https://www.pulse.bot/legaltech/blogs/ellen-bardash-law-firms-are-using-ai-as-strategy-tool-not-for-reliable-forecasts-of-litigation-outco-646026a4-c38f-4c92-91ad-316fbc55ed1e/)
- Commercial tools exist (Canotera litigation outcome prediction; vendor marketing — treat with caution). — [Artificial Lawyer](https://www.artificiallawyer.com/2025/04/10/walk-through-canotera-litigation-outcome-prediction/)
- Vietnam-specific: **CMC-AI-Legal-32B** (C-OpenAI/CMC) reports **90.67% on court decision prediction** on VLegal-Bench, surpassing GPT-4o on some tasks (self-reported). — [VLegal-Bench](https://arxiv.org/html/2512.14554v3), [VietnamNet](https://vietnamnet.vn/en/cmc-openai-unveils-vietnam-s-first-legal-llm-and-benchmark-suite-2476212.html)

### Inferences
- "Outcome simulation" in TraLuat's sense (Monte-Carlo over possible rulings) is essentially unbuilt in open research; what exists is single-shot classification. Building a true probabilistic simulator would be net-new and hard to validate.
- Vietnam already has a judgment-prediction capability (CMC, Viettel) reaching high self-reported accuracy — competitive landmark for TraLuat's Judgment Analysis.

### Gaps
- No published **calibration** results for LLM win-probability simulators found — accuracy claims unverified.

## Sense 3 — Policy / legislative IMPACT simulation (effect of a law/amendment before/after change)

### Takeaway
Mature in **agent-based modeling (ABM)** and now **LLM-agent economic simulation**, but these are economics/social-science tools, not legal-tech products, and they simulate *behavioral/economic* effects of regulation — not contract/clause-level propagation. Directly conceptually relevant to TraLuat Change-Propagation, but none grounds in real statute text or does clause diffing. Dual-use risk flagged.

### Cited Findings
- **EconAgent** (Tsinghua, ACL 2024, arXiv 2310.10436). LLM-empowered macroeconomic simulation: labor, consumption, financial markets, govt taxation; progressive tax (2018 US brackets); monthly steps; reproduces inflation/unemployment more plausibly than rule-based/RL baselines; adapts to environment changes. — [arXiv](https://arxiv.org/html/2310.10436v4)
- **TaxAgent** (arXiv 2506.02838, 2026): LLM designs fiscal policy; reports better equity-efficiency trade-off than Saez optimal taxation and US federal income tax. — [deeppaper](https://arxiv.deeppaper.ai/papers/2506.02838v1)
- Classic ABM-for-regulation: Troitzsch review on static/dynamic microsimulation + ABM for **legislative/regulatory impact assessment** (Informatica e diritto, 2013). — [vLex](https://it.vlex.com/vid/legislation-regulatory-impact-assessment-550346598)
- Benthall & Strandburg (Frontiers in Physics 2021): **legal scholarship has under-used ABM** beyond Law & Economics; few law-journal mentions of ABM. — [Frontiers](https://www.frontiersin.org/journals/physics/articles/10.3389/fphy.2021.666386/pdf)
- ABM applied to specific regulation: Basel banking rules + emissions (Cheng PhD, U Michigan, w/ empirical game-theoretic analysis); Korean online-game regulation (PACIS 2019); policy-instrument strength vs innovation (Southampton thesis). — [DeepBlue](https://deepblue.lib.umich.edu/handle/2027.42/155192?show=full), [Elsevier Pure](https://khu.elsevierpure.com/en/publications/using-an-agent-based-model-to-measure-industry-regulations-a-case/)
- 2026 preprints: policy-simulation component modeling agent populations + regulatory interventions + outcome metrics incl. market concentration / regulatory arbitrage (arXiv 2512.13260); static-vs-adaptive regulation in emissions ABM (2606.20699). — [arXiv 2512.13260](https://arxiv.org/pdf/2512.13260)
- Critique: ABM has not yet significantly advanced policy-process theory or policy advice (IPPA 2019). — [IPPA](https://ippapublicpolicy.org/conference/icpp4-montreal-2019/panel-list/10/panel/agent-based-models-in-public-policy-research-perspectives-and-issues/get-panel-pdf-full/738)
- **Regulatory sandboxes** (adjacent governance mechanism, NOT simulation): Brazil launched national AI sandbox before an AI law; EU requires a national sandbox per member state by 2 Aug 2026 (tests real products, not draft rules); Germany's Bundesnetzagentur ran a "simulation of an AI regulatory sandbox" pilot (May 2025) — simulates compliance processes, not draft legislation, no generative agents reported. — [OECD.ai](https://oecd.ai/en/ai-publications/regulatory-sandboxes), [Bundesnetzagentur](https://www.bundesnetzagentur.de/EN/Areas/Digitalisation/AI/05_Innovation/artikel.html)

### Inferences
- For TraLuat Change-Propagation, the useful transfer is the ABM/LLM-agent *framing* (simulate affected actors' behavior when a rule changes), not any reusable legal codebase. These are economics simulators requiring heavy domain modeling and validation.
- No existing system does "law X amended → simulate impact on affected contracts/clauses." That is net-new and closer to a diff/dependency-graph problem than to agent simulation.

### Gaps
- No tool found that simulates legislative impact grounded in actual statute text + effective-dates.
- Peer-review status of 2026 preprints unverified.

## Sense 4 — Agent-based SOCIETY simulation with NORMS / laws (generative agents under a ruleset)

### Takeaway
Active, credible research line (generative agents / Smallville / AI-town lineage) on how norms emerge, spread, and are complied with or violated. Strong for studying *compliance/violation behavior under a ruleset*, but these are social-science sandboxes, not legal engines; norms are abstract, not real statutes. Key cautionary finding: LLM agents reward-hack and norms are unstable.

### Cited Findings
- **CRSEC** (Ren et al., IJCAI 2024): architecture (Creation & Representation, Spreading, Evaluation, Compliance) for norm emergence; in **Smallville** sandbox it establishes social norms and reduces conflicts in generative multi-agent systems. — [IJCAI 2024](https://www.ijcai.org/proceedings/2024/0874)
- **PAVE** (arXiv 2605.19351, 2026): cognitive architecture for **legitimate rule-violation** (e.g., fire evacuation); Perception/Assessment/Verdict/Emulation pipeline; tested in traffic env forked from Smallville; evaluated on legitimate violation, authority deference, bounded scope, recovery. — [arXiv](https://arxiv.org/pdf/2605.19351)
- **Cheng et al. (IJCAI 2026)**: current LLM agents frequently **reward-hack** (optimize metrics at expense of norm adherence); follow legal norms better with structured self-refine learning + psychologically-informed mechanisms. — [IJCAI 2026](https://www.ijcai.org/proceedings/2026/0848.pdf)
- **Ashery et al. (2025)**: LLM populations develop shared conventions, but **small adversarial minorities can flip them** (norm instability). — (cited via PAVE related work)
- **He et al. (2024)**: tests whether LLMs can spot norm violations; 80 household-context stories vs human majority labels. — [arXiv 2403.16517](https://www.arxiv.org/abs/2403.16517)

### Inferences
- Most relevant to a TraLuat "compliance/loophole sandbox": you could simulate whether modeled actors comply with or exploit a ruleset. But grounding is abstract norms, not VN statutes, and the reward-hacking/instability findings are direct warnings about reliability.

### Gaps
- No society-sim grounded in real codified law found; all use toy/abstract norms.

## Sense 5 — Counterfactual / "what-if" legal reasoning + game-theoretic/strategic simulation

### Takeaway
Two sub-threads: (a) counterfactual legal reasoning (change a fact/provision → should outcome change?) is an active benchmark area and the most directly relevant to TraLuat Change-Propagation + Judgment Analysis; (b) game-theoretic exploit-chain simulation (LegalSim) targets loophole discovery. Both surface the core risk: LLMs are unstable under perturbation and can be misled.

### Cited Findings
- **"Which Changes Matter?"** (arXiv 2605.26530, 2026): a legal AI should stay stable under legally *irrelevant* changes but update under legally *material* ones. Perturbation tests alter conduct, subject identity, role in offense, amount thresholds, harm severity, causation. Finds **existing LLM legal reasoners are sensitive to legal-element changes and can be misled even when operative facts are unchanged.** Advocates relevance-sensitive eval + solver-grounded reasoning. — [arXiv](https://arxiv.org/pdf/2605.26530), [summary](https://bittide.aicompass.dev/article/ef394a21-4533-4b3b-9127-7cd079909bde?locale=en)
- **Beyond Guilt / Trichotomous Reasoning** (arXiv 2412.14588): uses LLM to rewrite case facts into **counterfactual versions** (e.g., lowering timber volume below a charge threshold, adding self-defense) to create not-guilty training samples. — [arXiv](https://arxiv.org/pdf/2412.14588)
- **Legal hallucination** study (arXiv 2401.01301): LLMs show **contra-factual bias** on legal tasks, often going along with wrong premises. — [arXiv](https://arxiv.org/pdf/2401.01301)
- Counterfactual-reasoning degradation: reasoning over multiple hypothetical scenarios degrades LLM performance (causal-reasoning surveys). — [survey arXiv 2503.09326](https://arxiv.org/pdf/2503.09326)
- **LegalSim** (arXiv 2510.03405, Oct 2025, Rutgers, sole author Badhe): adversarial litigation sim; plaintiff/defendant agents pick procedural actions (discovery, motions) validated by a **JSON rules engine**; **stochastic judge** with calibrated grant rates / cost allocation / sanction tendencies. Compared PPO vs contextual-bandit-LLM vs direct-LLM vs heuristic (PPO wins most; bandit most consistent; LLM trails; heuristic weakest). Reports **emergent exploit chains** (cost-inflating discovery sequences, calendar-pressure tactics). Purpose: **red-team codified legal systems themselves**, not just models. No GitHub repo found. — [arXiv](https://arxiv.org/html/2510.03405v1)
- **L4M** (arXiv 2511.21033, NUS + Griffith): neuro-symbolic — adversarial LLM agents (prosecutor + defense) + **SMT-solver** verifies soundness, detects conflicts, emits proof object a Judge-LLM narrates. More a verification/reasoning system than a simulator; relevant to grounded, auditable reasoning. — [arXiv](https://arxiv.org/html/2511.21033v1)

### Inferences
- LegalSim is the closest existing analog to TraLuat's "loophole / policy exploit" idea; reusable as a *design pattern* (actions + rules engine + stochastic judge) but it uses synthetic rules, not VN statutes, and has no released code.
- "Which Changes Matter?" and neuro-symbolic L4M point to the robust direction for Change-Propagation: constrain/verify with symbolic rules + effective-date-aware grounding rather than trusting raw LLM counterfactuals.

### Gaps
- No LegalSim code; reproduction would be from paper only.
- No counterfactual legal system grounded in versioned statutes with effective-dates.

## Cross-cutting assessment for TraLuat

### Takeaway
There is a rich prototype landscape, but it is almost entirely research-grade, China/India/US-centric, frequently **license-free (commercially unusable as-is)**, and — critically — **not grounded in versioned statutes with effective-dates**, which is exactly what TraLuat's Change-Propagation needs. No Vietnamese simulation system exists; VN work to date is benchmarks (VLegal-Bench) and judgment-prediction LLMs (CMC, Viettel), i.e. Sense 2 classification, not simulation.

### Cited Findings
- No Vietnamese court/legal simulation found; VN state-of-art = VLegal-Bench benchmark + CMC-AI-Legal-32B + Viettel judicial assistant (173k+ docs, 1.4M+ judgments). — [VLegal-Bench](https://arxiv.org/html/2512.14554v3), [Viettel AI](https://viettelai.vn/en/tin-tuc/tuong-lai-tro-ly-ao-phap-luat-phuc-vu-toan-dan-viet-nam-ngay-mot-gan)
- VN law is civil-law (code-based, not precedent) — matches statute-grounded, diff/propagation approaches over case-precedent simulation. — [VLegal-Bench](https://arxiv.org/html/2512.14554v3)

### Inferences (recommendation)
- **Reusable (patterns, not code):** role-typed agent + procedure-script architecture (AgentCourt/SimCourt) for a Judgment-Analysis "devil's advocate" / argument-stress-test feature; SAMVAD's RAG-grounded-citation pattern; LegalSim's actions+rules-engine+stochastic-judge pattern for a loophole/exploit explorer; L4M's neuro-symbolic SMT verification for auditable Change-Propagation.
- **Worth building (net-new, highest TraLuat value):** Sense 3/5 hybrid for **Change-Propagation** — when a statute/clause changes, propagate to affected contracts/obligations via a dependency graph grounded in **versioned statute text + effective-dates** (nothing off-the-shelf does this). Secondary: a constrained compliance "what-if" (Sense 5 counterfactual) with relevance-sensitivity checks.
- **Lower priority / risky:** full courtroom role-play and win-probability "outcome simulation" — impressive demos but weak grounding, no calibration, EU-high-risk classification, and VN competitors already ship judgment-prediction.

### Honest risks
- **Hallucination / instability:** LLM legal reasoners are misled by legally-irrelevant perturbations and show contra-factual bias (2605.26530, 2401.01301); agents reward-hack and norms flip under small adversarial pressure (IJCAI 2026; Ashery 2025).
- **No grounding / no effective-dates:** essentially every surveyed system lacks versioned-statute grounding — the single biggest gap vs TraLuat's needs.
- **Dual-use (policy simulation):** Sense 3 tools model how actors adapt to/arbitrage regulation; the same engine that tests a client's compliance can surface regulatory-arbitrage/loophole strategies — reputational and ethical exposure.
- **Regulatory:** outcome prediction is EU-AI-Act high-risk; relevant if TraLuat targets EU-facing clients or mirrors that framing.
- **Licensing:** AgentCourt/AgentsCourt and most repos show no license = default "all rights reserved," not reusable commercially without author permission; LegalSim has no public code.
