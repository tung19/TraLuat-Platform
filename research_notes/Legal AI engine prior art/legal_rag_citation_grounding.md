# Legal RAG at Clause/Article Granularity + Citation Grounding & Verification

Scope: reusable open-source building blocks for a legal RAG + citation-grounding layer, with maturity and license / commercial-use status. Current as of Nov 2026. Note: several cited items carry 2606.x / 2609.x / 2601.x arXiv IDs and "2026" conference tags that appear in search results; I flag these as recent/unverified-vintage where relevant.

## Q1: Verify & deep-dive LegalBench-RAG

### Takeaway
LegalBench-RAG (ZeroEntropy, Aug 2024) is the first open-source benchmark isolating the *retrieval* step of legal RAG, scored with character-level Precision@k / Recall@k over contract-law datasets. Code is MIT; the underlying corpora are CC BY 4.0 (commercial use OK with attribution).

### Cited Findings
- First benchmark specifically designed to evaluate the retrieval step of RAG pipelines in the legal domain; authors Nicholas Pipitone & Ghita Houir Alami (ZeroEntropy). Paper arXiv:2408.10343 — [arXiv](https://arxiv.org/html/2408.10343v1); [ZeroEntropy writeup](https://www.zeroentropy.dev/articles/legalbench)
- Built by retracing LegalBench context back to original expert-annotated sources; "6,858 query-answer pairs spanning a corpus of over 79 million characters" per ZeroEntropy — [ZeroEntropy](https://www.zeroentropy.dev/articles/legalbench)
- Source datasets (4): **ContractNLI** (NDAs; 977 queries, 95 docs), **CUAD** (private commercial contracts; 4,042 queries, 462 docs), **MAUD** (M&A agreements; 1,676 queries, 150 docs, ~52.7M chars), **PrivacyQA** (privacy policies; 194 queries, 7 docs) — [arXiv](https://arxiv.org/html/2408.10343v1)
- Corpus ~79.7M characters across 714 documents; query count stated as 6,858 (abstract/Table 1) but 6,889 (Section 3.3.1/Table 2) — paper does not reconcile the discrepancy — [arXiv](https://arxiv.org/html/2408.10343v1)
- **LegalBench-RAG-mini:** 194 queries from each dataset = 776 total across 72 docs (~8.7M chars) for cheaper iteration — [arXiv](https://arxiv.org/html/2408.10343v1)
- Ground truth = character-index spans; each query's answer is contained in a single document. Metrics: Precision@k and Recall@k for k=1..64, computed deterministically "even at the exact character level" — [arXiv](https://arxiv.org/html/2408.10343v1); [GitHub](https://github.com/zeroentropy-ai/legalbenchrag)
- Chunking strategies compared: **Naive** (fixed 500-char, no overlap) vs **RCTS** (Recursive Character Text Splitter: paragraphs→sentences→words) — [arXiv](https://arxiv.org/html/2408.10343v1)
- Baseline stack: OpenAI `text-embedding-3-large` embeddings, SQLite-Vec vector store, Cohere `rerank-english-v3.0` reranker — [arXiv](https://arxiv.org/html/2408.10343v1)
- Representative scores: RCTS no-reranker all-datasets Precision@1 6.41 / Recall@64 62.22; Naive Recall@64 76.39. PrivacyQA easiest (P@1 14.38, R@64 84.19); MAUD hardest (P@1 2.65, R@64 28.28). Paper notes Cohere reranker gave small/sometimes negative effect — [arXiv](https://arxiv.org/html/2408.10343v1)
- **License: MIT** (repo label). Regenerating the benchmark requires agreeing to usage policies of the 4 source datasets; the generation script uses LLMs so it will NOT reproduce the exact released benchmark — [GitHub](https://github.com/zeroentropy-ai/legalbenchrag); [ZeroEntropy](https://www.zeroentropy.dev/articles/legalbench)
- Canonical repo is `github.com/zeroentropy-ai/legalbenchrag` (task's `zeroentropy-cc` spelling appears to be an older/paper link) — [GitHub](https://github.com/zeroentropy-ai/legalbenchrag)

### Inferences
- The low Precision@1 across the board shows clause-level contract retrieval is genuinely hard; recall only becomes usable at large k, implying a grounding/verification layer downstream is essential rather than optional.
- MIT code + CC BY 4.0 data makes LegalBench-RAG directly reusable as an internal retrieval regression harness for a commercial product (attribution required).

### Gaps
- Benchmark is contract/English-centric (no statutes/case law, no non-US/Vietnamese law) — limited transfer to statute-article retrieval.
- Could not independently open the repo LICENSE file text; MIT is from the repo label only.

## Q2: Citation Grounding benchmarks — proving citations are real AND valid/in-force

### Takeaway
There is now a concrete, purpose-built benchmark for *detecting* legal citation hallucinations — LePhantomCite (Princeton, 2026) — plus Stanford's influential (non-released) RAG evaluation. "Still valid / in-force" (statute currency, overruled-case) checking is largely unaddressed by open benchmarks; existence + support ("misgrounding") is the active frontier.

### Cited Findings
- **LePhantomCite** (arXiv:2606.21155, "Who Checks the Citations? Benchmarking Legal Hallucination Detection"; Patty Liu, Dominik Stammbach, Peter Henderson, Princeton Polaris Lab): 1,300 federal-appellate legal-brief excerpts with systematically injected citation errors following a taxonomy drawn from real court filings; task = extract all hallucinated segments; labels manually verified; source briefs from CourtListener — [arXiv PDF](https://arxiv.org/pdf/2606.21155); [Princeton CITP blog](https://blog.citp.princeton.edu/?p=19171)
- LePhantomCite taxonomy: non-existent citations and name mismatches are catchable via database lookups; the other error types require access to the opinion text. Findings: hallucinated citations in court filings steadily growing; models improving at agentic cite-checking but far from solved — [Princeton blog](https://blog.citp.princeton.edu/?p=19171); [arXiv](https://arxiv.org/pdf/2606.21155)
- Reported detection ceiling: best model ~68.8% F1; "content misrepresentation" (real cite, wrong meaning) is the hardest category across all systems — [search summary of benchmark paper](https://arxiv.org/pdf/2606.21155)
- A public **Legal Citation Benchmark / LegalCiteBench leaderboard** exists (Phala) — [HF Space](https://phalanetwork-legal-citation-leaderboard.hf.space); [Phala research](https://phala.com/research/legalcitebench)
- **Stanford "Hallucination-Free?" (May 2024)** defines two hallucination types: *Incorrect* (describes law wrongly) and *Misgrounded* (states law correctly but cites a source that does not support the claim) — the misgrounded category is the operational definition of citation grounding. Pre-registered dataset of 200+ queries; NOT stated as publicly released. Authors: Magesh, Surani, Dahl, Suzgun, Manning, Ho — [Stanford HAI](https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries)
- Mella-LRC released a test/validation dataset on Hugging Face for citation-hallucination benchmarking (URL not given on the press page) — [Georgia Tech](https://www.cc.gatech.edu/news/researchers-create-tool-detect-ai-hallucinated-legal-citations)

### Inferences
- The field has split "is the citation real?" (solvable via DB lookup) from "does it support the claim?" / "is it still good law?" — the latter two are the hard, high-value problems and are where a product can differentiate.
- No open benchmark found that specifically tests *currency/in-force* status (overruled cases, repealed/amended statutes); this is a genuine white space for a Vietnamese statute product where amendment tracking matters.

### Gaps
- Could not confirm LePhantomCite dataset license / download location from these sources (check arXiv:2606.21155 + princeton-polaris-lab GitHub).
- "Still valid/in-force" validation: no concrete open dataset/tool found — likely must be built from statute amendment metadata.

## Q3: Clause/article-level, hybrid (dense+sparse), and multi-hop retrieval over statutes

### Takeaway
The dominant open pattern is hybrid BM25+dense (e.g. bge-m3) fused with Reciprocal Rank Fusion, then a neural reranker; the distinctive legal need is injecting structural context (article/section headings) into chunks and following cross-references via citation graphs for multi-hop queries.

### Cited Findings
- **Hybrid for statutes:** VLSP 2025 legal article retrieval combines BM25 + bge-m3 dense vectors to maximize recall before reranking — [VLSP 2025 paper](https://preview.aclanthology.org/anlp-naacl/2025.vlsp-1.20.pdf)
- Structure-aware statute QA (arXiv:2604.06173) fuses BM25 + dense via Reciprocal Rank Fusion then adds a structure-aware reranker — [arXiv PDF](https://arxiv.org/pdf/2604.06173)
- Fusion trade-off: on a NanoLaw statute benchmark, dense retrieval gave best top-10 ranking, hybrid second (improves over BM25, approaches but does not beat dense at top-10) — [Hakari/NanoLaw benchmark docs](https://hakari-bench-leaderboard.hf.space/docs/benchmark-tasks/NanoLaw/NanoAILAStatutes)
- **Legal-specific reranking:** "Neural reranking for UK statutory retrieval: Provision-level evaluation and an open distilled model" — neural reranking consistently improves nDCG/MRR over first-stage retrieval across sparse+dense pools; includes an open distilled reranker model (single-instrument eval caveat) — [PhilPapers](https://philpapers.org/rec/ALSNRF)
- **LegalMALR**: multi-agent query reformulation + LLM-based reranking for Chinese statute retrieval — [search cluster](https://aclanthology.org/2026.nllp-1.43/)
- **Clause-loses-context problem:** vendor writeup argues fusion+reranking don't fix a clause losing which article it belongs to; proposes Anthropic-style contextual retrieval (prepend structural context to each chunk). Vendor opinion, not evidence — [Vaquill engineering](https://www.vaquill.ai/engineering/hybrid-retrieval-and-the-exact-identifier-problem)
- **Multi-hop / cross-reference graphs:**
  - Indonesian UU ITE study: citation graph over statute docs + RRF hybrid; Full-Hit Rate rose 0.500→0.714, no effect on single-hop queries (gain is specifically on multi-hop) — [JAIC Polibatam](https://jurnal.polibatam.ac.id/index.php/JAIC/article/download/14131/4022/46061)
  - "Document forests" three-tier RAG: parses each doc into a tree, adds cross-reference edges linking articles across trees; argues standard RAG cannot follow cross-references — [search cluster](https://arxiv.org/pdf/2609.27009)
  - **LegalGraphRAG** (arXiv:2605.28120): hierarchical graph with Ontology/Fact/Rule layers + multi-agent retrieve-verify-adjudicate — [arXiv HTML](https://arxiv.org/html/2605.28120)
  - **KoBLEX**: open legal QA benchmark with multi-hop statutory reasoning (arXiv:2509.01324) — [arXiv PDF](https://arxiv.org/pdf/2509.01324)
  - Labour-law agentic traversal: planner chooses max hop depth h and allowed edge types — [arXiv:2609.27814](https://arxiv.org/pdf/2609.27814)
- Reusable sparse/dense/hybrid baseline sets exist for case-to-statute retrieval (e.g. NELSR Nepali benchmark) — [search cluster](https://arxiv.org/pdf/2604.06173)

### Inferences
- For a statute/article product: best-practice pipeline = chunk at article/clause granularity WITH structural header context prepended, hybrid BM25+dense (bge-m3 is the common multilingual choice, relevant for Vietnamese) + RRF, then a reranker; add a citation/cross-reference graph for multi-hop and definitional lookups.
- Graph-augmentation's value shows up specifically on multi-hop/cross-reference queries, not single-hop — so it's worth the engineering only if the use case has chained references.

### Gaps
- No single standard shared benchmark for statute cross-reference multi-hop retrieval; most evidence is recent small preprints.
- Licenses for the individual models/datasets (bge-m3 is MIT; others unverified here) not individually confirmed in this pass.

## Q4: Open tools detecting LLM citation hallucination in legal answers + Stanford study

### Takeaway
Three usable open tools have emerged: cite.review (AGPL-3.0), Mella-LRC (GT/IBM, open source), and the CourtListener Citation Lookup API (+ eyecite BSD parser) as infrastructure. All do existence/metadata checks well; quote-exact and "does it support the claim" checks are LLM-assisted and weaker. Stanford RegLab's two studies are the field's anchor evidence.

### Cited Findings
- **Stanford "Large Legal Fictions" (Jan 2024):** general LLMs (GPT-3.5, Llama 2, PaLM 2) hallucinate on legal queries 69%–88%; worse on complex tasks and lower-court case law; models lack awareness of own errors — [Stanford HAI](https://hai.stanford.edu/news/hallucinating-law-legal-mistakes-large-language-models-are-pervasive)
- **Stanford "Hallucination-Free?" (May 2024):** RAG-based commercial tools still err — Lexis+ AI and Ask Practical Law >17%, Westlaw AI-Assisted Research >34%; vs GPT-4 baseline. Introduced the Incorrect vs Misgrounded distinction. Vendors (Thomson Reuters) disputed methodology — [Stanford HAI](https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries); [Legal Dive](https://www.legaldive.com/news/legal-use-genai-tools-error-prone-hallucinations-stanford-reglab-HAI-fake-citations/704454/)
- **cite.review** (by Kirin Chang): free, open-source, **AGPL-3.0**. Step 1 = checks case existence + name/court/reporter/volume/page match against CourtListener; Step 2 (optional) = asks a user-chosen LLM whether the verified case supports the memo's proposition ("real cases cited for wrong proposition"). Statutes via Cornell LII (US Code, CFR) + GovInfo; confirms provision exists, NOT that text supports claim. US-only. Does NOT do exact quote matching. Repo: github.com/kirinccchang/citereview — [cite.review FAQ](https://citereview.pages.dev/faq.html)
- **Mella-LRC (Mellea Legal Requirements Checker)** (Georgia Tech CSSE/OSPO; Adrian Lozada & Di Wu; IBM-funded): extracts citations, checks each is authentic AND supports the document's content; uses LLMs + IBM's open-source **Mellea** framework (write output constraints as code, retry until satisfied). Tested on 26 public court filings with falsified citations, ~8 min/doc. Open source (license not named on page). Repo: github.com/gt-csse/mellea-lrc — [Georgia Tech](https://www.cc.gatech.edu/news/researchers-create-tool-detect-ai-hallucinated-legal-citations)
- **CourtListener Citation Lookup API** (Free Law Project): `POST /api/rest/v4/citation-lookup/`; extracts+normalizes citations, returns status per cite (200 found / 300 multiple / 404 valid-format-but-not-found / 400 bad reporter / 429 rate). DB of ~18.1M citations, 9M+ decisions, 2,000+ courts. Case citations only (no statutes, law journals, id./supra). 404 = needs review (fabrication OR coverage gap), not definitive hallucination. Free tier limited (e.g. 5 req/min, 125/day); token required; FLP membership raises limits — [Vaquill guide](https://www.vaquill.ai/blog/courtlistener-citation-lookup-api-guide)
- **eyecite** (Free Law Project + Harvard LIL): high-performance open-source citation extractor, tested on 50M+ citations, powers CourtListener's extraction. **BSD license** (permissive, commercial-safe); `pip install eyecite`; JOSS paper — [free.law/projects/eyecite](https://free.law/projects/eyecite); [PyPI](https://pypi.org/project/eyecite/)
- Also noted: **web-researcher-mcp** (MIT, Go binary) has a general-purpose (non-legal) citation verification tool — [DEV community](https://dev.to/zoharbabin/ai-assistants-lie-about-citations-heres-how-to-catch-them-5608)

### Inferences
- A pragmatic grounding stack: eyecite (BSD) for extraction → a database lookup (CourtListener for US case law; for Vietnam, a national statute DB must be built) for existence → LLM/NLI check for support/faithfulness → quote-span alignment against retrieved source text for exact-quote verification.
- AGPL-3.0 on cite.review is a commercial blocker if its code is embedded in a hosted modified product (copyleft triggers on network deployment); study the pattern, don't fork the code into a proprietary SaaS without compliance.

### Gaps
- Mella-LRC license not stated (check repo LICENSE); its HF dataset URL not surfaced.
- No open tool found that natively does exact-quotation span verification against opinion text for legal content (must be custom-built); content-misrepresentation detection remains the weakest link everywhere (~68.8% F1 ceiling per LePhantomCite).

## Q5: Production-grade vs research demos

### Takeaway
Production-grade = the commercial legal research suites (Westlaw/CoCounsel, Lexis+ AI, Harvey, vLex Vincent) and the retrieval/parser infrastructure (eyecite, CourtListener API, BM25/bge-m3, Cohere rerank). Everything doing *claim-level citation grounding/verification* is still research-demo or early-tool stage.

### Cited Findings
- **Vals Legal AI Report (VLAIR, Feb 2025):** first major independent benchmark of commercial legal AI across 7 tasks vs a lawyer control group. Tools: Harvey Assistant, CoCounsel (Thomson Reuters), Vincent AI (vLex), Oliver (Vecflow); Lexis+ AI withdrew. Harvey top Document Q&A 94.8%, beat lawyer baseline in 5/6 tasks; CoCounsel won summarization (~77.2); both sub-minute latency. A follow-up Oct 2025 legal-research report also exists (vals.ai/industry-reports/vlair-10-14-25) — [LawNext](https://www.lawnext.com/2025/02/legal-ai-tools-show-promise-in-first-of-its-kind-benchmark-study-with-harvey-and-cocounsel-leading-the-pack.html); [Vals](https://www.vals.ai/vlair)
- Vals report does NOT break out a citation-grounding / source-verification accuracy metric (confirmed absent in searched summaries) — [Vals](https://www.vals.ai/vlair)

### Inferences
- Maturity ladder for reuse:
  - **Production-grade infrastructure (reusable, permissive):** eyecite (BSD), CourtListener Citation Lookup API (free tier/membership), BM25 (Lucene/Elastic), bge-m3 dense embeddings, Cohere/other rerankers (commercial API). These are safe foundations.
  - **Production-grade end products (not reusable, competitors/benchmarks):** Westlaw AI / CoCounsel, Lexis+ AI, Harvey, vLex Vincent — closed, used as quality bars, and shown by Stanford to still misground 17–34%.
  - **Research demos / early tools:** cite.review (AGPL, working but unlabeled maturity), Mella-LRC (fellowship project, 26-doc eval, ~8 min/doc), LegalGraphRAG / document-forest / LabourCrew multi-hop systems (preprints), LePhantomCite (benchmark not a product).
- The citation-grounding layer the user wants to build does not yet exist as an off-the-shelf production component — the opportunity is to assemble permissive infrastructure (eyecite-style extraction + DB existence check + NLI/LLM support check + quote-span alignment) into a product-grade verifier.

### Gaps
- No public citation-grounding accuracy numbers for Harvey/CoCounsel/Vincent (would require the full VLAIR PDF or vendor docs).
- Vietnamese-jurisdiction production tools and statute databases not covered in this English-source pass — a dedicated follow-up is needed given the project (TraLuat) appears Vietnam-focused.
