"""Pipeline de análise: veredito → detetores → `.localalibi/project.json`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .config import Config, load_config
from .detectors import run_detectors
from .detectors.project_kind import KindResult, classify
from .models import ProjectProfile
from .project import Project
from .storage import save_evidence


@dataclass
class ScanResult:
    kind: KindResult
    profile: ProjectProfile | None = None  # None quando a análise não correu
    output: Path | None = None


def scan(path: str | Path, config: Config | None = None, *, force: bool = False, write: bool = True) -> ScanResult:
    config = config or load_config()
    kind = classify(path, config)
    if not kind.analyzable and not force:
        return ScanResult(kind=kind)

    project = Project(kind.path, config)
    kind.claim.detected_at = project.now
    claims = [kind.claim, *run_detectors(project)]
    profile = ProjectProfile(
        version=__version__,
        root=str(project.root),
        verdict=kind.verdict,
        forced=force and not kind.analyzable,
        scanned_at=project.now,
        claims=claims,
    )
    output = None
    if write:
        project.fs.ensure_output_dir()
        output = project.fs.write_text(
            project.fs.output_dir / "project.json", profile.model_dump_json(indent=2) + "\n"
        )
        save_evidence(project.fs, profile)
    return ScanResult(kind=kind, profile=profile, output=output)


def load_profile(path: str | Path) -> ProjectProfile | None:
    file = Path(path) / ".localalibi" / "project.json"
    if not file.is_file():
        return None
    return ProjectProfile.model_validate_json(file.read_text(encoding="utf-8"))
