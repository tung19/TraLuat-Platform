# Indigo / Cobalt / Bluebell — deep read for TraLuat L3 (Canonical Knowledge)

Read-only extraction of the bitemporal / FRBR / Akoma Ntoso effectivity data model from
Laws.Africa's stack, re-modelled for TraLuat (Postgres + SQLAlchemy, **not** Django).

Repos read:
- `refs/indigo` — Django app; the authoritative effectivity model (works, documents, amendments, commencements).
- `refs/cobalt` — Python lib; FRBR URI parsing + Akoma Ntoso (AKN) XML (de)serialization.
- `refs/bluebell` — Rust + Python; plain-text → AKN XML parser (structure segmentation + eId generation).

TL;DR for TraLuat: Indigo gives us a battle-tested **valid-time** model (Work = FRBR Work,
Document = FRBR Expression keyed by `expression_date`, Amendment/Commencement = the events that
spawn new expressions, provision-level partial commencement via eId lists). It does **NOT** give us
true bitemporality (no transaction-time dimension as a queryable axis), a **typed norm-relation
graph** (only amendment / repeal / commencement / parent_work hardcoded FKs), or any
**conflict-resolution** (lex superior/posterior/specialis). Those three are TraLuat's net-new moat.

---

## 1. FRBR Work / Expression model (Indigo)

### 1a. Work — the abstract legal instrument (`refs/indigo/indigo_api/models/works.py`)

A **Work** is an abstract act/decree independent of any text version. Keyed globally by its FRBR URI.

Key fields (`works.py:503-578`):
```python
frbr_uri = models.CharField(max_length=512, unique=True)   # GLOBAL identity key (works.py:503)
title; country (FK); locality (FK, nullable)
doctype, subtype, actor, date, number   # the FRBR URI components, denormalized (works.py:513-517)
# publication / lifecycle dates:
publication_name, publication_number, publication_date (DateField)   # works.py:520-524
assent_date (DateField)                                              # works.py:526
commenced = BooleanField(default=False)                              # works.py:528
# repeal:
repealed_by = ForeignKey('self', ...)      # the work that repealed this one (works.py:532)
repealed_date = DateField(null=True)       # works.py:535
repealed_verb = CharField  # repealed/revoked/withdrawn/lapsed/retired/expired/replaced/disapplied (works.py:483-492, 536)
repealed_note
parent_work = ForeignKey('self', related_name='child_works')  # subsidiary legislation (works.py:542)
principal = BooleanField   # has full text vs. being just an amend/repeal/commence instrument (works.py:546)
stub = BooleanField        # stub works have no content / no points in time (works.py:549)
as_at_date_override = DateField  # "last checked for updates up to" (works.py:556)
main_commencement = ForeignKey('Commencement')  # works.py:568
created_at / updated_at / approved_at (+ *_by_user)   # audit timestamps (works.py:570-578)
```

FRBR URI is the single source of identity. On `save()` the component fields are re-derived from the
URI (`set_frbr_uri_fields`, `works.py:642-648`) by parsing via Cobalt's `FrbrUri` (`work_uri` property,
`works.py:149-154`). So the URI string is canonical; the columns are a denormalized cache for querying.

Lifecycle helper props (WorkMixin, `works.py:140-467`):
- `repeal` → builds a `cobalt.RepealEvent` from `repealed_date`/`repealed_by` (`works.py:165-175`).
- `commencement_date` / `commencing_work` → delegate to `main_commencement` (`works.py:181-197`).
- `amended()`, `amendments_after_date(date)` (`works.py:199-208`).

**`expressions()`** (`works.py:234-245`) — the Work→Expression fan-out:
```python
def expressions(self):
    from .documents import Document
    return (Document.objects.undeleted().no_xml()
            .filter(work=self).order_by('expression_date'))
```
i.e. all Documents (expressions) of this work, ascending by `expression_date`.

**`possible_expression_dates()`** (`works.py:252-282`) — the heart of the timeline. Returns, in
descending date order, a dict per candidate date tagged with `amendment` / `consolidation` / `initial`:
```python
amendment_dates     = [a.date for a in self.amendments.all()]
consolidation_dates = [c.date for c in self.arbitrary_expression_dates.all()]
initial = self.publication_date or min(consolidation_dates + [commencement_date])
# union of all; each tagged {date, amendment:bool, consolidation:bool, initial:bool}
```
This is TraLuat's "list of valid-from boundaries on the timeline of a document."

`create_expression_at(user, date, language)` (`works.py:683-718`) materializes a new expression by
**cloning the most recent expression at-or-before `date`** as a template:
```python
template = self.document_set.undeleted() \
    .filter(expression_date__lte=date, language=language) \
    .order_by('-expression_date').first()
# copy title + content (XML) into a new Document with expression_date=date
```

`versions()` (`works.py:720-724`) = `django-reversion` audit history of the Work row itself (metadata
edits), separate from the expression timeline. `as_at_date()` = override or place default (`works.py:726`).

### 1b. Document — the FRBR Expression (`refs/indigo/indigo_api/models/documents.py`)

A **Document** is one language+date version (expression) of a Work (`documents.py:334-384`):
```python
work = ForeignKey('Work')                 # documents.py:346
frbr_uri = CharField                       # work-level URI (documents.py:355)
title
language = ForeignKey('Language')          # 3-letter ISO-639-2 (documents.py:362)
draft = BooleanField(default=True)         # drafts hidden from public API (documents.py:365)
document_xml = TextField                    # the actual AKN XML body (documents.py:368)
expression_date = DateField(null=False)    # VALID-TIME KEY: publication date or latest amendment (documents.py:373)
deleted = BooleanField
created_at / updated_at (+ _by_user)        # row audit timestamps (documents.py:378-384)
```
Note comment at `documents.py:371-372`: *"Date from the FRBRExpression element. This is either the
publication date or the date of the last amendment. Used to identify this particular version."*

So **(work_id, language, expression_date)** is effectively the expression identity. The expression's
valid-time window is `[expression_date, valid_until())`.

---

## 2. Amendments — the versioning engine (`refs/indigo/indigo_api/models/amendments.py`)

### 2a. Amendment (`amendments.py:19-48`)
```python
class Amendment(models.Model):
    amended_work  = ForeignKey('work', related_name='amendments')        # the target
    amending_work = ForeignKey('work', related_name='amendments_made')   # the source instrument
    date = DateField(null=False)   # "Date on which the amendment comes into operation" (amendments.py:28-29)
    verb = CharField(default="amended")
    created_by_user / updated_by_user / created_at / updated_at
    class Meta: ordering = ['date']
```
This is a directed edge `amending_work --[amended, date]--> amended_work`. The `date` is the
**operation/commencement date of the amendment** = the `expression_date` of the new version it produces.

`Amendment.expressions()` (`amendments.py:45-48`): the amended work's documents whose
`expression_date == self.date` — i.e. the expression that embodies this amendment.

### 2b. How applying an amendment materializes a NEW expression

Two layers:

1. **post_save signal** (`amendments.py:80-101`): when an Amendment is created, re-save any documents
   already at that date so the amendment metadata is "stashed" into each expression (forces
   `doc.copy_attributes()`). It does **not** itself create the new text — it wires up the date.

2. **The actual new expression** is created by `Work.create_expression_at(user, date)`
   (`works.py:683-718`, see §1a) — clone latest prior expression's XML, stamp new `expression_date`.
   Then editors apply the textual change, or it's applied provision-by-provision via **AmendmentInstruction**.

### 2c. AmendmentInstruction — provision-level amendment application (`amendments.py:104-179`)
This is the fine-grained "apply this amendment to this specific provision" record — very relevant to
TraLuat's Điều/Khoản/Điểm-level tracking:
```python
amendment = ForeignKey(Amendment, related_name="instructions")
language  = ForeignKey('Language')
state     = FSMField(default='new')          # FSM: new -> applied (amendments.py:112, 145-157)
amending_provision = CharField               # which provision of the amending act
provision_id = CharField   # the eId of the provision to be amended, e.g. "sec_2" (amendments.py:117-118)
amended_provision_id = CharField  # actual eId after applying (amendments.py:124-125)
amended_document = ForeignKey('Document')
amended_text / amended_xml / final_amended_text / final_amended_xml  # before/after snapshots (amendments.py:127-132)
applied_by_user / applied_at
```
- `apply(user)` / `unapply()` are `django_fsm` transitions (`amendments.py:145-157`).
- `determine_provision_id()` (`amendments.py:159-167`) resolves a natural-language provision name
  (e.g. "section 32(a)") to an eId by searching the best prior document.

**TraLuat lesson:** keep the amendment as a graph edge *and* store per-provision instructions with
before/after XML snapshots + an eId pointer. This is exactly the audit trail a legal-AI needs to
explain *why* text at date T differs from T-1.

---

## 3. Point-in-time reconstruction — "văn bản tại ngày T" (`documents.py`)

### 3a. Expression selection at a date — `DocumentQuerySet.get_for_frbr_uri` (`documents.py:94-145`)
The canonical resolver. Expression date semantics come straight from the FRBR URI's expression-date
token (`@`, `@date`, `:date`):
```python
query = self.filter(frbr_uri=frbr_uri.work_uri(work_component=False))
if frbr_uri.language:
    query = query.filter(language__language__iso_639_2T=frbr_uri.language)   # documents.py:106-107
expr_date = frbr_uri.expression_date
if not expr_date:
    expr_date = ':' + today            # no date == "current as of now" (documents.py:112-114)

if expr_date == '@':                   # earliest expression
    query = query.order_by('expression_date')
elif expr_date[0] == '@':              # EXACT date
    query = query.filter(expression_date=parse_date(expr_date[1:]))
elif expr_date[0] == ':':              # latest at-or-BEFORE date  <-- THE as-of-T query
    query = query.filter(expression_date__lte=parse_date(expr_date[1:])) \
                 .order_by('-expression_date')
obj = query.first()
```
**`expression_date__lte=T order_by('-expression_date').first()`** is the core "reconstruct as-of T":
pick the most recent expression whose valid-from ≤ T. This is TraLuat's primary temporal read.

### 3b. Language handling
- `prefer_language(lang_code)` (`documents.py:82-92`): order so the requested language sorts first
  (`When(... then=Value('aaa'))`), else alphabetical by ISO code.
- `latest_expression()` (`documents.py:77-80`): `distinct('frbr_uri').order_by('frbr_uri','-expression_date')`
  — Postgres `DISTINCT ON` to get newest per work. (Note: TraLuat must replicate `DISTINCT ON` in SQLAlchemy.)

### 3c. Valid-until (the end of a version's validity window) — `valid_until()` (`documents.py:276-302`)
Indigo stores only `expression_date` (valid-**from**); valid-**to** is *computed*:
```python
if self.is_latest():
    as_at = self.work.as_at_date()
    return as_at if as_at and as_at > self.expression_date else None   # open-ended, checked up to as_at
else:
    # day before the next NON-ARBITRARY (initial or amendment) expression date
    dates = [d['date'] for d in work.possible_expression_dates()
             if (d['initial'] or d['amendment']) and d['date'] > self.expression_date]
    return min(dates) - timedelta(days=1)
```
Consolidation ("arbitrary") dates do **not** close a window; only initial/amendment dates do.
`is_latest()` (`documents.py:248-271`) and `validity_notice()` (`documents.py:304-331`) build the
human-readable "This is the version from X to Y / including amendments up to Z" coverpage text.

**TraLuat lesson:** either compute `valid_to` on the fly like Indigo, or (recommended for a query
store) **materialize `valid_from`/`valid_to`** on each unit_version row so point-in-time SQL is a simple
range predicate `valid_from <= T AND (valid_to IS NULL OR T <= valid_to)`.

### 3d. Partial / provision-level commencement — `Commencement` (`works.py:941-1023`)
```python
class Commencement(models.Model):
    commenced_work  = ForeignKey(Work, related_name="commencements")
    commencing_work = ForeignKey(Work, related_name="commencements_made", null=True)
    date = DateField(null=True)   # null = "commenced but date unknown" (works.py:952)
    main = BooleanField           # the date most provisions come into force (works.py:954)
    all_provisions = BooleanField # True = whole work commenced on this date (works.py:957)
    note = TextField
    provisions = JSONField(default=list)   # list of commenced eIds e.g. ["sec_2","sec_4.3.list0.a"] (works.py:963-966)
    unique_together = ('commenced_work','commencing_work','date')          # works.py:978
```
So commencement is tracked **per provision eId**. The query side:
- `all_commenceable_provisions(date)` (`works.py:302-377`): walks the TOC of expressions up to `date`,
  cumulatively building the set of provisions that exist and can commence (cached, cross-document).
- `all_uncommenced_provision_ids(date)` (`works.py:379-401`): `commenceable − commenced`.
- `Document.commencements_relevant_at_expression_date()` (`documents.py:211-...`).

**TraLuat lesson:** Vietnamese laws routinely have "Điều X có hiệu lực từ ngày…" differing from the
act's main date. Model commencement at the unit (Điều/Khoản/Điểm) level via a provision-id list, exactly
like `Commencement.provisions`. A unit's effective date = its own commencement, not the document's.

---

## 4. Cobalt — FRBR URI scheme + AKN (de)serialization (`refs/cobalt`)

### 4a. FRBR URI grammar (`refs/cobalt/cobalt/uri.py:3-20`)
Single regex `FRBR_URI_RE`. Structure (AKN 3.0 / `akn-nc` naming convention):
```
/akn /{country}(-{locality})? /{doctype} (/{subtype})? (/{actor})? /{date} /{number}
     (/{language}([@:]{expression_date})?)?
     (/ (!{work_component})? (~{portion})? )?
     (.{format})?
```
Worked example (`uri.py:39-69`):
```
/akn/za-jhb/act/by-law/2003/public-health/eng:2015-01-01/!main~part_1.xml
 country=za locality=jhb doctype=act subtype=by-law date=2003 number=public-health
 language=eng expression_date=:2015-01-01 work_component=main portion=part_1 format=xml
```
Three URI projections (`uri.py:127-179`):
- `work_uri()`  → `/akn/za-jhb/act/by-law/2003/public-health`           (identity, no version)
- `expression_uri()` → `…/eng:2015-01-01/!main~part_1`                    (version = language + date)
- `manifestation_uri()` → `… .xml`                                        (format/serialization)

Expression-date token encodes the temporal operator inline: `@` earliest, `@YYYY-MM-DD` exact,
`:YYYY-MM-DD` latest-at-or-before. (This is what `get_for_frbr_uri` in §3a decodes.)

### 4b. AKN XML (de)serialization (`refs/cobalt/cobalt/akn.py`)
`StructuredDocument` wraps the AKN XML and exposes the FRBR metadata as live properties backed by the
`<meta><identification>` block, which has the AKN three-tier structure (`akn.py:224-245`):
```
FRBRWork        → FRBRthis/FRBRuri/FRBRalias(title)/FRBRdate(name="Generation")/FRBRcountry/FRBRnumber
FRBRExpression  → FRBRthis/FRBRuri/FRBRdate/FRBRauthor/FRBRlanguage
FRBRManifestation → FRBRthis/FRBRuri/FRBRdate
```
- `work_date` / `expression_date` / `manifestation_date` getters+setters read/write the respective
  `FRBRdate/@date` (`akn.py:323-356`). Setting `expression_date` cascades to all components (`akn.py:336-342`).
- `frbr_uri` getter parses `FRBRManifestation/FRBRuri`; setter rewrites all three tiers + every component
  (`akn.py:371-389`).
- `datestring()` / `parsedate()` (`akn.py:32-53`) normalize dates ↔ ISO strings.
- Subclasses per doc type via `for_document_type` (`akn.py:161`; schema map in `cobalt/schemas.py`,
  hierarchical model in `cobalt/hierarchical.py`).

**Reusable for TraLuat canonical IDs:** adopt Cobalt's FRBR URI scheme wholesale as TraLuat's canonical
document/expression identifier. Vietnam mapping, e.g.:
`/akn/vn/act/luat/2015/91/vie@2021-01-01/!main~dieu_1` (Luật số 91/2015, bản hợp nhất 2021, Điều 1).
`cobalt.FrbrUri.parse()` can be reused directly (pure Python, no Django). It is already imported by
Indigo's `citations.validate_frbr_uri` (`refs/indigo/indigo_api/models/citations.py:5-14`).

---

## 5. Bluebell — plain text → structured AKN (structure segmentation) (`refs/bluebell`)

Bluebell is "Markdown for AKN": indentation + keyword headings → valid AKN XML. Reference impl is
Python (`bluebell/parser.py`); `refs/bluebell/crates/bluebell-core` is a Rust port that must produce
**byte-for-byte canonical-XML-identical** output (`refs/bluebell/AGENTS.md`).

### 5a. Grammar approach (PEG, `refs/bluebell/crates/bluebell-core/src/grammar.pest`)
- Document roots per AKN type (`grammar.pest:1-56`): `act`/`bill` → `hierarchicalStructure`
  (`preface? preamble? body conclusions? attachments?`); `doc`/`statement`/`debateReport` →
  `openStructure`; `debate` → `debateStructure`; `judgment` → `judgmentStructure`.
- **Indentation = hierarchy** (preprocess step emits synthetic INDENT/DEDENT tokens —
  `preprocess.rs`, `DEDENT`/`INDENT` in `lib.rs`), à la Python. Two-space indents (`docs/grammar.md`).
- Hierarchical element keywords (`grammar.pest`, `hier_element_name`): `CHAPTER, PART, SECTION,
  ARTICLE, SUBSECTION, PARAGRAPH, SUBPARAGRAPH, POINT, CLAUSE, RULE, TITLE, DIVISION, …` (+ short
  aliases `SEC, ART, PARA, CHAP, SUBSEC…`). A heading line = `KEYWORD num - heading`.
- Design guarantee (`README.md`): *"Bluebell will always produce structurally valid Akoma Ntoso, no
  matter what input is given. It will never refuse to parse malformed input."* — robust, forgiving parser.

### 5b. eId generation — the hierarchical unit IDs (`crates/bluebell-core/src/eid.rs`, `xml.rs:1995-2280`)
After parsing, `rewrite_all_eids` (`xml.rs:1995-1998`) walks the tree with `EidRewriter`:
- Each element's eId = `{parent_prefix}__{alias(name)}_{clean_num}` (`xml.rs:2257-2274`), e.g.
  `chp_1__sec_1__p_1`, `list_1__item_a` (test assertions `xml.rs:2447-2448, 2531`).
- `__` joins hierarchy levels; `_` joins element-alias and number (AKN eId convention).
- `clean_num()` (`eid.rs:5-35`) normalizes the printed number: strips edge punctuation/space, collapses
  internal punctuation to single `-`, keeps unicode letters/digits. E.g. `"(123.4-5)"`→`123-4-5`,
  `"(i)"`→`i`, `"(2bis)"`→`2bis`, `"(三)"`→`三` (tests `eid.rs:62-90`).
- Numberless-but-expected elements get `nn`; otherwise an incrementing counter per (prefix, name)
  (`xml.rs:2265-2273`). `meta` subtree is skipped (`xml.rs:2221-2222`). Supports an `eid_prefix` for
  embedding fragments.

**TraLuat lesson:** this is exactly TraLuat's **structure-segmentation + stable unit-ID** stage. The eId
(`dieu_1__khoan_2__diem_a`) is the stable within-document identity that amendments/commencements point
at (cf. Indigo's `Commencement.provisions` and `AmendmentInstruction.provision_id`). Build a
Vietnamese keyword grammar: `PHẦN, CHƯƠNG, MỤC, TIỂU MỤC, ĐIỀU, KHOẢN, ĐIỂM` → AKN
`part/chapter/section/subsection/article…`, reuse Bluebell's indentation+eId scheme. The Rust core is
embeddable; the Python reference is the easiest to port/mirror.

---

## 6. Proposed TraLuat SQLAlchemy re-model

### 6a. Entity mapping (Indigo → TraLuat)

| Indigo (Django)                    | TraLuat (SQLAlchemy)         | Notes |
|------------------------------------|------------------------------|-------|
| `Work` (works.py:470)              | `document`                   | Abstract instrument. PK = FRBR work URI. Holds lifecycle: publication/assent/commenced/repeal, parent_work, principal/stub. |
| `Document` (documents.py:334)      | `document_version` (expression) | One (language, valid_from) version. Carries AKN XML. |
| AKN element / eId                  | `unit`                       | Điều/Khoản/Điểm; stable eId within a document (Bluebell). |
| per-version provision text         | `unit_version`               | The text/XML of a unit in a given expression; `valid_from`/`valid_to`. |
| `Amendment` (amendments.py:19)     | `norm_relation` (type=amends) | Typed edge source→target + operation date. |
| `AmendmentInstruction` (amendments.py:104) | `amendment_instruction`      | Per-unit apply record + before/after snapshot + eId pointer. |
| `Commencement` (works.py:941)      | `commencement` (+ `provisions` eId list) | Provision-level in-force dates. |
| `repealed_by` FK / `parent_work` FK | `norm_relation` (type=repeals/child_of) | Fold into the typed graph. |
| `ArbitraryExpressionDate` (works.py:1026) | `consolidation_date`         | Non-amendment expression dates. |
| `django-reversion` Version         | transaction-time columns / audit table | See §6c. |

### 6b. Suggested core tables (sketch)
```
document(id, frbr_work_uri UNIQUE, title, doctype, subtype, country, number, date,
         publication_date, assent_date, commenced BOOL, repealed_date, repealed_verb,
         parent_document_id FK, principal BOOL, stub BOOL, as_at_date,
         -- transaction time (bitemporal, see 6c):
         tx_from TIMESTAMPTZ, tx_to TIMESTAMPTZ)

document_version(id, document_id FK, language, valid_from DATE, valid_to DATE NULL,
                 akn_xml, is_consolidation BOOL, source_amendment_id FK NULL,
                 tx_from, tx_to)
         -- as-of-T read: WHERE document_id=? AND language=? AND valid_from<=T
         --               AND (valid_to IS NULL OR T<=valid_to)
         -- mirrors get_for_frbr_uri's expression_date__lte (documents.py:125-129)

unit(id, document_id FK, eid, unit_type, parent_unit_id FK, seq)   # eid from Bluebell (xml.rs:2257)

unit_version(id, unit_id FK, document_version_id FK, num, heading, text, akn_xml,
             valid_from DATE, valid_to DATE NULL, commenced_from DATE NULL,
             tx_from, tx_to)
         -- valid_to computed like Document.valid_until (documents.py:276-302), but MATERIALIZED

norm_relation(id, source_document_id FK, target_document_id FK, rel_type,
              operation_date DATE, source_unit_eid NULL, target_unit_eid NULL,
              verb, note, tx_from, tx_to)
         -- rel_type ∈ {amends, repeals, replaces, commences, consolidates,
         --             guides/detains (hướng dẫn), child_of, cites, conflicts_with}

commencement(id, document_id FK, commencing_document_id FK NULL, date DATE NULL,
             is_main BOOL, all_provisions BOOL, provisions JSONB /* eId list */, note)
         -- == Commencement.provisions (works.py:963-966)

amendment_instruction(id, norm_relation_id FK, language, state, source_unit_eid,
                       target_unit_eid, before_xml, after_xml, applied_at, applied_by)
         -- == AmendmentInstruction (amendments.py:104-132)
```

### 6c. Bitemporality — the key gap to close
Indigo is **valid-time only**: `expression_date` is valid-from; valid-to is *derived*
(`documents.py:276-302`); transaction-time is just `created_at`/`updated_at` audit stamps
(`documents.py:378-384`, `works.py:570-578`) plus `django-reversion` snapshots (`works.py:720-724`).
It cannot answer "what did we *believe* the law at date T looked like, as of knowledge-date K"
(e.g. a retroactive amendment entered last week but effective 2 years ago).

For TraLuat (a legal-AI that must be auditable/defensible) add a **true second axis**:
- `valid_from`/`valid_to` (DATE) = when the norm is *in force* (Indigo's `expression_date`/`valid_until`).
- `tx_from`/`tx_to` (TIMESTAMPTZ) = when TraLuat *recorded/believed* it; never hard-delete, close the
  row by setting `tx_to` and insert a new row. As-of query = `valid predicate AND tx_from<=K AND (tx_to IS NULL OR K<tx_to)`.
- This supports retroactive amendments and "diff of what changed in our knowledge" — critical for
  explaining AI answers and for Vietnam's frequent `văn bản hợp nhất` / retroactive effect provisions.

### 6d. What Indigo does well (adopt)
1. **FRBR URI as global canonical identity** + three projections (work/expression/manifestation) —
   adopt Cobalt directly (`uri.py`), it's pure Python.
2. **Expression = (work, language, date)**, newest-at-or-before-T selection (`documents.py:125-129`) —
   simple, correct, index-friendly.
3. **Provision-level commencement & amendment** via stable eIds (`works.py:963`, `amendments.py:117-125`)
   — exactly what Điều/Khoản/Điểm granularity needs.
4. **Amendment as a dated edge** amending_work→amended_work that *spawns* a new expression by cloning
   the prior one (`works.py:683-718`) — clean versioning step.
5. **before/after XML snapshots per instruction** (`amendments.py:127-132`) — ready-made explainability.
6. **Timeline computation** (`possible_expression_dates`, `works.py:252-282`) distinguishing
   initial vs amendment vs consolidation dates.

### 6e. What Indigo LACKS for TraLuat (build net-new = the moat)
1. **No generic typed norm-relation graph.** Only hardcoded FKs: `Amendment`, `Commencement`,
   `repealed_by`, `parent_work`. No "hướng dẫn / quy định chi tiết / đính chính / thay thế một phần /
   dẫn chiếu" relation types, and relations aren't first-class queryable edges. → build `norm_relation`.
2. **No conflict resolution.** Nothing encodes lex superior (hierarchy of legal force — Hiến pháp > Luật
   > Nghị định > Thông tư), lex posterior (later wins), or lex specialis (specific wins). Indigo assumes
   an editor manually curates the single correct consolidated text. TraLuat must *reason* about conflicts
   → needs a legal-force rank on `document`, effective-date ordering, and a conflict/override relation.
3. **No transaction-time / true bitemporality** (see §6c) — only valid-time + audit stamps.
4. **No automatic cross-reference / citation graph** beyond manual `CitationAlias` (`citations.py`) and a
   citator plugin; TraLuat will want a dense `cites` edge set extracted at parse time.
5. **Consolidation is manual/arbitrary** (`ArbitraryExpressionDate`, works.py:1026) — a human creates the
   consolidated expression. TraLuat should *auto-apply* amendment instructions to synthesize the as-of-T
   text and flag low-confidence merges for review.
6. **Repeal is coarse** — `repealed_by`/`repealed_date` live on the whole Work; partial repeals are only
   representable as amendments. TraLuat may need partial-repeal as a relation at unit granularity.

---

## Appendix — exact file references
- Work model + timeline: `refs/indigo/indigo_api/models/works.py`
  (Work:470-821, WorkMixin:140-467, expressions:234-245, possible_expression_dates:252-282,
   create_expression_at:683-718, Commencement:941-1023, ArbitraryExpressionDate:1026, post_save:824-834).
- Amendments: `refs/indigo/indigo_api/models/amendments.py`
  (Amendment:19-48, post_save_amendment:80-101, AmendmentInstruction:104-179).
- Expression/point-in-time: `refs/indigo/indigo_api/models/documents.py`
  (get_for_frbr_uri:94-145, prefer_language:82-92, latest_expression:77-80, Document:334-460,
   is_latest:248-271, valid_until:276-302, validity_notice:304-331).
- Citations: `refs/indigo/indigo_api/models/citations.py` (uses `cobalt.FrbrUri`).
- Cobalt FRBR URI: `refs/cobalt/cobalt/uri.py` (regex:3-20, FrbrUri:23-215).
- Cobalt AKN XML: `refs/cobalt/cobalt/akn.py` (meta/identification:207-249, date props:323-356, frbr_uri:371-389).
- Bluebell grammar: `refs/bluebell/crates/bluebell-core/src/grammar.pest`; docs `refs/bluebell/docs/grammar.md`.
- Bluebell eId: `refs/bluebell/crates/bluebell-core/src/eid.rs` (clean_num:5-35) and
  `refs/bluebell/crates/bluebell-core/src/xml.rs` (rewrite_all_eids:1995, EidRewriter:2212-2280).
- Bluebell contract/overview: `refs/bluebell/README.md`, `refs/bluebell/AGENTS.md`.
