"""End-to-end (Postgres): reference-data adapter — PII gate · idempotent · hiệu-lực lookup."""

from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from tests.reference_helpers import seed_reference_sources
from traluat.tools.reference import RefRow, lookup_reference, upsert_reference
from traluat.w2.db import make_engine
from traluat.w2.models import ReferenceValue

D = dt.date


@pytest.fixture()
def session():
    try:
        conn = make_engine().connect()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"Postgres không sẵn: {e}")
    trans = conn.begin()
    if conn.execute(sa.text("select to_regclass('public.reference_value')")).scalar() is None:
        trans.rollback(); conn.close()
        pytest.skip("reference_value chưa migrate")
    s = Session(bind=conn, future=True)
    seed_reference_sources(s, ['nd99__dieu_3', 'nd50__dieu_1'])
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        conn.close()


def _count(s, dataset="muc_phat", key="hanh_vi_x"):
    # ĐẾM THEO KHOÁ (không đếm toàn bảng) → robust với seed-data đã commit; vẫn chứng
    # minh idempotent (re-upsert cùng khoá không nhân đôi).
    return s.scalar(sa.select(sa.func.count()).select_from(ReferenceValue).where(
        ReferenceValue.dataset == dataset, ReferenceValue.key == key))


def test_effectivity_aware_lookup_with_source(session: Session):
    # mức phạt hành vi X đổi theo luật: 5tr [2020,2023) → 10tr [2023,∞), CÓ nguồn điều
    rows = [RefRow("hanh_vi_x", {"muc": 5_000_000}, D(2020, 1, 1), D(2023, 1, 1), "nd99__dieu_3"),
            RefRow("hanh_vi_x", {"muc": 10_000_000}, D(2023, 1, 1), None, "nd50__dieu_1")]
    out = upsert_reference(session, "muc_phat", rows)
    assert out.loaded == 2 and out.quarantined == []

    assert lookup_reference(session, "muc_phat", "hanh_vi_x", D(2022, 1, 1)).value["muc"] == 5_000_000
    v = lookup_reference(session, "muc_phat", "hanh_vi_x", D(2024, 1, 1))
    assert v.value["muc"] == 10_000_000 and v.source_eid == "nd50__dieu_1"   # calculator có-nguồn-luật

    upsert_reference(session, "muc_phat", rows)        # idempotent → không nhân đôi
    assert _count(session) == 2


def test_pii_check_off_for_numeric_dataset(session: Session):
    # A2-fix: dataset SỐ (muc_phat) đặt pii_check=False → số tiền 12 chữ số KHÔNG bị
    # quarantine oan (100 tỷ ≈ CCCD về regex).
    out = upsert_reference(session, "muc_phat",
                           [RefRow("x", {"muc": 100_000_000_000}, D(2020, 1, 1), source_eid="nd99__dieu_3")],
                           pii_check=False)
    assert out.loaded == 1 and out.quarantined == []


def test_pii_gate_quarantines(session: Session):
    out = upsert_reference(session, "danh_ba", [
        RefRow("cb_ok", {"co_quan": "Sở KHĐT Hà Nội"}, D(2020, 1, 1)),
        RefRow("cb_pii", {"phone": "0912345678"}, D(2020, 1, 1)),   # có SĐT → giữ
    ])
    assert out.loaded == 1 and out.quarantined == ["cb_pii"]
    assert lookup_reference(session, "danh_ba", "cb_pii", D(2022, 1, 1)) is None


def test_reference_requires_known_applicable_law_source(session):
    out = upsert_reference(session, "muc_phat", [
        RefRow("missing", {"muc": 1}, D(2020, 1, 1)),
        RefRow("unknown", {"muc": 1}, D(2020, 1, 1), source_eid="not-imported"),
        RefRow("too_early", {"muc": 1}, D(1800, 1, 1), source_eid="nd99__dieu_3"),
    ], pii_check=False)
    assert out.loaded == 0 and set(out.quarantined) == {"missing", "unknown", "too_early"}


def test_published_versions_are_immutable_and_explicitly_reviewed(session):
    row = RefRow("version_test", {"muc": 100}, D(2020, 1, 1), source_eid="nd99__dieu_3")
    assert upsert_reference(session, "muc_phat", [row]).loaded == 1
    changed = RefRow("version_test", {"muc": 200}, D(2020, 1, 1), source_eid="nd99__dieu_3")
    assert upsert_reference(session, "muc_phat", [changed]).loaded == 0
    assert upsert_reference(session, "muc_phat", [changed], version="v2").loaded == 0
    assert upsert_reference(session, "muc_phat", [changed], version="v2", reviewed_change=True).loaded == 1
    assert lookup_reference(session, "muc_phat", "version_test", D(2022, 1, 1)).value["muc"] == 200
    assert lookup_reference(session, "muc_phat", "version_test", D(2022, 1, 1), version="v1").value["muc"] == 100
    # Idempotent replay of v1 does not republish it over the reviewed correction.
    upsert_reference(session, "muc_phat", [row])
    assert lookup_reference(session, "muc_phat", "version_test", D(2022, 1, 1)).value["muc"] == 200


def test_runtime_does_not_return_reference_after_its_source_expires(session):
    from traluat.w2.models import Unit, UnitVersion
    row = RefRow("expired_source", {"muc": 100}, D(2020, 1, 1), source_eid="nd99__dieu_3")
    assert upsert_reference(session, "muc_phat", [row]).loaded == 1
    unit = session.scalar(sa.select(Unit).where(Unit.eid == row.source_eid))
    version = session.scalar(sa.select(UnitVersion).where(UnitVersion.unit_id == unit.id))
    version.valid_to = D(2021, 1, 1)
    session.flush()
    assert lookup_reference(session, "muc_phat", row.key, D(2020, 6, 1)) is not None
    assert lookup_reference(session, "muc_phat", row.key, D(2022, 1, 1)) is None


def test_unknown_dataset_requires_an_explicit_contract(session):
    with pytest.raises(ValueError, match="contract"):
        upsert_reference(session, "unknown_dataset", [RefRow("x", {"rate": .1}, D(2020, 1, 1))])


def test_lookup_rejects_legacy_rows_that_bypassed_publication_validation(session):
    session.add(ReferenceValue(dataset="thue_gtgt", key="legacy_poison", value={"rate": -5},
                               valid_from=D(2020, 1, 1), version="legacy",
                               source_eid="nd99__dieu_3"))
    session.flush()
    assert lookup_reference(session, "thue_gtgt", "legacy_poison", D(2022, 1, 1)) is None


def test_concurrent_version_publication_serializes_review_check(session):
    """Two publishers cannot both pass a pre-insert overlap check for one key."""
    import uuid
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    engine = make_engine()
    if not (engine.url.database or "").endswith("_test"):
        pytest.skip("concurrency test commits only to an explicit *_test database")
    key = "concurrent_" + uuid.uuid4().hex
    first = Session(engine)
    pool = ThreadPoolExecutor(max_workers=1)
    started = Event()

    def competing_publication():
        with Session(engine) as second:
            started.set()
            outcome = upsert_reference(second, "danh_ba", [
                RefRow(key, {"co_quan": "Synthetic second publisher"}, D(2020, 1, 1))
            ], version="v2")
            second.commit()
            return outcome

    try:
        assert upsert_reference(first, "danh_ba", [
            RefRow(key, {"co_quan": "Synthetic first publisher"}, D(2020, 1, 1))
        ]).loaded == 1
        future = pool.submit(competing_publication)
        assert started.wait(2)
        with pytest.raises(TimeoutError):
            future.result(timeout=.1)  # competing transaction waits for the logical-key lock
        first.commit()
        outcome = future.result(timeout=5)
        assert outcome.loaded == 0 and outcome.quarantined == [key]
    finally:
        first.rollback()
        first.close()
        pool.shutdown(wait=True)
        with engine.begin() as connection:
            connection.execute(sa.delete(ReferenceValue).where(
                ReferenceValue.dataset == "danh_ba", ReferenceValue.key == key))
        engine.dispose()
