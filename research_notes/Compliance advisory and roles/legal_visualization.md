# Legal Visualization & Role-Specific Workbenches (for TraLuat, VN legal-AI)

Scope: open-source repos/frameworks and notable products for role-specific legal UIs (judge / procuracy / investigator / auditor), law + precedent visualization (citation networks, point-in-time "law as of date", statute-amendment timelines, evidence↔law mapping), and what is genuinely reusable vs net-new for a bilingual (VN/EN) legal workbench. Current as of Nov 2026.

---

## Q1. Open-source legal UIs / case-management / e-discovery / legal-research frontends with role-specific views, citation navigation, timelines, evidence↔law mapping, or judicial decision-support dashboards

### Takeaway
There is real, reusable open-source infrastructure for legal *data and content* (CourtListener for case law + citation graph; Indigo for point-in-time legislation), but almost no open-source *role-specific decision-support workbench* for judges/prosecutors/investigators — those patterns exist only in commercial products. Open-source case-management tools are either dormant hobby projects or government/FOIA-oriented (ArkCase). E-discovery open source is analytics-engine-level, not full review UIs.

### Cited Findings

**Case law / legal research frontends (most mature, reusable)**
- CourtListener (Free Law Project) is "a fully-searchable and accessible archive of court data" covering opinions, oral arguments, judges, judicial financial records, federal filings; started 2009; Django-based (`cl/` holds ~99% of the code, with a `FRONTEND.md`). Maturity: ~26,648 commits, ~1.1k stars, 288 forks, ~972 open issues. License: **Affero GPL (AGPL)** — "All materials in this repository are copyright Free Law Project under the Affero GPL." — [GitHub: freelawproject/courtlistener](https://github.com/freelawproject/courtlistener)
- AGPL is a strong copyleft that triggers source-disclosure obligations for networked/hosted use — material for a commercial SaaS; usable as a data backend/reference but the license must be cleared with counsel before adopting code. — [GitHub: freelawproject/courtlistener](https://github.com/freelawproject/courtlistener)

**Legislation management + point-in-time (most relevant to "law as of date")**
- Indigo (Laws.Africa / AfricanLII) is a "legislation database for managing, consolidating and publishing legislation" in Akoma Ntoso XML. Backend: Django + Django REST Framework, using Cobalt (Akoma Ntoso Python lib) and Bluebell (Akoma Ntoso 3 parser). Frontend is migrating JS modules to Vue (ES6, webpack), with legacy Backbone.js present. Localization via CrowdIn + Django `.po`/`.mo` + separate JS translations. License: **GNU GPL v3**. Maturity: ~78 stars, 39 forks, ~11,134 commits, 179 open issues, 25 open PRs. — [GitHub: laws-africa/indigo](https://github.com/laws-africa/indigo)
- Indigo supports "amendments, point-in-time comparison, complex commencements and multiple output formats." — [Laws.Africa](https://laws.africa/open-law-technology)
- Kenya Law uses Indigo to manage, consolidate and publish the Laws of Kenya. — [Laws.Africa Kenya Law case study](https://laws.africa/case-studies/kenyalaw/)

**Open-source case management (weak / caution)**
- Open Legal Case Management (OLCM) — case strategy, evidence collection, documentation; **GPLv2**; SourceForge-hosted (likely dormant). — [SourceForge OLCM](https://sourceforge.net/projects/olcm)
- Legal Practice Case Manager — cases, notes, calendars, deadlines, conflict checks, reporting; **GPLv2**; SourceForge. — [SourceForge legalpractice](https://sourceforge.net/projects/legalpractice/)
- ArkCase (Armedia) — open-source case management (ArkCase Community Edition) that is platform-agnostic; supports "FOIA, legal case management, investigative case management, docket, correspondence management, complaint management" and an AI add-on (ArkCase Illume) for FOIA/legal/public-records/investigative work. Has FedRAMP ATO at moderate impact level. Commercial tiers ~$60/user/mo. Specific OSS license not confirmed from search. — [ArkCase](https://www.arkcase.com/); [Armedia FedRAMP PR](https://www.streetinsider.com/Business+Wire/Armedia+Achieves+FedRAMP%C2%AE+Authorization+for+ArkCase/23765573.html); [govlaunch ArkCase](https://govlaunch.com/products/arkcase-open-source)

**E-discovery (analytics engines, not full review UIs)**
- FreeEed (SHMsoft) — legal discovery tool; OCR, culling, document review; built on Hadoop/Tika/Lucene/ElasticSearch; companion FreeEedReview for review. License: **Apache 2.0**. — [GitHub: freethinkingit/FreeEed](https://github.com/freethinkingit/FreeEed)
- FreeDiscovery — e-discovery/IR engine on scikit-learn: text categorization, semantic search, clustering, duplicates detection, email threading. License: **3-clause BSD**. Analytics component, not an end-to-end review platform. — [PyPI freediscovery](https://pypi.org/project/freediscovery)

**Citation-navigation frontends (small/demo-grade)**
- LexChat2 (delphium226) — React (TS) + Vite + Tailwind frontend for a Scottish Govt legal research assistant; split-screen "Source Viewer" shows cited text verbatim beside the AI answer (closest OSS match to citation navigation). — [GitHub: delphium226/LexChat2](https://github.com/delphium226/LexChat2)
- Lex AI (N-Look) — claims clickable quote references that jump to exact source location in the document; searches CanLII via natural language; license not confirmed. — [GitHub: N-Look/legal](https://github.com/N-Look/legal)

**Notable commercial products (pattern reference only)**
- equivant Judicial Tools — case management built specifically for judges. — [equivant](https://www.equivant.com/case-management-built-specifically-for-judges-spotlight-judicial-tools/)
- NCSC Judicial eBench Tools — "digital workbench of tools, tasks and resources" used "on the bench and in chambers" for judges and judicial staff. — [NCSC](https://ncsc.org/consulting-and-research/areas-of-expertise/technology/application-component-model/courtroom-components/judicial-e-bench-tools)
- Thomson Reuters CoCounsel — a "Judicial" setting that switches to a neutral default and judge-specific prompts. — [Thomson Reuters](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/navigation/about/use-judicial-experience)
- Casefleet — chronology + visual timeline view with filters/minimap, linking facts to witnesses, issues, and evidence (strong evidence↔fact pattern reference). — [Casefleet timelines](https://casefleet.com/features/timelines)
- Pandektes (commercial) hiring for a React/Next.js "document viewer where lawyers read and annotate legislation and case law." — [startup.jobs Pandektes](https://startup.jobs/senior-frontend-engineer-pandektes-8344858)

### Inferences
- The reusable OSS layer is "content + data" (CourtListener case/citation data; Indigo legislation/point-in-time), not "role UI." A judge/procuracy/investigator/auditor workbench is effectively net-new, informed by commercial patterns (equivant, NCSC eBench, Casefleet, SAS Law Enforcement).
- AGPL (CourtListener) and GPLv3 (Indigo) are both copyleft; for a proprietary commercial SaaS, safest use is as a separate backend service / data reference or re-implementation, not direct linking into closed frontend code. Apache-2.0 (FreeEed) and BSD (FreeDiscovery) are permissive and commercial-friendly.

### Gaps
- No open-source e-prosecution / procuracy case-management system found — every result was commercial (eProsecutor/Journal Tech, MatrixProsecutor, CASE 365, CSI InfoShare, India MP e-Prosecution). — [search: prosecutor case management OSS](https://www.journaltech.com/eprosecutor)
- Could not confirm ArkCase's specific OSS license (AGPL vs other) or whether the Community Edition is usable for production FOIA/investigation without a commercial contract.

---

## Q2. Visualization of legal knowledge graph / citation network / statute-amendment timeline (point-in-time), and open tooling (CourtListener, Indigo, legislation.gov.uk)

### Takeaway
Citation-network visualization has one notable (now semi-deprecated) open implementation — CourtListener/SCOTUS Mapping Project. Legislation knowledge-graph viz exists as research prototypes (Graphie, Lex Graph) that are small and partly archived. Point-in-time / amendment timeline UX is best demonstrated (production-grade) by legislation.gov.uk and Indigo, but the polished front-end of legislation.gov.uk is not itself an off-the-shelf OSS component. Generic graph-viz libraries (Cytoscape.js, Sigma.js) are the practical reusable building blocks.

### Cited Findings

**Citation network visualization**
- Free Law Project launched a SCOTUS citation-network tool in 2016 (with the SCOTUS Mapping Project, Univ. of Baltimore): users create citation networks representing "lines of cases" in Supreme Court doctrine; visualizations can be saved, shared, commented on, embedded; networks drawn within three degrees of separation; circle size reflects citation counts; clicking an opinion reads its text. — [free.law viz post](https://free.law/2016/02/22/viz/); [LawNext](https://www.lawnext.com/2016/02/scotus-visualization-project-shows-lines-of-cases-literally.html)
- Current status is degraded: creating/editing visualizations still works via the API, but "it is no longer possible to display visualizations on CourtListener.com itself" — only via embed links. — [wiki.free.law visualizations API v4](https://wiki.free.law/c/courtlistener/help/api/rest/v4/visualizations)
- CourtListener's Citation API powers "visualizations, tables of authorities, citation search"; the citation graph is exported quarterly as bulk data; it does not have every parallel citation for every decision. — [wiki.free.law citations API v4](https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations)

**Legislation knowledge-graph viz (research prototypes)**
- Graphie (KCL Quant Law) — network-based visual interface for UK primary legislation; models legal sources as directed multigraphs representing all structural elements of a legal source; repo at github.com/kclquantlaw/graphie. — [Graphie paper (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10230175/); [arXiv PDF](https://arxiv.org/pdf/2210.02165)
- Lex Graph (i.AI / UK govt) — builds a knowledge graph of UK legislation from National Archives CLML XML; relationships from explicit XML references (implicit refs may be missed); visualization is a **Streamlit** app (`demo/app.py`), interactive but may slow on large subgraphs; prebuilt graph on Hugging Face. License: **MIT** (source data under OGL v3.0). Maturity: Prototype, 26 stars, 8 commits; **repository archived May 22, 2026** (read-only, no further development). — [GitHub: i-dot-ai/lex-graph](https://github.com/i-dot-ai/lex-graph)
- LynxSight (osoc-es) — web tool for graph visualization of legal events, part of an EU Legal Knowledge Graph (LKG) project; aimed at "who sued whom and when." — [GitHub: osoc-es/lynx-Sight](https://github.com/osoc-es/lynx-Sight)
- LegalViz — research dataset for diagramming legal text, generating diagrams via Graphviz DOT. — [arXiv 2502.06147](https://arxiv.org/pdf/2502.06147)
- legalis-viz — Rust crate for decision trees/flowcharts/dependency graphs/discretionary-zone highlighting; outputs Mermaid, Graphviz, ASCII. — [rust-digger legalis-viz](https://rust-digger.code-maven.com/crates/legalis-viz)

**Point-in-time / amendment timeline UX (production patterns)**
- legislation.gov.uk "Timeline of Changes" shows the different points in time where a change occurred; each date is the earliest a change took effect; first date is usually first-in-force. Turned on via Advanced Features > Show Timeline of Changes, or a point-in-time advanced search. — [legislation.gov.uk example](https://www.legislation.gov.uk/ukpga/2000/10/section/3/2000-07-20)
- "What Version" selector box switches among: Latest Available (Revised), Point in Time, Original (As enacted); return to latest via the same controls. — [legislation.gov.uk example](https://www.legislation.gov.uk/ukpga/2022/37/schedule/9/part/1/2023-11-01)
- Limit: pending changes not yet applied by editors only show in the latest view — not accessible in point-in-time view; superseded provisions show a status like "This version of this provision no longer has effect." — [legislation.gov.uk](https://www.legislation.gov.uk/ukpga/2020/17/schedule/15/part/2/2021-04-30)
- Indigo point-in-time concept: a "point in time" is the set of a Work's expressions on a particular date, with all previous amendments applied; points in time usually carry an event (publication or amendment); editor workflow creates a new document at the new point in time. — [Laws.Africa Editor Guide](https://docs.laws.africa/llms-full.txt)

**Reusable generic graph-viz libraries (building blocks)**
- Cytoscape.js — general-purpose graph theory lib for browser visualization; no hard dependencies; renders thousands of elements on average hardware; JSON import/export; extensions include ELK/Dagre layouts. More built-in analysis/styling. — [Cytoscape.js paper (PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4708103/)
- Sigma.js — open-source WebGL renderer for large graphs; pairs with ForceAtlas2 (worker threads); better for very large networks. — [search result summary]
- (For timelines) shadcn/ui "legal case" timeline block — React/Next.js/Tailwind copy-paste block tracking proceedings filing→verdict with status badges/case numbers/judges; a copy-paste block, not an installable package. — [shadcn.io legal-case timeline](https://www.shadcn.io/blocks/timeline-legal-case)

### Inferences
- For a citation/precedent network, the practical reusable path is: CourtListener-style data model + a generic renderer (Cytoscape.js for analysis-rich medium graphs, Sigma.js for large). The CourtListener viz UI itself is not a drop-in and is now embed-only.
- For "law as of date," legislation.gov.uk's "What Version" selector + "Timeline of Changes" is the gold-standard UX pattern to emulate; Indigo provides a reusable OSS *data/engine* layer (Akoma Ntoso + point-in-time expressions) but its editor UI is for publishers, not decision-makers.
- Legislation KG visualization is still research-grade in OSS (Graphie/Lex Graph both small, Lex Graph archived) — not production-adoptable as-is, but validates the approach and data modeling.

### Gaps
- No OSS component found that renders a statute-amendment timeline AND an interactive citation network together in a single decision-maker view.

---

## Q3. How do these present "which law applies, at what date, with which precedent" to a decision-maker? Role-based access/views?

### Takeaway
"Which law, at what date" is solved in production by legislation.gov.uk/Indigo via explicit version selectors + change timelines + applied-amendment expressions. "With which precedent" is solved via citation graphs / tables of authorities (CourtListener). But presenting all three in one role-tailored decision-support surface is a commercial-product pattern, not an OSS one; role-based views are an established design principle (role home pages, task queues, least-privilege, audit trails) but not packaged as reusable legal OSS.

### Cited Findings
- "Which law at what date": legislation.gov.uk "What Version" (Latest Revised / Point in Time / Original) + "Timeline of Changes" dates give exactly the as-of-date presentation, with status flags on superseded provisions. — [legislation.gov.uk](https://www.legislation.gov.uk/ukpga/2022/37/schedule/9/part/1/2023-11-01)
- Indigo materializes this as "expressions" per point-in-time with all prior amendments applied, each tied to an event. — [Laws.Africa Editor Guide](https://docs.laws.africa/llms-full.txt)
- "Which precedent": CourtListener Citation API powers tables of authorities + citation search + network viz; citation graph exported quarterly. — [wiki.free.law citations](https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations)
- Role-based views (design patterns from products):
  - Prosecutor CMS: "customized login dashboards based on user roles," because "prosecuting attorneys and clerks have very different tasks." — [CivicEye](https://www.civiceye.com/?p=2856)
  - Judges: NCSC eBench = digital workbench on bench + in chambers; CoCounsel "Judicial" mode uses neutral defaults + judge-specific prompts. — [NCSC](https://ncsc.org/consulting-and-research/areas-of-expertise/technology/application-component-model/courtroom-components/judicial-e-bench-tools); [Thomson Reuters](https://www.thomsonreuters.com/en-us/help/cocounsel/legal/navigation/about/use-judicial-experience)
  - Investigators: SAS Law Enforcement Intelligence uses role-based home pages; investigator = gathers evidence, updates reports; worklist-oriented view distinct from full case-management view. — [search: role based legal workbench]
  - Access control (audit/compliance): forensic/prosecution vendors stress role-based access, supervisory review, audit trails; investigators may get read-only access with temporary, logged privilege escalation. — [hoop.dev RBAC forensic](https://hoop.dev/blog/role-based-access-control-in-forensic-investigation-databases)
  - Workbench "My…" task-queue model (Clio/Sharedo) organizes work items assigned to the user. — [Sharedo workbench](https://sharedo.helpjuice.com/your-workbench)

### Inferences
- Common cross-role design principles to adopt: (1) role-specific home screen + task queue; (2) least-privilege + full audit logging (critical for judicial/procuratorial legitimacy and VN oversight norms); (3) neutral read-focused view for judges vs disclosure/review workflows for procuracy vs evidence/report intake for investigators vs audit-trail/compliance dashboards for auditors.
- The "which law + date + precedent" triad maps cleanly to three reusable backend capabilities (point-in-time legislation engine à la Indigo; citation graph à la CourtListener; a role/RBAC + audit layer) with a net-new presentation layer per role.

### Gaps
- No published study or standard covering judge+procuracy+investigator+auditor views together; must be composited from the above.

---

## Q4. What is genuinely reusable vs build-from-scratch for a bilingual (VN/EN) per-role legal workbench

### Takeaway
Reusable: data/engine layers (Akoma Ntoso tooling + Indigo point-in-time engine; CourtListener data model/citation API; generic graph-viz and timeline components; i18n plumbing). Build-from-scratch: the per-role decision-support UIs, evidence↔law mapping views, the integrated "law-as-of-date + precedent" decision surface, and genuine Vietnamese-first bilingual legal UX. Bilingual legal content is standardized at the data level (Akoma Ntoso) but there is no ready-made bilingual legal *viewer*.

### Cited Findings

**Reusable (permissive or as backend service):**
- Akoma Ntoso: OASIS XML standard for machine-readable legislative/judicial docs; provides identifiers for different versions, languages and publication forms of the same document; multilingual interconnection via the Akoma Ntoso Naming Convention; `<foreign>` native element handles language/tradition variation; adopted by the UN HLCM (April 2017). — [Wikipedia Akoma Ntoso](https://en.wikipedia.org/wiki/Akoma_Ntoso); [FAO/CNR paper](https://cris.unibo.it/retrieve/e1dcb333-6110-7715-e053-1705fe0a6cc9/LvI2019-CNR-FAO.pdf)
- Indigo stack (Cobalt, Bluebell parsers; Django) — reusable point-in-time legislation engine (GPLv3 — copyleft; use as service). — [GitHub: laws-africa/indigo](https://github.com/laws-africa/indigo)
- Indigo already supports i18n: CrowdIn + Django `.po`/`.mo` + separate JS translations — a working bilingual plumbing model. — [GitHub: laws-africa/indigo](https://github.com/laws-africa/indigo)
- CourtListener citation data model + quarterly bulk citation graph (AGPL — use as data/service). — [wiki.free.law citations](https://wiki.free.law/c/courtlistener/help/api/rest/v4/citations)
- Cytoscape.js (graph viz, permissive) / Sigma.js (WebGL large graphs) — citation-network rendering. — [Cytoscape.js](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4708103/)
- shadcn/ui timeline + "legal case" blocks (MIT-style, copy-paste) for case/amendment timelines. — [shadcn.io](https://www.shadcn.io/blocks/timeline-legal-case)
- FreeEed (Apache-2.0) / FreeDiscovery (BSD) for evidence processing/IR analytics if e-discovery is in scope. — [FreeEed](https://github.com/freethinkingit/FreeEed); [FreeDiscovery](https://pypi.org/project/freediscovery)

**Build-from-scratch (no adoptable OSS):**
- Per-role workbenches (judge / procuracy / investigator / auditor) — only commercial patterns exist.
- Evidence↔law mapping view — only Casefleet-style commercial reference (facts linked to witnesses/issues/evidence); no OSS component. — [Casefleet](https://casefleet.com/features/timelines)
- Integrated "law-as-of-date + applicable precedent" decision surface — no single OSS tool combines point-in-time law + citation network.
- Vietnamese-first bilingual legal UI — no OSS bilingual legal viewer found; standard only addresses the data layer.

### Inferences
- Recommended build posture: adopt **engines/data + generic viz libs + i18n plumbing**; **build** the role UIs and the integrated decision surface. Treat GPLv3/AGPL projects (Indigo, CourtListener) as separate services behind APIs to avoid copyleft contaminating a proprietary frontend; freely embed permissive pieces (Cytoscape.js, shadcn blocks, FreeEed/FreeDiscovery).
- Akoma Ntoso is the strategic data standard for both point-in-time and bilingual needs — modeling VN legislation in Akoma Ntoso (via Cobalt/Bluebell) would unlock Indigo's amendment/point-in-time logic and standardized language-version identifiers, which is the single highest-leverage reuse decision.
- Bilingual (VN/EN) is largely net-new at the presentation layer, but the Indigo CrowdIn/`.po` + Akoma Ntoso language-identifier approach is a proven template to copy rather than invent.

### Gaps
- No evidence of any VN-specific or Vietnamese-language open legal-UI project surfaced in these searches.
- Did not verify current maintenance/commit recency of the dormant SourceForge case-management projects or ArkCase's exact OSS license terms.
- Did not find an off-the-shelf bilingual Akoma Ntoso viewer component (UN/FAO tooling may exist but was not confirmed).
