"""Fleet contract for drawing points derived from known recipe geometry."""

from __future__ import annotations

from pathlib import Path


SCRIPTS = Path(__file__).resolve().parent


def test_production_drawing_recipes_do_not_project_model_points_at_runtime() -> None:
    offenders = [
        path.name
        for path in sorted(SCRIPTS.glob("draw_*.py"))
        if "model_point_in_view" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
