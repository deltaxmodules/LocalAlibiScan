"""Cliente mínimo do Ollama (Fase 6). Opcional: nada essencial depende dele.

Regra "sem rede": só aceita endereços locais (localhost, 127.0.0.1, ::1).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from .i18n import t

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class LLMUnavailable(RuntimeError):
    """O Ollama não está a correr, não tem o modelo, ou respondeu com erro."""


class NotLocal(ValueError):
    """Tentativa de usar um servidor que não está nesta máquina."""


class TextModel(Protocol):
    name: str

    def generate(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str: ...


@dataclass
class OllamaClient:
    url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"
    timeout: float = 180.0

    def __post_init__(self) -> None:
        host = urlparse(self.url).hostname
        if host not in LOCAL_HOSTS:
            raise NotLocal(t("llm.not_local", url=self.url))

    @property
    def name(self) -> str:
        return self.model

    def _request(self, path: str, payload: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.url.rstrip("/") + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (só localhost)
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
            raise LLMUnavailable(str(exc)) from exc

    def available(self) -> bool:
        """O servidor responde e tem o modelo configurado."""
        try:
            tags = self._request("/api/tags", None, timeout=2)
        except LLMUnavailable:
            return False
        names = {m.get("name") for m in tags.get("models", [])}
        return self.model in names or f"{self.model}:latest" in names

    def generate(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "seed": 7},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        result = self._request("/api/generate", payload, timeout=self.timeout)
        if "error" in result:
            raise LLMUnavailable(str(result["error"]))
        return str(result.get("response", ""))
