# Legal Judgment Prediction (LJP) and Automated Judgment Assessment — Prior Art

Scope note: inventory of datasets, benchmarks, models, and systems for (a) predicting case outcomes, (b) generating court reasoning/rationale, and (c) critiquing/verifying an existing judgment. Current as of early Nov 2026. Many of the most relevant works (judgment critique, court-view generation) are 2024-2026 arXiv preprints; where I could not open the full text or the arXiv ID is very recent, this is flagged as UNVERIFIED VINTAGE. arXiv IDs use YYMM, so "2601" = Jan 2026, "2605" = May 2026, "2607" = Jul 2026, etc.

## Q1: Major LJP datasets/benchmarks — task, size, language/jurisdiction, license, commercial usability

### Takeaway
The field's canonical datasets are CAIL (Chinese criminal), ECtHR (human-rights violation prediction, in LexGLUE under CC BY 4.0), ILDC (Indian Supreme Court outcome + explanation), and Swiss-Judgment-Prediction (multilingual). CAIL and ILDC have ambiguous/unstated licenses (treat as research-only); ECtHR-via-LexGLUE is the cleanest for commercial use (CC BY 4.0). US outcome prediction is older, feature/metadata-based (Katz et al.), not a shared NLP corpus.

### Cited Findings
- **CAIL2018** (Chinese, criminal): >2.6M criminal cases from the Supreme People's Court of China published-judgments site; defines three subtasks — relevant law article prediction, charge prediction, and prison-term prediction. The paper states the dataset was released for/after the CAIL competition — [CAIL2018 paper, arXiv:1807.02478](https://arxiv.org/pdf/1807.02478). License: Hugging Face card lists license as "unknown"; TensorFlow Datasets catalog lists "no known license." No explicit commercial license located — treat as research-only — [HF cail2018 card](https://huggingface.co/datasets/china-ai-law-challenge/cail2018), [TFDS catalog](https://www.tensorflow.org/datasets/community_catalog/huggingface/cail2018).
- **CAIL series**: CAIL2019 had three tasks — Legal QA/reading comprehension, Legal Case Element Prediction, and Similar Case Matching (SCM). CAIL2019-SCM (Xiao et al.): 8,964 triplets of fact descriptions from the Supreme People's Court; task = decide which two of three cases are more similar; similarity defined by legal workers — [CAIL2019-SCM, arXiv:1911.08962](https://ar5iv.arxiv.org/html/1911.08962). Official repos: github.com/thunlp/CAIL and china-ai-law-challenge GitHub (I did not retrieve CAIL2021 task details or a license).
- **ECtHR (Chalkidis et al.)** via **LexGLUE** (English): ~11k ECtHR cases, chronological split (train 2001-2016, dev 2016-2017, test 2017-2019). Task A = predict set of articles the Court found *violated* from case facts (multi-label); Task B = predict *allegedly* violated articles. Task A is harder (requires identifying relevant articles + violation status) — [LexGLUE, arXiv:2110.00976](https://arxiv.org/pdf/2110.00976). License: LexGLUE on Hugging Face (`coastalcph/lex_glue`, configs `ecthr_a`, `ecthr_b`) is **CC BY 4.0** (commercially usable with attribution) — [HF lex_glue card](https://huggingface.co/datasets/coastalcph/lex_glue/blob/main/README.md).
- **LexGLUE** overall: benchmark of English legal NLU tasks; evaluates BERT, RoBERTa, DeBERTa, Longformer, BigBird, Legal-BERT; ECtHR/SCOTUS use hierarchical model variants — [LexGLUE, arXiv:2110.00976](https://arxiv.org/pdf/2110.00976).
- **ILDC for CJPE** (Malik et al., ACL 2021; Indian, Supreme Court): ~35k Indian Supreme Court cases each tied to its decision; a held-out test set has gold expert explanation annotations. Task = Court Judgment Prediction and Explanation (CJPE): predict the final decision + explain it. Best model ~78% accuracy vs 94% for human legal experts; proposed hierarchical occlusion-based explanation model; machine explanations differ substantially from expert ones — [ILDC paper, arXiv:2105.13562](https://arxiv.org/abs/2105.13562v2), [ACL 2021 PDF](https://aclanthology.org/2021.acl-long.313.pdf). Code/corpus: GitHub Exploration-Lab/CJPE (license not confirmed in sources — verify; practically treat as research-only).
- **Swiss-Judgment-Prediction** (German/French/Italian; Swiss Federal Supreme Court): multilingual LJP benchmark; task = predict case approval/dismissal — [SJP paper, arXiv:2110.00806](https://arxiv.org/abs/2110.00806v1). License is ambiguous across sources: HF loader `.py` has an Apache-2.0 header (covers code, not data); TFDS lists "no known license"; the paper file is CC BY 4.0 on the BFH repository; a follow-up paper (arXiv:2306.09237) says the authors' Swiss data is public-domain and on HF under **CC BY-SA**. Most likely data license CC BY-SA but this is an inference — verify on HF `rcds/swiss_judgment_prediction` / Zenodo before commercial use — [HF rcds/swiss_judgment_prediction](https://huggingface.co/datasets/rcds/swiss_judgment_prediction), [follow-up arXiv:2306.09237](https://arxiv.org/pdf/2306.09237), [Zenodo 5529712](https://zenodo.org/record/5529712).
- **US outcome prediction (Katz, Bommarito, Blackman 2017, PLOS ONE)**: time-evolving random-forest classifier predicting SCOTUS outcomes 1816-2015; 240k+ justice votes, 28k case outcomes; 70.2% case-level accuracy, 71.9% justice-vote accuracy; strictly out-of-sample (only pre-decision data). Open access, CC (PLOS ONE), DOI 10.1371/journal.pone.0174698 — this is feature/metadata-based (SCDB variables), not a text NLP corpus — [Katz et al. PLOS ONE](https://pmc.ncbi.nlm.nih.gov/articles/PMC5389610/), [arXiv:1612.03473](https://arxiv.org/abs/1612.03473v2). Earlier Ruger et al. (2004) "Supreme Court Forecasting Project" reported experts ~67.4% case-level vs model — [computationallegalstudies.com](https://computationallegalstudies.com/tag/random-forest/) (original Columbia Law Review figures unverified).
- **LegalBench** (Guha et al., 2023; English): collaboratively built benchmark measuring legal reasoning in LLMs (162 tasks). **No single license** — each task carries its source dataset's license (CC BY 4.0, CC BY-NC-SA 4.0, CC BY-SA 4.0, MIT, CC BY-NC 3.0, etc.); some tasks are non-commercial/share-alike — must check per task; repo provides a notebook to filter tasks by license — [LegalBench, arXiv:2308.11462](https://arxiv.org/pdf/2308.11462), [HF nguha/legalbench](https://huggingface.co/datasets/nguha/legalbench).

### Inferences
- For a commercial product, ECtHR-via-LexGLUE (CC BY 4.0) is the safest ready-made LJP dataset; CAIL and ILDC should be treated as research-only pending explicit license confirmation; Swiss-Judgment-Prediction is probably CC BY-SA (share-alike has copyleft implications for derived data).
- US work is a methodological precedent (out-of-sample, metadata features) rather than a reusable text corpus — relevant as design guidance, not as training data.

### Gaps
- Exact license text for CAIL2018/CAIL2019 (thunlp/china-ai-law-challenge GitHub) not retrieved; CAIL2021 task composition not confirmed.
- ILDC/CJPE repository license not confirmed from sources.
- Definitive Swiss-Judgment-Prediction *data* license (vs paper/loader license) not pinned down.

## Q2: Court view generation / rationale generation — concrete papers and datasets

### Takeaway
Court-view / rationale generation is a mature sub-field but overwhelmingly Chinese and criminal-case-focused; it generates the court's reasoning text (not just a label). Key datasets: Court-View-Gen, AC-NLG (civil), C3VG, CCVG, LeGen; English efforts (US-CVG from Caselaw Access Project) and multilingual Swiss work are newer and smaller. Licenses are mostly unstated (scraped from China Judgments Online) — treat Chinese CVG data as research-only.

### Cited Findings
- **"Interpretable Charge Predictions... Learning to Generate Court Views from Fact Descriptions"** (Ye et al., NAACL 2018, arXiv:1802.08504) — foundational court-view generation work: generate the court's rationale + charge from fact descriptions — [arXiv:1802.08504](https://arxiv.org/pdf/1802.08504).
- **Court-View-Gen** dataset: 171,981 cases (one defendant, one charge), 51 charge labels, from China Judgments Online (CJO) — [Survey on LJP, arXiv:2204.04859](https://arxiv.org/pdf/2204.04859).
- **AC-NLG** (Wu et al., 2020; civil): 66,904 civil judgment documents from CJO, annotated with judgment + rationales; later described as a counterfactual/attentional generative model; focuses only on the private-lending civil category — [Survey, arXiv:2204.04859](https://arxiv.org/pdf/2204.04859); category limitation per [ClaimGen-CN, arXiv:2508.17234](https://arxiv.org/html/2508.17234v2) (UNVERIFIED VINTAGE, Aug 2025). MSJudge (Ma et al., 2021) similarly limited to private lending.
- **C3VG**: fact descriptions, charges, and rationales for both adjudging and sentencing circumstances; two-stage design — [search summary of court-view survey corpus](https://arxiv.org/pdf/2204.04859) (details via the C3VG paper directly).
- **CCVG** + **ShiZhi** model: criminal dataset >110K cases, fact descriptions paired with court views, judgments 1985-2021; used to train ShiZhi, a 0.5B-parameter court-view model — [Exploring Lightweight LLMs for Court View Generation, arXiv:2605.16770, CC BY 4.0](https://arxiv.org/pdf/2605.16770) (UNVERIFIED VINTAGE, ~May 2026).
- **LeGen**: benchmark for criminal court views with linked legal concepts and exhaustive rationales; aims to generate a rationale per legal concept — [court-view survey/search](https://arxiv.org/pdf/2204.04859).
- **US-CVG** (English): derived from the Caselaw Access Project, processed via the IRAC (Issue-Rule-Analysis-Conclusion) framework using GPT-4, validated by legal professionals — [court view generation search results](https://aclanthology.org/2024.findings-emnlp.194.pdf).
- **Knowledge-injection CVG (KIG)** (2024): "Enhancing Court View Generation with Knowledge Injection and Guidance" — [arXiv:2403.04366](https://ar5iv.labs.arxiv.org/html/2403.04366).
- **ClaimGen-CN** (2025): large-scale Chinese legal *claim* generation dataset; criticizes prior CVG datasets (AC-NLG, MSJudge) for covering only one/few causes of action — [arXiv:2508.17234](https://arxiv.org/html/2508.17234v2) (UNVERIFIED VINTAGE).
- **Multilingual "One Law, Many Languages"** (2023): trilingual German/French/Italian benchmark including judicial-support/generation tasks; states its Swiss data is on HF under CC BY-SA — [arXiv:2306.09237](https://arxiv.org/pdf/2306.09237).

### Inferences
- Rationale generation is technically well-trodden but the released datasets are almost all Chinese CJO scrapes with no explicit license — not directly reusable for a commercial product; the English US-CVG (Caselaw Access Project, public-domain source) is more promising license-wise but is GPT-4-synthesized reasoning (quality caveat).
- The IRAC-structured US-CVG and the "rationale-per-legal-concept" LeGen framing are useful design patterns for a Vietnamese reasoning-generation feature.

### Gaps
- Explicit licenses for Court-View-Gen, AC-NLG, C3VG, CCVG, LeGen, US-CVG not confirmed.
- Original AC-NLG (Wu et al. 2020) architecture/attention details not retrieved from primary source.

## Q3: Systems that EVALUATE / CRITIQUE an existing judgment (the user's specific feature)

### Takeaway
This is an emerging but still thin area, concentrated in 2025-2026 preprints. The single closest prior art is **AR-Bench (Jan 2026)**, which operationalizes "appellate review" as error detection + classification + correction over finalized Chinese criminal judgments. LEGIT (ACL 2026) scores reasoning traces against court-derived rubrics, and an Oct 2024 paper critiques LLM inference patterns in judgments. Beyond these, true "is this judgment correct / consistent with law and precedent" checking is largely unexplored — most prior work still predicts outcomes rather than auditing finished judgments. No production-grade system found; all are research benchmarks.

### Cited Findings
- **AR-Bench** ("Benchmarking Legal Reasoning with Judgment Error Detection, Classification and Correction", arXiv:2601.22742, ~Jan 2026 — UNVERIFIED VINTAGE but full text retrieved): frames appellate review as three sequential subtasks — (1) binary error detection (does the judgment contain a legal-application error), (2) error classification (charge / prison-term / fine error), (3) error correction (generate a local fix). Dataset: 8,700 finely annotated judgments + 34,617 supplementary judgments, 20 annotation fields, six manually created error types; Chinese criminal cases. Evaluated 14 LLMs (GPT-5.1, Qwen3-Max, DeepSeek-V3.2, Kimi-K2-Thinking, GPT-4o, domain models Farui-Plus, LawLLM-7B) + fine-tuned TopJudge/LADAN/NeurJudge. Results: Qwen3-Max 92.03% detection / 94.75% classification / 74.10% correction; correction hardest (GPT-5.1 only 50.86%); domain-specific models trailed (LawLLM-7B detection 26.34%); explicit reasoning helped, adding statute text did not; on a 150-sample subset human correction macro-F1 70.10 vs 53.81 for Qwen3-Max. **License/availability**: data derived from the open-source **JuDGE** dataset under **MIT License** (adaptation retains original copyright); authors state the dataset is **for academic research only, not commercial use or actual judicial decisions** — [AR-Bench, arXiv:2601.22742](https://arxiv.org/html/2601.22742).
- **LEGIT** ("Evaluating Legal Reasoning Traces with Legal Issue Tree Rubrics", ACL 2026 / arXiv:2512.01020, CC BY 4.0 — UNVERIFIED VINTAGE ~Dec 2025): scores LLM reasoning traces against rubrics built from court judgments, treating the judge's conclusions and opposing parties' arguments as a hierarchical issue tree. Finds SOTA LLMs are not fully capable of complex LJP; two failure modes — decomposition error (missing relevant issues) and deduction error (wrong reasoning over facts) — [arXiv:2512.01020](https://arxiv.org/html/2512.01020v2).
- **Inference-pattern correctness** ("Evaluating the Correctness of Inference Patterns Used by LLMs for Judgment", arXiv:2410.09083, Oct 2024): argues correct-looking outputs can hide flawed reasoning; found a significant portion of the LLM's inference patterns are misleading or irrelevant logic — [fugumt summary of arXiv:2410.09083](https://fugumt.com/fugumt/paper_check/2410.09083v2_enmode).
- **Consistency / reliability**: a 2025 "Craft of Selective Prediction" study on ECtHR advocates reliable/selective case-outcome classification (abstain when unsure) — [arXiv:2409.18645](https://arxiv.org/pdf/2409.18645). A small hackathon study on SCOTUS found LLMs near chance accuracy with low variance across repeated decisions (treat with caution — small study) — [Women in AI Safety hackathon](https://mindyng.github.io/cv/Women_in_AI_Safety_Hackathon_Submission.pdf).
- **LLM-as-judge caveat in legal text**: a 2025 paper on unsupervised legal-text metrics concluded LLM-based evaluation enables scalable screening but, with moderate correlations/low CCC, cannot replace human judgment in high-stakes legal contexts — [per LLM-critique search cluster](https://arxiv.org/pdf/2512.01020).

### Inferences
- The user's feature ("is this judgment correct / consistent with applicable law and precedent") maps almost exactly onto AR-Bench's detection+classification+correction framing — but only for Chinese criminal judgments, research-only, no Vietnamese or precedent-consistency component. There is **no existing precedent-consistency-checking or Vietnamese judgment-critique system** found.
- The closest building blocks are: AR-Bench's error taxonomy, LEGIT's issue-tree rubric scoring, and appeal-outcome/dissent prediction (Q4) as proxies for "will this be reversed." A product combining these for Vietnam would be substantially novel prior-art-wise.

### Gaps
- No commercial/production judgment-critique system identified (all are academic benchmarks).
- No work on checking a judgment against *precedent* consistency specifically (as opposed to statute-application errors).
- AR-Bench/LEGIT arXiv IDs are very recent (late 2025/2026) and not peer-review-confirmed in all cases — vintage flagged.

## Q4: Appeal-outcome / dissent prediction (adjacent prior art for "will it be overturned")

### Takeaway
Dissent/disagreement and appeal-reversal prediction exist as a small, older strand, mostly US Courts of Appeals and (recently) Indian Supreme Court — relevant as proxies for judgment-correctness but not framed as judgment critique.

### Cited Findings
- **Indian Supreme Court reversal prediction (2025)**: "Legal Logit Model" (neural extension of multinomial logit) predicts whether the Court reverses a lower court; uses case + judge features; 80% accuracy, beating conventional logit and deep-learning baselines; notes only 928 of ~8k appeal cases show lower-court/Supreme-Court disagreement — [Frontiers in AI 2025, 10.3389/frai.2025.1671474](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1671474/full), [PMC Legal Logit](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12586031/).
- **US Courts of Appeals dissent prediction (Chen, Parthasarathy, Verma, 2017)**: ML to predict vote alignment/dissent; average F1 ~73%; key features = opinion length, citation counts, voting valence; also tests seating patterns and "memetic" phrases — [search result cluster](https://iast.fr/node/99773).

### Inferences
- Reversal/dissent prediction is a credible proxy signal for "is this judgment likely wrong," and the Indian 2025 feature set (case + judge features) is portable, but these are not reasoning-level critiques.

### Gaps
- No Vietnamese appeal/dissent-prediction work found.

## Q5: Known pitfalls / critiques of LJP

### Takeaway
The dominant critique is that headline LJP accuracy reflects shortcut learning / data leakage / surface-feature pattern-matching rather than genuine legal reasoning; a methodological critique (Medvedeva & McBride) is that the vast majority of "prediction" papers actually require the decision itself as input, so they aren't true forecasting. Fairness, temporal validity, and poor generalization are recurring concerns.

### Cited Findings
- **Shortcut learning / leakage (UK Employment Tribunal, 2026)**: high scores can come from the retrospective nature of source judgment texts; performance rose when test data contained outcome-revealing cues; a model trained only on the 4% of features flagged as leakage still beat human experts; conclusion — models exploit shortcuts when available, and inputs must be limited to what was available at prediction time — [Shortcut Learning in LJP, arXiv:2607.04261](https://www.alphaxiv.org/abs/2607.04261) (UNVERIFIED VINTAGE ~Jul 2026).
- **Surface signals / confounding (ECtHR, Santosh et al., EMNLP 2022 / 2023)**: LJP systems without expert-informed adjustments are vulnerable to shallow distracting surface signals from corpus construction, case distribution, and confounders; proposed deconfounding to better align with expert reasoning — ["Deconfounding LJP for ECtHR" review](https://liner.com/review/deconfounding-legal-judgment-prediction-for-european-court-human-rights-cases).
- **Methodological critique (Medvedeva & McBride)**: "Legal Judgment Prediction: If You Are Going to Do It, Do It Right" (NLLP Workshop 2023) — field grew >100 papers in 3 years; offers a validity checklist. A 2024 JURIX follow-up: of 171 papers claiming judgment prediction, 159 (93%) require the decision they predict as input; only the remaining 7% avoid this, and those reach <80% accuracy — [Medvedeva & McBride, arXiv:2410.21306](https://arxiv.org/html/2410.21306v2), [JURIX24 slides](https://webspace.science.uu.nl/~prakk101/talks/JURIX24.pdf).
- **LLM reasoning stays surface-level**: GLARE (2025) observed model reasoning often stays at pattern-matching rather than legal principles, motivating agentic reasoning — [GLARE, arXiv:2508.16383](https://arxiv.org/html/2508.16383v1) (UNVERIFIED VINTAGE).
- **Survey framing**: Cui et al. "A Survey on LJP: Datasets, Metrics, Models and Challenges" (IEEE Access 2023) reviews 31 LJP datasets across 6 languages and catalogs challenges — [arXiv:2204.04859](https://arxiv.org/pdf/2204.04859).

### Inferences
- For a Vietnamese product, the leakage/temporal-validity critique is the most actionable: training and inference must use only pre-decision inputs (facts, claims, statutes) and exclude any text that encodes the outcome, or metrics will be inflated and legally meaningless.
- The Medvedeva 93%/7% finding implies most "LJP" literature is really post-hoc classification, not forecasting — a product claiming "prediction" must be explicit about which it is.

### Gaps
- Fairness/bias quantification specific to LJP (demographic disparities) not deeply sourced here beyond general mentions.

## Q6: Vietnamese LJP work

### Takeaway
Vietnamese judgment-prediction work is nearly absent; the one directly relevant effort is the **ALQAC 2026 shared task** (predict plaintiff/defendant winner + retrieve supporting evidence). Other Vietnamese legal NLP resources exist (NLI, QA, LLM benchmarks) but are statute/QA-oriented, not judgment prediction — so this is largely greenfield.

### Cited Findings
- **ALQAC 2026 shared task** (Automated Legal Question Answering Competition): a task to predict whether plaintiff or defendant wins, from a short query drawn from a Vietnamese court judgment; systems also retrieve supporting evidence from a case-content corpus and relevant provisions from a law corpus; organizers expose segmented case content via official APIs rather than full judgments — [ALQAC 2026](https://sites.google.com/view/alqac2026).
- **ViLegalNLI (Apr 2026)**: Vietnamese legal natural-language-inference dataset, 42,012 premise-hypothesis pairs from official statutory documents, labeled Entailment/Non-entailment — built from statutes, not judgments — [search result](https://arxiv.org/abs/2605.0116) (arXiv ID as returned; UNVERIFIED VINTAGE).
- **VLQA**: Vietnamese legal QA dataset, 3,000+ real citizen legal questions annotated with relevant articles and long-form answers — [Vietnamese LJP search cluster](https://arxiv.org/pdf/2507.19995v1).
- **VietLegal**: Vietnamese civil-law LLM evaluation benchmark; authors note legal NLP benchmarks are English-centric and common-law/case-based, implying a civil-law gap — [search cluster](https://www.emergentmind.com/papers/2605.00116) (UNVERIFIED VINTAGE).
- General background: Cui et al. survey reviews 31 LJP datasets in 6 languages; no Vietnamese judgment-prediction dataset appears beyond ALQAC — [arXiv:2204.04859](https://arxiv.org/pdf/2204.04859).

### Inferences
- A Vietnamese judgment-prediction or judgment-critique engine would be close to first-of-its-kind; ALQAC 2026 is the only direct precedent and is win/lose outcome + evidence retrieval, not reasoning critique or precedent-consistency.
- Vietnam is a civil-law jurisdiction with a limited, recently-introduced "precedent" (án lệ) system — relevant because most LJP methodology assumes either common-law case reasoning (US/India/ECtHR) or Chinese statute-heavy criminal law (CAIL); the Chinese civil-law CVG/AR-Bench line is the closest analogue.

### Gaps
- ALQAC 2026 dataset size and license not retrieved.
- ViLegalNLI/VietLegal arXiv IDs returned by search look malformed/very recent (e.g., "2605.0116") and could not be fully verified — flag before citing.
- No published Vietnamese court-view/rationale generation or judgment-error-detection work found.

## Cross-cutting note on maturity & commercial viability
- **Research demos vs production**: everything found is research-grade (benchmarks/preprints). No production-grade judgment-critique system identified. Chinese CVG models (ShiZhi 0.5B) and LLM baselines are reproducible but data is research-only.
- **Cleanest commercial data**: LexGLUE/ECtHR (CC BY 4.0); US Katz features are public-domain-ish (PLOS ONE OA, SCDB). CAIL, ILDC, AR-Bench/JuDGE, and most Chinese CVG corpora are research-only or unstated-license — not safe to ship commercially without permission.
- **Vintage caution**: AR-Bench (2601), LEGIT (2512), ShiZhi/lightweight-CVG (2605), shortcut-learning (2607), GLARE (2508), several Vietnamese entries (2605/2507) are 2025-2026 preprints; treat as directional, re-verify before load-bearing use.
