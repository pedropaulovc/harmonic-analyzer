"""Offline contracts for the McMaster replica driver (diag_build_mcmaster.py)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def test_replica_driver_names_a_missing_local_vendor_file(
    tmp_path: Path, monkeypatch
) -> None:
    """Codex P2 on #857: the vendor SLDPRT is local-only, so a clean checkout
    must get a download instruction, not a bare FileNotFoundError."""
    from diagnostics import diag_build_mcmaster as driver

    monkeypatch.setattr(driver, "MCMASTER_DIR", tmp_path / "mcmaster")
    monkeypatch.setattr(driver, "REPORTS_DIR", tmp_path / "reports")
    why = driver._missing_inputs("90280A108")
    assert "vendor SLDPRT not present locally" in why
    assert "https://www.mcmaster.com/90280A108/" in why
    (tmp_path / "mcmaster").mkdir()
    (tmp_path / "mcmaster" / "90280A108.SLDPRT").write_bytes(b"")
    assert "no harvest" in driver._missing_inputs("90280A108")
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "mcmaster-90280A108-dump.json").write_text("{}")
    assert driver._missing_inputs("90280A108") is None


def test_replica_driver_skips_missing_parts_under_all(monkeypatch) -> None:
    from diagnostics import diag_build_mcmaster as driver

    ran: list[str] = []

    async def fake_replica(adapter, part_no, builder):
        ran.append(part_no)
        return {}

    monkeypatch.setattr(driver, "run_replica", fake_replica)
    monkeypatch.setattr(
        driver, "_missing_inputs", lambda p: "absent" if p == "90280A108" else None
    )
    monkeypatch.setattr(driver.sys, "argv", ["diag_build_mcmaster.py", "--all"])
    asyncio.run(driver.build(None))
    assert "90280A108" not in ran and len(ran) == len(driver.REGISTRY) - 1
    monkeypatch.setattr(driver.sys, "argv", ["diag_build_mcmaster.py", "90280A108"])
    with pytest.raises(SystemExit, match="90280A108: absent"):
        asyncio.run(driver.build(None))
