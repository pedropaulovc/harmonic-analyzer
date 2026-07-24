"""SolidWorks-render fallback contracts that do not require a COM session."""

from __future__ import annotations

import json

import render_compare


def test_stale_only_refreshes_align_without_connecting_to_solidworks(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(render_compare.composite, "COMP", tmp_path)
    pair = {
        "id": "pair",
        "model": "harmonic_analyzer",
        "camera": {"zoom": 1.0},
        "reference": {"path": "reference.png"},
        "align": {"scale": 1.0, "dx_px": 0, "dy_px": 0},
    }
    model = tmp_path / "harmonic-analyzer.SLDASM"
    model.touch()
    paths = render_compare.composite.pair_paths(pair["id"])
    for name in ("render", "cad", "blend"):
        paths[name].parent.mkdir(parents=True, exist_ok=True)
        paths[name].touch()
    sidecar = render_compare.composite.sidecar_path(pair["id"])
    sidecar.write_text(json.dumps({
        "camera": pair["camera"],
        "reference": pair["reference"],
        "align": {"scale": 1.13, "dx_px": 20, "dy_px": -247},
        "model_mtime": model.stat().st_mtime,
    }))
    refreshed: list[set[str]] = []

    def fail_connect(_build):
        raise AssertionError("align-only refresh connected to SolidWorks")

    monkeypatch.setattr(render_compare.sys, "argv", ["render_compare.py", "--stale-only"])
    monkeypatch.setattr(
        render_compare.composite,
        "load_manifest",
        lambda: {"pairs": [pair]},
    )
    monkeypatch.setattr(render_compare, "model_path", lambda _model: model)
    monkeypatch.setattr(
        render_compare.composite,
        "regenerate",
        lambda only: refreshed.append(only),
    )
    monkeypatch.setattr(render_compare, "run_build", fail_connect)

    assert render_compare.main() == 0
    assert refreshed == [{pair["id"]}]
    assert json.loads(sidecar.read_text())["align"] == pair["align"]
