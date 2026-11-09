# Temporal / Point-in-Time Legal Knowledge Representation — Prior Art Inventory

Scope: standards, open datasets, repos, and research systems for effective-dating ("what did the law say on date X") and legal norm graphs (hierarchy, cross-reference, amendment/repeal, conflict). Civil-law vs common-law orientation and LICENSE/commercial-use status flagged throughout. Current as of 2026-11-05.

---

## Q1. Standards for legislation markup & temporal versioning (Akoma Ntoso, LegalRuleML, ELI, FRBR)

### Takeaway
Akoma Ntoso + the FRBR Work/Expression split is the de-facto backbone for point-in-time legislation, but AKN versions robustly at the *document* level and does **not** natively version at the *component* (article/section) level — the exact granularity a "never cite repealed text" engine needs. ELI encodes a point-in-time slot and entry-into-force/no-longer-in-force dates in its URI and ontology. LegalRuleML adds machine-reasoning (deontic + temporal validity of rules). All four are open and jurisdiction-neutral, so usable for a civil-law country like Vietnam.

### Cited Findings
- **Akoma Ntoso (OASIS LegalDocML)** is an open, non-proprietary XML markup for parliamentary/legislative/judiciary documents; became an **OASIS standard in 2018**. It is the basis of the EU's AKN4EU profile. — [AfricanLII/Indigo](https://africanlii.org/articles/2019-03-28/mariya-badeva-bright/indigo-legislation-platform-consolidate-and-publish-legislation); [EUR-Lex via search](https://interoperable-europe.ec.europa.eu/collection/semic-support-centre/solution/common-structured-format-eu-legislative-documents)
- AKN point-in-time concept (per Laws.Africa): a "point in time" is **all expressions of a Work on a particular date**, each incorporating all earlier amendments; the oldest point-in-time is the Work as originally published. — [Laws.Africa docs](https://docs.laws.africa/llms-full.txt)
- **AKN's key limitation**: a 2025 paper (Hudson de Martim, Federal Senate of Brazil) argues AKN provides robust **document-level** versioning but its temporal model "does not natively extend to the component level" and lacks built-in constructs for component version history or for linking a textual change to the event that caused it. — [arXiv 2506.07853v4](https://arxiv.org/html/2506.07853v4)
- **ELI (European Legislation Identifier)** URI template includes an explicit **{point in time}** component = "version of the act valid on a given date," written YYYYMMDD, plus a {version} slot. Defined in the Council's 2012 conclusions. — [Wikipedia: ELI](https://en.wikipedia.org/wiki/European_Legislation_Identifier); [BOE ELI](https://boe.es/legislacion/eli.php)
- ELI ontology (ELI-DL) metadata tracks: `date_entering_in_force` (applicable date if known/unique, else controlled vocab 'multiple'/'unspecified-future'), `date_no_longer_in_force`, date of document (adoption/signature), date of publication, and `version_date` (point at which a description is valid). schema.org `legislationDateVersion` is declared equivalent to ELI `version_date`; `legislationDateOfApplicability` captures that a text may *enter into force* on one date but *apply* from a later one. — [schema.org legislationDateVersion](https://attic.schema.org/legislationDateVersion); [schema.org legislationDateOfApplicability](https://attic.schema.org/legislationDateOfApplicability)
- **LegalRuleML Core v1.0** approved as an **OASIS Standard (vote 30 Aug 2021, announced Sept 2021)**. Models deontic operators (obligation/permission/prohibition/right), **temporal parameters for rule validity that can vary over time**, and metadata (provenance, jurisdiction, logical interpretation). Covers legislation, contracts, and case law. HTML/PDF/XSD/examples published on OASIS docs site. — [OASIS press release](https://www.oasis-open.org/?p=7649); [OASIS members announcement](https://lists.oasis-open.org/archives/members/202109/msg00000.html)
- **FRBR / FRBRoo / LRMoo**: the de Martim paper builds on **LRMoo** (harmonized with CIDOC CRM, refines the WEMI distinction) to separate language-agnostic Temporal Versions (F1 Work) from language-specific Language Versions (F2 Expression); amendments modeled as F27 Work Creation events typed as E11 Modification, with macro-events decomposed into micro-events. — [arXiv 2506.07853v4](https://arxiv.org/html/2506.07853v4)

### Inferences
- A production point-in-time engine almost certainly needs the de Martim-style **component-level** version chain layered on top of AKN, because vanilla AKN won't guarantee "never cite repealed text" at section granularity.
- The FRBR Work→Expression→Manifestation split is the shared mental model across AKN, ELI, and LRMoo; adopting it early makes the data model interoperable with all three standards.

### Gaps
- Did not retrieve the authoritative AKN 1.0 OASIS spec text on its `<lifecycle>`, `<temporalGroup>`, `<timeInterval>` elements (AKN *does* have temporal metadata elements at document level); confirm exact element names against the OASIS spec before concluding AKN has "nothing" at component level.
- Did not pull the official ELI-DL ontology doc on Joinup for exact date formats / cardinalities.

---

## Q2. Research repos — CapturingLegalReasoningPaths (rkondo3) & NyayGraph

### Takeaway
Both are 2025 academic LLM+KG retrieval systems, **not** temporal/effective-dating systems — neither models when a provision is in force, version history, or repeals. CapturingLegalReasoningPaths (Japan, civil-law) offers a reusable lightweight legal-inference ontology (Fact/Norm/Application/Provision). NyayGraph (India, common-law) offers the "first complete IPC knowledge graph" of cross-references between statute sections. Both ship code but **neither states a license** in the repo, which blocks commercial reuse by default.

### Cited Findings — CapturingLegalReasoningPaths
- Exact repo: **github.com/rkondo3/CapturingLegalReasoningPaths**; paper "Capturing Legal Reasoning Paths from Facts to Law in Court Judgments using Knowledge Graphs," Ryoma Kondo + 4 co-authors, **arXiv:2508.17340 (24 Aug 2025)**. — [arXiv abstract](https://arxiv.org/abs/2508.17340v1)
- Repo contents (sparse): folders `intances` [sic] and `prompts`, a `.gitignore`, and `lightweight_LKG_ontology.jsonld`. **3 commits, 0 stars/forks, no LICENSE file, no description.** Very early-stage. — [GitHub repo](https://github.com/rkondo3/CapturingLegalReasoningPaths)
- Ontology/schema (RDF/JSON-LD, schema.org-compatible): core classes **Fact, LegalNorm, LegalApplication, Provision**. `LegalApplication` is a reasoning step with `appliesNorm`→LegalNorm and `toFact`→Fact. Extracted edges: Provision→LegalNorm (interpretive derivation), LegalNorm→LegalApplication, Fact→LegalApplication. (Paper is internally inconsistent on whether Norm→Norm edges are allowed.) — [arXiv HTML](https://arxiv.org/html/2508.17340v1)
- Provision reference normalization: GPT-4o canonicalizes phrases like "the Act"/"Article 2" into canonical legal titles (method of defining/verifying canonical titles not described). — [arXiv HTML](https://arxiv.org/html/2508.17340v1)
- **Temporal: none.** Paper does not address versioning or effective dates of provisions; only time criterion is using judgments issued after 2008 (a formatting standard). — [arXiv HTML](https://arxiv.org/html/2508.17340v1)
- Dataset: **648 Japanese district-court civil administrative litigation decisions** (NII legal dataset, "reasoning" section only); expert annotation of 57 sections (nodes) + 92 sections (edges); retrieval benchmark of 1,242 gold fact→provision labels. Jurisdiction = **Japan (civil law)**. — [arXiv HTML](https://arxiv.org/html/2508.17340v1)

### Cited Findings — NyayGraph
- Repo: **github.com/SiddharthShukla48/NyayGraph**; paper at **NLLP Workshop 2025** (ACL Anthology 2025.nllp-1.11, pp. 147–156, Suzhou). Authors: Siddharth Shukla, Tanuj Tyagi, Abhay Singh Bisht, Ashish Sharma, Basant Agarwal. — [ACL Anthology](https://aclanthology.org/2025.nllp-1.11)
- Purpose: KG-enhanced **Legal Statute Identification (LSI)** for Indian law using LLMs; claims the **"first complete IPC knowledge graph"** encoding structural/cross-reference relationships between Indian Penal Code sections. — [ACL Anthology](https://aclanthology.org/2025.nllp-1.11)
- Results: on the **IL-TUR benchmark**, explicit KG inference improves recall without substantially hurting precision; naively adding KG context to prompts raises coverage but lowers precision, so reranking matters. — [ACL Anthology](https://aclanthology.org/2025.nllp-1.11)
- **Temporal: none.** Page/abstract do not mention temporal modeling or effective dates. Jurisdiction = **India (common law)**. — [ACL Anthology](https://aclanthology.org/2025.nllp-1.11)
- License: abstract says "code and data are publicly available" at the GitHub repo but **does not name a license**; ACL Anthology CC BY 4.0 covers the paper, not necessarily the repo. — [ACL Anthology](https://aclanthology.org/2025.nllp-1.11)
- Related (separate) Indian-law KG projects: **KING** (court-decision KG on the Nyaya ontology, github.com/ShubhamKalson/KING) and **NyayaRAG** (RAG judgment prediction, github.com/ShubhamKumarNigam/NyayaRAG; arXiv 2508.00709). — [search results](https://arxiv.org/html/2508.00709v3)

### Inferences
- Both repos are reusable as **ontology/pattern inspiration** (Fact/Norm/Application pattern; statute cross-reference graph) but **not as drop-in temporal engines** — the hardest "moat" (effective-dating) is absent from both.
- Absence of a LICENSE file is a practical blocker: without an explicit open-source license, default copyright reserves all rights, so TraLuat cannot safely reuse the code/data commercially until the authors add one (worth an email request).

### Gaps
- Did not open `lightweight_LKG_ontology.jsonld` or NyayGraph's repo files directly to inventory exact predicates / node counts — recommend a follow-up pass cloning both repos to confirm license files and graph schema.

---

## Q3. National portals publishing structured, point-in-time law (UK, EU, US)

### Takeaway
The UK (legislation.gov.uk) is the gold standard for point-in-time consolidated law with a public API, full amendment tracking, and an open license. EUR-Lex offers consolidated versions + ELI + machine formats via Cellar/SPARQL/REST, reusable under a Commission Decision. The US (govinfo/OLRC USLM) is public-domain and has date-versioned URL access but weaker provision-level effective-date metadata. All three are common-law (UK/US) or supranational (EU); none is a civil-law template per se.

### Cited Findings — UK (legislation.gov.uk)
- **Point-in-time / "revised" versions**: dated URL pattern returns the text as it stood on a date, e.g. `.../ukpga/1964/29/section/7/2021-11-25`; each provision page has a **timeline of changes** to navigate between dates; "point in time" view reached via Advanced Features > Show Timeline of Changes. — [example dated section](https://www.legislation.gov.uk/ukpga/1964/29/section/7/2021-11-25)
- Handles **geographic extent**: where a substitution applies to only part of the UK, separate texts are held per extent (e.g. Scotland-only vs England-and-Wales-only vs Northern Ireland-only versions of the same section); amendments take the extent of the provision they amend. — [legislation.gov.uk search result](https://www.legislation.gov.uk/ukpga/1964/29/section/7/2021-11-25)
- Timeline base-date: first timeline date is usually commencement; where unknown, base-date is **01/02/1991** (or 01/01/2006 for NI legislation). — [legislation.gov.uk](https://www.legislation.gov.uk/ukpga/1964/29/section/7/2021-11-25)
- **Formats**: append `/data.xml` or `/data.rdf` to any URL (whole item, part, or section) for raw data; `/data.feed` returns ATOM lists; underlying format is **Crown Legislation Markup Language (CLML)**; National Archives also provides **bulk download in HTML5 and Akoma Ntoso**. API provides XML/Atom/HTML (no JSON). — [search: data formats](https://govloop.com/community/blog/sheridan-on-legislation-gov-uk); [NuGet client lib](https://feed.nuget.org/packages/Uk.Legislation)
- **License: Open Government Licence v3.0 (OGL)** for API data and bulk downloads — permissive, commercial-use allowed with attribution. — [.NET client lib docs](https://feed.nuget.org/packages/Uk.Legislation); [OGP report 2015](https://www.opengovpartnership.org/sites/default/files/UKNAPupdate_June2015_Legislation.pdf)

### Cited Findings — EU (EUR-Lex)
- Access channels: **Cellar** repository reachable via **SPARQL endpoint** and **RESTful API**; formats include PDF, HTML, and **Formex** (specialised XML for Official Journal material). EU's future legal-document exchange profile is **AKN4EU** (Akoma Ntoso-based). — [search: EUR-Lex formats](https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html); [Kardami ELI formats](https://op.europa.eu/documents/2050822/2138819/Maria-Kardami-Formats_ELI_20160321.pdf)
- EUR-Lex provides **consolidated (point-in-time) versions**; but the **authentic text remains what was published in the Official Journal** — consolidated versions are editorial, not authentic/binding. — [EUR-Lex excerpt](https://eur-lex.europa.eu/eli/dec/2011/163(1)/2022-12-15/eng)
- **License/reuse**: governed by **Commission Decision 2011/833/EU of 12 Dec 2011** (CELEX 32011D0833, OJ L 330, 14 Dec 2011), which replaced 2006/291/EC and makes Commission documents generally reusable **without individual application**, via open reuse licences or simple disclaimers — commercial reuse permitted. — [Decision 2011/833/EU](https://eur-lex.europa.eu/eli/dec/2011/833/oj); [eumonitor summary](https://www.eumonitor.eu/9353000/1/j9vvik7m1c3gyxp/vivi69stinnd)
- Full ELI implementation: entry-into-force, applicability, and no-longer-in-force dates exposed as linked-data metadata (see Q1). — [BOE ELI](https://boe.es/legislacion/eli.php)

### Cited Findings — US (govinfo / OLRC USLM)
- **USLM (United States Legislative Markup)** XML schema maintained at **github.com/usgpo/uslm**; beta USLM XML on govinfo covers enrolled bills, public/private laws, Statutes at Large (113th Congress forward; Statutes at Large from 108th). — [govinfo beta USLM](https://www.govinfo.gov/features/beta-uslm-xml); [usgpo/uslm](https://github.com/usgpo/uslm)
- Point-in-time: a secondary source reports US Code XML supports **date-versioned lookups** with `@ISO-date`, e.g. `/us/usc/t5/s1/a@2013-05-02` = that subsection as it stood on 2 May 2013; OLRC also publishes **release points** (e.g. `xml_uscAll@119-36` = all titles as of Public Law 119-36) in USLM 2.0. — [OLRC release point](https://uscode.house.gov/download/releasepoints/us/pl/114/11/usc-rp@114-11.htm); [josh-docs US Code](https://josh-docs-9p7.pages.dev/sources/us-code/)
- **License: public domain** (US government works) for Public Laws and the US Code (per developer notes — confirm against GPO terms). — [josh-docs public laws](https://josh-docs-9p7.pages.dev/sources/public-laws/)
- Schema versioning: major.minor.point; point = non-breaking change, minor = breaking change; releases on GovInfo + "Proposed" branch of usgpo/uslm repo. — [search: USLM schema](https://www.govinfo.gov/features/beta-uslm-xml)

### Inferences
- UK legislation.gov.uk is the single best **reference implementation** of a point-in-time engine with amendment tracking + extent handling + open license; worth deep study of its CLML model and timeline/base-date mechanics as a blueprint.
- The UK "multiple versions by extent" mechanism is directly relevant to any country with regional/overlapping validity, and conceptually to Vietnam's effective-date vs applicability-date distinction.

### Gaps
- Could not load the official `legislation.gov.uk/developer` page or the EUR-Lex English reuse help page (both returned empty via fetch) — point-in-time URL patterns and CLML details here come from search snippets + secondary sources, not the primary docs. Recommend verifying CLML schema and the exact developer API contract directly.
- US per-provision **effective-date metadata** in USLM is unconfirmed — found date-versioned URLs but no evidence govinfo tags each provision with an in-force interval; check the USLM User Guide.

---

## Q4. Open-source engines/libraries for temporal / bitemporal data & legal norm graphs

### Takeaway
Two reusable layers exist: (a) **bitemporal databases** (valid-time vs transaction-time) that cleanly model legal validity intervals + audit trail, led by open-source **XTDB (MPL 2.0)**; and (b) **open-source Akoma Ntoso legislation-consolidation platforms**, led by **Indigo / Laws.Africa (GPL-3, Django/PostgreSQL)** with its **Bluebell** AKN parser and MIT-licensed **Slaw**. The bitemporal DB layer is the strongest technical fit for "valid-time = in force, transaction-time = when we recorded/knew it."

### Cited Findings
- **Bitemporal model**: valid time = when a fact was true in the real world (→ maps to a statute's in-force period); transaction time = when the DB recorded it (→ maps to when the consolidation was published/known). Enables point-in-time queries along a user-assigned valid-time axis. — [XTDB bitemporality docs](https://v1-docs.xtdb.com/concepts/bitemporality/)
- **XTDB**: open-source JVM bitemporal database, **Mozilla Public License 2.0** (commercial-use friendly). Tracks both system time and user-assigned valid-time intervals per record. 1.x stable; 2.x adds SQL:2011 bitemporal support. Document-centric, schemaless, Kafka-based "unbundled" design. — [XTDB GitHub](https://github.com/xtdb/xtdb/blob/master/README.md); [XTDB FAQ](https://v1-docs.xtdb.com/resources/faq/)
- **Datomic**: XTDB's FAQ compares it as bitemporal-adjacent, but Datomic's licensing and native valid-time support unconfirmed in sources (Datomic is now free-but-proprietary, not open source — flag for verification). — [XTDB FAQ](https://v1-docs.xtdb.com/resources/faq/)
- **Bitempura**: small in-memory Go bitemporal key-value store inspired by XTDB/Datomic; experimental, author abandoned the SQL-backed version — not production-grade. — [github.com/elh/bitempura](https://github.com/elh/bitempura)
- SQL:2011 standardized `PERIOD FOR SYSTEM_TIME` (transaction) and application-time periods (valid) — implemented in MariaDB, DB2, Oracle, SQL Server (general standard knowledge; XTDB 2.x cites SQL:2011 bitemporal support). — [XTDB FAQ](https://v1-docs.xtdb.com/resources/faq/)
- **Indigo (Laws.Africa / AfricanLII)**: open-source Akoma Ntoso **legislation consolidation + publishing** platform; Django + PostgreSQL; built for exactly the "consolidate amendments into point-in-time versions" workflow. **License: GNU GPL-3** per repo README (one secondary source says LGPL-3 — trust repo LICENSE). Copyright 2015–2020 AfricanLII. — [Indigo GitHub (Code4SA)](https://github.com/Code4SA/indigo); [Indigo docs](https://indigo.readthedocs.io/en/latest/)
- **Bluebell** (generic Akoma Ntoso 3 parser) and **Slaw** (AKN parser library, **MIT**, but repo archived) from Laws.Africa. — [awesome.ecosyste.ms slaw](https://awesome.ecosyste.ms/projects/github.com%2Flaws-africa%2Fslaw); [Laws.Africa open law tech](https://laws.africa/open-law-technology)
- **LEOS** (EU open-source legislation drafting editor, Akoma Ntoso-based) surfaced as EU-backed open-source tooling for editing legislation. — [EU interoperable-europe LEOS](https://interoperable-europe.ec.europa.eu/collection/justice-law-and-security/solution/leos-open-source-software-editing-legislation/eif-perspective)

### Inferences
- The cleanest architecture for TraLuat's moat is likely **bitemporal store (XTDB-style valid/transaction time) + AKN/FRBR component-version model (de Martim) + a norm graph (cross-reference, amends/repeals/replaces edges)**. XTDB (MPL-2.0) and Indigo (GPL-3) are the two most mature open-source building blocks; GPL-3 on Indigo means a derivative consolidation engine would itself have to be GPL — weigh that against building fresh on an MPL/MIT stack.
- Bitemporality specifically solves the "retroactive amendment / we learned later that the in-force date was different" problem that plain single-timeline versioning cannot.

### Gaps
- Did not confirm whether any project combines bitemporal storage *with* a legal norm graph out of the box — appears to be a genuine integration gap (no off-the-shelf "bitemporal legal KG" engine found).
- Temporal knowledge graph (TKG) ML research (e.g. temporal embeddings, ICEWS-style) exists but was not surveyed here; those target event prediction, not legal-validity bookkeeping — likely low relevance.

---

## Q5. Genuinely reusable vs. unsolved — especially for civil-law Vietnam

### Takeaway
Reusable now: the standards layer (AKN markup, ELI identifiers/dates, LRMoo component-version pattern, LegalRuleML for rules), open bitemporal DBs (XTDB), and open consolidation platforms (Indigo). Unsolved/hard everywhere: automated, reliable **component-level** point-in-time reconstruction from unstructured text, and automated extraction of amendment/repeal relations — the research systems (de Martim, NyayGraph, CapturingLegalReasoningPaths) all stop short of a production temporal engine. For civil-law Vietnam specifically, all tooling is adaptable (standards are jurisdiction-neutral) but none is pre-built for Vietnamese.

### Cited Findings
- de Martim explicitly lists as **open challenges / future work**: large-scale instantiation requires parsing unstructured legislation (hard), deterministic reconstruction tooling, and benchmarks; no OWL ontology published yet (planned); repeals not modeled (only modifications). — [arXiv 2506.07853v4](https://arxiv.org/html/2506.07853v4)
- Research KGs (NyayGraph, CapturingLegalReasoningPaths) model statute cross-references and fact→law reasoning but **neither models in-force intervals, version history, amendment events, or repeals** (see Q2). — [ACL 2025.nllp-1.11](https://aclanthology.org/2025.nllp-1.11); [arXiv 2508.17340](https://arxiv.org/html/2508.17340v1)
- The standards are all **jurisdiction-neutral and civil-law-compatible**: AKN is used across civil-law systems (EU, Brazil via de Martim/LexML, Switzerland via the Bologna IRI resolver); ELI is EU/civil-law native; LRMoo demonstrated on Brazil's (civil-law) constitution. — [arXiv 2506.07853v4](https://arxiv.org/html/2506.07853v4); [Bologna AKN resolver](https://akresolver.cs.unibo.it/)
- Indigo is designed for consolidating legislation in jurisdictions that lack it (African countries) — a workflow directly analogous to a civil-law country building point-in-time law from scratch. — [Indigo/AfricanLII](https://africanlii.org/articles/2019-03-28/mariya-badeva-bright/indigo-legislation-platform-consolidate-and-publish-legislation)

### Inferences (civil-law / Vietnam specific)
- **Reusable off-the-shelf**: AKN markup + FRBR/LRMoo component-version pattern + ELI-style date metadata (entry-into-force vs applicability vs no-longer-in-force) + XTDB bitemporality + Indigo's consolidation workflow. These cover the *representation* and *storage* of validity intervals well.
- **What every project leaves unsolved (TraLuat's actual moat)**: (1) reliable *extraction* of amendment/repeal/replacement relations from Vietnamese legal text (civil-law amendments are often "điều X được sửa đổi bởi…" style textual modifications needing NLP); (2) deterministic *reconstruction* of a provision's exact text on date X; (3) conflict/hierarchy resolution between norms (lex superior/posterior/specialis) — none of the surveyed systems implement legal conflict rules, and LegalRuleML models defeasibility but ships no Vietnamese ruleset.
- Vietnam has no AKN/ELI national publication (unverified but none surfaced), so corpus construction and markup is itself unsolved groundwork — unlike UK/EU where structured data exists.

### Gaps
- No Vietnamese-specific legal KG, AKN corpus, or point-in-time portal surfaced in this research (did not run a Vietnam-targeted query — out of tool budget). Recommend a dedicated follow-up search on "vbpl.vn", "LuatVietnam", and whether Vietnam's legal portal exposes effective dates / consolidated text.
- Conflict-of-norms (lex posterior/superior/specialis) automation: no open implementation found; confirm whether any JURIX/ICAIL system handles it.

---

## Summary table (maturity + license)

| Asset | Type | Jurisdiction / orientation | Temporal support | License | Commercial use |
|---|---|---|---|---|---|
| Akoma Ntoso (OASIS LegalDocML) | XML markup standard | Neutral (civil+common) | Document-level versioning; weak at component level | Open OASIS standard | Yes |
| ELI | URI + ontology standard | EU / civil-law native | Point-in-time URI slot + in-force/applicability/no-longer dates | Open standard | Yes |
| LegalRuleML Core v1.0 | Rule markup standard | Neutral | Temporal validity of rules + deontic | OASIS standard (2021) | Yes |
| LRMoo / de Martim model | Conceptual model + paper | Brazil demo (civil law) | **Component-level** point-in-time (proposed) | Paper CC BY 4.0; **no code/ontology released yet** | N/A (no artifact) |
| CapturingLegalReasoningPaths | Research repo | Japan (civil law) | **None** | **No LICENSE** (3 commits, early) | Blocked until license added |
| NyayGraph | Research repo | India (common law) | **None** | **No LICENSE** stated | Blocked until license added |
| legislation.gov.uk | National portal + API | UK (common law) | Full point-in-time + extent + timeline | OGL v3.0 | Yes |
| EUR-Lex / Cellar | Portal + SPARQL/REST | EU (civil law) | Consolidated versions + ELI dates (editorial, not authentic) | Decision 2011/833/EU | Yes |
| govinfo / OLRC USLM | Portal + XML schema | US (common law) | Date-versioned URLs + release points | Public domain | Yes |
| XTDB | Bitemporal DB engine | Neutral (tech) | Valid-time + transaction-time (bitemporal) | MPL 2.0 | Yes |
| Indigo (Laws.Africa) | AKN consolidation platform | Africa (mixed) | Point-in-time consolidation workflow | GPL-3 (repo) | Yes but copyleft |
| Slaw / Bluebell | AKN parser libraries | Neutral | Parsing only | Slaw MIT (archived); Bluebell see repo | Yes |
| LEOS | AKN drafting editor | EU (civil law) | Drafting, not point-in-time query | EU open source (EUPL — verify) | Yes |
