"""Model-tier router (pure — không cần model/API)."""

from traluat.w3.routing import HAIKU, OPUS, SONNET, route


def test_route_by_node():
    assert route("answer").model == OPUS and route("answer").effort == "high"
    assert route("adjudicator").model == OPUS          # phán quyết nặng
    assert route("auditor.element").model == SONNET    # bulk → rẻ hơn
    assert route("route").model == HAIKU               # phân loại rẻ nhất
    assert route("khong_biet").model == OPUS           # default an toàn


def test_sensitive_routes_local():
    c = route("answer", sensitive=True)
    assert c.provider == "local"                       # dữ liệu khách → vLLM trong VN
