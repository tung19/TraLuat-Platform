# eyecite — Citation-Extraction Pipeline (deep read for TraLuat L2/L6)

Source: `refs/eyecite` (freelawproject/eyecite v2.7.8, BSD-2-Clause). US case-law centric.
Read-only analysis. TraLuat mapping: L2 = citation extraction from judgments/documents; L6 = citation verification.

**One-line takeaway:** eyecite is a *data-driven regex-token pipeline*. The **engine** (tokenize → find → resolve → annotate) is language-agnostic and reusable; the **pattern database** (`reporters-db`, `courts-db`) is 100% US-specific and must be rebuilt from scratch for Vietnamese law. The span-preserving annotation (`annotate.py` + `fast-diff-match-patch`) and the antecedent-tracking resolution (`resolve.py`) are the two most directly transplantable pieces.

---

## 1. Directory map + the 4-stage pipeline

### Package layout (`refs/eyecite/eyecite/`)
| File | Role |
|---|---|
| `__init__.py` | Public API: exports exactly 4 functions — `clean_text`, `get_citations`, `resolve_citations`, `annotate_citations` (`refs/eyecite/eyecite/__init__.py:1-11`). These *are* the 4 pipeline stages. |
| `clean.py` | **Stage 1 (clean)** — pre-processing of raw/OCR/HTML text. |
| `find.py` | **Stage 2 (find)** — `get_citations()`, the main workhorse; builds `Document`, tokenizes, classifies each citation token. |
| `tokenizers.py` | The tokenizer engine + **where the US pattern DB is loaded** (`_populate_reporter_extractors()`). |
| `resolve.py` | **Stage 3 (resolve)** — group short/supra/id/reference cites to their antecedent full citation. |
| `annotate.py` | **Stage 4 (annotate)** — span-preserving markup insertion via diff. |
| `models.py` | All data classes: `Document`, token types, citation types, `TokenExtractor`, `Resource`. |
| `regexes.py` | All hand-written regex building blocks (pin-cite, year, court/date paren, id/supra/section, antecedent). |
| `helpers.py` | Metadata extraction (case-name, law/journal post-metadata), `match_on_tokens`, `filter_citations`, court disambiguation (`courts_db`). |
| `utils.py` | HTML balance/whitespace helpers used by annotation. |

### The 4 stages (as a data flow)
```
raw text ──clean.py: clean_text()──▶ plain_text
         ──find.py: get_citations()──▶ list[CitationBase]   (uses tokenizers.py + helpers.py + regexes.py)
         ──resolve.py: resolve_citations()──▶ dict[Resource → [citations]]
         ──annotate.py: annotate_citations()──▶ marked-up text (offsets preserved via diff)
```
Canonical usage is shown in `refs/eyecite/README.rst` and `TUTORIAL.ipynb`: `clean_text` → `get_citations` → `resolve_citations` → `annotate_citations`.

---

## 2. Tokenization / finding — how `get_citations` works

### Entry point: `find.py:get_citations()` (`refs/eyecite/eyecite/find.py:40-149`)
1. Wraps input in a `Document` (`models.py:901-983`). `Document.__post_init__` runs `clean_steps` and, for `markup_text`, builds `SpanUpdater` objects `plain_to_markup` / `markup_to_plain` to map offsets between HTML and plain text.
2. `document.tokenize(tokenizer)` → `tokenizer.tokenize(plain_text)` returns `(words, citation_tokens)`. `words` is a flat list mixing bare `str` words and `Token` objects; `citation_tokens` is the subset of non-string tokens with their index (`models.py:980-983`, `tokenizers.py:375-425`).
3. Iterate over `citation_tokens` and dispatch **by token type** (`find.py:79-130`):
   - `CitationToken` → `_extract_full_citation()` (or `_extract_shortform_citation()` if `token.short`).
   - `IdToken` → `_extract_id_citation()` ("id.", "ibid.").
   - `SupraToken` → `_extract_supra_citation()`.
   - `SectionToken` → `UnknownCitation` (kept so id-antecedent tracking stays accurate).
   - else → skip (plain word / stopword / paragraph).
4. After a `FullCaseCitation`, scan forward for **ReferenceCitations** (later re-mentions by party name) via `extract_reference_citations()` (`find.py:152-221`).
5. `filter_citations()` dedupes + sorts by span and resolves overlaps (`helpers.py:1068+`). Optional `disambiguate_reporters()`.
6. Returns a list **ordered by position in the text** — order matters so resolve.py can treat supra/id/short as back-references.

### Citation types (`models.py`)
`CitationBase` (abstract) → `ResourceCitation` → `FullCitation` → `FullCaseCitation` / `FullLawCitation` / `FullJournalCitation`; plus `CaseCitation` → `ShortCaseCitation`; and standalone `SupraCitation`, `IdCitation`, `ReferenceCitation`, `UnknownCitation`. Each carries `span()` / `full_span()` offsets and a `.metadata` dataclass (plaintiff, defendant, court, year, pin_cite, parenthetical, antecedent_guess, publisher...).

### The tokenizer
- A **`TokenExtractor`** (`models.py:838-870`) = (regex, constructor, extra-fields, flags, `strings`). Each extractor applies one regex (`finditer`) and emits typed `Token`s via `from_match` (`models.py:735-745`, which captures `m.groupdict()` into `token.groups`).
- `Tokenizer.tokenize()` (`tokenizers.py:375-425`): runs all candidate extractors, sorts matches by `(start, -end)`, merges duplicate matches (same span matched by 2 regexes → `CitationToken.merge` combines editions), drops overlaps (with a special nominative-reporter preference), and interleaves plain-text words between matches so spans stay exact.

### Aho-Corasick (pyahocorasick) — the performance prefilter
- `AhocorasickTokenizer` (`tokenizers.py:451-521`) is the **default** (`default_tokenizer`, `tokenizers.py:664`).
- Idea: there are ~thousands of reporter regexes; running them all on every text is slow. Each extractor declares the literal `strings` a text **must contain** for its regex to possibly match (e.g. `"U.S."`, `"S.E. 2d"`). A pyahocorasick `Automaton` (`make_ahocorasick_filter`, `tokenizers.py:500-521`) maps those literal strings → extractors. `get_extractors(text)` runs the automaton once over the (whitespace-stripped) text and returns only the extractors whose trigger string is present, plus the always-on `unfiltered_extractors` (id/supra/section/etc. that have no trigger string). This is a **candidate-set prefilter**, not the matcher — the actual spans still come from running the selected regexes.
- An optional `HyperscanTokenizer` (`tokenizers.py:524-661`) compiles all regexes into one Hyperscan DB for a single-pass scan; same results, different engine. `hyperscan` is an optional dev dependency.

### Pattern definition & matching — where patterns come from
Patterns are **not** hand-written per citation. They are generated from the data DB in `_populate_reporter_extractors()` (`tokenizers.py:133-359`), see §3. Only the *grammar fragments* (pin cite, year, court/date paren, id/supra/section, antecedents) are hand-written regexes in `regexes.py`.

---

## 3. THE KEY LESSON — data vs. engine split

**The matching engine (`find.py`, `tokenizers.py`, `resolve.py`, `annotate.py`, `models.py`) contains almost no US-specific knowledge. All US-specific pattern data lives in two external pip packages.**

Dependencies (`refs/eyecite/pyproject.toml:37-44`):
```
courts-db>=0.10.9        # court names → court IDs
reporters-db>=3.2.53     # reporters.json, laws.json, journals.json + regex variables
pyahocorasick            # prefilter engine
fast-diff-match-patch    # span-preserving annotation
lxml, regex
```

Where the pattern DB is loaded (`refs/eyecite/eyecite/tokenizers.py:14-15`):
```python
from reporters_db import JOURNALS, LAWS, RAW_REGEX_VARIABLES, REPORTERS
from reporters_db.utils import process_variables, recursive_substitute
```
and courts (`refs/eyecite/eyecite/helpers.py:8`):
```python
from courts_db import courts
```

How the data becomes extractors (`tokenizers.py:133-359`, function `_populate_reporter_extractors()`):
- `RAW_REGEX_VARIABLES` from reporters-db defines reusable template variables (`$volume`, `$reporter`, `$page`, `$full_cite = "$volume $reporter,? $page"`) — `tokenizers.py:137-140`.
- For every entry in `REPORTERS` (case reporters), `LAWS` (statutes), `JOURNALS`, it reads the per-edition `regexes` template list (defaulting to `["$full_cite"]`), substitutes the reporter string and variables (`recursive_substitute` + `Template.safe_substitute`), and registers one `TokenExtractor` per resulting regex with the literal trigger `strings` (`tokenizers.py:222-311`).
  - Case reporters → `source="reporters"` → become `FullCaseCitation`.
  - `LAWS` → `source="laws"` → `FullLawCitation`; note the code even patches statute regexes to allow multi-section cites: `r.replace(r"§ ", r"§§? ?")` (`tokenizers.py:265-267`).
  - `JOURNALS` → `source="journals"` → `FullJournalCitation`.
- The `source` string is what `find.py:_extract_full_citation()` keys on to pick the citation class (`find.py:235-250`).
- Only *after* all data-derived extractors are built does it append the handful of **engine-level, non-citation** extractors (id, supra, paragraph, stopwords, placeholder, section) from `regexes.py` (`tokenizers.py:317-356`).

**Confirmation for TraLuat:** the engine is reusable as-is in shape. To support Vietnam you do **not** touch `find.py`/`resolve.py`/`annotate.py`'s structure — you replace the *data layer* (`reporters-db`/`courts-db`) with a Vietnamese legal-source DB and the *grammar fragments* in `regexes.py`. eyecite's own design (data in a separate versioned pip package, regex templates with variables) is the model to copy: build a `vn-legal-db` package (Luật/Nghị định/Thông tư/Quyết định/án lệ sources + issuing-body names) separate from the `traluat-cite` engine.

---

## 4. Resolution — antecedent tracking (`resolve.py`)

`resolve_citations(citations)` (`refs/eyecite/eyecite/resolve.py:248-358`) consumes the **position-ordered** list and walks it once, carrying state:
- `resolved_full_cites: list[(FullCitation, Resource)]` — all full cites seen so far.
- `last_resolution` — the resource of the most recently resolved citation (for `id.`).
- Returns `dict[Resource → [citations]]`, i.e. every short/supra/id/reference cite is clustered under the full citation it points to.

Per-type resolution logic:
- **Full** (`resolve_full_citation`, `resolve.py:30-60`): wraps in a `Resource` (hash of volume+reporter+page; missing-page cites get a unique id to avoid false merges — `models.py:873-898`). Override point for DB lookup against canonical IDs.
- **Short** (`_resolve_shortcase_citation`, `resolve.py:148-183`): match candidates where `corrected_reporter()` **and** `volume` equal a prior full cite; if ambiguous, refine by checking the short cite's `antecedent_guess` against prior cites' plaintiff/defendant (`_filter_by_matching_antecedent`).
- **Supra** (`_resolve_supra_citation`, `resolve.py:186-201`): resolve purely by matching `antecedent_guess` (the party name captured before "supra") against prior full cites' plaintiff/defendant.
- **Reference** (`_resolve_reference_citation`, `resolve.py:204-224`): match by plaintiff/defendant/resolved case-name fields; accept only if exactly one full cite matches.
- **Id.** (`_resolve_id_citation`, `resolve.py:227-245`): resolve to `last_resolution` (the immediately preceding resolved cite) — unless the pin cite is impossible for that resource (`_has_invalid_pin_cite`, `resolve.py:110-145`, e.g. "1 U.S. 1. Id. at 200" rejected via `MAX_OPINION_PAGE_COUNT`).

**Key principle:** id/supra/short are *never* resolved at find time — only at resolve time, using the running list of antecedents. The `antecedent_guess` itself is captured during find by scanning backward from the token with `SUPRA_ANTECEDENT_REGEX` / `SHORT_CITE_ANTECEDENT_REGEX` via `match_on_tokens(..., forward=False)` (`find.py:325-337`, `regexes.py:262-283`, `helpers.py:984-1042`). All five resolver functions are **injectable parameters** of `resolve_citations`, so you can swap in TraLuat DB-backed resolvers while keeping the walk.

---

## 5. Annotation — span-preserving markup (`annotate.py`)

`annotate_citations(plain_text, annotations, source_text=...)` (`refs/eyecite/eyecite/annotate.py:129-257`). `annotations` = list of `((start, end), before_text, after_text)`.

The problem it solves: citations were found on *cleaned* `plain_text`, but you want to insert links into the *original* `source_text` whose offsets differ. Naive insertion would corrupt every offset after the first insert.

How offsets are preserved:
- **`SpanUpdater`** (`annotate.py:20-121`) diffs `text_before` vs `text_after` using **`fast_diff_match_patch.diff(...)`** (`annotate.py:81-99`) and precomputes a step function: a sorted list of `offsets` + per-range `updaters` (each either `shift_offset(+delta)` or `replace_offset`). `update(offset, bisect)` does a `bisect` into the offset table and applies the matching updater — O(log n) offset remap from cleaned→source space. (A `difflib` fallback `get_diff_steps_builtin` exists for debugging — `annotate.py:101-115`.)
- In `annotate_citations`, if `source_text != plain_text`, it builds a `SpanUpdater(plain_text, placeholder_markup(source_text))` and remaps each annotation's `start`/`end` into source space before inserting (`annotate.py:191-209`). Uses `bisect_right` for start, `bisect_left` for end so boundaries land correctly.
- Insertion itself is done left-to-right by slicing the source text and appending `before + span_text + after`, tracking `last_end` to handle **overlap** (partial-skip) — never mutating offsets in place (`annotate.py:202-257`).
- HTML safety: `unbalanced_tags` = `"unchecked"|"skip"|"wrap"`; `maybe_balance_style_tags` / `wrap_html_tags` (`utils.py`) keep the result valid HTML when a citation span straddles a tag boundary.

**Relevance to TraLuat clause-level anchoring:** this is exactly the mechanism TraLuat needs to anchor a citation to a character span in the *original* judgment/document after cleaning/normalization. The `SpanUpdater` diff-remap pattern (clean text for matching, project spans back onto source for anchoring) is directly reusable for anchoring Điều/Khoản/Điểm references to canonical IDs while keeping exact source offsets. `markup_to_plain`/`plain_to_markup` on the `Document` (`models.py:914-953`) already do this both ways for HTML inputs.

---

## 6. Concrete plan for TraLuat

### Reuse (engine — largely language-agnostic)
1. **Pipeline shape**: keep the 4 stages and their separation — `clean_text` (VN-specific: unicode NFC normalization, OCR artifacts, số/ký hiệu cleanup) → `get_citations` → `resolve_citations` → `annotate_citations`. Mirror the 4-function public API.
2. **TokenExtractor + typed-token model** (`models.py` Token/CitationToken/TokenExtractor; `find.py` type-dispatch loop): build-regex-from-data, emit typed tokens, dispatch by type. Keep `Document` + position-ordered token list + `citation_tokens`.
3. **Aho-Corasick prefilter** (`tokenizers.py` AhocorasickTokenizer): reuse the `strings`-trigger → candidate-extractor pattern once the VN pattern set grows large (trigger strings like "Điều", "Khoản", "Nghị định", "Thông tư", "án lệ số").
4. **Resolution walk** (`resolve.py`): reuse the single-pass antecedent-tracking design and the injectable resolver functions. Map onto VN back-references (see below).
5. **Span-preserving annotation** (`annotate.py` `SpanUpdater` + `fast-diff-match-patch`, and `Document.markup_to_plain`): reuse almost verbatim for clause-level anchoring to canonical IDs on the original text.

### Build (data + grammar — 100% new for Vietnam)
1. **A Vietnamese legal-source DB** (the analogue of `reporters-db`/`courts-db`, as a *separate versioned package*):
   - Document-type vocabulary + abbreviations: Luật, Bộ luật, Nghị định (NĐ-CP), Thông tư (TT), Thông tư liên tịch, Quyết định (QĐ), Nghị quyết (NQ), Pháp lệnh, Công văn, án lệ.
   - Issuing bodies / ký hiệu suffixes (-CP, -TTg, -BTC, -BCA, -NHNN, -TANDTC...) — analogue of courts-db.
   - Regex-template variables (analogue of `RAW_REGEX_VARIABLES`): `$so` (số), `$nam` (năm/ngày ban hành), `$dieu`, `$khoan`, `$diem`, `$loai_vb`, `$co_quan`.
2. **A Vietnamese citation grammar** (new `regexes.py`), covering at least:
   - Hierarchical anchors: `Điều X Khoản Y Điểm Z` (and reversed order "điểm z khoản y Điều x"), ranges ("các Điều 1 đến 5", "Khoản 1 và 2"), và "Chương/Mục/Phần".
   - Instrument reference: `của Luật/Bộ luật … số .../QH.., Nghị định số .../NĐ-CP, Thông tư số .../TT-…, ngày…/năm…`.
   - Named codes without number ("Bộ luật Dân sự 2015", "Luật Đất đai").
   - Case law: `án lệ số .../AL` (e.g. `Án lệ số 05/2016/AL`).
   - Back-references (the VN analogue of id./supra/short): "điều này", "khoản trên", "nêu trên", "nói trên", "cùng điều", "văn bản này" → resolve to the nearest prior full instrument (reuse `antecedent_guess` + `last_resolution` logic).
   - Cross-reference / amendment detection: "được sửa đổi, bổ sung bởi …", "được thay thế bởi …", "bãi bỏ bởi …", "hướng dẫn bởi …", "quy định chi tiết …" — capture as typed relations between two instrument citations (feeds L6).
3. **Resolver to canonical IDs**: override `resolve_full_citation` to hit TraLuat's canonical legal-document registry (Luật/NĐ/TT → canonical ID; án lệ → AL ID), falling back to eyecite-style thin `Resource` clustering when unknown. This is the L2→L6 hand-off.

### What eyecite does NOT do (gaps TraLuat must own — important for L6)
- **No temporal / in-force reasoning**: no effective-date (ngày có hiệu lực), no "currently in force" check, no version/consolidation handling. eyecite's only date logic is (a) edition disambiguation by publication year (`guess_edition`, `models.py:363-376`) and (b) sanity bounds on years (`get_year`, `helpers.py:85-95`). TraLuat's L6 (verification: is the cited Điều/Khoản still valid at the judgment date; has it been amended/replaced) is entirely out of scope here and must be built on top.
- **No semantic validation** that the cited Điều/Khoản actually exists in the target instrument — eyecite only pattern-matches; it never checks the reference resolves to a real provision.
- **No amendment-graph**: eyecite has no notion of "sửa đổi/bãi bỏ" relations between documents — TraLuat must add this as a new citation-relation type.
- **English-only tokenization assumptions**: stopwords, "v.", "supra", "id.", month names in `regexes.py` are all English/US; whitespace handling assumes Latin script. Diacritic-aware normalization is TraLuat's responsibility in the clean stage.

### Suggested module mapping (TraLuat)
| eyecite file | TraLuat analogue |
|---|---|
| `tokenizers._populate_reporter_extractors` + `reporters-db` | `vn-legal-db` package + extractor builder (keep separate from engine) |
| `regexes.py` | VN legal-citation grammar (Điều/Khoản/Điểm + instrument + án lệ + amendment verbs) |
| `find.py` type-dispatch | reuse shape; add amendment-relation extraction pass |
| `resolve.py` | reuse walk; VN back-references + canonical-ID resolver (L2→L6 hand-off) |
| `annotate.py` SpanUpdater | reuse for clause-level anchoring onto original judgment text |
| `courts-db` | issuing-body / ký hiệu registry |
