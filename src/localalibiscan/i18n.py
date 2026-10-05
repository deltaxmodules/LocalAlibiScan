"""Traduções da interface (Fase 9).

- Catálogos em `locales/<língua>.py` (`MESSAGES`), com chaves estáveis.
- Língua, por esta ordem: `--lang-ui` (`set_language`), `LOCALALIBI_LANG`,
  `[ui] language` em `~/.localalibi/config.toml`, e por omissão `en`.
- Uma chave que falte numa língua cai para `en`; uma que falte em todas mostra
  a própria chave. Nunca rebenta.
- Os factos não dependem da língua: os detetores gravam o texto em `en` e as
  chaves (`label_key`, `value_key`, `note_key`, `snippet_key` + `params`); a
  tradução faz-se só na apresentação.
"""

from __future__ import annotations

import importlib
import os
import re
from functools import cache
from pathlib import Path
from typing import Any

DEFAULT_LANG = "en"
LANGUAGES: tuple[str, ...] = ("en", "pt")
ENV_VAR = "LOCALALIBI_LANG"

_override: str | None = None


def normalize(lang: str | None) -> str | None:
    """"pt_PT.UTF-8" -> "pt", "EN-us" -> "en"; vazio -> None."""
    if not lang:
        return None
    code = re.split(r"[_.\-@]", lang.strip().lower(), maxsplit=1)[0]
    return code or None


def set_language(lang: str | None) -> None:
    """Escolha explícita (opção `--lang-ui`); None volta à escolha automática."""
    global _override
    _override = normalize(lang)


@cache
def _config_language(path: str, mtime_ns: int) -> str | None:
    from .config import ConfigError, load_config

    try:
        return normalize(load_config(Path(path)).language)
    except (ConfigError, ValueError, OSError):
        return None


def current() -> str:
    if _override:
        return _override
    env = normalize(os.environ.get(ENV_VAR))
    if env:
        return env
    from .config import config_path

    path = config_path()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return DEFAULT_LANG
    return _config_language(str(path), mtime) or DEFAULT_LANG


@cache
def catalog(lang: str) -> dict[str, str]:
    if not re.fullmatch(r"[a-z]{2,3}", lang):
        return {}
    try:
        module = importlib.import_module(f"{__package__}.locales.{lang}")
    except ImportError:
        return {}
    return dict(getattr(module, "MESSAGES", {}))


def has_key(key: str, lang: str) -> bool:
    return key in catalog(lang)


def _resolve(value: Any, lang: str) -> Any:
    """Parâmetros podem ser mensagens: {"key": ..., "params": ...} ou listas delas."""
    if isinstance(value, dict) and "key" in value:
        return t(value["key"], lang=lang, **(value.get("params") or {}))
    if isinstance(value, list) and value and all(isinstance(v, dict) and "key" in v for v in value):
        return "; ".join(_resolve(v, lang) for v in value)
    return value


def t(key: str, /, lang: str | None = None, **params: Any) -> str:
    lang = normalize(lang) or current()
    template = catalog(lang).get(key)
    if template is None:
        template = catalog(DEFAULT_LANG).get(key, key)
    if not params:
        return template
    resolved = {k: _resolve(v, lang) for k, v in params.items()}
    try:
        return template.format(**resolved)
    except (KeyError, IndexError, ValueError):
        return template


def tn(key: str, n: int, /, lang: str | None = None, **params: Any) -> str:
    """Plural: `key.one` quando n == 1, senão `key.other` (com `n` nos parâmetros)."""
    return t(f"{key}.{'one' if n == 1 else 'other'}", lang=lang, n=n, **params)


def msg(key: str, **params: Any) -> dict[str, Any]:
    """Mensagem por traduzir, para guardar dentro de valores ou parâmetros."""
    return {"key": key, "params": params} if params else {"key": key}


# ---------------------------------------------------------------------- Claims


def _params(obj: Any) -> dict[str, Any]:
    return getattr(obj, "params", None) or {}


def claim_label(claim: Any, lang: str | None = None) -> str:
    key = getattr(claim, "label_key", None)
    return t(key, lang=lang, **_params(claim)) if key else claim.label


def claim_note(claim: Any, lang: str | None = None) -> str | None:
    key = getattr(claim, "note_key", None)
    return t(key, lang=lang, **_params(claim)) if key else claim.note


def claim_text_value(claim: Any, lang: str | None = None) -> Any:
    """O valor para mostrar: traduzido se for texto gerado (`value_key`)."""
    key = getattr(claim, "value_key", None)
    return t(key, lang=lang, **_params(claim)) if key else claim.value


def evidence_snippet(ev: Any, lang: str | None = None) -> str:
    key = getattr(ev, "snippet_key", None)
    return t(key, lang=lang, **_params(ev)) if key else ev.snippet


def item_reason(item: dict[str, Any], lang: str | None = None) -> str:
    """Motivo de um ficheiro importante (`files.important`)."""
    if item.get("reasons"):
        return t("reasons", lang=lang, reasons=item["reasons"])
    return str(item.get("reason", ""))


def language_name(lang: str | None = None) -> str:
    """Nome da língua para pedir à LLM que escreva nela."""
    return t("llm.language", lang=lang)
