# Automated Contract Review Prior Art — Omission Detection & Compliance Checklists

Scope: datasets, benchmarks, open-source tools, techniques for contract clause extraction, risk flagging, and especially MISSING-clause / omission detection, plus how commercial vendors describe playbook/gap features. Current as of late 2026.

## Q1. Core datasets: CUAD, ContractNLI, MAUD (task, size, annotation, license, commercial use)

### Takeaway
All three flagship public contract datasets (CUAD, ContractNLI, MAUD) are released under CC BY 4.0, which permits commercial use with attribution. All three cover review of clauses/provisions that are PRESENT; none is built to detect missing clauses, though ContractNLI's "NotMentioned" label is the closest native analogue to absence.

### Cited Findings
- **CUAD (Contract Understanding Atticus Dataset)** — created by The Atticus Project + Dan Hendrycks et al., NeurIPS 2021 (arXiv 2103.06268). Task: highlight the salient portions of a contract that a human reviewer should look at ("finding needles in a haystack"); framed as extractive QA (span extraction) in the `cuad-qa` HF release. The abstract reports "over 13,000 annotations" created with dozens of legal experts. — [arXiv abstract](https://arxiv.org/abs/2103.06268), [GitHub repo](https://github.com/TheAtticusProject/cuad)
- CUAD is widely documented as **510 commercial contracts annotated for 41 clause/label categories** (e.g., governing law, limitation of liability, non-compete, change of control); one search summary stated "510 English commercial contracts in which 41 different types of legal clauses have been annotated." — [search summary of CUAD](https://huggingface.co/datasets/theatticusproject/cuad-qa)
- **CUAD license: CC BY 4.0.** The HF loading script states: "CUAD is licensed under the Creative Commons Attribution 4.0 (CC BY 4.0) license"; the dataset card lists `cc-by-4.0`; IEEE DataPort and Google Dataset Search mirrors agree. Commercial use allowed with attribution. — [HF cuad.py script](https://huggingface.co/datasets/cuad/blob/refs%2Fpr%2F1/cuad.py), [IEEE DataPort listing](https://ieee-dataport.org/documents/cuad-contract-understanding-atticus-dataset-legal-ai-and-contract-review)
- **ContractNLI** — Yuta Koreeda & Christopher Manning, Findings of EMNLP 2021 (arXiv 2110.01799). Task: document-level natural language inference — given a contract and a fixed set of hypotheses, label each as ENTAILMENT, CONTRADICTION, or NOTMENTIONED, and identify supporting evidence spans. — [arXiv PDF](https://arxiv.org/pdf/2110.01799), [Stanford project page](https://stanfordnlp.github.io/contract-nli)
- ContractNLI size: **17 hypotheses annotated across 607 NDAs (non-disclosure agreements)**; the 17 hypotheses are fixed across all contracts including the test set. Evidence identification is modeled as multi-label classification over spans. — [arXiv PDF 2110.01799](https://arxiv.org/pdf/2110.01799), [ACL Anthology 2021.findings-emnlp.164](https://preview.aclanthology.org/new-sigs/2021.findings-emnlp.164/)
- **ContractNLI license: CC BY 4.0** ("Our dataset is released under CC BY 4.0"). Code at `stanfordnlp/contract-nli-bert`. Commercial use allowed with attribution. — [arXiv PDF 2110.01799](https://arxiv.org/pdf/2110.01799)
- **MAUD (Merger Agreement Understanding Dataset)** — Steven Wang et al. (incl. Dan Hendrycks), EMNLP 2023 (arXiv 2301.00876). Built on the American Bar Association's 2021 Public Target Deal Points Study. Task: answer 92 reading-comprehension questions given extracted deal-point text from merger agreements. — [arXiv abstract 2301.00876](https://arxiv.org/abs/2301.00876v1), [EMNLP 2023 proceedings](https://preview.aclanthology.org/nschneid-patch-1/2023.emnlp-main.1019)
- MAUD size: **~39,000 examples / ~47,000 annotations**, from legal text extracted from **152 public English-language merger agreements** sourced from SEC EDGAR. Described as the only large-scale AND expert-annotated English legal reading-comprehension dataset. — [DeepAI publication page](https://deepai.org/publication/maud-an-expert-annotated-legal-nlp-dataset-for-merger-agreement-understanding), [MarkTechPost](https://www.marktechpost.com/2023/01/10/check-out-this-legal-nlp-dataset-called-maud-with-over-39000-examples-released/)
- **MAUD license: CC BY 4.0** (per Atticus Project datasets page and arXiv HTML license line). Commercial use allowed with attribution. — [arXiv HTML 2301.00876v3](https://arxiv.org/html/2301.00876v3), [Atticus datasets page](https://theatticusproject.pages.dev/datasets/)

### Inferences
- For a commercial product, all three datasets are safe to use for training/evaluation provided attribution is given; CC BY 4.0 has no non-commercial or share-alike restriction. (This is the single most favorable license posture among serious legal NLP datasets.)
- CUAD's 41 clause types effectively define a clause-presence taxonomy — one can derive a "presence/absence" signal by checking whether a model found a span for each of the 41 categories, which is a practical bridge toward omission detection even though CUAD was not labeled for it.

### Gaps
- CUAD's exact per-category annotation counts and the canonical "510 contracts / 41 categories" figure were confirmed via secondary summaries, not read directly from the GitHub README in this session (GitHub page fetch returned limited text); numbers are consistent across many sources so confidence is high.

## Q2. Does ANY public dataset/tool explicitly address MISSING/omitted clauses? (the key gap question)

### Takeaway
Omission detection is largely an unsolved / under-served gap in public datasets. No mainstream public benchmark is labeled specifically for "this contract lacks clause X." The nearest public analogues are ContractNLI's NOTMENTIONED label and LegalBench's Contract QA (yes/no "does this contract contain provision type Y"). The only work treating missing-clause detection as a first-class task is a construction-contracts paper (dataset/code not public) and some domain-specific studies (privacy policies). In practice, omission detection is implemented commercially as playbook/checklist compliance, not learned from a dedicated dataset.

### Cited Findings
- A targeted search for a "missing-clause detection dataset" found **no public benchmark labeled explicitly for that task**; the closest matches are the construction-contract paper and ContractNLI's "not mentioned" framing. — [WebSearch synthesis, missing clause datasets]
- **Construction contracts (closest dedicated work):** Jallow et al.-style paper, "Intelligent detection on construction project contract missing clauses based on deep learning and NLP," *Engineering, Construction and Architectural Management* (2023/2025), DOI 10.1108/ECAM-02-2023-0172. Two-stage method: (1) multi-label classifier over long construction-contract clauses flags which clause labels are absent; (2) a clause-similarity algorithm adapting the **MatchPyramid** model (image-matching-inspired) combined with **BERT** finds missing substantive content. Dataset: **1,322 construction project contracts**. Results: multi-label classification accuracy ~93%, similarity-matching accuracy ~83%, recall and F1 above 0.7 for both. **No public dataset or code released** (paywalled, no repo mentioned). — [Emerald article](http://www.emerald.com/ecam/article/32/3/1546-1580/1242389)
- **ContractNLI NOTMENTIONED label** is the strongest public analogue to absence: for each of 17 fixed hypotheses it classifies whether the contract does NOT mention the concept — effectively presence/absence of a concept per NDA. — [Stanford project page](https://stanfordnlp.github.io/contract-nli)
- **LegalBench Contract QA task** (`contract_qa`): yes/no questions about whether a contract clause is an instance of a given provision type (e.g., severability, confidentiality, BIPA consent, PII breach) — generalizes across clause types and can serve as a presence/absence classifier. Part of LegalBench (Guha et al. 2023, arXiv 2308.11462; 162 tasks). — [LegalBench paper](https://arxiv.org/pdf/2308.11462)
- **Privacy policies:** a cited study used an SVM to detect missing clauses in privacy policies, reporting precision 0.85 / recall 0.96. — [WebSearch synthesis citing privacy-policy study]
- **AGB-DE** (German consumer contracts, arXiv 2406.06809): 3,764 expert-annotated/legally-assessed clauses; focus is VOID-clause detection (assessing present clauses as legal/illegal), NOT absence; best approach did not exceed F1 0.54. — [arXiv AGB-DE](https://arxiv.org/html/2406.06809v1)
- **German employment contracts** (TUM/SEBIS IRIS benchmark, 2025, arXiv 2501.17194): 1,094 samples each = a clause + its section title + three annotations, covering legality and fairness review (present-clause assessment). — [TUM SEBIS publication](https://www.cs.cit.tum.de/sebis/publications/2025/wa25a)

### Inferences
- Omission detection is treated as a GAP/COMPLIANCE problem, not a supervised NLP dataset problem: the dominant public pattern is "define a checklist/playbook of required clauses, then classify presence/absence per item" (ContractNLI-style NOTMENTIONED, LegalBench Contract QA yes/no). A product can build omission detection on top of CUAD's 41-category taxonomy or a custom required-clause list rather than wait for a dedicated dataset.
- There is a genuine white-space opportunity: no large, expert-annotated, commercially-licensed benchmark exists for "required clause missing" across general commercial contracts — the construction paper proves the task is tractable (~93% multi-label, ~83% similarity) but keeps its data private.

### Gaps
- No public gold dataset labeling missing/omitted clauses for general commercial contracts was found. The construction-contract dataset (1,322 contracts) is not released.
- The privacy-policy SVM study's precise citation/URL was not captured (appeared only as a secondary search synthesis) — treat the 0.85/0.96 figures as unverified.

## Q3. Open-source contract-review pipelines / libraries (segmentation, classification, risk scoring)

### Takeaway
There is no single canonical end-to-end open-source contract-review pipeline; the ecosystem is a set of model cards and libraries. The practical stack is: LexNLP (segmentation/extraction) → a clause classifier fine-tuned on CUAD/LEDGAR (Legal-BERT/ModernBERT) → optional LLM segmentation. Licenses vary and matter (LexNLP is AGPL; atticusclassifier is MIT).

### Cited Findings
- **LexNLP** (LexPredict, GitHub): open-source Python library for legal NLP including segmentation and extraction features; reported under an **AGPL** license — copyleft, important for commercial/SaaS use. — [WebSearch synthesis citing arXiv 1806.03688]
- **atticusclassifier** (GitHub `jsv4`): **MIT-licensed** spaCy classifiers (BERT and Word2Vec) trained on the Atticus/CUAD open contract label corpus; small project (~14 stars). — [awesome.ecosyste.ms listing](https://awesome.ecosyste.ms/projects/github.com%2Fjsv4%2Fatticusclassifier)
- **ContractGuard clause classifier** (HF `AnuragBodkhe/contractguard-clause-classifier`): Legal-BERT model labeling a single clause among 40 types; trained on CUAD + LEDGAR combined; described as the first stage of an open-source clause-analysis platform with five models total. — [HF model card](https://huggingface.co/AnuragBodkhe/contractguard-clause-classifier)
- **LiTiL Clause Classifier** (HF `litillabs/litil-clause-classifier`): ModernBERT-based; assigns one taxonomy label per provision; designed to run after parsing + clause segmentation, keeping source location of each provision. — [HF model card](https://huggingface.co/litillabs/litil-clause-classifier)
- **ruBERT-tiny2 clause classifier** (HF `alexmaryin/clause-classificator-rubert-tiny2`): classifies document structure (titles, clauses, sub-clauses, tables) into 10 classes; Russian-only. — [HF model card](https://huggingface.co/alexmaryin/clause-classificator-rubert-tiny2)
- **Two-stage NDA analysis** (arXiv 2603.09990): uses LLaMA-3.1-8B-Instruct for segmentation + fine-tuned Legal-RoBERTa-Large for classification; reports ROUGE F1 0.95 for segmentation; references a Kleister-NDA GitHub repo. — [arXiv 2603.09990](https://arxiv.org/pdf/2603.09990)
- **LEDGAR** is a commonly paired corpus for clause classification (used with CUAD to train ContractGuard). — [HF ContractGuard model card](https://huggingface.co/AnuragBodkhe/contractguard-clause-classifier)

### Inferences
- A production pipeline would most likely combine LexNLP or an LLM for segmentation, a CUAD/LEDGAR-trained Legal-BERT/ModernBERT classifier for clause typing, then layer a playbook/checklist step for omission detection and risk scoring — the last step being custom, not off-the-shelf.
- The AGPL on LexNLP is a real commercial constraint; the MIT atticusclassifier and CC BY 4.0 datasets are cleaner starting points for a proprietary product.

### Gaps
- No widely-adopted, actively-maintained, fully end-to-end open-source "contract review" product (segmentation + classification + risk + omission) surfaced; the pieces exist but integration is left to the builder.
- Exact current license of LexNLP (AGPL vs dual-license) should be re-checked at the repo before use.

## Q4. How commercial products describe omission/missing-clause & playbook features (public marketing/docs only)

### Takeaway
All major contract-review vendors (LegalOn, Spellbook, Luminance, Robin AI) market missing-clause / "missing term" detection, universally implemented via PLAYBOOKS (user-encoded required clauses, standard positions, and fallbacks) rather than a learned omission model. The AI compares the contract to the playbook and reports which requirements are met vs. missing. All claims are vendor/third-party; no independent head-to-head accuracy benchmark for omission detection was found.

### Cited Findings
- **LegalOn "My Playbooks":** LegalOn's help docs state its AI sends the user's playbook instruction text to a pre-trained model to decide whether each requirement is met, with each alert showing a status such as MET. Launched Jan 2025. Marketing cites "95% of in-house legal teams report gaps in playbook coverage" and "54% don't have playbooks," pitching AI gap-filling. — [LegalOn Intercom help article](https://intercom.help/legalon/en/articles/10159978-review-contracts-with-my-playbooks-in-legalon-contract-ai), [Artificial Lawyer coverage](https://www.artificiallawyer.com/2025/01/21/legalon-launches-personalized-ai-review-playbooks-demo/), [LegalOn AI-ready playbooks](https://www.legalontech.com/post/ai-ready-playbooks)
- **Robin AI playbooks:** lets teams codify "standard positions, fallback positions, and must-have clauses" into a digital playbook; the AI reads the contract, labels clauses, and lists markup suggestions based on predefined positions, fallbacks, and required clauses. Word add-in explicitly markets: "detect and highlight missing clauses, placeholders, or undefined terms to prevent delays before signing." — [Robin AI custom playbook features](https://robinai.com/post/latest-custom-playbook-features), [Robin AI Word add-in](https://robinai.com/news-and-resources/robin-university/word-add-in-an-intelligent-ai-sidekick-for-contract-review), [Robin AI FAQ](https://robinai.com/faqs)
- **Luminance:** classifies clauses green (acceptable) / amber (review) / red (unacceptable) vs. organizational standards; "Automatic Document and Clause Compliance" tools compare each clause to a chosen standard/model clause, so a missing clause surfaces as a gap vs. the model document; Diligence product gives insight across 1,000+ legal concepts (clauses present, governing law, term). Secondary sources say it identifies "non-standard clauses, missing provisions, and risk indicators." — [Luminance legal AI](https://www.luminance.com/legal-contract-management-software/), [Dentons case study](https://www.casestudies.com/company/luminance/case-study/dentons-dusseldorf-leverages-ai-technology-in-contract-review)
- **Spellbook:** third-party comparisons credit Spellbook (and Luminance) with "missing-term detection and market benchmarking"; playbooks encode fallback positions for recurring clause types (NDAs, MSAs). Spellbook markets a dedicated Playbooks product. — [rfp.wiki Spellbook/Luminance comparison](https://www.rfp.wiki/vendors/spellbook/luminance), [Spellbook Playbooks](https://www.spellbook.legal/playbooks-3)
- **Setup cost & reliability caveats:** vendor playbooks require significant up-front effort (Robin AI: "weeks of playbook setup and training on past redlines"); reviewers report AI hallucinations/factual errors needing attorney verification; one (unsourced) figure claims 40–60% of Robin AI's AI-drafted redlines needed significant rewriting. — [rfp.wiki Robin AI/Spellbook](https://www.rfp.wiki/vendors/robin-ai/spellbook)
- **Robin AI corporate-status conflict (late 2025/early 2026):** one aggregator page says Robin AI sold its managed legal services division to Scissero (Dec 2025) and Microsoft acqui-hired the remaining tech team (early 2026), ending standalone operations; another says Microsoft only hired key engineering staff without acquiring the entity. Neither verified against a primary source. — [rfp.wiki Robin AI pages](https://www.rfp.wiki/vendors/robin-ai/spellbook); status described in past tense by [Pangea glossary](https://pangea.app/glossary/robin-ai)

### Inferences
- The commercial state of the art for omission detection = playbook-driven compliance checking (required-clause list → per-item met/missing status), not a trained "missing clause" classifier. This validates building omission detection as a checklist/playbook layer rather than a supervised model.
- The recurring vendor pain point (playbook setup effort, 95% report coverage gaps) is a product opportunity: automating playbook creation and reducing setup time is a differentiator.

### Gaps
- No primary LegalOn doc read directly (the help.legalontech.com redirect returned 404; relied on the Intercom mirror + marketing). Exact status labels beyond "MET" (e.g., "MISSING"/"NOT MET") not confirmed from primary source.
- Robin AI's current operating status (standalone vs. absorbed by Microsoft) is genuinely unclear from available sources — flag for verification before citing in a report.
- No vendor-neutral benchmark of omission-detection accuracy across LegalOn/Spellbook/Luminance/Robin AI exists publicly.

## Q5. Techniques to turn a compliance requirement into a checklist and verify a document against it

### Takeaway
The established pattern is: encode requirements as a structured checklist, have an LLM check each item against the document, return per-item status (met/gap) with an observation + recommendation, and route low-confidence items to human review with an audit trail. Reported LLM checklist-verification accuracy (~86.6% in one study) is near human-level but errors cluster on items the model structurally cannot verify.

### Cited Findings
- **Academic:** a 2025 arXiv survey (LLMs for automated scholarly review, 2501.10326) cites Liu & Shah (2024) finding LLMs reached ~86.6% accuracy on checklist verification, described as comparable to human performance; errors clustered on items the model couldn't handle (e.g., verifying figures with a text-only model). — [arXiv 2501.10326](https://arxiv.org/pdf/2501.10326)
- **Commercial document checker pattern:** ValidMind's Document Checker compares documentation against a selected regulatory standard using a structured checklist, flags gaps, and returns an observation + recommendation for each question. — [ValidMind docs](https://docs.validmind.ai/guide/documentation/check-documents-for-compliance.html)
- **Retrieval + constrained review pattern (omission-specific):** a developer write-up describes missing-clause detection as a separate pass AFTER clause extraction, combining a deterministic retrieval stage with a constrained model review (general technique, not a specific vendor). — [DEV.to "The Clause Nobody Caught"](https://dev.to/muazashraf/the-clause-nobody-caught-how-i-built-missing-clause-detection-for-contracts-3eef)
- **Audit practice:** practitioner guidance recommends checking every factual claim/citation against primary sources (models invent references), rating each section's confidence, and sending low-confidence sections to human review. — [practitioner guide](https://frisbyaiops.pages.dev/free-guide/)
- **LegalOn mechanism (vendor):** playbook instruction text → pre-trained model → met/unmet determination per requirement (a concrete instance of requirement-to-check conversion). — [LegalOn help](https://intercom.help/legalon/en/articles/10159978-review-contracts-with-my-playbooks-in-legalon-contract-ai)

### Inferences
- The convergent design across academia (checklist verification), compliance tooling (ValidMind), and legal vendors (playbooks) is the same three-part loop: (1) structured requirement list, (2) per-item LLM check returning status + evidence + recommendation, (3) human-in-the-loop on low-confidence/flagged items. For omission detection specifically, a retrieval-then-constrained-review two-pass design (find the clause if present; if not found, flag absence) is the practical architecture.
- Pairing a deterministic retrieval/presence check with an LLM reduces hallucinated "it's missing" false positives — the retrieval stage grounds the absence claim.

### Gaps
- No single authoritative standard/spec for compliance-checklist verification exists; approaches are a mix of research and vendor practice.
- The ~86.6% figure is from the scholarly-review domain, not contracts; transferability to contract omission detection is an inference, not a measured result.
