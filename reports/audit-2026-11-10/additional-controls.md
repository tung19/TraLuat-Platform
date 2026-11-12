# Additional model / readiness audit (read-only)

## Model supply-chain controls not enforced (no exploit claim)

- Policy: docs/security.md:35–41 requires safetensors only, explicit restricted loading, commit revision and SHA-256 verification, approved local mirror, sandbox worker.
- src/traluat/w3/embed_bge.py:25 constructs SentenceTransformer(model_name, device=device), no revision, checksum, local_files_only or explicit use_safetensors enforcement.
- src/traluat/w3/nli_xnli.py:24–25 calls AutoTokenizer/AutoModel.from_pretrained(model_name), no revision, checksum, local_files_only or explicit safetensors enforcement.
- src/traluat/w1/ocr_vietocr.py:30–33 loads named remote config and passes to VietOCR Predictor without local artifact validation.
- Installed dependency evidence (not repository-owned implementation): .venv/lib/python3.12/site-packages/vietocr/tool/config.py:30–32 downloads configs; utils.py:34–38 fetches https://vocr.vn/data/vietocr/config/<id>; predictor.py:15–20 downloads weights then torch.load; utils.py:20–22 reuses existing temp file by basename without digest validation.
- No model execution, network fetch, pickle exploit, dependency CVE assessment or production deployment test was performed in this pass. Modern torch defaults may restrict deserialization; do not claim proven arbitrary code execution. Missing pins/integrity checks and contradiction with safetensors-only policy are directly observed.

## Retrieval / evaluation implementation gaps

- docs/feature-registry.md:39 says FR-10 DONE (hybrid BM25+bge+RRF+rerank).
- src/traluat/w3/orchestrator.py:71 and src/traluat/w4/reasoner.py:94 call retrieve without an embedder. The serving path remains lexical and builds chunks across the corpus. retrieve_indexed has no source caller outside tests.
- Reranker is only a Protocol plus NoopReranker; no rerank invocation in application source.
- .github/workflows/ci.yml:29 installs core/dev without model extras. eval/gold/smoke.jsonl contains two synthetic cases only; tests/test_pg_eval_gold.py:42 uses EchoLLMGateway and :49 gates article recall only.
- docs/specs/performance.md:128–132 requires ANN recall-oracle calibration and no skipping rerank in high-stakes cases. No tests for recall-oracle floor, high-stakes rerank enforcement, or measured p95/p99 were found.
- tests/test_pg_phase_d_followup.py:57–70 is a useful narrow two-date fixture for indexed/non-indexed version presence; it does not establish byte-identical complete result equivalence or general recall guarantees.
- Treat these as readiness/scaffold gaps, not production latency measurements or proven security exploits.

## Extra static trace: unreviewed graph edges

- src/traluat/w2/repo.py:492–496 multihop filters relationship type/date but not review_status.
- src/traluat/w2/graph_neo4j.py:27–31 projects all review statuses; Neo4jGraphStore.multihop around :118–123 also ignores status.
- src/traluat/w4/reasoner.py:107 consumes these graph expansions. Auditor validates target article existence/effectivity/elements, never the edge's review status. Missing article checklist is treated applicable by src/traluat/w4/auditor.py:63–64.
- Potential consequence: rejected or pending cites/guides can influence the verified candidate set. This was statically traced; no separate Postgres end-to-end output proof was run for this finding.
