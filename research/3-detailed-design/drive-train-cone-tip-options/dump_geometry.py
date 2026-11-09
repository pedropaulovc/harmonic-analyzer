"""Dump the cone-tip geometry (mm) from cad/scripts for cone_tip_options.py; run from the repo root."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("cad/scripts").resolve()))

import cone_line
import dt_cone_gear_shaft_spec as sh
import dt_cone_gear_spec as g
import dt_cone_tip_block_spec as tb
import dt_vn_cone_tip_collar_spec as col

out = {"gears": {}}
for t in (6, 12, 18, 24, 30, 36):
    lo, hi = g.floor_limits_mm(t)
    out["gears"][t] = {
        "od": g.outside_dia_mm(t),
        "root_min": lo,
        "root_max": hi,
        "bore": g.bore_dia_mm(t),
        "land": g.land_section(t),
        "material": g.material_specification(t),
    }
out["face_width"] = g.FACE_WIDTH
out["section_dias"] = sh.SECTION_DIAS
out["section_ends"] = sh.SECTION_ENDS
out["section_flat_af"] = sh.SECTION_FLAT_AF
out["section_teeth"] = [list(x) if x else None for x in sh.SECTION_CONE_GEAR_TEETH]
out["front_stub"] = sh.FRONT_STUB
for name in (
    "T006_NORTH_FACE_STATION",
    "TIP_COLLAR_START_STATION",
    "TIP_COLLAR_END_STATION",
    "TIP_BLOCK_NORTH_FACE_STATION",
    "TIP_BLOCK_SOUTH_FACE_STATION",
    "ADJUSTER_CUP_RIM_STATION",
    "T006_TIP_STATION",
    "TIP_LAND_START_STATION",
    "TIP_STUB_LENGTH",
    "SHAFT_LENGTH",
    "COLLAR_FEELER",
    "TIP_COLLAR_WIDTH",
    "CUP_DEPTH",
    "PIVOT_FROM_T006_NORTH_FACE",
):
    out[name] = getattr(sh, name, None)
for name in (
    "BLOCK_X",
    "BLOCK_Z",
    "BLOCK_HEIGHT",
    "ADJUSTER_AXIS_HEIGHT",
    "PINCH_HEIGHT",
    "ADJUSTER_EMBED",
    "ADJUSTER_SCREW_LENGTH",
    "SHAFT_PASSAGE_DIA",
    "SLIT_W",
):
    out["tb_" + name] = getattr(tb, name)
out["collar"] = {
    k: getattr(col, k)
    for k in dir(col)
    if k.isupper() and isinstance(getattr(col, k), (int, float))
}
out["cone_line"] = {
    k: getattr(cone_line, k)
    for k in dir(cone_line)
    if k.isupper() and isinstance(getattr(cone_line, k), (int, float))
}
print(json.dumps(out, indent=1, default=str))
