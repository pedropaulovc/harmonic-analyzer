"""Reject undefined names in build orchestration and CAD scripts without SolidWorks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_tracked_build_sources_have_no_undefined_names() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "F821,F822,F823",
            "--no-cache",
            "--output-format",
            "concise",
            "cad/scripts",
            "dodo.py",
            "build.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
