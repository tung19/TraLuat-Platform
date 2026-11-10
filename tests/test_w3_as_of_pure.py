"""resolve_as_of — event-date-first + lex-mitior + HITL (pure)."""

import datetime as dt

from traluat.w3 import resolve_as_of

D = dt.date


def test_event_date_explicit_wins():
    p = resolve_as_of("tranh chấp hợp đồng", "dan_su", event_date=D(2018, 5, 1))
    assert p.primary == D(2018, 5, 1) and p.anchors == [D(2018, 5, 1)]
    assert not p.needs_human and not p.lenient_fetch


def test_event_date_from_query():
    assert resolve_as_of("hợp đồng ký ngày 15 tháng 6 năm 2019").primary == D(2019, 6, 15)
    assert resolve_as_of("sự kiện 15/6/2019").primary == D(2019, 6, 15)
    assert resolve_as_of("trong năm 2019").primary == D(2019, 1, 1)


def test_lex_mitior_adds_now_anchor():
    p = resolve_as_of("hành vi năm 2019", "hinh_su", today=D(2026, 1, 1))
    assert p.anchors == [D(2019, 1, 1), D(2026, 1, 1)]
    assert p.lenient_fetch and "lex_mitior" in p.reason


def test_no_event_date_criminal_needs_human():
    p = resolve_as_of("có phạm tội không", "hinh_su", today=D(2026, 1, 1))
    assert p.needs_human and "HITL" in p.reason


def test_no_event_date_general_falls_back_today():
    p = resolve_as_of("quy định hiện hành", "general", today=D(2026, 1, 1))
    assert p.primary == D(2026, 1, 1) and not p.needs_human
