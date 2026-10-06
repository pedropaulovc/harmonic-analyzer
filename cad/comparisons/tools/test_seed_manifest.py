"""Historical catalog labels must select and frame current CAD identities."""
import json

import pytest

import pose_to_meshprobe as p2m
import seed_manifest as seed


def test_catalog_top_assembly_and_in_context_framing(tmp_path, monkeypatch):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"entries": [
        {"id": "whole", "source": "ch01", "path": "whole.jpg", "keep": True,
         "class": "machine-detail", "components": ["harmonic_analyzer", "rocker_arm"]},
        {"id": "detail", "source": "video1", "time_s": 12, "keep": True,
         "class": "machine-detail", "components": ["rocker_arm", "cone_gear", "crank_pedestal"]},
    ]}), encoding="utf-8")
    monkeypatch.setattr(seed, "CATALOG", catalog)
    with pytest.warns(UserWarning, match="crank_pedestal"):
        whole, detail = seed.seed_from_catalog(seed.part_stems())
    assert whole["model"] == "ha_harmonic_analyzer"
    assert whole["component_focus"] == ["ha_harmonic_analyzer", "ch_rocker_arm"]
    assert "frame_components" not in whole["camera"]
    assert detail["model"] == "ha_harmonic_analyzer"
    assert detail["component_focus"] == ["ch_rocker_arm", "dt_cone_gear", "crank_pedestal"]
    # Exercise the actual meshprobe consumer, including instance suffix matching.
    target, zoom = p2m.resolve_framing(
        detail["camera"],
        [("machine/ch-rocker-arm-2", (10, 20, 30, 20, 30, 40)),
         ("machine/dt-cone-gear", (20, 30, 40, 30, 40, 50)),
         ("machine/fr-top-frame", (0, 0, 0, 200, 200, 200))],
        (0, 0, 0), (200, 200, 200),
    )
    assert target == (20, 30, 40)
    assert zoom == pytest.approx(7.5)
