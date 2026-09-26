"""Offline contracts for the McMaster replica driver (diag_build_mcmaster.py).

91255A148, the #6-32 button head MHA-140 used until I31, stays in the replica
fleet only; these driver tests keep using it as the example local-only part.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from _stock_fastener import STOCK_RECIPES


def test_91255A148_is_a_diagnostic_recipe_only() -> None:
    """I31 moved MHA-140 to 93075A150; no production builder imports the old
    button head, which stays registered for the replica fleet."""
    from diagnostics import diag_build_mcmaster as driver

    scripts = Path(__file__).resolve().parent
    importer = re.compile(r"diag_build_91255A148\s+import|import\s+diag_build_91255A148")
    users = [
        path.name
        for path in scripts.glob("build_*.py")
        if importer.search(path.read_text(encoding="utf-8"))
    ]
    assert users == []
    assert "91255A148" in driver.REGISTRY
    assert "91255A148" in STOCK_RECIPES


def test_replica_driver_names_a_missing_local_vendor_file(
    tmp_path: Path, monkeypatch
) -> None:
    """Codex P2 on #857: the vendor SLDPRT is local-only, so a clean checkout
    must get a download instruction, not a bare FileNotFoundError."""
    from diagnostics import diag_build_mcmaster as driver

    monkeypatch.setattr(driver, "MCMASTER_DIR", tmp_path / "mcmaster")
    monkeypatch.setattr(driver, "REPORTS_DIR", tmp_path / "reports")
    why = driver._missing_inputs("91255A148")
    assert "vendor SLDPRT not present locally" in why
    assert "https://www.mcmaster.com/91255A148/" in why
    (tmp_path / "mcmaster").mkdir()
    (tmp_path / "mcmaster" / "91255A148.SLDPRT").write_bytes(b"")
    assert "no harvest" in driver._missing_inputs("91255A148")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "mcmaster-91255A148-dump.json").write_text("{}")
    assert driver._missing_inputs("91255A148") is None


def test_replica_driver_skips_missing_parts_under_all(monkeypatch) -> None:
    from diagnostics import diag_build_mcmaster as driver

    ran: list[str] = []

    async def fake_replica(adapter, part_no, builder):
        ran.append(part_no)
        return {}

    monkeypatch.setattr(driver, "run_replica", fake_replica)
    monkeypatch.setattr(
        driver, "_missing_inputs", lambda p: "absent" if p == "91255A148" else None
    )
    monkeypatch.setattr(driver.sys, "argv", ["diag_build_mcmaster.py", "--all"])
    asyncio.run(driver.build(None))
    assert "91255A148" not in ran and len(ran) == len(driver.REGISTRY) - 1
    monkeypatch.setattr(driver.sys, "argv", ["diag_build_mcmaster.py", "91255A148"])
    with pytest.raises(SystemExit, match="91255A148: absent"):
        asyncio.run(driver.build(None))
