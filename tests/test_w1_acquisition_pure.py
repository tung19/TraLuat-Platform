"""L1 Acquisition — cổng license + dedup + provenance (pure)."""

from traluat.w1.acquisition import AcquiredBlob, LicenseGate, SourceConnector, acquire


class _Conn:
    def __init__(self, blobs):
        self._b = blobs
    def fetch(self):
        return list(self._b)


def test_blocks_aggregator_allows_official():
    gate = LicenseGate()
    agg = AcquiredBlob("TVPL", "https://thuvienphapluat.vn/x", b"noi dung")
    off = AcquiredBlob("vbpl", "https://vbpl.vn/y", b"van ban")
    out = acquire(_Conn([agg, off]), gate)
    assert [b.source for b in out.accepted] == ["vbpl"]
    assert any("aggregator" in r for _, r in out.rejected)       # TVPL bị chặn (ToS)


def test_dedup_by_content_hash():
    b1 = AcquiredBlob("file", None, "cùng nội dung".encode())
    b2 = AcquiredBlob("file", None, "cùng nội dung".encode())            # trùng hash
    out = acquire(_Conn([b1, b2]))
    assert len(out.accepted) == 1 and any("trùng" in r for _, r in out.rejected)
    assert out.provenance[0]["hash"] == b1.content_hash          # provenance ghi hash


def test_unknown_url_host_rejected():
    out = acquire(_Conn([AcquiredBlob("x", "https://random-site.com/a", b"z")]))
    assert out.accepted == [] and "chính thức" in out.rejected[0][1]


def test_www_prefix_official_allowed():
    # A1-fix: removeprefix('www.') đúng — www.vbpl.vn → vbpl.vn (chính thức)
    out = acquire(_Conn([AcquiredBlob("vbpl", "https://www.vbpl.vn/x", b"z")]))
    assert len(out.accepted) == 1
