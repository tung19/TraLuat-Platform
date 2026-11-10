"""L1 Acquisition (thu nạp nguồn) — cổng license/terms + provenance + dedup.

Nguồn luật VN có rào pháp lý: CHỈ nguồn chính thức (vbpl.vn · Công báo · phapluat.gov.vn
· cổng TANDTC); TUYỆT ĐỐI loại aggregator (thuvienphapluat/luatvietnam/lawnet — ToS).
Mỗi blob ghi provenance + content-hash (blake2) → dedup. Đây là bề mặt rủi ro TÁCH
khỏi xử lý (W1 stage sau). FileDropConnector = nạp file đội data đã lấy hợp pháp.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable
from urllib.parse import urlparse

# Nguồn CHÍNH THỨC được phép (host). Mở rộng qua JurisdictionPack sau.
OFFICIAL_HOSTS = {
    "vbpl.vn", "congbao.chinhphu.vn", "phapluat.gov.vn",
    "congbobanan.toaan.gov.vn", "anle.toaan.gov.vn", "chinhphu.vn",
}
# Aggregator bị CHẶN (ToS — không scrape).
BLOCKED_HOSTS = {"thuvienphapluat.vn", "luatvietnam.vn", "lawnet.vn", "lawnet.thuvienphapluat.vn"}


@dataclass
class AcquiredBlob:
    source: str                 # tên nguồn
    source_url: str | None      # URL gốc (nếu có) → kiểm license theo host
    blob: bytes                 # nội dung thô
    content_hash: str = ""      # blake2b (dedup + provenance)
    acquired_at: dt.date | None = None

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.blake2b(self.blob, digest_size=32).hexdigest()


@runtime_checkable
class SourceConnector(Protocol):
    def fetch(self) -> Iterable[AcquiredBlob]: ...


class FileDropConnector:
    """Nạp file đội data đã lấy hợp pháp (không tự fetch — tránh ToS)."""
    def __init__(self, directory: str | Path, source: str = "file-drop",
                 source_url: str | None = None) -> None:
        self.dir = Path(directory)
        self.source = source
        self.source_url = source_url

    def fetch(self) -> Iterable[AcquiredBlob]:
        for p in sorted(self.dir.glob("*")):
            if p.is_file():
                yield AcquiredBlob(self.source, self.source_url, p.read_bytes(),
                                   acquired_at=dt.date.today())


class LicenseGate:
    """Cổng license/terms — chỉ cho nguồn chính thức, chặn aggregator."""
    def __init__(self, official: set[str] | None = None, blocked: set[str] | None = None) -> None:
        self.official = official or OFFICIAL_HOSTS
        self.blocked = blocked or BLOCKED_HOSTS

    def check(self, blob: AcquiredBlob) -> tuple[bool, str]:
        # removeprefix (KHÔNG lstrip — lstrip xoá mọi ký tự w/. : 'worldbank'→'orldbank').
        host = urlparse(blob.source_url).netloc.lower().removeprefix("www.") if blob.source_url else ""
        if host in self.blocked:
            return False, f"aggregator bị chặn (ToS): {host}"
        if blob.source_url and host not in self.official:
            return False, f"nguồn không trong danh sách chính thức: {host}"
        return True, "ok"          # file-drop (không URL) → tin đội data đã kiểm


@dataclass
class AcquireOutcome:
    accepted: list[AcquiredBlob] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)   # (source, lý do)
    provenance: list[dict] = field(default_factory=list)            # ghi chép nguồn gốc


def acquire(connector: SourceConnector, gate: LicenseGate | None = None,
            seen_hashes: set[str] | None = None) -> AcquireOutcome:
    """Thu nạp: cổng license → dedup content-hash → ghi provenance. Chỉ accepted mới
    đi tiếp vào xử lý (W1 stage sau)."""
    gate = gate or LicenseGate()
    seen = seen_hashes if seen_hashes is not None else set()
    out = AcquireOutcome()
    for blob in connector.fetch():
        ok, reason = gate.check(blob)
        if not ok:
            out.rejected.append((blob.source, reason))
            continue
        if blob.content_hash in seen:            # dedup (đã nạp)
            out.rejected.append((blob.source, "trùng content-hash (đã nạp)"))
            continue
        seen.add(blob.content_hash)
        out.accepted.append(blob)
        out.provenance.append({"source": blob.source, "url": blob.source_url,
                               "hash": blob.content_hash,
                               "acquired_at": blob.acquired_at.isoformat() if blob.acquired_at else None})
    return out
