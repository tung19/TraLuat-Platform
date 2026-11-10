# TraLuat Postgres — pgvector (L4 HNSW) + PostGIS (FR-39 geo danh bạ) trong 1 image.
# Base = pgvector image (postgres:16 bookworm, đã có `vector`); thêm PostGIS từ PGDG.
FROM pgvector/pgvector:pg16
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-16-postgis-3 postgis \
 && rm -rf /var/lib/apt/lists/*
