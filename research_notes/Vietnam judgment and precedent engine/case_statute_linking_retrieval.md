# Case-to-Statute Linking, Precedent/Case-Law Retrieval, and Case-Based Reasoning

Scope: prior art for (a) linking judgments to the statutes and precedents they rely on, (b) precedent/case-law retrieval and (c) case-based/analogical reasoning — the machinery needed to ground an "is this judgment correct, based on which article and which precedent" answer. Current as of early-Nov 2026. Licenses and commercial viability captured where found; research demos flagged vs. production-grade; recent arXiv vintages flagged as unverified where the claim is author-reported only.

---

## Key Question 1 — Precedent / case-law retrieval benchmarks & competitions (COLIEE case-law tasks, LeCaRD, etc.)

### Takeaway
COLIEE (case-law Tasks 1/2/5, Canadian Federal Court data) and LeCaRD/LeCaRDv2 (Chinese criminal cases) are the two mature benchmark families for precedent retrieval. COLIEE data is access-restricted (registration + agreement, underlying judgments via Compass Law); LeCaRD is openly on GitHub but built from Chinese court documents. Neither is directly reusable for Vietnamese case law; both are strong methodological templates.

### Cited Findings
- COLIEE is an annual Competition on Legal Information Extraction/Entailment, co-located with JURISIN/JSAI; official site coliee.org, organizer pages hosted at University of Alberta (sites.ualberta.ca/~rabelo/COLIEE20xx) — [COLIEE2024 page](https://sites.ualberta.ca/~rabelo/COLIEE2024/); [COLIEE2022 page](https://sites.ualberta.ca/~rabelo/COLIEE2022/)
- COLIEE 2025 has five tasks: Tasks 1, 2, 5 = case law; Tasks 3, 4 = statute law. Task 5 is a pilot on judgment of civil cases — [NOWJ@COLIEE2025, arXiv 2509.08025](https://arxiv.org/html/2509.08025v1)
- COLIEE Task 1 (case retrieval): return the "noticed cases" (precedents) that a given query case relies on, from a large candidate case collection — [NOWJ@COLIEE2025](https://arxiv.org/html/2509.08025v1)
- COLIEE Task 2 (case entailment): for a supporting case, pinpoint which paragraph(s) entail the decision of the query case — a paragraph-level binary relevance problem — [NOWJ@COLIEE2025](https://arxiv.org/html/2509.08025v1)
- COLIEE 2025 top results (author-reported): NOWJ 1st in Task 2 (F1 0.3195); UQLegalAI 2nd in Task 1 (F1 0.2962) using a graph method (CaseLink); Task 4 best NOWJ accuracy 0.7397 (6th) — authors read low scores as evidence LLMs still struggle with real legal entailment — [NOWJ@COLIEE2025](https://arxiv.org/html/2509.08025v1); [UQLegalAI@COLIEE2025, arXiv 2505.20743](https://arxiv.org/html/2505.20743v1)
- COLIEE Task 1 corpus = case law from the Federal Court of Canada, distributed through Compass Law; scale varies by year (2023: 959 train query cases vs 4,400 candidates; 319 test queries vs 1,335 candidates; 2021: 650 queries / 4,415 candidate pool) — [nigam@COLIEE-22, arXiv 2204.07853](https://arxiv.org/pdf/2204.07853)
- "Yes, BM25 is a Strong Baseline for Legal Case Retrieval" — BM25 is competitive on COLIEE, a key practical finding for a lexical-first pipeline — [arXiv 2105.05686](https://arxiv.org/pdf/2105.05686)
- LeCaRD (v1): SIGIR 2021 short paper; 107 query cases, >43,000 candidate cases; query sampling by difficulty + diversity; relevance based mainly on factual description — [LeCaRDv2 paper, arXiv 2310.17609](https://ar5iv.labs.arxiv.org/html/2310.17609)
- LeCaRDv2 (SIGIR 2023, THUIR): 800 queries, 55,192 candidates drawn from 4.3M criminal case documents; 50 crime types; relevance broadened to three aspects — characterization, penalty, procedure; expert-annotated; repo github.com/THUIR/LeCaRDv2; source cases from the government-run China Judgment Online — [LeCaRDv2, arXiv 2310.17609](https://arxiv.org/pdf/2310.17609)

### Inferences
- The three-aspect relevance definition in LeCaRDv2 (characterization/penalty/procedure) is a reusable annotation schema for a Vietnamese precedent-relevance rubric; COLIEE's "noticed cases" framing maps well to "which precedent did this judgment rely on."
- Reported F1s around 0.30 for case retrieval and ~0.74 for entailment indicate this is an unsolved problem — a Vietnamese system should set modest accuracy expectations and keep a human-in-the-loop.

### Gaps
- No explicit COLIEE license terms found in search; data is obtained by registering and signing a usage/NDA-style agreement with organizers, and underlying Canadian judgments sit under Compass Law terms — treat as research-only, not redistributable; needs verification on the official site.

---

## Key Question 2 — Statute retrieval + statute entailment given facts (COLIEE statute tasks, bar-exam tasks); how "which article applies" is modeled

### Takeaway
COLIEE statute track (Tasks 3/4) is the canonical model: retrieve the Japanese Civil Code articles relevant to a yes/no bar-exam question (Task 3), then decide entailment Yes/No from the retrieved articles (Task 4). India's LeSICiN frames the civil-law-style version — "which statutes apply to these facts" — as multi-label Legal Statute Identification over a case–statute citation graph, and ships open code+data.

### Cited Findings
- COLIEE Task 3 (statute retrieval): given a bar-exam question, extract the subset of Japanese Civil Code articles appropriate to answer it (that entail Q or not-Q); evaluated by precision/recall/F2 because it feeds the entailment stage — [COLIEE2021 page](https://sites.ualberta.ca/~rabelo/COLIEE2021/)
- COLIEE Task 4 (statute entailment): input = yes/no bar-exam question + retrieved articles; output = Yes/No — [COLIEE2021 page](https://sites.ualberta.ca/~rabelo/COLIEE2021/)
- COLIEE statute data: questions from Japanese bar exams; Civil Code articles provided in Japanese + English translation — [COLIEE2020 CFP](https://sites.ualberta.ca/~rabelo/COLIEE2020/)
- CAPTAIN@COLIEE2023 placed 1st in Tasks 2 and 3; entailment approach split articles and queries into condition and statement components via semantic role labeling — [CAPTAIN 2023 review](https://www.themoonlight.io/review/captain-at-coliee-2023-efficient-methods-for-legal-information-retrieval-and-entailment-tasks)
- LeSICiN (AAAI 2022, IIT Kharagpur): Legal Statute Identification = find statutes relevant to a case's facts; adds the case↔statute citation network on top of text; heterogeneous graph of statutes + training docs, predicts links for new documents; ILSI dataset (Indian court case facts + Indian Penal Code), multi-label; code+data at github.com/Law-AI/LeSICiN — [LeSICiN, arXiv 2112.14731](https://www.arxiv.org/pdf/2112.14731); [AAAI 2022](https://ojs.aaai.org/index.php/AAAI/article/view/21363)
- "Statute-enhanced lexical retrieval of court cases for COLIEE 2022" — injecting statute signal improves case retrieval, showing case↔statute links aid precedent retrieval — [arXiv 2304.08188](https://arxiv.org/pdf/2304.08188)

### Inferences
- "Which article applies to these facts" is modeled two ways: (1) retrieval-then-entailment over a closed statute set (COLIEE) and (2) multi-label classification over a graph that encodes historical case→statute citations (LeSICiN). For Vietnam's civil-law system, the LeSICiN graph framing is the closer conceptual fit and is open-licensed to study.
- CAPTAIN's condition/statement decomposition is reusable: Vietnamese statutes also split into hypothesis (điều kiện) and disposition (hệ quả), enabling the same SRL-style matching.

### Gaps
- LeSICiN license not confirmed from search (Law-AI repos are generally research-use; verify the specific LICENSE file).

---

## Key Question 3 — Linking a judgment to the specific provisions & prior cases it cites (citation extraction, networks, treatment detection)

### Takeaway
US-centric eyecite (BSD-2-Clause, production-grade) is the only clearly open, battle-tested citation extractor, but it does extraction/parsing only — not treatment classification. Treatment detection (followed/distinguished/overruled) is dominated by commercial tools (Vaquill) and patents (Thomson Reuters/LexisNexis lineage); open treatment classifiers are essentially absent, and a 2026 arXiv paper frames multi-label treatment classification as still open. No non-US open citation tooling surfaced for civil-law jurisdictions — this is a build-it area for Vietnam.

### Cited Findings
- eyecite (Free Law Project, behind CourtListener): open-source Python citation extractor; recognizes full citations, short forms, "supra", "id."; tested against >50M citations; used to annotate CourtListener and the Caselaw Access Project; BSD 2-Clause license (all Free Law libraries) — [Free Law open-source tools](https://free.law/open-source-tools); [eyecite project page](https://free.law/projects/eyecite); [eyecite whitepaper](https://free.law/pdf/eyecite-whitepaper.pdf)
- eyecite does extraction/parsing, not treatment classification — a treatment layer must be built/fine-tuned on top — [search synthesis of Free Law docs](https://free.law/projects/eyecite)
- Commercial treatment: Vaquill's citation graph labels citing cases as Followed, Distinguished, Overruled, Questioned, or Superseded, with a citation-network API — [Vaquill citation graph](https://www.vaquill.ai/docs/guides/citation-graph)
- Patent lineage (incumbent legal publishers): rule-based negative-treatment detection scans opinions for overruling language via verb-tense and proximity rules; "depth of treatment" symbol assigned by how much text a court devotes to a citation; "distinguished" and implied-overruling also covered — [USPTO 8145675/8250118/7778954/8661066](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8145675); [implied-overruling app 11615492](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11615492)
- A 2026 arXiv paper benchmarks LLMs on multi-label precedent treatment classification and notes CaseHOLD only gives a binary overruled-or-not label from a single holding sentence (i.e., prior data is thin) — [search result, arXiv 2605.17691 — UNVERIFIED vintage/ID](https://arxiv.org/pdf/2605.17691)

### Inferences
- A Vietnamese judgment→provision/precedent linker will need a custom citation parser (eyecite's architecture is a reusable template but its regexes are US-reporter-specific and won't transfer; Vietnamese citations reference Điều/Khoản/Luật and Án lệ số NN/YYYY/AL, which are regular and tractable to rule-based extraction).
- Treatment detection is the hardest and least-supported sub-problem; for Vietnam, "án lệ" are explicitly curated by the Supreme Court, so overruling/superseding status may be obtainable from official metadata rather than NLP inference.

### Gaps
- Could not verify the 2026 treatment-classification arXiv paper's ID/vintage — flagged unverified.
- No open-source, non-US treatment detector or civil-law citation-network dataset found.

---

## Key Question 4 — Case-based reasoning (CBR) in AI&Law: HYPO/CATO lineage and modern neural CBR; what is reusable

### Takeaway
The HYPO→CATO factor/dimension tradition plus Horty's precedential-constraint formalism give a rigorous, reusable conceptual vocabulary (factors, dimensions, 3-ply argument, reason vs. result model). It is symbolic and hand-engineered; modern work connects factor reasoning to ML explainability but there is little off-the-shelf neural CBR. Reusable as a design scaffold and explanation layer, not as a ready library.

### Cited Findings
- HYPO used dimensions (each with a continuous/discrete magnitude); CATO used factors (points on dimensions); HYPO's dimensions are independent while CATO arranges factors in a hierarchy; only dimensions with a basis in law and values seen in real cases were used — [Atkinson/Bench-Capon et al., JURIX](https://www.csc.liv.ac.uk/~katie/jurix13b.pdf)
- CATO's 3-ply argument pattern: (1) cite a favorable precedent sharing factors; (2) opponent gives counter-examples and distinguishes; (3) original side distinguishes the counter-example and adds reasons — [JURIX paper](https://www.csc.liv.ac.uk/~katie/jurix13b.pdf)
- Argumentation schemes for reasoning with factors + dimensions formalized in ASPIC+ (Atkinson, Bench-Capon, Prakken, Wyner, JURIX 2013) — [jurix13b.pdf](https://www.csc.liv.ac.uk/~katie/jurix13b.pdf)
- Horty's precedential-constraint models: how a new case must be decided to preserve consistency; uses the reason model (not the result model); extended from factors to dimensions by Horty/Rigoni; Prakken 2021 proposes a less expressive but easier-to-apply alternative — [Prakken, cbrailj20.pdf](https://webspace.science.uu.nl/~prakk101/pubs/cbrailj20.pdf)
- Hierarchical precedential constraint adds factor hierarchies and multi-step (not single-step) reasoning from case base to outcome — [Utrecht: Hierarchical precedential constraint](https://research-portal.uu.nl/en/publications/hierarchical-precedential-constraint/)
- Factor-based reasoning is acquiring a new role in explaining ML predictions; a line of work links factor-based CBR with logical specification of classifiers — [Modelling and Explaining Legal Case-based Reasoners through Classifiers](https://arxiv.org/html/2505.00474v1)

### Inferences
- Reusable for the Vietnam engine: (a) represent each precedent as a set of factors/dimensions tied to legal issues; (b) use the 3-ply scheme to structure the "why is this judgment correct / how is it analogous" explanation; (c) use precedential-constraint logic to flag when a new outcome is inconsistent with the án lệ base. These are civil-law-compatible as explanation structures even though the tradition is common-law.

### Gaps
- No mature, reusable neural CBR library surfaced; the tradition remains largely symbolic/hand-built. Factor annotation for Vietnamese cases would be a from-scratch effort.

---

## Key Question 5 — Arguing "this case is analogous to precedent X therefore outcome Y": analogical reasoning with LLMs (concrete recent work)

### Takeaway
Several 2024–2026 systems do retrieval-plus-reasoning: AALawyer (ACL 2026) pairs symbolic statute retrieval with an "Analogical Precedent Retrieval" module; CaseLink (SIGIR 2024) uses case-connectivity graphs; SAILER (SIGIR 2023) and PromptCase exploit case structure/prompts; ReaKase-8B (Oct 2025) fine-tunes an LLM over extracted facts/issues/relation-triplets/reasoning. Most are research demos with author-reported gains; treat metrics cautiously.

### Cited Findings
- AALawyer (ACL 2026): symbolic constrained retriever for statutes + Analogical Precedent Retrieval (APR) module using dense retrieval over a newly collected large criminal dataset; authors report reduced hallucination and better explainability — [ACL 2026, 2026.acl-long.633](https://aclanthology.org/2026.acl-long.633.pdf)
- Section-weighted hybrid case retrieval (June 2026): two-stage — lexical+semantic candidate gathering, then compare the reasoning sections of query vs. candidate cases; premise is that true analogy needs legal reasoning beyond surface word overlap — [arXiv 2606.03138 — UNVERIFIED vintage](https://alphaxiv.org/abs/2606.03138v1)
- ReaKase-8B (Oct 2025): fine-tunes an LLM to represent cases via extracted facts, issues, relation triplets, and reasoning; code public — [arXiv 2510.26178](https://arxiv.org/abs/2510.26178v1)
- CaseLink (SIGIR 2024): inductive graph learning; builds a Global Case Graph from case-to-case semantic similarity + case-to-charge relations; GNN case representations; trains on precedent-reference relations via contrastive loss with degree regularization; SOTA on COLIEE 2022/2023 (author-reported); code github.com/yanran-tang/CaseLink — [arXiv 2403.17780](https://arxiv.org/html/2403.17780v3)
- CaseLink reproducibility study (accepted SIGIR 2025) reproduces on COLIEE 2022/2023 and notes reproducibility is a known challenge in this area — caution on original claims; code github.com/doGregor/caselink_reproducibility — [arXiv 2504.08400](https://arxiv.org/html/2504.08400v1)
- SAILER (SIGIR 2023): structure-aware pretrained LM; asymmetric encoder-decoder reconstructing key legal elements + judgment result to build case representations — [arXiv 2304.11370](https://arxiv.org/pdf/2304.11370)
- PromptCase / "Prompt-based Effective Input Reformulation for Legal Case Retrieval": instructive legal prompts help, misleading prompts hurt, irrelevant prompts slightly hurt — [arXiv 2309.02962](https://arxiv.org/pdf/2309.02962)

### Inferences
- The dominant reusable pattern is two-stage: cheap lexical/semantic recall → structure-aware or LLM reasoning over the reasoning/holding sections → analogical justification. AALawyer's explicit split (symbolic statute retrieval + analogical precedent retrieval) is the closest architectural blueprint for the "which article + which precedent" grounding the Vietnam engine needs.

### Gaps
- Two cited 2026 arXiv items have unverifiable IDs/vintages (2606.03138; the 2026 treatment paper) — flagged. ACL 2026 AALawyer link is from ACL Anthology (more reliable) but metrics are author-reported.
- Little work specifically on LLMs doing common-law-style analogy with explicit distinguishing; mostly retrieval-framed.

---

## Key Question 6 — Vietnamese case-law linking (honest report)

### Takeaway
There is NO dedicated public Vietnamese precedent-retrieval (án lệ) dataset. Existing Vietnamese legal NLP is statute-centric (VLQA, BKAI VNLAWQC, large thuvienphapluat corpora). Critically, ALQAC 2026 is the first shared task to directly target "predict the case outcome + retrieve the governing legal provisions + case evidence" for Vietnamese court judgments — essentially the exact "is this judgment correct, based on which article" problem — but it uses an organizer-gated API and prohibits proprietary/large models. The án lệ corpus itself (~82 precedents as of Dec 2025) is small and officially curated.

### Cited Findings
- ALQAC = Automated Legal Question Answering Competition, annual, co-located with KSE; inspired by COLIEE, for low-resource Vietnamese; first edition 2021 (Vietnamese + Thai, but participants used only Vietnamese) — [ALQAC 2024](https://sites.google.com/view/ALQAC-2024); [arXiv 2204.10717](https://www.arxiv.org/pdf/2204.10717)
- ALQAC statute retrieval: given a legal question, return relevant articles; main metric macro-averaged F2 (recall-weighted) — [ALQAC overview, arXiv 2204.10717](https://www.arxiv.org/pdf/2204.10717)
- ALQAC 2026 (Nguyen Lab – JAIST): single shared task "Vietnamese legal case understanding" = case outcome prediction + legal provision retrieval + case evidence retrieval. Outcome labels: A_WIN, PARTIAL_A_WIN, PARTIAL_B_WIN, B_WIN (full/partial/reject of plaintiff claims). Law evidence scored micro-F1; case queries omit verdict/reasoning/gold evidence; case content accessed only via an organizer Case Content API (1 req / 5s; recall penalized beyond 2n calls, zero at 5n). Rules: proprietary models (ChatGPT/GPT-4/Claude/Gemini) prohibited; only open-weight <10B params; no externally annotated legal QA/entailment datasets; 3 submissions/day — [ALQAC 2026](https://sites.google.com/view/alqac2026)
- VLQA: first large high-quality Vietnamese legal QA dataset; >3,000 real citizen questions annotated by professionals with statutory references; covers Vietnamese statutory law, NOT precedents — [VLQA, arXiv 2507.19995](https://arxiv.org/html/2507.19995v1)
- BKAI VNLAWQC / VNSynLawQC: Vietnamese legal retrieval dataset sourced from the Vietnamese Law Library (statutory) — [arXiv 2412.00657](https://arxiv.org/html/2412.00657v1)
- th1nhng0/vietnamese-legal-documents: 518,255 Vietnamese legal documents from thuvienphapluat.vn; CC BY 4.0, research-use intended — [HF dataset](https://huggingface.co/datasets/th1nhng0/vietnamese-legal-documents)
- Gated HF "vietnamese_legal_retrieval" (thanhdath): ~200K question↔article/document pairs; access requires sharing contact info — [HF dataset](https://huggingface.co/datasets/thanhdath/vietnamese_legal_retrieval)
- VLegal-Bench explicitly notes existing legal benchmarks emphasize common-law case-based reasoning/precedent interpretation, a poor fit for Vietnam's civil-law system — [VLegal-Bench, arXiv 2512.14554](https://arxiv.org/html/2512.14554v4)
- Vietnamese precedents (án lệ) are centrally curated by the Supreme People's Court; numbering reached No. 82/2025/AL — Decision 339a/QĐ-CA (25/12/2025) published án lệ 73–82/2025/AL; No. 81/2025/AL applies to trials from 01/02/2026; 20 draft precedents for 2025 published 14/11/2025 — [thuvienphapluat precedent news](https://thuvienphapluat.vn/hoi-dap-phap-luat/toan-van-quyet-dinh-339aqdca-cong-bo-10-an-le-chi-tiet-nhu-the-nao-138079767.html); [TANDTC 20 draft precedents](https://thuvienphapluat.vn/banan/tin-tuc/toa-an-nhan-dan-toi-cao-cong-bo-20-du-thao-an-le-nam-2025-19142.html)
- English precedent lists on lawnet.vn (e.g., a page listing 63 precedents; another listing 43) and a VN-law MCP tool on Glama listing "90 án lệ chính thức" with keyword/full-text lookup — counts differ by source/date — [lawnet 63 precedents](https://lawnet.vn/thong-tin-phap-luat/en/an-le/total-of-63-precedents-in-vietnam-latest-update-113041.html); [Glama VN-luat MCP](https://glama.ai/mcp/servers/phuocnguyen1308-creator/vn-luat-mcp/tools/liet_ke_an_le)

### Inferences
- ALQAC 2026 is the single most relevant prior art for this project's core goal and should be tracked closely: its label schema (A_WIN/PARTIAL/B_WIN) and its "provision retrieval as evidence for an outcome" framing are directly adoptable. Its no-proprietary-model / <10B-param rules are a competition constraint, not a product constraint — the project can ignore them but can reuse the data design.
- The án lệ corpus is tiny (dozens, not thousands) and officially curated with structured metadata (number, adoption date, effective date, superseding status), so precedent linking in Vietnam is more a curated-knowledge-base + matching problem than a large-scale retrieval problem — far more tractable than COLIEE/LeCaRD scale.
- No treatment-detection problem at scale: the Supreme Court explicitly announces when án lệ cease to apply, so "overruled/superseded" can come from official decisions.

### Gaps
- No ready-made, downloadable, licensed án lệ dataset with case→precedent/article links found; the án lệ full texts' license/redistribution status was not confirmed (likely government-published, reusable, but verify).
- No cumulative official count of án lệ confirmed; "82" is inferred from sequential numbering as of Dec 2025 — verify against the Supreme People's Court's own tally.
- ALQAC 2026 dataset license/reuse terms not stated on the site; access appears competition-bound via the organizer API.

---

## Cross-cutting notes on maturity & license

- Production-grade / open: eyecite (BSD-2-Clause, US-only extraction). CaseLink, SAILER, ReaKase-8B, LeSICiN = research code on GitHub (verify per-repo LICENSE; typically research-use).
- Benchmark data access: COLIEE = registration + agreement, underlying judgments under Compass Law (not redistributable). LeCaRD/LeCaRDv2 = GitHub, Chinese court source. ILSI (LeSICiN) = GitHub. VLQA/BKAI = arXiv/HF, statutory. th1nhng0 VN corpus = CC BY 4.0.
- Commercial: Vaquill (citation graph + treatment labels + API) is the clearest commercial analog for treatment/citation-network features; incumbent treatment detection (Shepard's/KeyCite-style) is patent-encumbered.
- Recency flags: arXiv 2606.03138 and the 2026 treatment-classification paper (quoted as 2605.17691) have IDs implying mid/late-2026 and could not be independently verified — report-writer should treat as tentative.
