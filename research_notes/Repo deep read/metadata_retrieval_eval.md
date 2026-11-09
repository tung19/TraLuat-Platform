# Metadata & Data-Type Schemas for Retrieval + Eval/Training — Reference Repos vs TraLuat

Scope: the concrete field/type schemas that reference repos attach to documents / chunks / nodes for (a) RETRIEVAL (filtering + ranking) and (b) EVALUATION / TRAINING (gold sets, ground truth, labels, weights). All paths are under `refs/`. Read-only extraction; nothing was built or executed.

Purpose: feed a gap analysis for TraLuat (Vietnam legal-AI engine), whose differentiators are temporal/effectivity (hiệu lực) and jurisdiction/tenant scoping — dimensions that, as noted at the end, almost none of these repos carry.

---

## 1. legalbenchrag — EVAL ground-truth schema (span-level retrieval gold)

File: `refs/legalbenchrag/legalbenchrag/benchmark_types.py`

### Chunk / snippet metadata (the retrieval unit of truth)
- `Snippet` (lines 24–32): `file_path: str`; `span: tuple[int, int]` (character offsets, half-open). Computed `answer` property reads `./data/corpus/{file_path}[span[0]:span[1]]` — i.e. the gold text is addressed purely by (file, char-span), no structural IDs.
- `validate_snippet_list` (35–49): enforces spans within one `file_path` are **disjoint** (no overlap).
- `RetrievedSnippet(Snippet)` (75–77): adds `score: float` — the only ranking field; set by the method, not gold.

### Test / ground-truth record
- `QAGroundTruth` (52–60): `query: str`; `snippets: list[Snippet]` (gold spans); `tags: list[str] = []`. Post-validator re-checks span disjointness.
- `Benchmark` (63–64): `tests: list[QAGroundTruth]`.
- `Document` (70–73): `file_path: str`, `content: str` — the corpus entry. No other metadata (no date, jurisdiction, doctype).

### What the `tags` values actually are
- `refs/legalbenchrag/legalbenchrag/benchmark.py:62`: `test.tags = [benchmark_name]` — tags are set to the **source benchmark/corpus name**, drawn from `benchmark_name_to_weight` at `benchmark.py:13–18`: `"privacy_qa"`, `"contractnli"`, `"maud"`, `"cuad"` (each weight 0.25).
- `refs/legalbenchrag/legalbenchrag/run_benchmark.py:73`: `tag_filter is None or tag_filter in qa_result.qa_gt.tags` — tags are a **retrieval/eval filter dimension** (evaluate only tests from one corpus). This is the single filterable metadata field in the whole eval model, and it keys on dataset provenance — not legal attributes.

### Ranking / retrieval features (method side)
File: `refs/legalbenchrag/legalbenchrag/methods/baseline.py`
- `RetrievalStrategy` (39–45): `chunking_strategy` (`ChunkingStrategy{strategy_name: Literal["naive","rcts"], chunk_size:int}`, 34–36), `embedding_model`, `embedding_topk:int`, `rerank_model | None`, `rerank_topk:int`, `token_limit:int|None`.
- `EmbeddingInfo` (48–51): `document_id: str`, `span: tuple[int,int]` — the stored index payload. No metadata columns; the sqlite `vec0` virtual table (`baseline.py:169–171`) stores **only** `rowid` + `embedding float[N]`. Retrieval is pure vector distance (`ORDER BY distance ASC LIMIT embedding_topk`, 202–213), optional rerank (218–230), then `score = 1.0/(i+1)` as the emitted rank score (245). **No metadata filtering at query time at all.**

Takeaway: legalbenchrag's gold model = `(query, [disjoint char-spans in named files], corpus-tag)`. Ranking is score-only; the sole filter field is dataset provenance.

---

## 2. LeSICiN — TRAINING + EVAL schema (statute-linking over a heterogeneous graph)

README: `refs/LeSICiN/README.md`; code: `data_helper.py`, `helper.py`, `model/model.py`, `run.py`.

### Node / instance records (the .jsonl data model) — README lines 35–40
Each line is one instance (a Fact or a Section):
- `id [string]` — id/name of the fact or section instance (also the node id in the graph).
- `text [list[string]]` — list of sentences.
- `labels [list[string]] | null` — **gold-standard labels = list of Section ids** that the fact cites (null for inference). This is the positive-link gold.

Loaded by `LSIDataset` (`data_helper.py:10–36`): sets `self.annotated = True` iff `labels` present; `labels` stored as `np.array`.

### Node types & label hierarchy (graph schema) — README lines 41–48
- Node types via a **`type_map`** dict: node id → one of `Act / Chapter / Topic / Section / Fact`.
- **`label_tree`** edges: the statute hierarchy, stored as triples `(src node id, relationship name, trg node id)` — Act⊃Chapter⊃Topic⊃Section.
- **`citation_network`** edges: Fact→Section citation links, same triple format.
- **`schemas`**: metapath schemas per node type; each schema is a list of edges, each edge a tuple `(src node type, relationship name, trg node type)`.

### Graph construction & vocabularies — `helper.py`
- `generate_vocabs` (9–25): builds word `vocab` and **`label_vocab`** = `{section_id: index}` over the Section dataset (labels are the Section nodes).
- `generate_graph` (28–64): builds `node_vocab` (per-type id→index dicts), `edge_vocab` (relationship name→index), `edge_indices` keyed by `(src_type, rel, trg_type)`, and `adjacency` = `torch_sparse.SparseTensor` per edge-type key. This is the concrete metapath/edge schema used at train time.
- Metapath sampling: `data_helper.py:149–173` (`generate_metapaths`) samples neighbours per schema; `MiniBatch` (80–146) builds label indicator tensor `self.labels [D, C]` by scattering `label_vocab[l]` to 1 (136–137) — i.e. multi-hot gold over the Section label space.

### Gold positive link, negatives, and weights
- **Positive link** = a `(Fact id, Section id)` pair present in `labels` / the citation_network → `labels[D,C]` entry = 1.
- **Negatives** = implicit: all other Section columns in the multi-hot vector are 0 (no explicit negative sampling table).
- **`pos_weight` / label weights** — `helper.py:67–73` `generate_label_weights`: counts positives per label, then
  - `"tws"` (Threshold Weighting Scheme): `clamp(pos.max()/pos, max=thresh)`;
  - `"vws"` (Vanilla): `len(train_data)/pos`.
  These become `pos_weight` in `torch.nn.BCEWithLogitsLoss(pos_weight=label_weights)` at `model/model.py:16`. Chosen via `hyperparams.json` `weight_scheme` + `tws_thresh` (README 92–93); passed `run.py:92,187`.
- **Loss / score weighting** — `model/model.py`: `thetas=(attr, struct, align)` weight the three BCE losses (`calculate_losses`, 23–28); `lambdas=(attr, align)` weight the two matching scores (`scores = lambdas[0]*attr_scores + lambdas[-1]*align_scores`, line 80). `pthresh` (default 0.65) is the prediction threshold.

### Eval metrics — README 122–134 + `helper.py:106–176` `MultiLabelMetrics`
Per-label TP/FP/FN counters → macro P/R/F1, micro P/R/F1, and Jaccard. Inference output jsonl = `{id, predictions: list[section_id]}` (README 136–140).

Takeaway: LeSICiN is the richest training/eval schema here — typed nodes, a label hierarchy tree, an explicit citation (gold-link) network, metapath schemas, multi-label gold, and per-label positive weighting. It is the closest structural analogue to a Vietnamese statute-linking trainer, but carries **no temporal/effectivity and no jurisdiction fields** — statutes are static IPC nodes.

---

## 3. eyecite — citation METADATA extracted per citation (retrieval/linking metadata)

File: `refs/eyecite/eyecite/models.py`

### Base fields — `CitationBase` (82–98)
`token`, `index`, `span_start/span_end`, `full_span_start/full_span_end`, `groups: dict`, `metadata: Any`, `document`. Span accessors: `span()` (197–206), `span_with_pincite()` (208–238), `full_span()` (240–258).

### `groups` dict (regex-extracted identity keys) — documented at 131–148 & 458–464
- Case cites: `volume`, `reporter`, `page` (+ sometimes `reporter_nominative`, `volumes_nominative`).
- Law cites: `chapter`, `reporter`, `law_section`, `issue`, `page`, `docket_number`, `pamphlet`, `title`.
- Journal cites: `volume`, `reporter`, `page`.
These are the normalized identity fields used for equality/hash (dedup + resolution).

### `Metadata` dataclasses (nested, per citation type)
- `CitationBase.Metadata` (164–171): `parenthetical`, `pin_cite`, `pin_cite_span_start`, `pin_cite_span_end`.
- `ResourceCitation.Metadata` (304–310): + `year`, `month`, `day`; plus class fields `year: int|None` (273), `exact_editions`/`variation_editions`/`all_editions: Sequence[Edition]`, `edition_guess: Edition|None` (266–270).
- `FullLawCitation.Metadata` (388–394): + `publisher`, `day`, `month`.
- `CaseCitation.Metadata` (484–490): + `court` (guessable from reporter, `guess_court` 492–497 → `"scotus"`).
- `FullCaseCitation.Metadata` (530–540): + `plaintiff`, `defendant`, `extra`, `antecedent_guess`, `resolved_case_name_short`, `resolved_case_name`.
- `ShortCaseCitation.Metadata` (602–606): + `antecedent_guess`.
- `SupraCitation.Metadata` (634–639): `antecedent_guess`, `volume`.
- `ReferenceCitation.Metadata` (695–709): `plaintiff`, `defendant`, `resolved_case_name_short`, `resolved_case_name`.

### Supporting types
- `Reporter` (22–37): `short_name`, `name`, `cite_type`, `source` ∈ {reporters, laws, journals}, `is_scotus`.
- `Edition` (40–59): `reporter`, `short_name`, `start: datetime|None`, `end: datetime|None` + `includes_year(year)` — **the only temporal reasoning in any of these repos**: it date-ranges a reporter edition to disambiguate (`guess_edition`, 363–375). Note: this is metadata about the *citation source edition*, not document effectivity.
- Citation type hierarchy (the `type` dimension): `FullCaseCitation`, `ShortCaseCitation`, `SupraCitation`, `IdCitation`, `ReferenceCitation`, `FullLawCitation`, `FullJournalCitation`, `UnknownCitation`.
- `Resource` (873–898): a resolved target = `{citation: FullCitation}`, hashed by semantic equivalence (missing page ⇒ never equal, for safety).

Takeaway: eyecite is the citation-identity metadata model — volume/reporter/page + court + year + case names + pin-cite spans + citation `type`. This is linking/retrieval metadata for citations. It carries year/edition dates but NO jurisdiction scoping beyond `court` (US-centric) and no tenant metadata.

---

## 4. PAKTON — index-time Document/chunk metadata

Files: `refs/PAKTON/PAKTON Framework/Archivist/src/Archivist/indexers/*.py`, `parser/structuralParser.py`, `parser/naiveParser.py`.

### What's passed to the vector store
- `indexers/base.py:28` `index(docs: List[Document])` — LangChain `Document` objects (page_content + `.metadata` dict).
- `indexers/vectordb.py` (Pinecone or Chroma): `index()` (110–134) upserts docs **as-is** via `PineconeVectorStore.from_documents` / `Chroma.add_documents`. The vector store carries whatever is in each `Document.metadata`; there is **no explicit filterable metadata schema, no `filter=` at query time, and no metadata-field whitelist** defined in the indexer. Only collection-level `collection_metadata` (89,100) is set, not per-doc filter fields.

### Where per-chunk metadata is actually populated
- `parser/naiveParser.py:63,68,74`: `Document(page_content=..., metadata={"source": file_path})` — naive path attaches only `source`.
- `parser/structuralParser.py` `_assign_metadata_to_sections` (225–259): copies, **when present**, keys `['source','filename','last_modified','filetype','page_number']` from the loader (252) into `SectionWithMetadata.metadata` (48–55).
- `build_tree` (261–334) then adds structural keys per section (326–329): `in_document_index`, `in_document_parent_index`, `document_summary`, `document_id` (a `uuid4`, 308). Tree nodes also carry parent/child/sibling/ancestor structure (`TreeNode`, 62–136).

Takeaway: PAKTON's chunk metadata = provenance (`source`, `filename`, `filetype`, `last_modified`, `page_number`) + structural position (`in_document_index`, `in_document_parent_index`, `document_id`, `document_summary`). It is NOT used as a retrieval filter (no query-time filtering wired up), and carries NO legal-domain, temporal, or jurisdiction/tenant fields.

---

## 5. Indigo — FRBR / Akoma Ntoso identity & effectivity metadata (richest retrieval/identity model)

Files: `refs/indigo/indigo_api/models/works.py`, `indigo_api/models/documents.py`.

### `Work` (abstract act) — `works.py:470–581`
Identity: `frbr_uri` (unique, 503), `title` (507), `country` FK (508), `locality` FK (510), `doctype` (513), `subtype` (514), `actor` (515), `date` (FRBR date, 516), `number` (517).
Publication: `publication_name` (520), `publication_number` (522), `publication_date` (524), `assent_date` (526).
**Effectivity / temporal (the key dimension):**
- `commenced: bool` (528) + related `Commencement` objects (`main_commencement` FK, 568) with per-provision commencement (`all_commenceable_provisions`, `all_uncommenced_provision_ids`, 379–409).
- Repeal: `repealed_by` FK (532), `repealed_date` (535), `repealed_verb` (536; choices REPEALED/REVOKED/WITHDRAWN/LAPSED/RETIRED/EXPIRED/REPLACED/DISAPPLIED, 475–492), `repealed_note` (538).
- `as_at_date_override` (556), `consolidation_note_override` (558).
- Amendments via `Amendment` model (imported 25); timeline helpers (`get_serialized_timeline`, 466).
Classification / filtering: `taxonomy_topics` M2M → `TaxonomyTopic` MP_Node tree (`works.py:54–137`: `name`, `slug`, `description`, `public`, `project`, `copy_from_principal`); `properties` JSONField (552, place-specific key-values); `principal` (546), `stub` (549), `work_in_progress` (564).
Provenance: `created_at/updated_at/approved_at` (570–572), `created_by_user/updated_by_user/approved_by_user` (574–579).

### `Document` (= FRBR Expression) — `documents.py:334–380+`
`work` FK (346), `frbr_uri` (355), `title` (359), `language` FK → ISO-639-2 (362), `draft: bool` (365; drafts excluded from public API), `document_xml` (368, Akoma Ntoso), **`expression_date: DateField` (373, not null)** — the point-in-time version date, `deleted` (376), `created_at` (378).
Retrieval by FRBR URI resolves language + expression date: `DocumentQuerySet.get_for_frbr_uri` (94–143) filters by `language__language__iso_639_2T` and by `expression_date` (≤ requested date, latest-wins, 110–129); `latest_expression`/`distinct('frbr_uri').order_by('-expression_date')` (78–80).

Takeaway: Indigo is the only repo with a real **temporal/effectivity model** (commencement, repeal with 8 verbs, expression_date point-in-time, amendments, as-at date) AND a real **jurisdiction model** (country + locality + FRBR doctype/subtype). It is the structural template closest to TraLuat's hiệu lực + jurisdiction needs. It has no multi-tenant field (single-publisher per deployment) and no learned ranking — retrieval is DB-query/FRBR-resolution, not embedding ranking.

---

## 6. Contract-review label schemas (from prior note; eval/training label types)

Source: `research_notes/Legal AI engine prior art/contract_review_omission.md` (all CC BY 4.0).
- **CUAD** — 510 commercial contracts, **41 clause/label categories** (governing law, limitation of liability, non-compete, change of control, …). Task = extractive QA / span extraction ("find the span for clause type X"). Label type: **per-category answer span(s)**; >13,000 annotations. Presence/absence derivable by whether a span exists per category (not natively labeled for omission).
- **ContractNLI** — 607 NDAs, **17 fixed hypotheses**, each labeled **ENTAILMENT / CONTRADICTION / NOTMENTIONED** + supporting evidence spans (multi-label span identification). `NOTMENTIONED` is the closest public analogue to clause absence.
- **MAUD** — 152 merger agreements, **92 deal-point reading-comprehension questions** (ABA 2021 Deal Points Study), ~39k examples / ~47k annotations. Label type = **multiple-choice answer per deal-point question** over extracted deal-point text.

Label-type summary: CUAD = span-extraction per 41 categories; ContractNLI = 3-way NLI (incl. NOTMENTIONED) over 17 hypotheses + evidence spans; MAUD = MCQ over 92 questions. None carries temporal/jurisdiction metadata (English/US deal docs).

---

## 7. COMPARISON TABLE

Dimensions: retrieval-filter metadata | ranking features | eval ground-truth schema | training labels/weights.

| Repo | Retrieval-filter metadata | Ranking features | Eval ground-truth schema | Training labels / weights |
|---|---|---|---|---|
| **legalbenchrag** | Only `tags` = corpus name (cuad/contractnli/maud/privacy_qa); vec0 table stores embedding only — no query-time field filter | `RetrievedSnippet.score` (= `1/(rank+1)`); vector distance + optional rerank (`embedding_topk`, `rerank_topk`, `token_limit`) | `QAGroundTruth{query, snippets:[Snippet{file_path, span}], tags}`; spans disjoint per file; precision/recall@token-limit | None (no training; it's a retrieval benchmark) |
| **LeSICiN** | Node `type_map` (Act/Chapter/Topic/Section/Fact); edge-type keys `(src_type, rel, trg_type)`; metapath schemas | Matching scores `lambdas·(attr, align)`; `pthresh` (0.65) decision threshold | `labels: list[Section id]` per Fact → multi-hot `[D,C]`; metrics macro/micro P/R/F1 + Jaccard | Positive link = (Fact,Section) in citation_network; negatives implicit (0s); `pos_weight` via TWS `clamp(max/pos,thresh)` or VWS `N/pos` in BCEWithLogitsLoss; loss weights `thetas=(attr,struct,align)` |
| **eyecite** | Citation `type` (Full/Short/Supra/Id/Reference/Law/Journal); `groups`{volume,reporter,page,title,law_section,…}; `court`; `Edition.start/end` (year range) | None learned; resolution by hash-equality of `groups` + edition/date disambiguation (`guess_edition`) | n/a (extraction library, no gold set in repo) | n/a |
| **PAKTON** | None wired as query filter; per-chunk metadata = `source`, `filename`, `filetype`, `last_modified`, `page_number`, `in_document_index`, `in_document_parent_index`, `document_id`, `document_summary` | Vector similarity only (Pinecone/Chroma defaults); no rerank/filter logic in indexer | n/a (no gold set) | n/a |
| **Indigo** | `country`, `locality`, `doctype`, `subtype`, `actor`, `language`, `taxonomy_topics` tree, `properties` JSON, `draft`, `principal`, `stub`; **temporal**: `expression_date`, `commenced`, `repealed_date`, `as_at_date` | None learned; FRBR-URI DB resolution (latest expression ≤ date, language preference) | n/a (authoring/publishing platform, not a benchmark) | n/a |
| **CUAD** | n/a | n/a | 510 contracts × 41 clause categories; gold = answer span(s) per category | Span-extraction / extractive-QA labels; no sample weights documented |
| **ContractNLI** | n/a | n/a | 607 NDAs × 17 hypotheses; gold = ENTAILMENT/CONTRADICTION/NOTMENTIONED + evidence spans | 3-way classification + multi-label evidence-span labels |
| **MAUD** | n/a | n/a | 152 merger agreements × 92 deal-point questions; gold = MCQ answer per question | Multiple-choice classification labels (~39k examples) |

---

## 8. Expected-gap callouts (for TraLuat)

**NO temporal / effectivity (hiệu lực) metadata:**
- legalbenchrag — none (char-span + corpus tag only).
- LeSICiN — none (static IPC statute nodes; no in-force dates).
- PAKTON — only `last_modified` file timestamp (document provenance, not legal effectivity).
- CUAD / ContractNLI / MAUD — none.
- eyecite — partial only: `Edition.start/end` and citation `year`/`month`/`day` describe the *citation source edition*, not document in-force/repeal status.
- **Indigo — the ONLY repo with true effectivity modeling** (commencement incl. per-provision, repeal with 8 verbs, point-in-time `expression_date`, amendments, as-at date). → the template to follow for TraLuat's hiệu lực.

**NO jurisdiction metadata:**
- legalbenchrag, LeSICiN, PAKTON, CUAD, ContractNLI, MAUD — none. eyecite has only `court` (US) + US reporter scoping.
- **Indigo — the ONLY repo with jurisdiction modeling**: `country` + `locality` FKs, FRBR `doctype`/`subtype`/`actor`, `language`. → template for Vietnam national/provincial scoping.

**NO tenant / multi-org metadata:** NONE of the repos has any tenant field. Indigo is single-publisher-per-deployment (only user-provenance FKs created_by/updated_by/approved_by). → TraLuat's tenant isolation is greenfield across all prior art.

**Net:** For retrieval filtering + identity, adopt Indigo's FRBR/temporal/jurisdiction model. For training a statute-linking model, adopt LeSICiN's typed-node + citation-gold + pos_weight schema — but extend both with (expression_date/effectivity-range, jurisdiction, tenant) fields none of them carries. For eval gold, legalbenchrag's (query, disjoint char-spans, provenance-tag) is the minimal RAG-grounding schema; extend `tags` from dataset-name to real legal filter facets (jurisdiction, doc type, in-force-at-date).
