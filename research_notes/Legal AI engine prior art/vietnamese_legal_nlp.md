# Vietnamese Legal NLP and Bilingual (Vietnamese-English) Legal Language Processing — Prior Art

_Research current as of 2026-11-05. Every resource is annotated with maturity and LICENSE / commercial-use status where found. The no-scraping constraint on commercial aggregators (thuvienphapluat.vn, luatvietnam.vn) is respected throughout._

## ViLegalLM: corpus, models, license, commercial usability

### Takeaway
ViLegalLM (github.com/ntphuc149/ViLegalLM) is a real, recently published (ACL 2026 Findings) suite of Vietnamese legal models — one PhoBERT-based encoder and two Qwen-based decoder models — continually pretrained on a 16GB legal corpus. Code and the corpus are Apache-2.0, but the authors explicitly scope everything as "research purposes only," so commercial use is legally permitted by the Apache license yet the base-model inheritance (Qwen) and research-only framing are the real pitfalls to vet.

### Cited Findings
- ViLegalLM is "the first suite of Vietnamese pretrained language models for legal text understanding and generation," by Truong-Phuc Nguyen, Quy-Nhan Nguyen, and Minh-Tien Nguyen; accepted to ACL 2026 Findings — [ACL Anthology](https://aclanthology.org/2026.findings-acl.1801/); [GitHub](https://github.com/ntphuc149/ViLegalLM)
- Three models: **ViLegalBERT** (encoder-only, RoBERTa/PhoBERT-style, 135M params, 256-token context, continually pretrained from **PhoBERT-base-v2**; input must be word-segmented with PyVi/underthesea/VNCoreNLP); **ViLegalQwen2.5-1.5B-Base** (decoder-only Qwen2, 1.54B params, 2,048 ctx); **ViLegalQwen3-1.7B-Base** (decoder-only Qwen3, 1.72B params, 4,096 ctx). Both Qwen models are **base/CLM models that require fine-tuning before downstream use** — [GitHub README via fetch](https://github.com/ntphuc149/ViLegalLM); HF: [ViLegalBERT](https://huggingface.co/ntphuc149/ViLegalBERT), [ViLegalQwen2.5-1.5B-Base](https://huggingface.co/ntphuc149/ViLegalQwen2.5-1.5B-Base), [ViLegalQwen3-1.7B-Base](https://huggingface.co/ntphuc149/ViLegalQwen3-1.7B-Base)
- Corpus = **16GB** Vietnamese legal text, "crawled from four publicly available Vietnamese legal repositories" (the four are **not named** in the README, HF card, or ACL abstract). Distributed as .zip of .txt; HF card shows 2.45GB total file (compressed) — [HF dataset ViLegalText](https://huggingface.co/datasets/ntphuc149/ViLegalText)
- **Corpus license: Apache-2.0**, but the HF dataset is **gated** ("publicly accessible, but you have to accept the conditions to access its files" + agree to share HF contact info) — [HF dataset ViLegalText](https://huggingface.co/datasets/ntphuc149/ViLegalText)
- **Repo code license: Apache-2.0** (LICENSE file). Model-weight licenses are not separately stated on the HF/README pages beyond the Apache repo license — [GitHub](https://github.com/ntphuc149/ViLegalLM)
- Explicit use restriction (research-only framing): corpus/models are "intended for research purposes only and should not be used in production legal applications without expert validation"; models "not intended to replace professional legal counsel" — [GitHub README / HF cards](https://github.com/ntphuc149/ViLegalLM)
- Three accompanying synthetic fine-tuning datasets (LLM-generated + hard-negative mining): **ViLegalTF** (True/False QA, 13,032 train / 388 val), **ViLegalMCQ** (multiple-choice, 14,920 / 300), **ViLegalNLI** (NLI, 7,660 / 150) — [HF ViLegalTF](https://huggingface.co/datasets/ntphuc149/ViLegalTF), [ViLegalMCQ](https://huggingface.co/datasets/ntphuc149/ViLegalMCQ), [ViLegalNLI](https://huggingface.co/datasets/ntphuc149/ViLegalNLI)
- Performance claim: "state-of-the-art results among open-source models" across "four main Vietnamese legal downstream tasks spanning ten benchmarks"; a key claim is that continual pretraining from base models beats instruction-tuned adaptation. Benchmark names and numeric scores are NOT in the abstract/README (would need full PDF) — [ACL Anthology](https://aclanthology.org/2026.findings-acl.1801/)
- Also published: **ViLegalQwen3-1.7B-Base** is mirrored on inference platforms (e.g., Friendli) — [friendli.ai](https://friendli.ai/models/ntphuc149/ViLegalQwen3-1.7B-Base)

### Inferences
- Commercial usability: Apache-2.0 on code + corpus is itself commercial-friendly. The real constraints are (1) the Qwen2.5/Qwen3 base weights carry their own licenses (Qwen2.5 ≤ certain sizes are Apache-2.0; verify the exact checkpoint), (2) the corpus was crawled from third-party repositories whose underlying content may carry its own rights regardless of the Apache label the authors applied, and (3) the gated access + "research only" language signals the authors have not warranted commercial fitness.
- The encoder (ViLegalBERT, PhoBERT-base-v2 lineage) is the most directly production-reusable artifact for retrieval/classification; the Qwen "Base" models need instruction/SFT work before use.

### Gaps
- The four source repositories are not named anywhere found; cannot confirm whether any is a commercial aggregator (a licensing risk if so).
- The 10 benchmark names and numeric SOTA scores are not on the pages fetched (only in full PDF).

## ALQAC and VLQA: tasks, datasets, years, license

### Takeaway
ALQAC is the established annual Vietnamese legal QA competition (2021–2025, co-located with KSE), releasing statute-based retrieval + QA datasets but with no stated open license (data obtained via registration, outputs published to public GitHub). VLQA is a distinct, newer (2025) academic dataset — the first large, expert-annotated Vietnamese legal QA dataset (3,129 triplets) — paper under CC BY-NC-SA 4.0 (non-commercial), and it became the basis of the VLSP 2025 DRILL shared task.

### Cited Findings — ALQAC
- ALQAC = Automated Legal Question Answering Competition, annual associated event of the KSE conference; editions 2021–2025 found — [JAIST Nguyen-lab ALQAC-2021](https://www.jaist.ac.jp/is/labs/nguyen-lab/home/alqac-2021/); [ALQAC 2024](https://sites.google.com/view/alqac-2024); [ALQAC 2025](https://sites.google.com/view/alqac-2025)
- 2021 (1st): three tasks — legal document retrieval, legal textual entailment, legal QA; data prepared in Vietnamese + Thai but all participants used Vietnamese — [JAIST](https://www.jaist.ac.jp/is/labs/nguyen-lab/home/alqac-2021/)
- 2022: two tasks — retrieval and factoid QA (answer = exact text span) — [KSE2022 CfC](https://kse2022.tbd.edu.vn/?p=726)
- 2023: eval.ai leaderboard; retrieval + answer-extraction — [ALQAC2023](https://sites.google.com/view/ALQAC2023)
- 2024 (4th): two tasks — legal document retrieval + legal QA; international teams invited (multilingual methods); retrieval metric **F2** (recall-weighted) — [ALQAC 2024](https://sites.google.com/view/alqac-2024)
- 2025: held 6–8 Nov 2025 in Dalat (KSE 2025). Task 1 Legal Document Retrieval (macro-avg **F2**); Task 2 Legal QA with three answer types — True/False (Đúng/Sai), multiple-choice (A–D), free-text (human-expert judged, accuracy). Dataset = new, manually annotated, based on well-known Vietnamese statute laws; train/test in JSON (fields: question_id, question_type, text, choices, relevant_articles{law_id, article_id}, answer) — [ALQAC 2025](https://sites.google.com/view/alqac-2025)
- ALQAC 2025 rules: **permitted** public research resources incl. online legal databases (explicitly names **vbpl.vn**) and open-weight LLMs < 10B params (e.g., LLaMA-3); **prohibited** closed/proprietary models (ChatGPT, GPT-4, Claude, Gemini) and externally annotated legal QA/entailment datasets — [ALQAC 2025](https://sites.google.com/view/alqac-2025)
- ALQAC license/terms: **no explicit dataset license stated**; data via registration; participant outputs published to a public GitHub repo. Credited to "NguyenLab" — [ALQAC 2025](https://sites.google.com/view/alqac-2025)
- Related ALQAC 2023 research (data enrichment for low-resource legal QA) — "NeCo@ALQAC 2023" — [aitopics](https://aitopics.org/doc/arxivorg:04CF01E2)

### Cited Findings — VLQA
- **VLQA = "The First Comprehensive, Large, and High-Quality Vietnamese Dataset for Legal Question Answering"** (arXiv 2507.19995, 2025) — [arXiv HTML](https://arxiv.org/html/2507.19995v1); [abstract](https://arxiv.org/abs/2507.19995)
- Size: **3,129 expert-annotated {question, relevant articles, answer} triplets**, linked to a corpus of **59,636 legal articles from 2,162 documents across 27 domains**; splits 7:1:2 (train/val/test) — [arXiv HTML](https://arxiv.org/html/2507.19995v1)
- Built from ~430,000 raw questions scraped from Vietnamese legal-advice websites (user-generated forum questions); regex-extracted article citations; cleaned; validated by 5 senior law students (double-annotated) + reviewed by a legal expert — [arXiv HTML](https://arxiv.org/html/2507.19995v1)
- Authors: Tan-Minh Nguyen (JAIST); Hoang-Trung Nguyen, Xuan-Hieu Phan, Thi-Hai-Yen Vuong (VNU University of Engineering and Technology, Hanoi); Trong-Khoi Dao (VNU University of Law, Hanoi); Ha-Thanh Nguyen (National Institute of Informatics, Tokyo) — [arXiv HTML](https://arxiv.org/html/2507.19995v1)
- License: **paper listed under CC BY-NC-SA 4.0** (non-commercial, share-alike); no separate dataset license stated. Availability: "dataset and source code will be publicly released soon" — no HF/GitHub link yet, DOI is placeholder — [arXiv HTML](https://arxiv.org/html/2507.19995v1)
- Distinguishes itself from ALQAC (ALQAC 2023 cited as ~100 jurist-curated bar-style pairs) by scale + real-citizen questions — [arXiv HTML](https://arxiv.org/html/2507.19995v1)
- Baselines evaluated: retrieval (BM25, fastText, SBERT, BGE-m3 zero-shot; fine-tuned mBERT, BGE-reranker); extractive QA (LEGAL-BERT, ViDeBERTa, mBERT, XLM-RoBERTa, PhoBERT); generative (ViT5, BARTpho); LLMs (Llama3-8B/3.1-8B, Qwen2.5-7B/14B, DeepSeek-V3, GPT-4o, GPT-4o-mini) — [arXiv HTML](https://arxiv.org/html/2507.19995v1)

### Inferences
- VLQA under CC BY-NC-SA 4.0 is **not commercially usable** as-is (non-commercial + share-alike). For a commercial product, VLQA is academic-benchmark-only.
- ALQAC data's lack of an explicit license + registration-gated access makes it academic/competition-only in practice; do not assume commercial redistribution rights.

### Gaps
- No public download link confirmed for VLQA yet ("released soon").
- ALQAC exact corpus sizes per year and formal license text not located.

## Other Vietnamese legal corpora, models, and competitions

### Takeaway
Beyond ViLegalLM/ALQAC/VLQA, the ecosystem includes the Zalo 2021 legal retrieval challenge (foundational but download status unconfirmed), the VLSP 2025 DRILL shared task (retrieval over VLQA), several HuggingFace PhoBERT/ViT5/SBERT legal encoders of mixed maturity, and research retrieval datasets (TVPL — note: derived from thuvienphapluat.vn). Most are academic-grade; license quality is uneven.

### Cited Findings
- **Zalo AI Challenge 2021 — Legal Text Retrieval** ("Legal Zalo 21"): used as a fine-tuning/eval source in later work; the challenge's own corpus-size/annotation description and current download status were NOT confirmed in search — [arXiv 2412.00657 "Improving Vietnamese Legal Document Retrieval using Synthetic Data"](https://arxiv.org/pdf/2412.00657)
- **TVPL dataset** (introduced in arXiv 2412.00657): Vietnamese legal text retrieval benchmark; ~10,000 test queries; **named after and sourced from thuvienphapluat.vn** (a commercial aggregator — licensing/scraping caveat) — [arXiv 2412.00657](https://arxiv.org/pdf/2412.00657)
- **VLSP 2025 DRILL Shared Task** ("Deep Retrieval in the Expansive Legal Landscape"): Vietnamese legal IR task, built on VLQA; retrieve statutory articles answering a query. Test: 312 public / 627 private questions. Best (EDM Team): F2 0.7261, P 0.6773, R 0.7394 (private). Overview by Vuong et al., VLSP 2025 proceedings pp.113–119 — [ACL VLSP 2025](https://aclanthology.org/2025.vlsp-1/); [DRILL overview](https://preview.aclanthology.org/setup/2025.vlsp-1.16); [bib](https://aclanthology.org/2025.vlsp-1.16.bib)
- DRILL noted systems struggle with commonsense, very long context, temporal relations — [DRILL overview](https://preview.aclanthology.org/setup/2025.vlsp-1.16)
- **VLSP** = Workshop on Vietnamese Language and Speech Processing; 11th edition = VLSP 2025 (proceedings Oct 2025) — [ACL VLSP 2025 event](https://aclanthology.org/events/vlsp-2025)
- HuggingFace legal encoders (maturity varies):
  - **NghiemAbe/Vi-Legal-PhoBert** — fill-mask RoBERTa-style, **Apache-2.0**, tied to a legal corpus, updated Apr 2024, thin card — [HF](https://huggingface.co/NghiemAbe/Vi-Legal-PhoBert)
  - **hmthanh/VietnamLegalText-SBERT** — ~135M params, max len 256, "20GB" pretraining text; loads with AutoModel (may be plain encoder despite SBERT name) — [HF](https://huggingface.co/hmthanh/VietnamLegalText-SBERT)
  - **KingLTD/pretrain_Law_model_vit5_version1** — fine-tune of VietAI/vit5-base, unnamed dataset, ROUGE reported, no data/use docs — [HF](https://huggingface.co/KingLTD/pretrain_Law_model_vit5_version1)
  - **hduc-le/vit5-large-legal-lora** — LoRA fine-tune of VietAI/vit5-large; card mostly placeholders, dataset "None" — [HF](https://huggingface.co/hduc-le/vit5-large-legal-lora/raw/main/README.md)
- Research: "Multi-stage Information Retrieval for Vietnamese Legal Texts" fine-tunes PhoBERT on legal corpus, compares word- vs syllable-level — [arXiv 2209.14494](https://arxiv.org/pdf/2209.14494)
- Research: "Vietnamese Legal Information Retrieval in Question-Answering System" — [arXiv 2409.13699](https://arxiv.org/pdf/2409.13699)
- General Vietnamese base models frequently used as legal backbones: **PhoBERT** (VinAI), **ViT5**/**BARTpho** (VietAI/VinAI), **ViDeBERTa** — referenced as VLQA baselines — [VLQA arXiv](https://arxiv.org/html/2507.19995v1)

### Inferences
- Production-usable encoders: ViLegalBERT (Apache-2.0) and NghiemAbe/Vi-Legal-PhoBert (Apache-2.0) are the cleanest licenses; the ViT5 legal fine-tunes inherit VietAI/vit5 licenses and have poor documentation (higher risk).
- Any dataset derived from thuvienphapluat.vn (TVPL) or luatvietnam.vn carries the no-scrape/commercial-aggregator licensing risk and should not be redistributed in a commercial product.

### Gaps
- Zalo 2021 legal retrieval dataset's exact size, license, and current availability unconfirmed.
- Several HF model cards lack training-data provenance and license clarity.

## Bilingual (Vietnamese-English) legal resources and concept alignment

### Takeaway
There is no single authoritative, openly licensed Vietnamese-English legal parallel corpus or concept-equivalence database. The practical building blocks are: general EN-VI MT corpora with a law subset (MTet, PhoMT), official English translations of Vietnamese law (Official Gazette English via Vietnam News Agency; commercial portals), and bilingual legal dictionaries/glossaries (Lê Đình Hồ dictionary, court-interpreter glossaries). Legal concept equivalence across the two legal systems is a known hard problem flagged in the terminology literature.

### Cited Findings — parallel corpora / MT
- **MTet** — multi-domain EN-VI corpus, ~4.2M sentence pairs (later version 6.2M), deliberately covers under-served fields **including law**, with human-checked test set; paired with EnViT5 — [arXiv 2210.05610](https://arxiv.org/pdf/2210.05610)
- **PhoMT** (VinAI) — 3.02M-pair EN-VI benchmark; best results with fine-tuned mBART — [Papers With Code](https://www.paperswithcode.com/paper/phomt-a-high-quality-and-large-scale)
- Legal-domain MT augmentation (back-translation, table pruning) evaluated on **IWSLT2015 legal domain**; reports BLEU gains of up to ~16.37 (and a separate +13.65) over baseline — [DOAJ/IEEE Access 2023](https://doaj.org/article/8adc80bff6d840a8b68ee527ee250616)
- ISLRN-registered 500,000-pair EN-VI corpus exists but sources are general (books/news/dictionaries), **not legal** — [islrn.org](https://www.islrn.org/resources/838-483-738-912-8)
- **No dedicated, publicly released Vietnamese-English legal parallel corpus found**; MTet's law subset or IWSLT2015 legal eval are the closest starting points — [arXiv 2210.05610](https://arxiv.org/pdf/2210.05610)

### Cited Findings — official English translations of Vietnamese law
- **Official Gazette (English)** of Vietnam: the Vietnam Law and Legal Forum / Vietnam Law Magazine, under the **Vietnam News Agency (VNA)**, is Prime-Minister-appointed to translate and issue the English Official Gazette — [Vietnam Law Magazine](https://vietnamlawmagazine.vn/official-gazette-issues-nos-130-132-2019-published-on-april-06-2020-27122.html)
- **LuatVietnam (english.luatvietnam.vn)** hosts Official Gazette translations; described as the online platform providing official English translations of the VNA Official Gazette — **commercial/subscription aggregator** (do not scrape) — [english.luatvietnam.vn intro](https://english.luatvietnam.vn/introducrtion/introduction-540-12129-article.html)
- **Allens** (law firm): ~10 Vietnamese laws translated to English; subscription collection with a free selection — [allens.com.au](https://allens.com.au/sectors-services/services/asia/vietnam/documents)
- Caveat (law-library guidance): available English translations "may not be official, or reflect the most current versions" — [Loyola LawLibGuides Vietnam](https://lawlibguides.luc.edu/foreignlegalresearch/vietnam/web_resources); [IALS Vietnamese Legal Translations](https://resources.ials.sas.ac.uk/eagle-i/vietnamese-legal-translations)

### Cited Findings — bilingual legal dictionaries / concept equivalence
- **English-Vietnamese, Vietnamese-English Dictionary of Law** (Từ điển luật pháp Anh-Việt, Việt-Anh) by **Lê Đình Hồ** — bidirectional, indexed (print; date not shown) — [SFPL catalog](https://link.sfpl.org/resource/YzDjX5XlALg)
- **Court-interpreter EN-VI legal glossary** (MassLegalServices JLW glossary) — working document; warns many legal terms have alternate meanings requiring careful choice of the correct Vietnamese equivalent — [PDF](https://www.masslegalservices.org/system/files/library/JLW__Vietnamese_glossary.pdf)
- Vancouver CC multilingual legal glossary — ~5,000 Canadian legal/court terms, plain English, Vietnamese among 6 target languages — (referenced in search results)
- Practitioner guidance: use the term established in Vietnamese regulatory/institutional usage, not a literal translation from English — [1stopasia](https://www.1stopasia.com/blog/wp-json/wp/v2/posts/13905)
- Equivalence theory: legal-terminology equivalence is "a very problematic issue because of the differences in law in each country"; typologies classify full / partial / non-equivalence — [Czech 2023 study, muni.cz](https://www.muni.cz/en/research/publications/2305937)
- Vietnamese academic work exists on criminal-science terminology and its English translation equivalents (VNU USSH theses) — [USSH TTLA](https://ussh.vnu.edu.vn/eng/dao-tao/luan-an/ttla-thuat-ngu-khoa-hoc-hinh-su-tieng-viet-va-tuong-duong-dich-thuat-cua-chung-trong-tieng-anh-14873.html)

### Inferences
- Cross-lingual legal concept alignment for a product will require building a custom term base (dictionary + Official Gazette parallel texts + MTet law subset), because no ready-made open resource maps VN↔EN legal concepts at scale. The civil-law (Vietnam) vs common-law (English-source) divergence means many concepts are partial/non-equivalents, not 1:1.
- Official-translation sources (VNA Official Gazette) are the authoritative seed for a parallel legal corpus, but they are distributed through commercial portals (luatvietnam) — rights must be cleared, not scraped.

### Gaps
- No openly licensed VN-EN legal parallel corpus located; MTet's exact law-subset size and license (the corpus is research-oriented) not itemized here.
- Licensing terms of the Lê Đình Hồ dictionary and glossaries for programmatic/commercial reuse unknown.

## Official / legitimately reusable Vietnamese legal text sources

### Takeaway
The authoritative government source is vbpl.vn (Cơ sở dữ liệu quốc gia về văn bản pháp luật, run by the Ministry of Justice), governed by Decree 52/2015/ND-CP; it was relaunched (upgraded, AI-powered) in April 2026. Its explicit reuse/terms page was not located in this research, so terms must be confirmed directly. Commercial aggregators (thuvienphapluat.vn, luatvietnam.vn, lawnet.vn) explicitly prohibit reuse of their data to build competing/commercial systems — do not scrape them.

### Cited Findings
- **vbpl.vn = National Database on Legal Documents (Cơ sở dữ liệu quốc gia về văn bản pháp luật)**, Ministry of Justice; upgraded/AI-powered version launched ~23 April 2026 to improve access, integration, automated processing — [VietnamPlus](https://en.vietnamplus.vn/vietnam-launches-upgraded-national-database-on-legal-documents-post341644.vnp); [VOV](https://english.vov.vn/en/politics/domestic/ai-powered-legal-database-launched-to-enhance-access-and-transparency-post1286158.vov); [SGGP](https://en.sggp.org.vn/upgraded-national-legal-database-officially-launched-post125694.html)
- Legal framework for the national database's development/management/use = **Decree 52/2015/ND-CP** — (cited in search results; best starting point for official reuse rules)
- ALQAC 2025 organizers explicitly treat **vbpl.vn as a permitted public legal database** for competition use — [ALQAC 2025](https://sites.google.com/view/alqac-2025)
- **LawNet.vn terms**: prohibit using its data to build a separate data system for commercial purposes and prohibit replicating its data for reuse in any form — [lawnet.vn ToS](https://lawnet.vn/en/thoa-uoc-dich-vu.html)
- **LuatVietnam terms**: restrict use of its (translated) documents to stated conditions on its own site — [english.luatvietnam.vn T&C](https://english.luatvietnam.vn/term-conditions/terms-conditions-of-using-luatvietnams-legal-documents-in-english-541-12130-article.html)
- Official Gazette (Công báo) English issues are produced by VNA/Vietnam Law Magazine — [Vietnam Law Magazine](https://vietnamlawmagazine.vn/official-gazette-issues-nos-130-132-2019-published-on-april-06-2020-27122.html)

### Inferences
- vbpl.vn and the Vietnamese-language Công báo (congbao.chinhphu.vn) are the legitimate primary sources for raw statutory text; legal documents (văn bản quy phạm pháp luật) as official state works generally are not subject to copyright in the way private content is, but vbpl.vn's own site terms and Decree 52/2015/ND-CP should be read before bulk ingestion.
- Commercial aggregators' value-add (consolidated/amended text, English translations, metadata) is explicitly protected — avoid entirely for commercial ingestion.

### Gaps
- vbpl.vn's own terms-of-use / API / bulk-access policy page was not located; needs direct confirmation (site footer "điều khoản sử dụng" or MOJ contact).
- Whether vbpl.vn offers an official API or bulk download (vs. only web access) is unconfirmed.

## Production-usable vs. academic-only — summary and licensing pitfalls

### Takeaway
Cleanly commercial-usable artifacts are scarce: ViLegalBERT and a couple of PhoBERT legal encoders carry Apache-2.0, but with research-only framing and unverified corpus provenance. VLQA (CC BY-NC-SA, non-commercial), ALQAC (no license, registration-gated), and any thuvienphapluat/luatvietnam-derived data are academic/competition-only for commercial purposes.

### Cited Findings
- Apache-2.0 (most permissive found): ViLegalLM code + ViLegalText corpus + ViLegalBERT; NghiemAbe/Vi-Legal-PhoBert — but ViLegalLM is "research purposes only / not for production without expert validation" — [GitHub](https://github.com/ntphuc149/ViLegalLM); [HF dataset](https://huggingface.co/datasets/ntphuc149/ViLegalText); [HF Vi-Legal-PhoBert](https://huggingface.co/NghiemAbe/Vi-Legal-PhoBert)
- Non-commercial: VLQA paper under CC BY-NC-SA 4.0 — [VLQA arXiv](https://arxiv.org/html/2507.19995v1)
- No stated license / registration-gated: ALQAC datasets (2021–2025) — [ALQAC 2025](https://sites.google.com/view/alqac-2025)
- Prohibited for reuse: LawNet.vn data, LuatVietnam translations (per their ToS); TVPL dataset derives from thuvienphapluat.vn — [lawnet ToS](https://lawnet.vn/en/thoa-uoc-dich-vu.html); [luatvietnam T&C](https://english.luatvietnam.vn/term-conditions/terms-conditions-of-using-luatvietnams-legal-documents-in-english-541-12130-article.html); [TVPL/arXiv 2412.00657](https://arxiv.org/pdf/2412.00657)

### Inferences / Pitfalls for commercial use
- Base-model inheritance: ViLegalBERT inherits PhoBERT (VinAI, typically MIT); ViLegalQwen inherits Qwen2.5/Qwen3 (per-size licenses — some Apache-2.0, some Qwen-specific). Verify the exact base checkpoint license before shipping.
- Corpus provenance: a dataset labeled Apache-2.0 by re-publishers does not cure upstream rights in crawled content (the "four repositories" are unnamed; TVPL is from a commercial aggregator). This is the single biggest commercial pitfall.
- CC BY-NC-SA (VLQA) blocks commercial use and forces share-alike — usable only for internal benchmarking, not as product data.
- Prefer building on vbpl.vn / Công báo primary statutory text (subject to confirming Decree 52/2015 + site terms) rather than aggregator-derived datasets.

### Gaps
- Exact base-checkpoint licenses for ViLegalQwen2.5/Qwen3 not individually verified here.
- No confirmed commercial-license path for any ready-made Vietnamese legal dataset found; all roads for commercial data lead back to primary government sources.
