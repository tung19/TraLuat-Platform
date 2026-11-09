# Compliance / Regulatory-Risk Advisory from a Business Scenario (scenario → violation → remediation + citation)

Scope note: this covers systems/papers that assess a *described business activity/fact pattern* against regulation and output violations + obligations breached + (ideally) remediation + statutory citation. It deliberately excludes contract review and general legal QA. Current as of Nov 2026.

## KQ1: Open-source repo that takes a business scenario and outputs violations + obligations breached + remediation + citations

### Takeaway
No open-source project does the *full* "scenario → violation + specific obligation + remediation steps + statutory citation" pipeline. The closest open systems check a *supplied target document* (ToS, technical documentation) against a regulation and emit compliant/non-compliant labels with evidence and explanations; remediation and precise provision citation are the consistently missing pieces. ARCCS is the single best reuse candidate but is early-stage and has no stated license.

### Cited Findings
- **ARCCS** (EMNLP 2026 System Demonstrations; Filandrianos, Sacadura Menezes, Zerva, Gianola) is described by its authors as "the first fully open-source system for end-to-end regulatory compliance checking and auditable report generation." It ingests a regulation PDF + a target document, uses an LLM to extract structured requirements, and checks the document against each — [papers.cool EMNLP 2026 demos](https://papers.cool/venue/2026.emnlp-demos.10@ACL); repo [github.com/geofila/ARCCS](https://github.com/geofila/ARCCS)
- ARCCS returns one of four labels per check: COMPLIANT, NON_COMPLIANT, INSUFFICIENT_INFORMATION, HUMAN_REQUIRED, with evidence quotes, a contradiction description, an explanation, and a confidence score; output includes a violations list, a needs-review list, and JSON export — [github.com/geofila/ARCCS](https://github.com/geofila/ARCCS)
- ARCCS architecture = two modules: RPEM (PDF parsing, sectioning, LLM extraction, quality filtering) and CCM (compliance checking, reporting, export). Extracted requirements carry IDs and source sections (e.g. "GDPR-Art-17-1" / "Article 17"), but findings do not surface these as citations, and **remediation steps are not produced** — [github.com/geofila/ARCCS](https://github.com/geofila/ARCCS)
- ARCCS maturity: ~4 stars, 0 forks, 36 commits; uses OpenAI models (README inconsistent: "gpt-5.2" in notebook vs "gpt-4" web default); **LICENSE is a placeholder "[Add your license information here]"** — reuse terms unclear, treat as not-yet-licensed — [github.com/geofila/ARCCS](https://github.com/geofila/ARCCS)
- ARCCS claimed results (from abstract, unverified): 98.8% accuracy in violation detection on an EU public-procurement benchmark of >1,200 rule checks; LLM-as-judge consistency up to 96.67% on a GDPR policy eval — [papers.cool](https://papers.cool/venue/2026.emnlp-demos.10@ACL)
- **thiagordp/obligation_extraction_for_compliance** is a GitHub repo linked from an LLM legal-compliance paper. It is tiny/early-stage (2 stars, 1 fork, 6 commits), a Python pipeline (main.py, evaluation_setup.py, src/, data/), **no visible LICENSE file**, no README description captured — likely an obligation-extraction experiment, not a scenario-advisory engine — [github.com/thiagordp/obligation_extraction_for_compliance](https://github.com/thiagordp/obligation_extraction_for_compliance)
- **ComplyJudge** (commercial, not OSS) scans GitHub repos for GDPR / EU AI Act / Data Act risks — [webcatalog listing](https://webcatalog.io/apps/complyjudge)
- Hackathon-grade only (not reusable): **RegWatch** classifies items as VIOLATION / AT_RISK / WATCH / CLEAR with confidence + clause reference — [lablab.ai](https://lablab.ai/ai-hackathons/amd-developer/darkside/regwatch); **RegiSphere** scans a repo against domain rules via Mistral API — [lablab.ai](https://lablab.ai/submissions/cmfsby4aw00003574m1bsj1rb)

### Inferences
- The "scenario → violation + remediation + citation" task is **largely unbuilt in open source**. Existing OSS checks *documents against regulations* (document-centric), not free-text business *scenarios* (fact-pattern-centric), and stops at a label+explanation rather than a remediation plan.
- ARCCS is architecturally the right skeleton to fork (requirement extraction + per-requirement checking + report), but TraLuat would have to add: (a) scenario intake instead of document intake, (b) precise provision citation surfaced in findings, (c) a remediation-generation step, and (d) resolve the licensing unknown before any reuse.

### Gaps
- ARCCS license is unresolved (placeholder) — must confirm directly with authors / repo before reuse.
- Could not capture README body of thiagordp repo; its exact task and whether it emits citations is unconfirmed.
- No Vietnam/Vietnamese-language compliance-advisory repo surfaced.

## KQ2: Academic work on automated legal/regulatory & business-process compliance checking

### Takeaway
Two distinct research traditions exist. (1) The symbolic AI&Law tradition (Governatori's Regorous, defeasible deontic logic, LegalRuleML) does rigorous *compliance-by-design* over formally modeled business processes — strong on correctness and provision traceability but requires hand-formalizing both the law and the process, and is not open source. (2) A newer LLM/RAG tradition (COLING 2025, AIReg-Bench, financial-auditing work) handles natural-language inputs but outputs labels/scores rather than citations+remediation.

### Cited Findings — Symbolic / deontic tradition (Regorous, LegalRuleML)
- **Regorous** (Governatori et al.) implements *compliance-by-design*: formal regulatory annotations are added to business-process models before deployment; it combines a logical representation of norms with mathematical process models. Norms are modeled in **FCL (Formal Contract Logic)** / Defeasible Deontic Logic — [CEUR Vol-2049 paper](https://ceur-ws.org/Vol-2049/01paper.pdf); [ar5iv 1403.6865 "ICT Support for Regulatory Compliance"](https://ar5iv.labs.arxiv.org/html/1403.6865)
- Regorous appears in **ICAIL 2013** proceedings (Governatori & Shek, pp. 245–246), and the compliance-checking algorithm in **JURIX 2008** (Governatori & Rotolo, "An algorithm for business process compliance") — [arxiv 2110.07710](https://arxiv.org/pdf/2110.07710)
- **LegalRuleML** linkage: Governatori, Hashmi, Lam, Villata, Palmirani (2016) represent norms and their dynamics in LegalRuleML and use the semantic annotations to support compliance checking, extending the Regorous Process Designer — [cris.unibo.it POST-PRINT Semantic Business](https://cris.unibo.it/bitstream/11585/581839/5/POST%20PRINT%20Semantic%20Business.pdf)
- Motivation for defeasible deontic logic: Linear Temporal Logic formalizations of norms yield compliance results that clash with the natural legal reading; defeasible deontic logic was proposed to overcome this — [arxiv 2110.07710](https://arxiv.org/pdf/2110.07710)
- Governatori, Hoffmann, Sadiq & Weber (BPM 2008 workshops) combine a non-monotonic deontic logic of violations with semantic annotations to build a logical state space and find **compliance gaps** — [Springer 10.1007/978-3-642-16289-3_17](https://rd.springer.com/chapter/10.1007/978-3-642-16289-3_17)
- Applied example: Amantea et al. convert LegalRuleML GDPR rules into Defeasible Deontic Logic and run them in Regorous for a Hospital-at-Home (BPMN) process — [arxiv 2110.07710 "Semi-automated checking for regulatory compliance in e-Health"](https://arxiv.org/pdf/2110.07710)
- A 2026 arXiv paper extracts ODRL policies from BPMN models via graph traversal ("compliance-by-extraction"), building on Natschläger's work that tasks on execution paths imply obligations — [arxiv 2608.02607](https://arxiv.org/pdf/2608.02607)

### Cited Findings — LLM / RAG tradition
- **COLING 2025 "A Compliance Checking Framework Based on Retrieval Augmented Generation"** (Sun, Luo, Li): verifies whether a company's **business processes comply with laws, regulations and industry standards**. Three layers: static (factual knowledge), dynamic (regulatory + business-process info), computational (retrieval + reasoning). Tested on **Chinese and English** compliance datasets, reports SOTA vs baselines — [aclanthology 2025.coling-main.178](https://aclanthology.org/2025.coling-main.178); [researchr bibtex](https://researchr.org/publication/SunLL25/bibtex)
- **AIReg-Bench** (arXiv 2510.01474, Cambridge/camlsys, Oct 2025; NeurIPS 2026): first benchmark for LLMs judging **EU AI Act** compliance. 120 fictional-but-plausible high-risk AI system tech-doc excerpts, each targeting one of Articles 9, 10, 12, 14, 15; legal experts label whether/how each violates the article. Task = 1–5 Likert compliance probability + free-text justification; **no provision-citation metric and no remediation**. Code/dataset at camlsys/aireg-bench (license not stated on paper page; paper is CC BY 4.0) — [arxiv 2510.01474v3](https://arxiv.org/html/2510.01474v3)
- AIReg-Bench results: Gemini 2.5 Pro best (quadratic-weighted κ 0.863, Spearman ρ 0.856); several models biased toward *higher* (over-compliant) scores; prompting GPT-4o to be "harsh/critical" cut the bias but worsened other metrics; human inter-rater reliability only moderate (Krippendorff α 0.651) — [arxiv 2510.01474v3](https://arxiv.org/html/2510.01474v3)
- **Financial auditing** (arXiv 2507.16642, IEEE BigData 2023): checks whether financial-report passages comply with accounting-standard mandates; notes existing AI only *recommends* passages, doesn't verify compliance. Llama-2-70B best at detecting non-compliance, GPT-4 best overall incl. non-English. PwC Germany datasets. **No specific provisions named, no remediation, no code release** — [arxiv 2507.16642](https://arxiv.org/abs/2507.16642)
- **CODE-ACCORD**: an open corpus of building-regulation sentences for rule generation toward automatic compliance checking (construction domain) — [arxiv 2403.02231v4](https://arxiv.org/html/2403.02231v4)
- Adjacent RAG work: multi-agent RAG and Graph-RAG frameworks for checking *software requirements* against regulations — [arxiv 2412.08593](https://arxiv.org/html/2412.08593v1)

### Inferences
- The symbolic tradition is the only line of work that reliably ties a conclusion to a *specific norm* (because norms are modeled individually in FCL/LegalRuleML with IDs), and it inherently produces violation/gap identification — but it needs the law AND the scenario pre-formalized, which is the opposite of TraLuat's free-text-scenario goal.
- The LLM/RAG tradition accepts natural language (matching TraLuat's intake) but none of the surveyed systems emit remediation or enforce correct statutory citation; they output labels + justification.
- A plausible TraLuat design is a hybrid: LLM/RAG to retrieve candidate provisions from a Vietnamese statute corpus + structured per-obligation checking (ARCCS/COLING style) + a dedicated remediation-generation and citation-grounding step — none of which exists off-the-shelf as one package.

### Gaps
- Could not extract full text of the COLING 2025 paper (PDF was binary; preview URL 404'd) — its exact handling of citations, remediation, and whether code is released is unconfirmed; only abstract-level claims captured.
- No benchmark found that scores *remediation quality* or *citation correctness* for compliance advisory.

## KQ3: Commercial RegTech framing of "activity → applicable regulation → gap → remediation"

### Takeaway
Commercial RegTech is where the full pipeline (including remediation and cited references) is most fully realized, but as closed vendor products with self-reported capabilities and no independent accuracy evaluations. The canonical structure is an obligation-to-control traceability map, gap analysis against existing controls, and prioritized remediation.

### Cited Findings
- Category splits into: regulatory intelligence / change management, obligation & requirement mapping, evidence/document management, and workflow/audit-trail tooling — [complianceandrisks.com](https://www.complianceandrisks.com/blog/regulatory-compliance-tools-what-the-best-teams-actually-use/)
- Core function = **obligation mapping**: a structured traceability link between a regulatory requirement and the internal control / process / evidence that satisfies it — [complianceandrisks.com](https://www.complianceandrisks.com/blog/regulatory-compliance-tools-what-the-best-teams-actually-use/)
- Typical pipeline (vendor-described): ingest regulation texts, track changes continuously, apply AI to map obligations, surface gaps vs internal controls, and **propose compliance remediations** — [dreamix.eu RegTech](https://dreamix.eu/regulatory-intelligence-software-development/)
- Gap analysis = comparing extracted regulatory requirements against the organization's existing compliance framework; remediation support ranges from prioritized recommendations to task tracking through evidenced closure — [complianceandrisks.com](https://www.complianceandrisks.com/blog/regulatory-compliance-tools-what-the-best-teams-actually-use/)
- **Deloitte** automated gap-analysis tool (built for DORA): labels each comparison match/gap and **cites the reference locations from the relevant regulations and policy documents** for each generated result — [deloitte.com](https://www.deloitte.com/de/de/products/aistudio/automated-gap-analysis-for-regulation-documents.html)
- Named vendors in this space: Corlytics, Cardamon.ai, Ascent, Sia Partners RegMatcher, CaseMark — [legaltechnologyhub Cardamon](https://www.legaltechnologyhub.com/vendors/cardamon-ai/); [legaltechnologyhub RegMatcher](https://www.legaltechnologyhub.com/vendors/regmatcher-by-sia-partners/); [corlytics.com](https://www.corlytics.com/)

### Inferences
- Commercial tools assume the customer supplies their *internal controls/processes*; the "activity" is the firm's existing control set, not a free-text scenario. TraLuat's "describe your business, get violations" intake is closer to a self-serve advisory than to enterprise obligation-mapping — a differentiator, but also means vendor products aren't a drop-in template.
- Deloitte's "cite reference locations" is the clearest commercial confirmation that citation-grounded gap output is feasible, but it operates over a known regulation+policy pair, not open-ended scenarios.

### Gaps
- All capability claims are vendor self-reported; no independent accuracy/benchmark evaluations surfaced.

## KQ4: How do these systems cite specific provisions and handle effective-date / jurisdiction?

### Takeaway
Confirmed: precise provision citation is weak-to-absent in the LLM/RAG systems, present only structurally in the symbolic tradition and in some commercial tools, and **effective-date / temporal-version handling is essentially unaddressed across all open and academic work surveyed**. This is the clearest open gap and a potential TraLuat differentiator.

### Cited Findings
- ARCCS *internally* assigns provision IDs + source sections to extracted requirements (e.g. "GDPR-Art-17-1"), but does not surface them as citations in findings, and has no remediation — [github.com/geofila/ARCCS](https://github.com/geofila/ARCCS)
- AIReg-Bench supplies the AI Act article as context and asks only for a compliance score + justification; it reports **no provision-citation metric** and does not address effective dates — [arxiv 2510.01474v3](https://arxiv.org/html/2510.01474v3)
- The symbolic/LegalRuleML tradition explicitly models **norm dynamics** (norms and their changes over time) — LegalRuleML represents "norms and their dynamics," the main mechanism in this literature for temporal/version handling — [cris.unibo.it Semantic Business](https://cris.unibo.it/bitstream/11585/581839/5/POST%20PRINT%20Semantic%20Business.pdf)
- Because symbolic systems model each norm with an ID in FCL/LegalRuleML, provision-level traceability is inherent (each obligation/prohibition/violation ties to a specific modeled norm) — [CEUR Vol-2049](https://ceur-ws.org/Vol-2049/01paper.pdf)
- Deloitte's DORA tool cites reference locations from the governing regulation + policy documents per result — the clearest provision-citation behavior found, but commercial/closed — [deloitte.com](https://www.deloitte.com/de/de/products/aistudio/automated-gap-analysis-for-regulation-documents.html)
- A 2026 IoT-data-compliance paper notes dynamic business environments and user-defined requirements increase the complexity of rule design/maintenance, and multiple sources stress regulations change over time so checks need continuous updating — [JEIT paper](https://www.jeit.ac.cn/en/article/doi/10.11999/JEIT250704); [search synthesis](https://www.themoonlight.io/review/enhancing-legal-compliance-and-regulation-analysis-with-large-language-models)

### Inferences
- For TraLuat's Vietnam engine, *statutory-citation grounding* and *effective-date/version awareness* (which Nghị định/Thông tư version was in force on a given date) are exactly where existing open and academic systems are weakest. LegalRuleML's "norm dynamics" is the only principled template, but it requires formally modeling Vietnamese norms — heavy, and no Vietnamese LegalRuleML corpus is known to exist.
- Reliable citation likely requires retrieval over a versioned, date-stamped statute corpus plus a grounding/verification step, rather than trusting an LLM to recall provision numbers — the over-compliance bias seen in AIReg-Bench reinforces that generative output needs grounding.

### Gaps
- Found no system (open, academic, or clearly documented commercial) that demonstrably resolves "which version of the provision was effective on date X in jurisdiction Y" for compliance advisory.
- No Vietnam-specific or Vietnamese-language regulatory-compliance-checking system or dataset surfaced in any search.

## Overall synthesis for build-vs-reuse
- **The exact task (free-text scenario → violations + obligations breached + remediation steps + statutory citation) is not available as an open-source product.** It is partially addressed: document-vs-regulation checking (ARCCS, COLING-RAG), scenario-vs-article judgment without citation/remediation (AIReg-Bench), and formal process compliance (Regorous — closed, needs formalization).
- **Best reuse candidates:** ARCCS (fork the extraction+checking+report skeleton; resolve license; add scenario intake, surfaced citations, remediation) and AIReg-Bench (reuse as an eval/benchmark methodology and its data-generation pipeline). COLING-RAG's three-layer design is a useful reference architecture.
- **Must-build regardless:** scenario intake, Vietnamese versioned/date-aware statute retrieval, provision-grounded citation, and remediation generation — none exist off-the-shelf, especially for Vietnam.
- **Honest bottom line:** this is a largely greenfield build. Open source gives reusable *components and architecture patterns*, not a working compliance-advisory engine, and nothing addresses Vietnamese law or effective-date handling.
