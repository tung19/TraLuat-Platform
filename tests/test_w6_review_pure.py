"""W6 ReviewService — bắt điều khoản bỏ sót (pure)."""

from traluat.w6 import RequiredClauseRule, ReviewService

_RULES = [
    RequiredClauseRule("bảo mật", ["bảo mật", "giữ bí mật"]),
    RequiredClauseRule("giải quyết tranh chấp", ["trọng tài", "tòa án có thẩm quyền"]),
    RequiredClauseRule("bất khả kháng", ["bất khả kháng", "force majeure"]),
]


def test_review_flags_missing_clauses():
    contract = ("Hợp đồng dịch vụ. Hai bên cam kết bảo mật thông tin. "
                "Tranh chấp giải quyết tại tòa án có thẩm quyền.")
    f = {r.rule: r.status for r in ReviewService().review(contract, _RULES)}
    assert f["bảo mật"] == "present"
    assert f["giải quyết tranh chấp"] == "present"
    assert f["bất khả kháng"] == "missing"        # bỏ sót → cờ
