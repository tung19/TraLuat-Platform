"""FR-39/40 · Danh bạ địa lý — luật sư / công chứng / toà án / cơ quan (geo-aware).

Dữ liệu CÔNG (không phải dữ liệu khách) → không RLS, phục vụ RULE tier. Toạ độ lưu
PostGIS `geometry(Point,4326)` + GiST index → `nearby(lat,lon,radius_m)` KNN (`<->`).
PII gate (F5): điện thoại/email là trường liên hệ NGHIỆP VỤ (được phép), nhưng chặn
CCCD (12 số) lọt vào danh bạ công — quarantine entry thay vì publish.

geoalchemy2 là **optional** (extra `geo`); import lười để core chạy không cần PostGIS.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..w2.models import Base

# CCCD 12 số — KHÔNG được xuất hiện trong danh bạ công (khác số ĐT 10 số/email nghiệp vụ).
_CCCD = re.compile(r"\b\d{12}\b")

# Loại mục danh bạ hợp lệ (FR-39 hành nghề · FR-40 cơ quan).
DIRECTORY_KINDS = frozenset(
    {"luat_su", "cong_chung", "toa_an", "vien_ksnd", "co_quan", "thi_hanh_an"})


def _geom_col():
    """Cột geometry (lười import geoalchemy2 — chỉ cần khi bật extra `geo`)."""
    from geoalchemy2 import Geometry
    return mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)


class Directory(Base):
    """Mục danh bạ — tên, địa chỉ, liên hệ nghiệp vụ, toạ độ (tuỳ chọn)."""
    __tablename__ = "directory"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(index=True)          # DIRECTORY_KINDS
    name: Mapped[str]
    address: Mapped[str | None]
    province: Mapped[str | None] = mapped_column(index=True)  # mã/tên tỉnh (lọc nhanh)
    phone: Mapped[str | None]                               # liên hệ nghiệp vụ (được phép)
    email: Mapped[str | None]
    geom = _geom_col()
    extra: Mapped[dict | None] = mapped_column(JSONB)


class DirectoryQuarantined(ValueError):
    """Entry chứa PII cá nhân (CCCD) → không nạp vào danh bạ công."""


@dataclass
class NearbyHit:
    entry: Directory
    distance_m: float
    lat: float | None = None       # ST_Y(geom) — tiện render bản đồ
    lon: float | None = None       # ST_X(geom)


def add_directory_entry(
    session, kind: str, name: str, *, address: str | None = None,
    province: str | None = None, phone: str | None = None, email: str | None = None,
    lat: float | None = None, lon: float | None = None, extra: dict | None = None,
) -> Directory:
    """Thêm 1 mục danh bạ. Chặn CCCD (quarantine). Toạ độ (lat,lon)→geom WGS84."""
    if kind not in DIRECTORY_KINDS:
        raise ValueError(f"kind không hợp lệ: {kind}")
    blob = " ".join(x for x in (name, address, province, phone, email, str(extra or "")) if x)
    if _CCCD.search(blob):
        raise DirectoryQuarantined("chứa CCCD — không publish danh bạ công")

    geom = None
    if (lat is None) != (lon is None):
        raise ValueError("lat and lon must be supplied together")
    if lat is not None and lon is not None:
        _coordinates(lat, lon)
        geom = sa.func.ST_SetSRID(sa.func.ST_MakePoint(lon, lat), 4326)  # (x=lon, y=lat)
    row = Directory(kind=kind, name=name, address=address, province=province,
                    phone=phone, email=email, geom=geom, extra=extra)
    session.add(row)
    session.flush()
    return row


def nearby(
    session, lat: float, lon: float, radius_m: float, *,
    kind: str | None = None, limit: int = 20,
) -> list[NearbyHit]:
    """KNN danh bạ trong bán kính `radius_m` quanh (lat,lon), gần→xa. Dùng geography để
    tính mét chính xác (ST_DWithin + ST_Distance), sắp theo khoảng cách."""
    _coordinates(lat, lon)
    if not math.isfinite(radius_m) or not 0 < radius_m <= 1_000_000:
        raise ValueError("radius_m must be finite and between 0 and 1,000,000")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if kind is not None and kind not in DIRECTORY_KINDS:
        raise ValueError("invalid directory kind")
    pt = sa.func.ST_SetSRID(sa.func.ST_MakePoint(lon, lat), 4326)
    geog = _Geography()
    # ::geography → khoảng cách tính bằng MÉT (không phải độ)
    dist = sa.func.ST_Distance(sa.cast(Directory.geom, geog), sa.cast(pt, geog))
    q = (sa.select(Directory, dist.label("d"),
                   sa.func.ST_Y(Directory.geom).label("lat"),
                   sa.func.ST_X(Directory.geom).label("lon"))
         .where(Directory.geom.isnot(None))
         .where(sa.func.ST_DWithin(
             sa.cast(Directory.geom, geog), sa.cast(pt, geog), radius_m))
         .order_by(dist).limit(limit))
    if kind is not None:
        q = q.where(Directory.kind == kind)
    return [NearbyHit(entry=row, distance_m=float(d), lat=float(y), lon=float(x))
            for row, d, y, x in session.execute(q)]


def _Geography():
    from geoalchemy2 import Geography
    return Geography()


def _coordinates(lat, lon):
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("invalid WGS84 coordinates")
