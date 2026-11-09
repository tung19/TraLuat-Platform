# LeSICiN — Deep Read for TraLuat L3 (Judgment↔Statute Linking)

**Repo:** `refs/LeSICiN` (code only; data files are gitignored, downloaded separately from Zenodo https://doi.org/10.5281/zenodo.6053791)
**Paper:** Paul, Goyal, Ghosh — "LeSICiN: A Heterogeneous Graph-based Approach for Automatic Legal Statute Identification from Indian Legal Documents", AAAI 2022.
**Last commit:** 2022-02-12 (pre-LLM; PyTorch + Sent2Vec + torch_sparse).
**Task (their LSI):** given a case's *facts* (free text), predict the set of **statutes (Sections of the Indian Penal Code)** that apply. This is exactly TraLuat L3: judgment facts → applicable Điều/Khoản. Multi-label link prediction over a fixed label set (the statute Sections), aided by a citation graph.

> SAFETY NOTE: this was a pure read. Nothing was run/built/installed. All data files (`.jsonl`, graph edge files, Sent2Vec `.bin`) are absent from the clone — schema below is reconstructed from code + README.

---

## 1. Directory map — where things live

```
refs/LeSICiN/
├── README.md                 # dataset schema + config documentation (authoritative for data format)
├── run.py                    # entry point: wiring of data→graph→model→train/dev/test/infer loop
├── data_helper.py            # LSIDataset (text loading/preprocess/sent-vectorize) + MiniBatch (batching + METAPATH SAMPLING)
├── helper.py                 # generate_vocabs, generate_graph (GRAPH CONSTRUCTION), label weights, train loop, metrics
├── model/
│   ├── basicmodules.py       # LstmNet (BiLSTM), AttnNet (additive attention w/ optional dynamic context)
│   ├── submodules.py         # HierAttnNet (text enc), MetapathAggrNet (graph enc = MAGNN+RotatE), MatchNet (matching net)
│   └── model.py              # LeSICiN top module: combines the 3 encoders, 3 score heads, loss
├── configs/
│   ├── data_path.json        # file paths (data/secs.jsonl, data/train.jsonl, graph edge files, sent2vec .bin, ...)
│   └── hyperparams.json      # all hyperparams + run flags (do_train_dev/do_test/do_infer)
├── data/ cache/ saved/       # EMPTY (gitignored); data comes from Zenodo
```

- **Model** → `model/model.py` + `model/submodules.py` + `model/basicmodules.py`
- **Graph construction** → `helper.py::generate_graph` (lines 28–64) + metapath sampling in `data_helper.py::MiniBatch.generate_metapaths` (lines 149–173)
- **Data schema** → README "Data" section + `data_helper.py::LSIDataset` (lines 10–76) + `configs/data_path.json`

---

## 2. The heterogeneous graph

### Node types (5)
From README and `helper.py` / `run.py`: `type_map` is a JSON dict mapping every node id → one of **Act / Chapter / Topic / Section / Fact**. These model the IPC statute hierarchy plus case documents:
- **Act** (top of statute tree, e.g. the IPC itself)
- **Chapter**
- **Topic** (a grouping level between Chapter and Section — NB: an extra semantic layer, not a strict legal division)
- **Section** = the **label set / statute leaves** (what gets predicted)
- **Fact** = a case document (train/dev cases are graph nodes; test/infer cases are NOT — see §4)

### Edge types (two sub-graphs merged into one hetero-graph)
README: two edge files, each line a triple `(src node id, relationship name, trg node id)`:
1. **Label tree** (`label_tree.json`) — the **statute hierarchy tree**: Act→Chapter→Chapter→Topic→Topic→Section edges (parent/child relationships).
2. **Citation network** (`citation_network.json`) — the **Fact↔Section citation edges**: a case document cites the Sections it invokes. This is the training signal (§5) and the only edge type touching Fact nodes.

Plus **metapath schemas** (`schemas.json`): per node-type, a list of metapaths; each metapath is a list of edge-tuples `(src node type, relationship name, trg node type)`. `run.py` uses `schemas['section']` for the Section side and `schemas['fact']` for the Fact side.

### How the graph is BUILT and STORED — quote `helper.py::generate_graph` (lines 28–64)
```python
def generate_graph(label_vocab, type_map, label_tree_edges, cit_net_edges, label_name='section'):
    node_vocab = defaultdict(dict) # each key is a node_type, each value a dict: node id -> local index
    node_vocab[label_name] = label_vocab # label vocab IS the Section node vocab (indices must line up with labels)

    edge_vocab = {}
    edge_indices = defaultdict(list) # key=(src type, rel name, trg type) -> list of [src_idx, trg_idx]

    for (node_a, edge_type, node_b) in label_tree_edges + cit_net_edges:   # <-- both subgraphs concatenated
        node_a_type, node_b_type = type_map[node_a], type_map[node_b]
        if edge_type not in edge_vocab:
            edge_vocab[edge_type] = len(edge_vocab)
        if node_a not in node_vocab[node_a_type]:
            node_vocab[node_a_type][node_a] = len(node_vocab[node_a_type])
        if node_b not in node_vocab[node_b_type]:
            node_vocab[node_b_type][node_b] = len(node_vocab[node_b_type])
        node_a_token = node_vocab[node_a_type][node_a]
        node_b_token = node_vocab[node_b_type][node_b]
        edge_indices[(node_a_type, edge_type, node_b_type)].append([node_a_token, node_b_token])

    num_nodes = {ntype: len(nodes) for ntype, nodes in node_vocab.items()}

    adjacency = {}
    for keys, edges in edge_indices.items():
        row, col = torch.tensor(edges).t()
        sizes = (num_nodes[keys[0]], num_nodes[keys[-1]])
        adj = torch_sparse.SparseTensor(row=row, col=col, sparse_sizes=sizes)   # <-- stored as SparseTensor per edge-type
        adjacency[tuple(keys)] = adj
    return node_vocab, edge_vocab, edge_indices, adjacency
```
Key points:
- Nodes are vocabularised **per type** (each type gets its own 0..N index space). Section indices are forced equal to `label_vocab` so the graph index == the label/prediction index.
- The graph is stored as a **dict of `torch_sparse.SparseTensor` adjacency matrices keyed by `(src_type, rel, trg_type)`** — i.e. a canonical heterogeneous-graph relation-slicing. There is no monolithic adjacency; neighbours are sampled per relation.
- Edges are treated as **directed as listed**; metapaths walk only in the stored direction (so edge files must contain the direction you want to traverse).

---

## 3. Label / hierarchy structure + multi-label architecture

### Label tree
The statute hierarchy (Act→Chapter→Topic→Section) is **not** used as a softmax-over-tree classifier. Instead it is encoded **structurally**: the tree edges live in the same hetero-graph, and each Section's position in the tree is turned into an embedding by walking metapaths from that Section up/through the hierarchy and aggregating (MAGNN, below). So the hierarchy informs the *Section's structural embedding*, not the loss shape.

### Label set / multi-label
- `label_vocab` (`helper.py::generate_vocabs`, lines 21–24) = ordered dict of every Section id → class index. The number of Sections `L` is the number of output classes.
- Each Fact's gold `labels` is a multi-hot vector of length `L` (`data_helper.py::MiniBatch`, lines 120–137: `self.labels[i].scatter_(0, label_list, 1.)`).
- Loss: **`BCEWithLogitsLoss` with per-label `pos_weight`** (`model.py` line 16) — standard multi-label, class-imbalance weighted. Weights from `helper.py::generate_label_weights` (lines 67–73): Threshold Weighting Scheme `clamp(pos.max()/pos, max=thresh)` (tws_thresh=10) or Vanilla `len(train)/pos`.
- Prediction: `scores > pred_threshold` (pthresh=0.51) per label (`model.py` lines 80–81). No tree constraint enforced at decode time.

### Model architecture at a high level (`model.py::LeSICiN.forward`, lines 30–88)
Three encoders + a matching network producing **three score heads** that are combined and co-trained:

1. **Text encoder** `HierAttnNet` (HAN) — `submodules.py` lines 4–37. Hierarchical: word→sentence BiLSTM+attention, then sentence→doc BiLSTM+attention. Used on BOTH facts and sections (shared weights). Produces `fact_attr_hidden [D,H]` and `sec_attr_hidden [C,H]`. (With Sent2Vec the word level is skipped; sentences come in pre-embedded.)
2. **Graph / structural encoder** `MetapathAggrNet` (MAGNN) — `submodules.py` lines 39–128. For a target node, samples metapath instances, embeds each node (per-type embedding + linear scale to common size), applies **RotatE rotational encoding** along the path (`rotational_encoding`, lines 81–96 — explicitly ports DeepGraphLearning/KnowledgeGraphEmbedding), intra-metapath attention aggregation, then inter-metapath attention aggregation. Produces `sec_struct_hidden [C,H]` (and `fact_struct_hidden` for train/dev facts).
3. **Matching network** `MatchNet` — `submodules.py` lines 130–148. Takes fact representation + section representation, runs a BiLSTM+attention over the (broadcast) section reps conditioned on a fact-derived dynamic context, concatenates and projects to `[D, C]` logits.

**Three heads** (`model.py`):
- `attr_logits/scores` = MatchNet(fact **text**, sec **text**) — lines 49–50
- `align_logits/scores` = MatchNet(fact **text**, sec **structure**) — line 60 (cross-modal: aligns text to graph)
- `struct_logits` = MatchNet(fact **structure**, sec **structure**) — lines 62–74, **only when fact has graph features** (train/dev)

**Score combination (inference):** `scores = lambdas[0]*attr_scores + lambdas[-1]*align_scores` (lambdas=[0.25,0.75]) — line 80. Note: **struct is NOT in the inference score** (test facts have no graph node), only attr + align.
**Loss (training):** `thetas · BCE` over `[attr, struct, align]` (thetas=[1,2,3]) — `calculate_losses` lines 23–28. The `align` head (text↔structure) carries the most weight; this is the "correlate text with graph" mechanism. The `struct` head is an auxiliary signal that trains the shared matcher to also work on graph-derived fact reps.

The mechanism that makes it transfer (§4): because text and structure are matched through the **same** MatchNet and the `align` head explicitly ties fact-text to section-structure, a fact with only text can still be scored against section structural embeddings.

---

## 4. The inductive part (unseen cases) — the key property for TraLuat

**Transductive vs inductive split is by node type, in `run.py`'s DataLoader wiring:**
- `train_loader` (lines 117–134) and `sec_loader` (lines 98–114) pass the full graph apparatus (`schemas`, `type_map`, `node_vocab`, `edge_vocab`, `adjacency`) → these examples DO sample metapaths (`MiniBatch.sample_metapaths=True`).
- `dev_loader`, `test_loader`, `infer_loader` (lines 136–175) pass **only `label_vocab` + max_segments** — **NO graph args**. So for dev/test/infer facts, `MiniBatch.sample_metapaths` is False and **no fact graph features are computed**.

Consequence in `model.py` forward (lines 62–77): `if fact_batch.sample_metapaths: ... else: struct_logits = None`. For a **test/unseen fact** only the **text encoder** runs; its representation is matched against the Sections' **text AND structural** embeddings via the `attr` and `align` heads. The Sections are always in the graph (fixed, known label set), so their rich structural embeddings are always available. This is precisely **inductive link prediction**: new Fact nodes (not in the graph, no citation edges) get linked to existing Section nodes purely from fact text matched into the pre-learned joint text/structure space.

This is the single most important transferable idea for TraLuat: **statutes are a fixed, graph-resident label universe with hierarchy embeddings; incoming judgments are text-only and never need to be in the graph.**

**How fact text is matched to sections:** via `MatchNet` (§3) — not a simple dot-product. The section reps are run through a BiLSTM+attention conditioned on a fact-derived dynamic context vector (`attr_match_context = match_context_transform(fact_attr_hidden)`, `model.py` line 47), then concatenated with the fact rep and linearly projected to a per-section logit. So "matching" is a learned, fact-conditioned read over section representations.

---

## 5. Training signal — positives and negatives

- **Positive link** = a (Fact, Section) pair where the case document cites that Section. These come from TWO places that must agree:
  - the `labels` field of each fact instance in the `.jsonl` (gold multi-hot target for BCE),
  - the **citation_network** edges (Fact→Section) that put the training fact into the graph so its metapaths reach the cited Sections.
- **Negatives:** there is **no explicit negative sampling**. It is full multi-label BCE over all `L` Sections — every non-cited Section is an implicit negative for that fact (dense negative signal). Class imbalance (few positives per fact) is handled by `pos_weight` (TWS/VWS), not by sampling. (Contrast: the RotatE graph embeddings are learned jointly inside the supervised objective, not via a separate KG negative-sampling loss.)
- **Metapath sampling** (`data_helper.py::generate_metapaths`, 149–173) randomly samples `num_mpath_samples` (=8) instances per schema with `adjacency[keys].sample(num_neighbors=1, ...)` — stochastic graph context, averaged. This is the only "sampling" and it is over graph neighbours, not negatives.
- Model selection: best **dev loss** (`run.py` 222–225); metrics = macro/micro P/R/F1 + Jaccard (`helper.py::MultiLabelMetrics`).

---

## 6. Concrete mapping to TraLuat (Vietnamese civil-law)

### Direct correspondence
| LeSICiN | TraLuat |
|---|---|
| Act | Bộ luật / Luật |
| Chapter | Chương |
| Topic | Mục (and/or Tiểu mục) |
| Section (label/leaf) | Điều — or Khoản if you want finer leaves |
| Fact (case doc) | Judgment facts (nội dung vụ việc / phần "Nhận định") |
| Fact→Section citation | Judgment → Điều/Khoản áp dụng |
| label tree | Bộ luật→Chương→Mục→Điều(→Khoản) hierarchy |

The civil-law hierarchy is actually **cleaner** than the IPC one (strict Bộ luật→Chương→Mục→Điều→Khoản), so the label-tree edge file is mechanical to build from structured statute data. TraLuat already needs this hierarchy for L3; LeSICiN's `(src_id, rel, trg_id)` triple format is a good serialization target.

### REIMPLEMENT (the durable ideas)
1. **The heterogeneous graph schema** (`helper.py::generate_graph`): per-type node vocab, relation-keyed sparse adjacency, hierarchy-tree edges + citation edges concatenated into one graph. Keep the 5-type design (map Topic→Mục). The idea "the label set lives in the graph with hierarchy context; queries are text-only nodes" is the core.
2. **Inductive design** (§4): judgments never need to be graph nodes at inference — exactly what a production legal engine needs (new judgments arrive constantly). Keep this strictly.
3. **Hierarchy-aware matching via the `align` head**: match judgment text against a statute representation that encodes *where the Điều sits in the hierarchy*, not just its text. This disambiguates near-duplicate Điều across different Chương/Bộ luật. Worth preserving conceptually even if you replace the encoder.
4. **Multi-label + class-imbalance weighting** (BCE + pos_weight): a judgment cites a *set* of Điều; frequency is very skewed (a few Điều dominate). TWS clamp is a cheap, effective trick.
5. **Metapath-based hierarchy encoding** as a design option — though see "replace" below.

### REPLACE / MODERNIZE
1. **Text encoder: HAN (BiLSTM word→sent→doc) + Sent2Vec → `bge-m3` (or Vietnamese-tuned) embeddings.** Sent2Vec (`run.py` lines 31–33, 8-era) is obsolete; HAN is a 2017-era architecture. Use a modern multilingual encoder for both judgment text and Điều text. `hidden_size=200` tied to Sent2Vec dim → becomes the embedding dim (1024 for bge-m3).
2. **Graph encoder: MAGNN+RotatE → a modern hetero-GNN (HGT/R-GCN) OR skip the GNN entirely.** The RotatE rotational encoding (`submodules.py` 81–96) is clever but heavy and pre-LLM. With strong text embeddings, a lighter hierarchy encoder (e.g. sum of ancestor embeddings, or a small R-GCN over the tree) may match it. Consider: embed each Điều's text with bge-m3, then add a learned hierarchy-position signal — far simpler than metapath sampling.
3. **Matching: learned MatchNet → bi-encoder retrieval (cosine over bge-m3) + optional cross-encoder re-rank.** Modern retrieval handles the "fact text → statute" match better and scales to thousands of Điều. The fixed-label BCE-over-all-classes approach (`model.py` 80) does not scale to the full VN statute corpus (tens of thousands of Điều); you need retrieval, not dense classification.
4. **ADD effective-date / temporal awareness — LeSICiN has NONE.** The biggest gap for Vietnamese law: statutes are amended/repealed, and a judgment must link to the Điều version *in force on the judgment's date*. LeSICiN's graph is a single static snapshot with no time dimension. TraLuat must: (a) version the statute nodes (hiệu lực from/to), (b) filter candidate Điều by the judgment date, (c) possibly store supersession edges (sửa đổi/bãi bỏ) as a new relation type. This is net-new, not a modification.

### Honest weaknesses / dated aspects
- **Static single-snapshot graph** — no temporal/versioning (critical miss for VN, see above).
- **Pre-LLM stack** — Sent2Vec + HAN + custom RotatE MAGNN; all superseded by transformer embeddings. The whole `model/` tree is a reimplementation target, not reusable code.
- **Fixed, modest label set** — IPC has a few hundred Sections; dense BCE over all labels works there but will NOT scale to the full VN statute universe. LeSICiN sidesteps retrieval entirely. TraLuat likely needs a retrieve-then-classify pipeline.
- **`num_epochs: 2`, `max_segments: 128` in the committed config** are clearly a smoke-test config, not the paper's; don't read numbers off `hyperparams.json` as tuned values.
- **Data not in repo** — all `.jsonl`, edge files, and `ils2v.bin` Sent2Vec model come from Zenodo; the clone is code-only. Exact graph statistics / metapath schemas can only be confirmed by pulling the Zenodo archive (not done here, per read-only scope).
- **Directed-edge fragility** — metapaths traverse only in stored edge direction; building the edge files wrong silently breaks structural encoding. For TraLuat, be deliberate about including both parent→child and child→parent hierarchy edges if metapaths need to walk both ways.
- **No explicit negatives / hard-negative mining** — fine for dense classification, but if TraLuat moves to retrieval, hard-negative mining (e.g. sibling Điều in the same Chương) becomes important and is absent here.

### Suggested TraLuat L3 adaptation sketch
1. Build the statute hetero-graph from structured VN law: nodes {Bộ luật, Chương, Mục, Điều, Khoản}, tree edges, **plus temporal attributes and supersession edges**.
2. Embed every Điều/Khoản (text) with bge-m3; add a hierarchy-position embedding (ancestors).
3. Index statute embeddings; at query time embed judgment facts (bge-m3), **filter candidates by judgment date**, retrieve top-k Điều, optionally cross-encode re-rank.
4. Keep LeSICiN's conceptual "align text to hierarchy-aware statute representation" as the re-ranker's feature; keep multi-label output (a judgment cites a set).
5. Supervision = existing judgment→Điều citations (positives); mine hard negatives from sibling Điều. Evaluate with the same macro/micro F1 + Jaccard as LeSICiN for comparability.
```
```

**Bottom line:** LeSICiN's transferable blueprint for TraLuat L3 is (a) the heterogeneous statute graph schema that puts the hierarchy and the label leaves in one graph, (b) the inductive stance — queries (judgments) are text-only and never graph-resident, statutes are the fixed graph-resident label universe, and (c) hierarchy-aware text↔structure matching. Everything in `model/` (Sent2Vec, HAN, RotatE-MAGNN, dense BCE-over-all-labels matcher) is dated and should be replaced with modern embeddings + retrieval. The one thing LeSICiN entirely lacks and TraLuat must add is temporal/effective-date awareness of statutes.
