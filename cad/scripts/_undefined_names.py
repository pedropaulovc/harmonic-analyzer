"""SolidWorks-free undefined-name check shared by doit and farm preflight."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def scan_undefined_names(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """Check CAD scripts and build entry points with the active environment's Ruff."""
    return subprocess.run(
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
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
