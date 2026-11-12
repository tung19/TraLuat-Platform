"""Ollama/local OpenAI-compatible inference, with strict evidence-shaped output."""
from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlsplit

import httpx

from .gateway import _SYSTEM_VI, BaseLLMGateway, NotConfigured
from .ports import Citation


class LocalModelError(RuntimeError):
    """Safe error code only; do not return provider bodies or client prompts."""


class DisabledLLMGateway(BaseLLMGateway):
    def healthy(self):
        return False

    def _draft(self, *args, **kwargs):
        raise NotConfigured("local model is not configured")


_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "text": {"type": "string"},
        "citations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {key: {"type": "string"} for key in ("unit_eid", "claim", "quote")},
            "required": ["unit_eid", "claim", "quote"],
        }},
    },
    "required": ["text", "citations"],
}


class LocalLLMGateway(BaseLLMGateway):
    """Configured private endpoint only; no redirects, proxies or cloud fallback.

    Ollama mode additionally checks model metadata for remote/cloud routing.
    Generic compatible servers must be operated locally by the deployer.
    """

    def __init__(self, *, base_url: str, model: str, backend="ollama", api_key="",
                 timeout=90.0, max_tokens=2048, max_prompt_chars=24000, transport=None):
        super().__init__()
        parts = urlsplit(base_url)
        host = parts.hostname or ""
        try:
            address = ipaddress.ip_address(host)
            private = address.is_loopback or any(address in ipaddress.ip_network(n) for n in (
                "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"))
        except ValueError:
            private = host in {"localhost", "host.docker.internal"}
        if (parts.scheme not in {"http", "https"} or not private or parts.username
                or parts.password or parts.query or parts.fragment or parts.path.rstrip("/") != "/v1"):
            raise ValueError("local base URL must be a private /v1 endpoint without credentials")
        if not model.strip() or "cloud" in model.lower() or backend not in {"ollama", "compatible"}:
            raise ValueError("a local model name and supported backend are required")
        if not 0 < timeout <= 300 or not 1 <= max_tokens <= 8192:
            raise ValueError("invalid local model limits")
        self.base_url, self.model, self.backend = base_url.rstrip("/"), model, backend
        self.api_key, self.timeout, self.max_tokens = api_key, timeout, max_tokens
        self.max_prompt_chars, self.transport = max_prompt_chars, transport

    def model_name(self):
        return self.model

    def cache_identity(self, node):
        return f"{self.base_url}:{self.backend}:{self.model}:{self.max_tokens}"

    def _request(self, method, url, *, body=None, probe=False):
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with httpx.Client(timeout=3.0 if probe else self.timeout, trust_env=False,
                              follow_redirects=False, transport=self.transport) as client:
                response = client.request(method, url, json=body, headers=headers)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LocalModelError("local_model_unavailable") from exc

    def healthy(self):
        try:
            if self.backend == "ollama":
                meta = self._request("POST", self.base_url.removesuffix("/v1") + "/api/show",
                                     body={"model": self.model}, probe=True)
                return (isinstance(meta, dict) and bool(meta.get("model_info"))
                        and not meta.get("remote_host") and not meta.get("remote_model"))
            models = self._request("GET", self.base_url + "/models", probe=True)
            return any(m.get("id") == self.model for m in models.get("data", []))
        except (LocalModelError, TypeError, AttributeError):
            return False

    def generate(self, *args, **kwargs):
        # No cross-request caching of client-sensitive question/answer content.
        # Base implementation's transient cache is removed even on errors.
        try:
            return super().generate(*args, **kwargs)
        finally:
            self._cache.clear()

    def _draft(self, query, chunks, prompt, as_of, node, lang):
        if not chunks:
            return "", []
        if len(prompt) > self.max_prompt_chars:
            raise LocalModelError("context_too_large")
        if not self.healthy():
            raise LocalModelError("local_model_unavailable")
        instruction = (_SYSTEM_VI + " Ưu tiên trả lời bằng nguyên câu đầy đủ trong nguồn nếu câu "
                       "đó đã giải đáp câu hỏi. Khi trích nguyên văn, text, claim và quote phải "
                       "giống nhau tuyệt đối. Giữ mọi điều kiện, ngoại lệ, phủ định và đơn vị "
                       "thời gian. Không được rút ngắn câu quote. claim phải xuất hiện nguyên "
                       "văn trong text. Trả JSON đúng schema. Trả lời ngắn, không tiêu đề, không "
                       "Markdown, không tự thêm ký hiệu trích dẫn trong text. Mỗi câu phải có "
                       "claim khớp nguyên câu và quote nguyên câu nguồn. Không đủ thông tin "
                       "để trả lời câu hỏi thì trả text rỗng và citations rỗng.")
        payload = self._request("POST", self.base_url + "/chat/completions", body={
            "model": self.model, "temperature": 0, "max_tokens": self.max_tokens,
            "stream": False,
            "messages": [{"role": "system", "content": instruction},
                         {"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "grounded_answer", "strict": True, "schema": _SCHEMA}},
        })
        try:
            choice = payload["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise ValueError("incomplete model output")
            data = json.loads(choice["message"]["content"])
            if (set(data) != {"text", "citations"} or not isinstance(data["text"], str)
                    or not isinstance(data["citations"], list) or len(data["citations"]) > 64):
                raise ValueError("invalid output shape")
            citations = []
            for c in data["citations"]:
                if (not isinstance(c, dict) or set(c) != {"unit_eid", "claim", "quote"}
                        or not all(isinstance(v, str) and v.strip() for v in c.values())):
                    raise ValueError("invalid citation")
                citations.append(Citation(c["unit_eid"], as_of, c["claim"], c["quote"]))
            return data["text"], citations
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise LocalModelError("invalid_model_output") from exc
