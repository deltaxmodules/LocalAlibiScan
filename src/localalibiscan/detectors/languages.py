"""Detetor `languages`: linguagens por contagem de ficheiros."""

from __future__ import annotations

from collections import Counter, defaultdict

from ..knowledge import CODE_LANGUAGES, language_of
from ..models import Claim
from ..project import Project
from .base import Detector, gen_evidence, register


def language_counts(project: Project) -> dict[str, list[str]]:
    """Linguagem -> ficheiros, ordenado por número de ficheiros (desc)."""
    if "languages" not in project.cache:
        by_lang: dict[str, list[str]] = defaultdict(list)
        for entry in project.files:
            lang = language_of(entry.extension)
            if lang:
                by_lang[lang].append(entry.path)
        project.cache["languages"] = dict(sorted(by_lang.items(), key=lambda kv: (-len(kv[1]), kv[0])))
    return project.cache["languages"]


CODE_LANGUAGE_NAMES = frozenset(CODE_LANGUAGES.values())


@register
class LanguagesDetector(Detector):
    name = "languages"

    def detect(self, project: Project) -> list[Claim]:
        counts = language_counts(project)
        code = {lang: files for lang, files in counts.items() if lang in CODE_LANGUAGE_NAMES}
        if not code:
            return [
                self.claim(
                    project,
                    id="lang.primary",
                    category="language",
                    label_key="claim.lang.primary",
                    status="unknown",
                    note_key="note.lang.none",
                )
            ]

        total = sum(len(f) for f in code.values())
        primary, files = next(iter(code.items()))
        ext_counts = Counter(f.rsplit(".", 1)[-1] for f in files)
        exts = ", ".join(f".{e}" for e, _ in ext_counts.most_common())
        claims = [
            self.claim(
                project,
                id="lang.primary",
                category="language",
                label_key="claim.lang.primary",
                value=primary,
                status="confirmed",
                evidence=[
                    gen_evidence(".", "count", "ev.lang.share", n=len(files), total=total, exts=exts),
                    gen_evidence(files[0], "file", "ev.lang.file", language=primary),
                ],
            ),
            self.claim(
                project,
                id="lang.breakdown",
                category="language",
                label_key="claim.lang.breakdown",
                value={lang: len(f) for lang, f in counts.items()},
                status="confirmed",
                evidence=[
                    gen_evidence(f[0], "count", "ev.lang.count", language=lang, n=len(f))
                    for lang, f in counts.items()
                ],
            ),
        ]
        return claims
