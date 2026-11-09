# Commercial & Major Open Legal-AI Platforms + Portability Across Jurisdictions

*Research current as of Nov 2026. Many vendor figures are marketing claims from vendor pages or aggregator/directory sites; these are flagged. Primary-source confirmation was limited by paywalls and vendor-only documentation. Where a claim rests only on a low-authority aggregator, it is marked as such.*

## Q1: Player profiles — work product, differentiators, jurisdictions, grounding/hallucination/effective-dating claims

### Takeaway
The leading platforms split into (a) "work-product" generators (Harvey, Legora, CoCounsel, Luminance, Robin, LegalOn, Spellbook, Hebbia) that output drafted/reviewed contracts, diligence matrices and memos, and (b) grounded legal-research engines (Lexis+ with Protégé, CoCounsel/Westlaw). All of them are US/UK/EU-common-law-first and English-first; none surfaced as having true effective-date/point-in-time correctness or omission-detection as a *headline* feature. Citation grounding is the universal anti-hallucination story; "effective-dating" and "missing-clause detection" exist only as secondary capabilities, if at all.

### Cited Findings

**Harvey**
- Work product: drafting, research, document analysis/contract review; "Ask LexisNexis" returns "AI-driven, citation-backed answers from LexisNexis, directly in the Harvey platform" — [Harvey](https://www.harvey.ai/resources/videos/introducing-ask-lexisnexis); partnership reported by [ABA Journal](https://www.abajournal.com/web/article/lexisnexis-and-harvey-team-up-to-revolutionize-legal-research-with-ai).
- Grounding: third-party reviews say Harvey validates cases against authoritative databases and marks citations with "grounding-confidence indicators" (unverified, review-site claim) — [tooliverse review](https://tooliverse.ai/tools/harvey); LexisNexis library integration for citation-grounded US research — [pangea glossary](https://pangea.app/glossary/harvey).
- Jurisdiction footprint (by customer count, not legal-system depth): Oct 2025 = 700 customers in 58 countries; Jan 2026 = 1,000+ customers across 59+ countries; Oct 2026 = 3,500+ customers in 85+ countries — [Lawyers Weekly (Tokyo expansion)](https://www.lawyersweekly.com.au/biglaw/45215-harvey-prepares-next-gen-lawyers-for-an-ai-driven-world-expands-into-tokyo); [EQT investment release](https://eqtgroup.com/news/harvey-announces-50-million-investment-from-eqt-growth-tapping-eqts-global-platform-to-accelerate-international-expansion-2025-10-06).
- Offices: London (EMEA HQ), Bengaluru, Dublin, Sydney, Singapore, Madrid (Apr 2026), Paris (announced Jan 2026, opened ~May 2026), Tokyo (planned 2027) — [Artificial Lawyer (Paris)](https://www.artificiallawyer.com/2026/01/15/harvey-to-open-paris-base-as-global-growth-continues/); [SecurityBrief Asia (Sydney)](https://securitybrief.asia/story/harvey-opens-sydney-office-to-expand-ai-legal-services-in-asia-pacific).
- Big deployments: CMS (all 21 member firms, 50+ countries); Eversheds Sutherland (initial 350 lawyers) — [LegalTech-Talk (CMS)](https://www.legaltech-talk.com/cms-announces-roll-out-of-harvey-across-50-countries); [Nonbillable (Eversheds)](https://www.nonbillable.co.uk/news/harvey-lands-eversheds-sutherland-europe-push).
- Note: No public source found on which *languages* Harvey supports; coverage described as practice-area depth in US/UK + growing European jurisdictions, "less coverage outside common-law systems" (review-site claim).

**Legora (formerly Leya)**
- Rebrand: Legora was formerly Leya — [Legal Technology Hub](https://www.legaltechnologyhub.com/vendors/legora/).
- Work product: "Tabular Review" (grid comparison across thousands of documents), M&A due diligence, jurisdiction-aware research with structured citations, playbooks that flag deviations/non-standard terms — [contracko review](https://contracko.com/clm-reviews/legora.md).
- Multi-jurisdiction: marketed for "multi-jurisdiction research"; a Leya-era directory claimed it identifies gaps in contract portfolios vs evolving EU AI Act requirements using "jurisdiction-specific legal precedent analysis" (low-authority) — [aiagentstore](https://aiagentstore.ai/ai-agent/legora).
- Funding: reported $550M Series D (Mar 2026) at a ~$5.55B valuation (directory sources, verify) — [techjockey](https://www.techjockey.com/us/detail/legora).

**Luminance**
- Work product: contract analysis/review/negotiation; proprietary vertical model "Luna Crescent" launched ~June 2026 — [Luminance press](https://www.luminance.com/press/luminance-unveils-luna-crescent-the-vertical-ai-model-powering-contract-intelligence-with-market-leading-accuracy-and-speed); [Lawyers Weekly](https://www.lawyersweekly.com.au/newlaw/44539-luminance-launches-proprietary-ai-model-designed-specifically-for-contract-analysis).
- Training: fine-tuned on a subset of Luminance's proprietary dataset said to draw on 220M+ verified legal documents (one source instead cites ~3.4M legal concepts — figures conflict); trained on "structure and language of legal agreements" not general text — [IT Brief UK](https://itbrief.co.uk/story/luminance-launches-luna-crescent-contract-ai-model); [Solicitors Journal](https://www.solicitorsjournal.com/sjarticle/luminance-launches-luna-crescent-ai-model--).
- Claimed performance: ~5% more accurate than leading general models on contract-understanding, up to 4x faster, on its internal "ContractIQ Bench" (180,000+ annotated data points) — vendor benchmark — [Luminance press](https://www.luminance.com/press/luminance-unveils-luna-crescent-the-vertical-ai-model-powering-contract-intelligence-with-market-leading-accuracy-and-speed).
- Footprint: 1,000+ organisations in 70+ countries (vendor) — same press release.
- No public detail found on jurisdictional coverage of training data or effective-dating.

**Robin AI**
- Work product: contract review/editing/drafting (NDAs, MSAs, SaaS, vendor agreements) "across multiple jurisdictions" (no list) — [Legal Technology Hub](https://www.legaltechnologyhub.com/vendors/robin/).
- UK-based; raised $26M to expand in US and APAC — [LegalTechnology.com](https://legaltechnology.com/?p=56708).
- Data: documents held in "secure AWS cloud environment" (directory claim) — [similarlabs](https://similarlabs.com/p/robin-ai).

**LegalOn**
- Work product: AI contract review flagging missing clauses / risky language, organized by category in a Word sidebar; "My Playbooks" (Jan 2025) lets teams encode internal standards/preferred language — [LawNext](https://www.lawnext.com/2025/01/legalon-expands-ai-contract-review-platform-with-feature-to-create-custom-playbooks.html); [Artificial Lawyer](https://www.artificiallawyer.com/2025/01/21/legalon-launches-personalized-ai-review-playbooks-demo/); [LegalOn: Introducing My Playbooks](https://www.legalontech.com/post/introducing-my-playbooks).
- Anti-hallucination framing: CEO says playbooks "ground the AI in reviewing against yours or industry standards, and not AI hallucinations" — [LegalOn playbooks post](https://www.legalontech.com/post/introducing-my-playbooks).
- Claim: "95% of organizations have gaps in their playbook coverage" (LegalOn 2025 State of Contracting report) — [Today's General Counsel](https://todaysgeneralcounsel.com/how-contract-playbooks-close-the-reliability-gap-in-ai-contract-review/).
- Note: LegalOn originated in Japan (Japanese + US/English coverage); no public technical doc found on how missing-clause detection works or its accuracy.

**Spellbook (by Rally)**
- Work product: Microsoft Word add-in; drafts and reviews contracts, scans for missing clauses, "aggressive" terms and risks; suggests redlines — [Spellbook: draft in minutes](https://spellbook.legal/draft-in-minutes); [Spellbook: contract issues](https://www.spellbook.legal/learn/contract-issues).
- Jurisdiction claims: vendor says it "compares every clause to jurisdiction-specific templates and industry benchmarks"; a third-party listing cautions coverage is strongest in US/English commercial contracts, weaker for non-English/niche jurisdictions — [Spellbook brief](https://www.spellbook.legal/briefs/legal-ai-assistant); [softwarefinder](https://softwarefinder.com/legal/spellbook).

**Hebbia (Matrix)**
- Work product: "Matrix" spreadsheet-style interface over large document sets; citation-backed answers; contract due diligence matrices, deal-point extraction, red-flag ID, credit-agreement analysis — [Hebbia law page](https://hebbia.com/industry/law); [Sacra analysis](https://sacra.com/chat/h/1bdd2f81-8e63-445c-b19d-ac79214794ff/).
- Positioning: Sacra frames Hebbia as trying to "own the work product, not just the search box" — [Sacra](https://sacra.com/chat/h/1bdd2f81-8e63-445c-b19d-ac79214794ff/).
- Adoption: Orrick (automating corporate DD workflows); Seyfarth (7M+ pages processed) — [Hebbia/Orrick](https://hebbia.com/customers/orrick); [BusinessWire](https://www.businesswire.com/news/home/20260312308364/en/). Vendor-sourced "75% faster credit agreement review" — [OpenAI customer page](https://openai.com/index/hebbia).

**CoCounsel (Thomson Reuters)**
- Work product: drafting (drawing on firm repositories, Practical Law, playbooks), review, cross-jurisdiction research synthesizing case law/statutes/secondary authority; runs in MS Word/365; next-gen "CoCounsel Legal" beta reportedly built on Anthropic's Claude Agent SDK (single secondary source, unverified) — [Thomson Reuters CoCounsel](https://legal.thomsonreuters.com/en/products/cocounsel-essentials); [boldstart/fastforward](https://fastforward.boldstart.vc/?p=711).
- Anti-hallucination: "prompting guardrails that confine GenAI outputs to vetted sources" (TR own content) — [theneuralbase summary](https://theneuralbase.com/ai-for-legal/learn/intermediate/casetext-cocounsel-now-thomson/).
- Data residency: region-based hosting in UK, Australia, Canada — same source.

**Lexis+ AI / Lexis+ with Protégé**
- Rebuilt Feb 2026 as "Lexis+ with Protégé," said to "fully replace Lexis+ AI" — [haqq review](https://www.haqq.ai/blog/lexis-plus-ai-review-vs-westlaw.html) (competitor source).
- Grounding: citations link directly to source docs; "if a citation isn't linkable, we flag it for manual validation"; a described 5-stage check (semantic understanding, recency filtering, authority ranking, citation validation) — [LexisNexis: legal AI citation integrity](https://www.lexisnexis.com/community/insights/legal/b/thought-leadership/posts/legal-ai-citation-integrity).
- Independent evidence: Stanford RegLab study (2024, peer-reviewed 2025) reported Lexis+ AI produced incorrect info on >17% of queries and concluded vendor accuracy claims were "overstated" (figure via secondary reporting; predates Protégé) — [haqq summary citing Stanford](https://www.haqq.ai/blog/lexis-plus-ai-review-vs-westlaw.html).

### Inferences
- "The work done" is now the explicit battleground (Harvey, Legora, Hebbia, CoCounsel, Luminance), displacing pure legal search as the differentiator. Hebbia's "own the work product" framing captures the category shift.
- All majors converge on citation grounding + restricting outputs to vetted corpora as the hallucination defense; none sells temporal correctness or omission-completeness as the primary promise.

### Gaps
- No vendor-published language lists (esp. non-English) for Harvey, CoCounsel, Luminance.
- Luminance training-corpus size figures conflict (220M docs vs 3.4M concepts); unresolved.
- Protégé-era (post-Feb-2026) independent accuracy data not found; the 17% figure is for the older product.

## Q2: Does anyone do effective-date/point-in-time correctness AND omission/missing-clause detection as a HEADLINE feature?

### Takeaway
No. Point-in-time/effective-dating exists in the *data layer* of legal publishers (vLex dated editions; Thomson Reuters TimeBase) but was not found as a headline AI feature of any work-product platform. Missing-clause/omission detection is a real but *secondary* feature of contract-review tools (LegalOn, Spellbook, Robin, Luminance), framed as playbook-driven deviation flagging — not as temporal-correctness-aware omission detection. The combination (effective-date-aware + omission-detecting) is an open space.

### Cited Findings
- Point-in-time concept = give a citation + a date, get the text in force on that date; requires storing every version with effective-date ranges, and "almost no US primary-law API gives true point-in-time retrieval" — [Vaquill blog](https://www.vaquill.ai/blog/amendment-history-point-in-time-law).
- "Version chain" design (each version links to predecessor/successor + carries effective-date range; output should state which version is cited and whether a newer exists) — [Auryth temporal-versioning blog](https://aurythwebsite.pages.dev/en/blog/temporal-versioning-legal-ai/).
- Publisher-level point-in-time exists: Thomson Reuters TimeBase "point-in-time" (Australia) — [Thomson Reuters TimeBase](https://www.thomsonreuters.com.au/en-au/products/timebase/point-in-time.html); vLex stores dated statute editions (e.g., "Edition 2023 / Edition 2016" pages) — [vLex Oregon section example](https://us.vlex.com/vid/section-419b-854-computing-1073586510).
- Academic framing: arXiv paper on "temporal drift" in legal LLMs — whether models stay reliable as provisions change (abstract-level only) — [arXiv 2605.23497](https://arxiv.org/html/2605.23497).
- Omission detection is playbook-driven, not temporal: LegalOn/Spellbook flag "missing clauses" against a clause library/playbook (see Q1 sources). No source found tying omission detection to the law *in force on a given date*.

### Inferences
- The effective-date capability lives with incumbents' *content* businesses (TR, vLex, LexisNexis), not their AI work-product layers — so an AI entrant that bakes effective-dating into generation/review is differentiated.
- "Omission detection relative to what the law required at time T" (vs "missing vs our playbook") appears to be genuinely unoccupied.

### Gaps
- Could not confirm whether Vincent (vLex) or CoCounsel expose an "as-of date" query to end users; only that the underlying data is versioned.

## Q3: How do multi-jurisdiction products architect for adding jurisdictions? Config-driven vs rebuild?

### Takeaway
Almost no public technical detail exists on config-driven vs rebuild architecture. Observable strategy is market/office expansion + partner law-firm rollouts (Harvey) and proprietary vertical models trained on large multi-country corpora (Luminance), plus customer-configurable playbooks (LegalOn, Legora, Spellbook) — which is effectively per-jurisdiction *content/playbook* configuration layered on a general model, not documented per-jurisdiction rules engines.

### Cited Findings
- Harvey scales jurisdictions via offices + large multi-country firm deployments (CMS 50+ countries, 21 firms) rather than any published config framework — [LegalTech-Talk](https://www.legaltech-talk.com/cms-announces-roll-out-of-harvey-across-50-countries).
- Luminance approach = one proprietary vertical model trained on a broad multi-country legal corpus used in 70+ countries (not per-jurisdiction modules disclosed) — [Luminance press](https://www.luminance.com/press/luminance-unveils-luna-crescent-the-vertical-ai-model-powering-contract-intelligence-with-market-leading-accuracy-and-speed).
- Customer-configurable playbooks are the de facto "add a standard" mechanism (LegalOn "My Playbooks"; Legora/Spellbook jurisdiction-specific templates) — [LegalOn](https://www.legalontech.com/post/introducing-my-playbooks); [Spellbook brief](https://www.spellbook.legal/briefs/legal-ai-assistant).
- Isolation architecture best-practice (relevant to multi-tenant jurisdiction data): filter retrieval by client_id at query time so one client's docs never surface for another — [theneuralbase on-prem/zero-retention guide](https://theneuralbase.com/ai-for-legal/learn/beginner/on-premises-zero-retention/) (non-authoritative).

### Inferences
- The market's "add a jurisdiction" today = train/ground on that country's corpus + let customers author playbooks; a declarative, config-driven jurisdiction model (rules/effectivity/clause requirements as data) is not publicly claimed by any major — a defensible architectural differentiator for a new entrant.

### Gaps
- No vendor publishes whether adding a jurisdiction is "configuration vs rebuild." This is a genuine information gap across all players.

## Q4: Who serves Southeast Asia / Vietnam / FDI cross-border compliance? Bilingual VN-EN gap?

### Takeaway
There is a clear bilingual Vietnamese-English FDI gap among the global majors (all English/common-law-first). The notable Vietnam-specific entrant is LEXcentra (government-linked, via the Ministry of Justice's National Legal Portal; attributed to developer "LEXengine"), which claims Vietnamese contract drafting/review against Vietnamese law — but bilingual drafting and FDI-specific features are unconfirmed. Harvey/CoCounsel have APAC offices (Singapore, Sydney, Tokyo planned) but no evidence of Vietnamese-law depth.

### Cited Findings
- LEXcentra: on Vietnam's National Legal Portal (lexcentra.phapluat.gov.vn), listed under the Ministry of Justice; "AI assistant that supports legal research, compliance, and documentation," including contract review against Vietnamese law + internal policies, and drafting a complete contract based on Vietnamese law — [LEXcentra portal via search; National Legal Portal]. Developer attributed to "LEXengine" by [Stanford TechIndex](https://techindex.law.stanford.edu/companies/lexengine).
  - *Note: direct fetch of lexcentra.phapluat.gov.vn failed (DNS not resolvable from this environment); details are from search snippets of the portal and Stanford TechIndex — verify directly.*
- Vietnam state/industry AI-legal activity: FPT partnered with Ministry of Justice on the National Legal Database / National Legal Portal; CMC+OpenAI showcased a legal AI platform ("CLEX" named in one report — possible naming discrepancy with LEXcentra) at ASEAN Law Forum 2026 — [FPT-IS](https://fpt-is.com/en/?p=24493); [Vietnamnet (CMC/OpenAI)](https://vietnamnet.vn/en/cmc-openai-showcases-legal-ai-capabilities-at-asean-law-forum-2547630.html); [FPT ASEAN Law Forum](https://fpt.com/en/news/fpt-showcases-ai-powered-justice-ecosystem-at-asean-law-forum-2026).
- Bilingual contract practice (the market need): FDI contracts commonly drafted bilingual (Vietnamese + English); for typical contracts enterprises may use bilingual with English as preferred, but the Vietnamese version "often prevails in legal matters, particularly if disputes arise," and court proceedings require Vietnamese translation — [Vietnam News / bizhub](https://bizhub.vn/foreign-language-contract-laws-vary-in-vn-post16918.html); [ASL Law bilingual risk](https://aslgate.com/?p=41359).
- Global majors in APAC: Harvey offices in Singapore, Sydney, Bengaluru; Tokyo planned 2027 — [SecurityBrief Asia](https://securitybrief.asia/story/harvey-opens-sydney-office-to-expand-ai-legal-services-in-asia-pacific). No evidence of Vietnamese-law or VN-EN bilingual capability for any global major.

### Inferences
- The strongest incumbent to displace in Vietnam is the government-linked LEXcentra, not the global majors. Its apparent weaknesses (per available info): unconfirmed bilingual output, no stated FDI cross-border focus, no stated effective-dating/omission detection — matching the entrant's intended differentiators.
- Bilingual VN-EN with the Vietnamese version as controlling + consistency-checking across versions is a concrete, defensible wedge; no global major addresses it.

### Gaps
- Could not load LEXcentra directly; its exact feature set (bilingual? FDI? grounding/accuracy claims?) is unconfirmed. "CLEX" vs "LEXcentra" naming needs resolution.
- No data on pricing, adoption, or accuracy of any Vietnam-specific tool.

## Q5: Regulatory/ethical framing + Vietnam PDPD / AI-law constraints

### Takeaway
Vendors universally position on: "not legal advice / human-in-the-loop," no-training-on-client-data, and per-tenant data isolation — but these are largely marketing assertions to be verified, not standardized. For Vietnam specifically, a product must comply with (a) personal-data law — Decree 13/2023 **now superseded by Decree 356/2025 (effective 1 Jan 2026)** under the new PDP Law, with mandatory transfer-impact-assessment dossiers and broad cross-border rules — and (b) the new standalone **Law on AI No. 134/2025/QH15 (effective 1 Mar 2026)** plus the Digital Technology Industry Law (AI-generated content labeling from 1 Jan 2026).

### Cited Findings

**Vendor ethical/data positioning (patterns, mostly non-authoritative guides):**
- Human-in-the-loop / "not legal advice": framed as a tool to improve quality/efficiency, "not independent legal advice"; "lawyer-in-the-loop" standard = no AI-generated text used without lawyer review — [Context Studios](https://www.contextstudios.ai/ai-for-legal.md); [theformtool LITL](https://theformtool.com/the-lawyer-in-the-loop-litl-the-new-professional-standard-for-ai-in-legal-work/).
- No-training & isolation: a "genuine zero-training policy" states client files are never used to train/fine-tune models; isolation enforced technically by filtering retrieval by client_id — [theneuralbase training-on-client-data](https://theneuralbase.com/ai-for-legal/learn/beginner/training-on-client-data-concerns/); [theneuralbase on-prem/zero-retention](https://theneuralbase.com/ai-for-legal/learn/beginner/on-premises-zero-retention/).
- Data residency as a vendor feature (CoCounsel UK/AU/CA region hosting) — see Q1.

**Vietnam PDP law (Decree 13/2023 → Decree 356/2025):**
- Decree 13/2023/ND-CP: effective 1 July 2023; first comprehensive personal-data decree; GDPR-like controller/processor roles; applies to entities in Vietnam and offshore entities processing Vietnamese personal data; 2-year SME grace period — [Tilleke & Gibbins](https://www.tilleke.com/insights/vietnam-issues-landmark-personal-data-protection-decree/); [Rouse deep dive](https://rouse.com/insights/news/2023/vietnam-a-deep-dive-into-the-personal-data-protection-decree-part-i).
- Cross-border transfer under Decree 13: must prepare a Personal Data Transfer Impact Assessment (TIA) dossier, kept available for Ministry of Public Security inspection; dossier copy to MPS cybersecurity dept (notification within ~60 days after processing); MPS can halt transfers that harm national security or if TIA not completed/updated — [Duane Morris Vietnam](https://blogs.duanemorris.com/vietnam/2023/11/30/new-decree-on-personal-data-protection-and-cross-border-provision-of-data-the-basics-and-guidance-on-practical-handling/); [CMS](https://cms.law/en/int/legal-updates/vietnam-launch-of-personal-data-protection-decree-on-1-july-2023).
- **Superseded:** Decree No. 356/2025/ND-CP (effective 1 Jan 2026) replaces Decree 13/2023 as the implementing regulation for the PDP Law (PDPL); cross-border transfer defined broadly to include direct transfers, offshore storage, **cloud-based processing**, and onward processing of Vietnam-collected data; regulators have explicit authority to suspend/halt transfers for national-security or serious-violation grounds — [China Briefing on Decree 356](https://www.china-briefing.com/china-outbound-news/vietnam-personal-data-protection-regulation-decree-356); [Vietnam Briefing](https://www.vietnam-briefing.com/news/vietnam-personal-data-protection-regulation-decree-356.html).

**Vietnam AI / digital-tech law:**
- Law on AI No. 134/2025/QH15: adopted 10 Dec 2025, effective 1 Mar 2026; covers R&D through provision/deployment/use of AI systems; **regulates by role, not by industry**; excludes national-defense/security/cryptography AI — [Tilleke draft-law analysis](https://www.tilleke.com/insights/ai-regulations-come-into-focus-in-vietnams-draft-law-on-digital-technology-industry/); [vLex overview of Vietnam's first standalone AI Law](https://vlex.com/vid/vietnams-first-standalone-ai-1112515426); [BABL.ai](https://babl.ai/vietnam-enacts-dedicated-digital-technology-law-and-ai-governance/).
- Digital Technology Industry Law No. 71/2025/QH15: first comprehensive framework for digital assets + core AI-governance principles; partly effective 1 July 2025, fully effective 1 Jan 2026; **AI-generated digital products must carry identifiable markings/labels from 1 Jan 2026** — [DFDL](https://www.dfdl.com/insights/legal-and-tax-updates/vietnam-landmark-law-on-digital-technology-industry-new-frameworks-for-ai-digital-assets/); [Vietnamnet (AI content labels)](https://vietnamnet.vn/en/vietnam-mandates-ai-generated-content-labels-starting-in-2026-2424484.html); [Baker McKenzie](https://insightplus.bakermckenzie.com/bm/data-technology/vietnam-digital-technology-law-legal-foundations-and-strategic-incentives-to-accelerate-digital-economic-growth).
- Sources disagree on overlap: the AI Law reportedly repeals/supersedes most AI provisions in the DTI Law — exact scope to be verified against official text — [Tilleke](https://www.tilleke.com/insights/ai-regulations-come-into-focus-in-vietnams-draft-law-on-digital-technology-industry/).

### Inferences — constraints on a Vietnam FDI legal-AI product
- Must likely: (1) complete/maintain a cross-border TIA dossier if any personal data leaves Vietnam (and note that **cloud-based processing itself now counts as a transfer** under Decree 356) — pushing toward in-country hosting or strong data-isolation/zero-retention; (2) label AI-generated output under the DTI Law; (3) comply with the role-based AI Law obligations (as provider/deployer); (4) carry clear "not legal advice"/human-in-the-loop framing consistent with professional-practice norms.
- Data isolation + no-training-on-client-data + in-Vietnam/region hosting are not just ethics marketing here — they map directly to Decree 356 transfer-control compliance, which is a sales advantage locally.

### Gaps
- Exact article-level obligations of the AI Law (No. 134/2025) for a legal-drafting SaaS (risk tier, provider duties) not extracted from primary text — only law-firm summaries.
- Whether "not legal advice" disclaimers interact with Vietnamese unauthorized-practice / legal-services licensing rules — not researched; flagged for follow-up.
- Decree 356 fine/penalty levels and TIA filing mechanics (forms, timelines under the new decree vs the old 60-day rule) not confirmed at article level.

## Q6 (ADDED): Anthropic's "Claude for Legal" open-source suite — license, layer, moats, reusability

### Takeaway
Claude for Legal (GitHub `anthropics/claude-for-legal`, Apache-2.0, "Copyright 2026 Anthropic PBC", README actively encourages forking) is **workflow/playbook orchestration scaffolding, not a grounding/retrieval/effectivity engine**. It closes NONE of the three target moats on its own: citation grounding exists only via *external* research connectors (model-only citations are flagged `[verify]`); effective-date/point-in-time correctness is not addressed (only deadline tracking + a community-skill "freshness gate" warning); missing-clause detection is not a built-in capability (reviews run against a user-configured playbook/profile); bilingual VN-EN is absent (the privacy plugin is GDPR/CCPA-only, "other jurisdictions need configuration"). For a separate FastAPI multi-tenant engine it is highly reusable as a *tier-3 accelerator* — the skills/profiles are markdown+JSON, Apache-2.0, portable as prompt/checklist/output-format scaffolding — but it is architected for the Claude Cowork/Claude Code plugin runtime, not as a drop-in backend, and provides none of the grounding/effectivity layer.

### Cited Findings

**License & forkability (a):**
- Repo `anthropics/claude-for-legal` is "Licensed under the Apache License, Version 2.0," copyright "Copyright 2026 Anthropic PBC," with a `LICENSE` file linked — confirmed on the repo page — [GitHub anthropics/claude-for-legal](https://github.com/anthropics/claude-for-legal). (Secondary coverage agrees: open-source Apache 2.0 — [findskill role guide](https://findskill.ai/blog/claude-legal-plugins-role-guide-2026/); [UseJunior](https://www.usejunior.ai/blog/anthropic-legal-plugin-how-it-works) says the related `knowledge-work-plugins` repo is Apache-2.0.)
- README explicitly encourages forking: "Fork skills for house style," "Edit the steps, the gates, the output format," "Everything is markdown and JSON… Fork, edit, PR" — [GitHub repo](https://github.com/anthropics/claude-for-legal). Apache-2.0 generally permits commercial use and derivative works (with attribution/NOTICE obligations); the repo page does not add commercial-use restrictions beyond the license. Disclaimers: outputs are "drafts for lawyer review," "not legal advice," and "do not represent Anthropic's legal positions."
- Inference: the playbooks/skills CAN be legally forked and adapted into a commercial product under Apache-2.0 (preserve license/NOTICE + attribution). The partner `external_plugins/cocounsel-legal` is Thomson Reuters-maintained and requires the customer's own CoCounsel subscription — not freely reusable.

**Layer of operation (b):**
- Operates at workflow/playbook orchestration. README calls contents "reference agents, skills, and data connectors"; each plugin has a `CLAUDE.md` practice profile + skills + optional agents; a "cold-start interview" / setup interview calibrates it to playbooks, escalation chains, and risk thresholds, producing an editable Markdown practice profile — [GitHub repo](https://github.com/anthropics/claude-for-legal); [LegalOn: Claude for Legal](https://www.legalontech.com/post/claude-for-legal).
- Runs inside Claude Cowork; MCP connectors link to external tools (Ironclad, DocuSign, Definely, Thomson Reuters CoCounsel) — [LegalOn](https://www.legalontech.com/post/claude-for-legal).
- Contents: 11–12 practice-area plugins (commercial, corporate/M&A, employment, privacy, product, regulatory, AI-governance, IP, litigation, legal-clinic/legal-education, law-student) + `legal-builder-hub` ecosystem plugin; named workflow agents (Vendor Agreement Reviewer, NDA Triager, DSAR Responder, Docket Watcher); slash-command skills (`/commercial-legal:review`, `/litigation-legal:claim-chart`); managed-agent cookbooks for headless deployment — [GitHub repo](https://github.com/anthropics/claude-for-legal). (Secondary sources say "12 plugins + 90+ / 80+ agents"; counts vary and conflict with GitHub naming — [findskill fork guide](https://findskill.ai/blog/fork-claude-for-legal-build-custom-vertical-plugin/).)
- `/review-contract` (risk-flagged summary + recommendations) and `/triage-nda` (approve/negotiate/reject, reported GREEN/YELLOW/RED tiers) are the headline commands per marketplace coverage — [pluginsforcowork](https://pluginsforcowork.com/plugins/legal/); note the LegalOn write-up instead names a `commercial-legal:review` skill, so exact command names vary by source.

**Do they close the 3 moats? (c):**
- Citation grounding against in-force law: NOT built in. Citations come from training data and are flagged `[verify]`/marked for verification unless an external research connector (CourtListener, Trellis, Descrybe, Solve Intelligence, or CoCounsel) is attached, in which case citations are "tagged with the source"; with no research tool connected, the reviewer note records sources weren't verified — [GitHub repo](https://github.com/anthropics/claude-for-legal); [LegalOn](https://www.legalontech.com/post/claude-for-legal).
- Effective-date / point-in-time correctness: NOT addressed by core plugins. Only deadline tracking (cancel-by dates, FMLA/CFRA, DSAR timelines) and a community-skill "freshness gate" that warns when bundled regulatory/statutory content passed its verification window; the page "does not say the core plugins check whether a law or rule is currently in effect" — [GitHub repo](https://github.com/anthropics/claude-for-legal). LegalOn confirms effective-date is not covered — [LegalOn](https://www.legalontech.com/post/claude-for-legal).
- Missing-clause detection beyond playbooks: NOT explicit. Reviews run against the configured profile/playbook (or "generic commercial standards" if none); "policy gaps" (Vendor AI Reviewer) and regulatory-to-policy "Gap Tracker" exist, but no systematic absent-contract-clause detection — [GitHub repo](https://github.com/anthropics/claude-for-legal); [LegalOn](https://www.legalontech.com/post/claude-for-legal).
- Bilingual VN-EN: NOT present. Privacy-legal is built for GDPR/CCPA; "other jurisdictions need configuration"; no non-English/Vietnamese support mentioned — [LegalOn](https://www.legalontech.com/post/claude-for-legal); [findskill role guide](https://findskill.ai/blog/claude-legal-plugins-role-guide-2026/).
- LegalOn-stated limitations (vendor, self-promoting): no centralized matter view/status tracking/reporting, no searchable knowledge base of fallback positions, redlines are "plausible" not attorney-vetted; cites *United States v. Heppner* (SDNY, Feb 2026) as a privilege concern — [LegalOn](https://www.legalontech.com/post/claude-for-legal).

**Reusability as a tier-3 workflow accelerator for a separate FastAPI multi-tenant engine (d):**
- High reusability as *content/scaffolding*: skills, agents and practice profiles are "markdown and JSON," Apache-2.0, and forkable — so clause checklists, review step-sequences, escalation tiers (NDA GREEN/YELLOW/RED), and output formats can be lifted into a separate engine's prompt/playbook layer — [GitHub repo](https://github.com/anthropics/claude-for-legal).
- But it is built for the Claude plugin runtime (Cowork/Claude Code slash commands, `CLAUDE.md`, MCP connectors, managed-agent cookbooks), NOT as a FastAPI backend; it supplies no retrieval/grounding/effectivity engine, so it would serve only as the workflow-orchestration tier on top of the entrant's own grounding + effectivity + omission + bilingual engine.
- Inference: Claude for Legal validates/commoditizes the workflow-orchestration tier (and lowers the entrant's build cost there via Apache-2.0 reuse), while leaving all three technical moats (effectivity-aware grounding, omission detection vs in-force law, bilingual VN-EN) open — it is an accelerator, not a competitor, for those moats.

**Claude for Word (adjacent, April 2026 beta):**
- Public beta ~10 April 2026 (a few sources say Apr 13); Word sidebar add-in (Mac + Windows) via Microsoft AppSource; AI edits appear as native tracked changes; legal contract review is the headline use case; available to Claude Team ($25/seat/mo) and Enterprise — [Artificial Lawyer](https://artificiallawyer.com/2026/04/11/anthropic-targets-lawyers-with-claude-for-word/); [TNW](https://thenextweb.com/news/dario-amodei-london-united-kingdom); [gc.ai](https://gc.ai/blog/claude-for-word).
- Limitations: "no automated enforcement of firm positions or detection of missing clauses"; can only access the currently open document; a separate surface from the Cowork Claude for Legal plugins — [Spellbook: Claude for Word](https://spellbook.com/briefs/claude-for-word); [gc.ai](https://gc.ai/blog/claude-for-word).

### Inferences
- Anthropic's move is an open-source scaffolding/orchestration layer that deliberately stops short of grounding, effectivity, and omission detection — exactly the entrant's moats. Forking it under Apache-2.0 is a legitimate way to cut build cost on the workflow tier while differentiating on the technical engine.

### Gaps
- Launch-date and plugin/agent-count figures conflict across secondary sources (Feb 3 vs May 12 2026; "12 plugins/90+ agents" vs GitHub's ~11 named plugins). GitHub repo page confirms Apache-2.0 + contents but the full LICENSE text and exact agent count were not read line-by-line.
- Exact slash-command naming differs by source (`/review-contract` + `/triage-nda` vs `commercial-legal:review`); not reconciled against the live repo tree.
- No independent (non-vendor) benchmark of the plugins' review quality was found.
