"""Explicit AI runtime configuration, loaded once per application process."""
from __future__ import annotations

import os
from dataclasses import dataclass

from ..w3.gateway import EchoLLMGateway
from ..w3.local_gateway import DisabledLLMGateway, LocalLLMGateway
from ..w3.retrieval import IndexedRetriever


@dataclass
class RuntimeAI:
    gateway: object
    retriever: object
    nli: object | None = None


def load_embedder(env=None):
    env = os.environ if env is None else env
    from ..w3.embed_bge import BgeM3Embedder
    embedder = BgeM3Embedder(
        model_name=env.get("TRALUAT_EMBED_MODEL", "BAAI/bge-m3"),
        device=env.get("TRALUAT_MODEL_DEVICE") or None,
        local_files_only=env.get("TRALUAT_MODELS_OFFLINE", "1") == "1",
        revision=env.get("TRALUAT_EMBED_REVISION") or None,
    )
    if embedder.dim != 1024:
        raise ValueError("the current index requires a 1024-dimensional embedding model")
    return embedder


def load_runtime_ai(env=None) -> RuntimeAI:
    env = os.environ if env is None else env
    mode = env.get("TRALUAT_AI_MODE", "disabled")
    if mode == "disabled":
        return RuntimeAI(DisabledLLMGateway(), IndexedRetriever())
    if mode == "demo":
        return RuntimeAI(EchoLLMGateway(), IndexedRetriever())
    if mode != "local":
        raise ValueError("TRALUAT_AI_MODE must be disabled, demo or local")
    gateway = LocalLLMGateway(
        base_url=env.get("TRALUAT_LOCAL_BASE_URL", "http://127.0.0.1:11434/v1"),
        model=env.get("TRALUAT_LOCAL_MODEL", ""),
        backend=env.get("TRALUAT_LOCAL_BACKEND", "ollama"),
        api_key=env.get("TRALUAT_LOCAL_API_KEY", ""),
        timeout=float(env.get("TRALUAT_LOCAL_TIMEOUT", "90")),
    )
    from ..w3.nli_xnli import XNLIVerifier
    embedder = load_embedder(env)
    nli = XNLIVerifier(
        model_name=env.get("TRALUAT_NLI_MODEL", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"),
        device=env.get("TRALUAT_MODEL_DEVICE") or None,
        local_files_only=env.get("TRALUAT_MODELS_OFFLINE", "1") == "1",
        revision=env.get("TRALUAT_NLI_REVISION") or None,
    )
    return RuntimeAI(gateway, IndexedRetriever(embedder), nli)
