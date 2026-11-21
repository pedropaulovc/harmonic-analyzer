"""The sub-plate's CAM recipe posted through headless FreeCAD, offline.

The plate's real feature export comes from the SolidWorks farm
(``package:features:ch_rocker_strap_tl_sub_plate``); this test stands in for
it with the drawing's requirement manifest (the features the export binds)
and a synthetic STEP of the plate built here in FreeCAD from the spec, then
posts both programs and runs every check the recipe declares, as ``cam_nc``
does.

Not in any ``check:*`` gate (``dodo._UNGATED``): it runs the local FreeCAD
install, which no build dependency tracks. Run it by hand after changing the
recipe or its plan:
``uv run --frozen python -m pytest -q cad/scripts/test_ch_rocker_strap_tl_sub_plate_cam_freecad.py``.
It skips only when no FreeCAD 1.1+ is found.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import ch_rocker_strap_tl_sub_plate_spec as spec
import export_features

STEM = "ch_rocker_strap_tl_sub_plate"
# The plate as the spec draws it: the bar, the plate top milled round the
# fence and stop, the notches, pockets, counterbore and holes.
_STEP_SCRIPT = f"""
import os
import FreeCAD
import Part

V = FreeCAD.Vector


def box(x, y, z):
    return Part.makeBox(x[1] - x[0], y[1] - y[0], z[1] - z[0], V(x[0], y[0], z[0]))


left, right = {spec.LEFT_END_X!r}, {spec.LEFT_END_X + spec.PLATE_LENGTH!r}
front, back = {spec.FRONT_EDGE_Y!r}, {spec.BACK_EDGE_Y!r}
plate = box((left, right), (front, back), ({spec.UNDERSIDE_Z!r}, {spec.FENCE_HEIGHT!r}))
cuts = [
    box((0, right + 1), (front - 1, 0), (0, 3)),
    box((0, {spec.NOTCH_LEFT_END!r}), (-1, {spec.NOTCH_DEPTH!r}), (0, 3)),
    box(({spec.NOTCH_RIGHT_START!r}, right + 1), (-1, {spec.NOTCH_DEPTH!r}), (0, 3)),
    Part.makeCylinder({spec.HUB_CBORE_DIA / 2!r}, 10, V({spec.HUB_X!r}, {spec.HUB_Y!r}, {-spec.HUB_CBORE_DEPTH!r})),
    Part.makeCylinder({spec.HUB_TAP_DRILL / 2!r}, 20, V({spec.HUB_X!r}, {spec.HUB_Y!r}, -15)),
]
for s in {spec.CLAMP_STATIONS!r}:
    cuts.append(box((s - {spec.POCKET_LENGTH / 2!r}, s + {spec.POCKET_LENGTH / 2!r}),
                    ({spec.POCKET_BACK_WALL_Y!r}, {spec.POCKET_NEAR_WALL_Y!r}), ({-spec.POCKET_DEPTH!r}, 3)))
    cuts.append(Part.makeCylinder({spec.CLAMP_TAP_DRILL / 2!r}, 20, V(s, {spec.CLAMP_SCREW_Y!r}, -15)))
for cut in cuts:
    plate = plate.cut(cut)
plate.exportStep(os.environ["PLATE_STEP_OUT"])
"""


def test_plate_programs_post_and_pass_their_checks(tmp_path) -> None:
    try:
        freecadcmd = cam_nc.resolve_freecadcmd()
    except cam_nc.FreeCadError as exc:
        pytest.skip(f"no usable FreeCAD: {exc}")
    script, step = tmp_path / "make_step.py", tmp_path / "plate.step"
    script.write_text(_STEP_SCRIPT, encoding="utf-8")
    subprocess.run(
        [str(freecadcmd), str(script)],
        env={**os.environ, "PLATE_STEP_OUT": str(step)},
        cwd=tmp_path,
        capture_output=True,
        check=True,
        timeout=cam_nc.FREECAD_TIMEOUT_S,
    )
    assert step.is_file()
    recipe = _cam_programs.load_recipe(STEM)
    plan = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
    shop = _process_plans.load_shop()
    ctx = recipe.context(
        export_features.requirement_manifest(STEM), plan, shop, str(step)
    )
    out = tmp_path / "nc"
    out.mkdir()
    result = cam_nc.run_freecad(
        _cam_programs.recipe_path(STEM),
        ctx,
        recipe.PROGRAMS,
        out,
        freecadcmd,
        tmp_path / "freecadcmd.log",
    )
    assert sorted(Path(f).name for f in result["files"]) == sorted(
        f"{name}.nc" for name, _ops in recipe.PROGRAMS
    )
    checks = recipe.expectations(ctx)
    assert cam_nc.verify(checks, out) == []
    times = cam_nc.cycle_times(checks, out)
    assert set(times) == {name for name, _ops in recipe.PROGRAMS}
