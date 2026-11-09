# TraLuat — Hạ tầng triển khai (deployment)

> Topology vật lý: tách **batch / online / data / model-serving**, đặt tại **VN**, residency + tenant isolation theo NĐ 356/2025.
> Điểm xuất phát đã verify: PAKTON `docker-compose.yml:11-95` (rabbitmq/redis/api/worker/postgres:15-alpine/chroma) = dev một-node → ta productionize.
> Giả định: đội mạnh & đông (chạy full stack), pháp nhân VN OK. Đọc kèm `specs/stack-db-and-models.md`, `platform-architecture-audit.md`.

---

## 1. Sơ đồ triển khai

```mermaid
flowchart TB
  subgraph VN[REGION: Việt Nam — ranh giới cư trú dữ liệu]
    subgraph EDGE[Edge]
      LB[Load Balancer / API Gateway + WAF]
    end
    subgraph ONLINE[Online plane - stateless, autoscale]
      API[FastAPI x N]
      WFsvc[Workflow/Reasoning svc]
      RETsvc[Retrieval svc]
      GNDsvc[Grounding/Verify svc]
      GW[LLM Gateway svc]
    end
    subgraph BATCH[Batch plane]
      TMP[Temporal workers]
      OCRw[OCR/Parse workers GPU]
      EXTw[Extractor workers GPU]
      IDXw[Index/Embed workers GPU]
    end
    subgraph MODEL[Model serving - GPU pool]
      VLLM[vLLM: LLM local - tenant nhạy cảm]
      EMB[bge-m3 embed server TEI]
      RRK[bge-reranker server]
      NLI[NLI/extractor server]
    end
    subgraph DATA[Data plane - stateful, HA]
      PG[(Postgres HA: primary+replica, PITR)\nSoR bitemporal + pgvector + FK/CTE graph]
      OBJ[(MinIO/S3 - PDF gốc)]
      RDS[(Redis - cache/queue)]
      CKP[(Postgres checkpointer)]
      TEN[(Tenant store - RLS + mã hoá KMS)]
    end
    subgraph OPS[Governance/Ops]
      OTEL[OTel collector + metrics + logs + cost]
      KMS[KMS/Vault - key-per-tenant]
      HITL[HITL console]
    end
  end
  CLAUDE[[Claude API - NGOÀI VN]]

  LB-->API-->WFsvc-->RETsvc-->GNDsvc
  WFsvc-->GW
  GW-->|KB luật công / tenant đã consent| CLAUDE
  GW-->|dữ liệu khách nhạy cảm| VLLM
  RETsvc-->PG & EMB & RRK
  GNDsvc-->PG & NLI
  TMP-->OCRw & EXTw & IDXw
  OCRw & EXTw & IDXw-->PG & OBJ
  EXTw-->EMB & NLI
  ONLINE-.->OTEL
  DATA-.->KMS
```

---

## 2. Các mặt phẳng (plane)

### 2.1 Online (stateless, autoscale thoải mái)
- **FastAPI x N** sau LB/WAF; resolve tenant + authn; fail-closed nếu thiếu tenant.
- **Workflow / Retrieval / Grounding / LLM-Gateway** = service tách (hoặc module trong một app lúc đầu, tách khi tải lớn). Stateless → scale ngang tự do.
- Đọc Postgres **replica** cho retrieval; ghi (hiếm, chỉ audit/session) vào primary.

### 2.2 Batch (nạp dữ liệu)
- **Temporal** điều phối pipeline 8-stage (durable, resume, checkpoint HITL).
- **Worker GPU** cho OCR / extractor / embed — tách khỏi online để không giành tài nguyên.
- Chạy theo đợt (nạp corpus mới, nạp sửa đổi) → kích hoạt **Change-Propagation** (§platform-audit §7).

### 2.3 Data (stateful, HA)
- **Postgres HA**: primary + ≥1 replica, **PITR** (point-in-time recovery), backup định kỳ. Chứa SoR bitemporal + pgvector + graph FK/CTE.
- **MinIO/S3 (tại VN)**: PDF/scan gốc + hash.
- **Redis**: cache nóng + broker.
- **Checkpointer (Postgres)**: lịch sử agent/hội thoại (no-persist mode cho tenant zero-retention).
- **Tenant store**: dữ liệu khách, **RLS/schema-per-tenant + mã hoá key-per-tenant (KMS)**.

### 2.4 Model serving (GPU pool)
- **vLLM**: LLM mở (Qwen/Llama) cho tenant yêu cầu xử lý trong nước. Cắm Gateway qua `endpoint_url`.
- **bge-m3** (embed, qua TEI/Triton) · **bge-reranker** · **NLI/extractor** · **OCR**. Tất cả **local, trong VN**.

### 2.5 Governance/Ops
- **OTel collector** → metrics/logs/trace + **cost theo tenant**.
- **KMS/Vault** → secret + key-per-tenant.
- **HITL console** → hàng chờ duyệt, chữ ký.

---

## 3. ĐIỂM NHẠY NHẤT — định tuyến LLM theo phân loại dữ liệu

**Căng thẳng:** Claude API đặt **ngoài VN**; NĐ 356/2025 coi xử lý dữ liệu cá nhân trên hạ tầng ngoài nước là **chuyển dữ liệu xuyên biên giới**. Nhưng **KB luật là dữ liệu CÔNG** (không phải dữ liệu cá nhân) → gửi sang Claude *không* vướng. Vướng là ở **văn bản hợp đồng/bản án của khách**.

**Giải: LLM Gateway định tuyến theo nhãn dữ liệu (data-classification routing):**

| Loại dữ liệu trong prompt | Route | Căn cứ |
|---|---|---|
| **Chỉ KB luật công** (Assistant tra luật, trích điều khoản) | **Claude API** (ngoài VN) | dữ liệu công, không phải PDPD |
| **Dữ liệu khách nhạy cảm** (hợp đồng, bản án chưa ẩn danh, PII) | **vLLM local trong VN** | residency NĐ 356/2025 |
| Khách đã ký **consent + TIA** cho chuyển xuyên biên | Claude API (có hồ sơ) | ngoại lệ hợp pháp |

→ Gateway phải **phân loại prompt trước khi gọi**, chặn rò dữ liệu khách ra API ngoài (guard), và **gắn nhãn AI** (Luật 71/2025) ở đầu ra. Đây là ranh giới residency chạy *bên trong* Gateway, không chỉ ở network.

---

## 4. Multi-tenancy & residency ở tầng hạ tầng
- **KB luật** = dịch vụ/kho **chia sẻ, read-only**, không gắn tenant.
- **Dữ liệu khách** = cô lập cứng: RLS hoặc schema-per-tenant; **mã hoá envelope key-per-tenant (KMS)**; tuỳ chọn **zero-retention** (checkpointer no-persist).
- **Mọi kho + mọi model local đặt tại VN.** Chỉ Claude API là egress có kiểm soát (chỉ dữ liệu công / đã consent).
- Network: segment batch/online/data; chỉ Gateway được egress ra Claude API; worker/DB không egress.

---

## 5. Môi trường & CI
- **dev / staging / prod**; prod tại VN.
- **CI cổng chất lượng (L13):** benchmark 3 chiều (đúng điều–khoản/đúng hiệu lực/bắt bỏ sót) chạy trên tập vàng + diskcache tất định → **fail-closed** nếu dưới threshold hoặc tụt so baseline. Không qua cổng = không deploy.
- IaC (Terraform/Helm) + container; GPU pool tách node.

---

## 6. Lộ trình hạ tầng (bám roadmap)
| Phase | Hạ tầng tối thiểu |
|---|---|
| 0–1 (nền + MVP) | 1 Postgres (pgvector) + 1 GPU node (embed+OCR) + API/worker + MinIO + Redis; Claude API cho LLM; **chưa cần vLLM** |
| 2 (trust) | Postgres HA + KMS + RLS tenant + OTel + CI gate |
| 3+ (Judgment, nhạy cảm) | **vLLM local** + data-classification routing + Change-Propagation/Notification |
| 5 (diện rộng) | autoscale online + GPU pool lớn + multi-jurisdiction routing |

> Lưu ý: PAKTON `docker-compose` (rabbitmq/redis/api/worker/postgres/chroma, một-node) là **điểm xuất phát dev tốt** — productionize: tách GPU pool, Postgres HA, bỏ Chroma (dùng pgvector), thêm Temporal + KMS + data-classification routing.
