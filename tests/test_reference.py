"""A referência do manual (`site/reference/`) é gerada a partir do código."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generated_reference_is_up_to_date() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gen_reference.py"), "--check"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr + "\n→ corre scripts/gen_reference.py"
