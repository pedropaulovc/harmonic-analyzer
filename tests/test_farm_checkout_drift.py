"""The submitter's checkout-drift guard against real Git checkouts (#1114).

The farm builds the launch commit while the submitter keys each task from its
live files; ``_farm.checkout_drift`` is what notices the two diverged.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "protocol.file.allow=always",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def launched(tmp_path: Path) -> tuple[Path, str, Path]:
    """A checkout with a submodule, clean at its launch commit."""
    library = tmp_path / "library"
    library.mkdir()
    _git(library, "init", "-q")
    (library / "adapter.py").write_text("VERSION = 1\n", encoding="utf-8")
    _commit_all(library, "library one")

    repo = tmp_path / "checkout"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "cad").mkdir()
    (repo / "cad" / "_drawing_common.py").write_text("SCALE = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("harmonic\n", encoding="utf-8")
    _git(repo, "submodule", "add", "-q", str(library), "library")
    commit = _commit_all(repo, "launch")
    return repo, commit, library


def test_an_untouched_checkout_has_no_drift(launched) -> None:
    repo, commit, _library = launched

    assert _farm.checkout_drift(repo, commit) is None


def test_a_commit_made_after_launch_is_drift_naming_both_heads(launched) -> None:
    repo, commit, _library = launched
    (repo / "cad" / "_drawing_common.py").write_text("SCALE = 2\n", encoding="utf-8")
    moved = _commit_all(repo, "mid-run edit")

    assert _farm.checkout_drift(repo, commit) == (
        f"submitter checkout changed since launch: HEAD {commit[:12]} -> "
        f"{moved[:12]}; changed: cad/_drawing_common.py; the farm builds "
        f"{commit[:12]}, so keys would not match. Launch from an untouched "
        "worktree (scripts/farm-run.ps1 does this)."
    )


def test_an_uncommitted_edit_to_a_tracked_file_is_drift(launched) -> None:
    repo, commit, _library = launched
    (repo / "README.md").write_text("harmonic analyzer\n", encoding="utf-8")

    drift = _farm.checkout_drift(repo, commit)

    assert drift is not None
    assert f"HEAD {commit[:12]} (unchanged); changed: README.md;" in drift


def test_a_submodule_moved_off_its_gitlink_is_drift(launched) -> None:
    repo, commit, library = launched
    (library / "adapter.py").write_text("VERSION = 2\n", encoding="utf-8")
    _commit_all(library, "library two")
    _git(repo / "library", "pull", "-q", "origin", "HEAD")

    drift = _farm.checkout_drift(repo, commit)

    assert drift is not None
    assert "changed: library;" in drift


def test_a_head_moved_to_an_identical_tree_is_not_drift(launched) -> None:
    """An empty commit moves HEAD but no key: the farm builds the same files."""
    repo, commit, _library = launched
    _git(repo, "commit", "-q", "--allow-empty", "-m", "message only")

    assert _git(repo, "rev-parse", "HEAD").strip() != commit
    assert _farm.checkout_drift(repo, commit) is None


def test_an_untracked_file_is_not_drift(launched) -> None:
    """Keys come from tracked inputs graphed at launch; scratch files feed none."""
    repo, commit, _library = launched
    (repo / "scratch.log").write_text("notes\n", encoding="utf-8")

    assert _farm.checkout_drift(repo, commit) is None
