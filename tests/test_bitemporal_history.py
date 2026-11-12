from datetime import UTC, date, datetime

from traluat.w2.bitemporal import UnitVersion, apply_amendment, reconstruct_as_of


def at(year):
    return datetime(year, 1, 1, tzinfo=UTC)


def test_split_and_same_date_replacement_preserve_previous_beliefs():
    versions = [UnitVersion("e", "vi", date(2020, 1, 1), None, "A", tx_from=at(2020))]
    apply_amendment(versions, "e", "B", date(2024, 1, 1), now=at(2023), order_key=1)
    assert reconstruct_as_of(versions, "e", date(2025, 1, 1), known_as_of=at(2022)) == "A"
    apply_amendment(versions, "e", "C", date(2024, 1, 1), now=at(2024), order_key=2)
    assert reconstruct_as_of(versions, "e", date(2025, 1, 1), known_as_of=at(2023)) == "B"
    assert reconstruct_as_of(versions, "e", date(2025, 1, 1), known_as_of=at(2025)) == "C"


def test_replay_identity_is_scoped_to_unit_and_language_even_after_supersession():
    versions = [UnitVersion(eid, lang, date(2020, 1, 1), None, "A", tx_from=at(2020))
                for eid, lang in [("e", "vi"), ("f", "vi"), ("e", "en")]]
    for eid, lang in [("e", "vi"), ("f", "vi"), ("e", "en")]:
        apply_amendment(versions, eid, "B", date(2024, 1, 1), lang=lang,
                        source_relation_id="same", now=at(2023))
        assert reconstruct_as_of(versions, eid, date(2025, 1, 1), lang, at(2025)) == "B"
    apply_amendment(versions, "e", "C", date(2024, 1, 1), order_key=2, now=at(2024))
    count = len(versions)
    apply_amendment(versions, "e", "B", date(2024, 1, 1), source_relation_id="same", now=at(2025))
    assert len(versions) == count
    assert reconstruct_as_of(versions, "e", date(2025, 1, 1), known_as_of=at(2025)) == "C"


def test_earlier_discovered_segment_stops_at_next_known_segment():
    versions = [UnitVersion("e", "vi", date(2024, 1, 1), None, "B", tx_from=at(2020))]
    apply_amendment(versions, "e", "A", date(2022, 1, 1), now=at(2023))
    assert reconstruct_as_of(versions, "e", date(2023, 1, 1), known_as_of=at(2025)) == "A"
    assert reconstruct_as_of(versions, "e", date(2025, 1, 1), known_as_of=at(2025)) == "B"
