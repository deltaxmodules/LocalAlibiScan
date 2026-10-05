from __future__ import annotations

import json
from pathlib import Path

from localalibiscan.detectors import REGISTRY, run_detectors
from localalibiscan.detectors.manifests import parse_manifests
from localalibiscan.models import Claim
from localalibiscan.project import Project


def claims_for(path: Path, config) -> dict[str, Claim]:
    return {c.id: c for c in run_detectors(Project(path, config))}


def test_registry_order() -> None:
    assert [d.name for d in REGISTRY] == [
        "languages",
        "manifests",
        "project_type",
        "entry_points",
        "structure",
        "docs",
        "database",
        "orm",
        "frameworks",
        "external_services",
        "routes",
        "important_files",
    ]


# ------------------------------------------------------------------ languages


def test_languages_node(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("node_sqlite_lying_readme"), config)
    assert claims["lang.primary"].value == "TypeScript"
    assert claims["lang.primary"].status == "confirmed"
    assert claims["lang.breakdown"].value["TypeScript"] == 3


def test_languages_none(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("empty_project"), config)
    assert claims["lang.primary"].status == "unknown"
    assert claims["lang.primary"].value is None


# ------------------------------------------------------------------ manifests


def test_package_json_dependency_lines(fixture_copy, config) -> None:
    root = fixture_copy("node_sqlite_lying_readme")
    claims = claims_for(root, config)
    dep = claims["dep.npm.better-sqlite3"]
    assert dep.status == "confirmed"
    ev = dep.evidence[0]
    assert (ev.file, ev.kind) == ("package.json", "dependency")
    assert (root / "package.json").read_text().splitlines()[ev.line - 1].strip() == ev.snippet
    assert '"better-sqlite3"' in ev.snippet
    assert claims["dep.npm.typescript"].value["dev"] is True
    assert claims["script.npm.start"].value == "node dist/index.js"


def test_requirements_lines(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("python_fastapi_openai"), config)
    openai = claims["dep.pypi.openai"]
    assert openai.value["spec"] == "==1.23.0"
    assert openai.evidence[0].location() == "requirements.txt:3"
    assert claims["dep.pypi.uvicorn"].evidence[0].line == 2


def test_pyproject_dependencies_and_scripts(fixture_copy, config) -> None:
    root = fixture_copy("projects_root") / "alpha_api"
    claims = claims_for(root, config)
    assert claims["dep.pypi.flask"].evidence[0].location() == "pyproject.toml:5"
    script = claims["script.pypi.alpha"]
    assert script.value == "alpha_api.app:main"
    assert script.evidence[0].location() == "pyproject.toml:8"


def test_gomod_and_cargo(tmp_path: Path, config) -> None:
    go = tmp_path / "go"
    go.mkdir()
    (go / "go.mod").write_text(
        "module x\n\ngo 1.22\n\nrequire (\n\tgithub.com/spf13/cobra v1.8.0\n\tgolang.org/x/sys v0.1.0 // indirect\n)\n"
        "require github.com/pkg/errors v0.9.1\n"
    )
    claims = claims_for(go, config)
    assert claims["dep.go.github.com/spf13/cobra"].evidence[0].line == 6
    assert claims["dep.go.github.com/pkg/errors"].evidence[0].line == 9

    rs = tmp_path / "rs"
    rs.mkdir()
    (rs / "Cargo.toml").write_text(
        '[package]\nname = "x"\n\n[dependencies]\nserde = { version = "1.0", features = ["derive"] }\ntokio = "1"\n'
    )
    claims = claims_for(rs, config)
    assert claims["dep.cargo.serde"].value["spec"] == "1.0"
    assert claims["dep.cargo.tokio"].evidence[0].line == 6


def test_broken_manifest_is_unknown_not_crash(tmp_path: Path, config) -> None:
    (tmp_path / "p").mkdir()
    (tmp_path / "p/package.json").write_text("{ not json")
    claims = claims_for(tmp_path / "p", config)
    broken = claims["manifest.error.package.json"]
    assert broken.status == "unknown"
    assert "não foi possível ler" in broken.note


def test_composer(tmp_path: Path, config) -> None:
    (tmp_path / "php").mkdir()
    (tmp_path / "php/composer.json").write_text(
        '{\n  "require": {\n    "laravel/framework": "^11.0"\n  }\n}\n'
    )
    claims = claims_for(tmp_path / "php", config)
    assert claims["dep.composer.laravel/framework"].evidence[0].line == 3
    assert claims["project.type"].value == "PHP"


def test_manifests_ignored_inside_node_modules(fixture_copy, config) -> None:
    paths = [m.path for m in parse_manifests(Project(fixture_copy("node_sqlite_lying_readme"), config))]
    assert paths == ["package.json"]


# ------------------------------------------------------------------ project_type


def test_project_types(fixture_copy, config) -> None:
    assert claims_for(fixture_copy("node_sqlite_lying_readme"), config)["project.type"].value == "Node.js/TypeScript"
    assert claims_for(fixture_copy("python_fastapi_openai"), config)["project.type"].value == "Python"
    loose = claims_for(fixture_copy("loose_scripts"), config)["project.type"]
    assert (loose.value, loose.status) == ("Scripts Python", "inferred")
    assert claims_for(fixture_copy("empty_project"), config)["project.type"].status == "unknown"


def test_monorepo_components(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("monorepo_mixed"), config)
    assert claims["project.type"].value.startswith("Monorepo")
    assert claims["project.components"].value == [
        {"path": "backend", "type": "Python"},
        {"path": "frontend", "type": "Node.js/JavaScript"},
    ]
    assert claims["project.type"].evidence[0].location() == "package.json:4"  # workspaces


# ------------------------------------------------------------------ entry_points


def test_entry_points_python(fixture_copy, config) -> None:
    entry = claims_for(fixture_copy("python_fastapi_openai"), config)["entry.points"]
    assert entry.value == ["main.py"]
    assert entry.evidence[0].location() == "main.py:14"
    assert entry.evidence[0].kind == "code"


def test_entry_points_node(fixture_copy, config) -> None:
    entry = claims_for(fixture_copy("node_sqlite_lying_readme"), config)["entry.points"]
    assert "dist/index.js (main)" in entry.value
    assert "npm run start" in entry.value
    assert all(e.line for e in entry.evidence)


def test_entry_points_go_rust(fixture_copy, config) -> None:
    root = fixture_copy("projects_root")
    go = claims_for(root / "gamma_cli", config)["entry.points"]
    assert go.evidence[0].location() == "main.go:5"
    rust = claims_for(root / "delta_tool", config)["entry.points"]
    assert rust.evidence[0].location() == "src/main.rs:1"


def test_entry_points_unknown(fixture_copy, config) -> None:
    assert claims_for(fixture_copy("empty_project"), config)["entry.points"].status == "unknown"


# ------------------------------------------------------------------ structure & docs


def test_structure(fixture_copy, config) -> None:
    value = claims_for(fixture_copy("node_sqlite_lying_readme"), config)["structure.main_dirs"].value
    assert value[0] == {"path": "src", "code_files": 3}
    assert {"path": "src/db", "code_files": 1} in value


def test_docs(fixture_copy, config) -> None:
    claims = claims_for(fixture_copy("python_fastapi_openai"), config)
    assert claims["docs.readme"].value == "README.md"
    assert claims["docs.readme"].evidence[0].snippet == "# Chat Service"
    assert "requirements.txt" not in claims["docs.files"].value


def test_docs_missing(tmp_path: Path, config) -> None:
    (tmp_path / "p").mkdir()
    (tmp_path / "p/go.mod").write_text("module x\n")
    assert claims_for(tmp_path / "p", config)["docs.readme"].status == "unknown"


# ------------------------------------------------------------------ invariantes


def test_every_claim_has_status_and_evidence(fixture_copy, config) -> None:
    for name in ("node_sqlite_lying_readme", "python_fastapi_openai", "monorepo_mixed", "loose_scripts", "empty_project"):
        for claim in claims_for(fixture_copy(name), config).values():
            assert claim.status in ("confirmed", "inferred", "contradiction", "unknown")
            if claim.status != "unknown":
                assert claim.evidence, f"{name}: {claim.id} sem evidência"
            assert claim.source.startswith("detector:")


def test_claims_serialize_to_spec_shape(fixture_copy, config) -> None:
    claim = claims_for(fixture_copy("node_sqlite_lying_readme"), config)["dep.npm.better-sqlite3"]
    data = json.loads(claim.model_dump_json())
    assert set(data) >= {"id", "category", "label", "value", "status", "evidence", "source", "detected_at"}
    assert set(data["evidence"][0]) == {"file", "line", "snippet", "kind"}
