r"""CadQuery STAND-IN for the summing lever (build_summing_lever.py).

The production part is authored against SolidWorks COM (PyWin32Adapter) and can
only be rebuilt on the Windows build seat. This module reproduces the same
geometry with CadQuery so the shape -- in particular the coefficients-plate
spring-hole field, now driven by a LINEAR PATTERN (a single seed hole arrayed up
the channel axis) instead of 20 hand-placed circles -- can be built and rendered
on any box (e.g. CI / a Linux dev container).

It is a stand-in, NOT the source of truth: the dimension constants below mirror
build_summing_lever.py (kept in sync by hand); the organic summation leaf / ribs
follow the same three-point-arc construction. Run::

    python cad/scripts/cq_summing_lever.py [out.png]

and it writes an isometric PNG render (VTK offscreen; wrap with `xvfb-run` on a
headless box). The hole field is generated exactly as the SolidWorks linear
pattern does -- seed at HOLE_Z[0], instances at HOLE_Z[0] + k*CHANNEL_PITCH.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cadquery as cq

IN = 25.4  # inch -> mm

# --- constants mirrored from build_summing_lever.py ------------------------
SX = -1.0  # coefficients plate on +X (the .cs authors it on -X)

PLATE_W = 1.75 * IN  # coefficients plate width (along the arm, X)
PLATE_L = 6.0 * IN   # coefficients/pivot length (along Z)
PLATE_T = 0.2 * IN   # plate thickness
CYL_R = 0.5 * IN     # pivot cylinder radius
RIB_T = 0.2 * IN     # edge / middle rib thickness
RIB_PAD = 0.1 * IN   # rib arc padding over the cylinder
SUM_H = 3.0 * IN     # summation plate height (tip reach)
SUM_CURV = 0.3 * IN  # summation plate side curvature
ANCHOR_R = 0.375 * IN  # summation anchor outer radius
ANCHOR_H = 0.75 * IN   # summation anchor height

# spring-hole registration (the machine channel bank)
HOLE_DIA = 4.5
HOLE_X = 37.10
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1
CHANNEL_PITCH = 7.0565
HOLE_Z_OFFSET = 0.8 - 2.75  # -1.95

# hex knife-edge protrusions
HEX_W = 8.653
HEX_H = 10.268
HEX_DEPTH = 21.717
HEX_Z_INNER = PLATE_L / 2.0
HEX_Z_OUTER = HEX_Z_INNER + HEX_DEPTH

# derived
SUM_BASE = PLATE_L / 2.0
TIP_X = SX * SUM_H
ARC_R = CYL_R + RIB_PAD
RIB_OFFSET = PLATE_L / 2.0 - RIB_T
ANCHOR_BORE_R = 1.5
MID_RIB_PLATE_REACH = HOLE_X - 4.1  # 33.0

# Seed station, then the linear-pattern instances (== the SolidWorks pattern).
HOLE_Z0 = CHANNEL_Z0 + HOLE_Z_OFFSET
HOLE_Z = [HOLE_Z0 + CHANNEL_PITCH * k for k in range(HOLE_COUNT)]


def _xz_plane() -> cq.Plane:
    """A workplane whose local (u, v) maps to world (x, z) -- normal -Y, so a
    profile drawn here extrudes through the plate thickness (Y)."""
    return cq.Plane(origin=(0, 0, 0), xDir=(1, 0, 0), normal=(0, -1, 0))


def _pivot_cylinder() -> cq.Solid:
    """Feature 2: solid pivot cylinder centred on the origin, axis = Z."""
    return cq.Solid.makeCylinder(
        CYL_R, PLATE_L, cq.Vector(0, 0, -PLATE_L / 2.0), cq.Vector(0, 0, 1)
    )


def _coefficients_plate() -> cq.Workplane:
    """Feature 1: the +X plate with the 20 spring holes as a LINEAR PATTERN.

    The seed hole (HOLE_X, HOLE_Z[0]) is arrayed up +Z at CHANNEL_PITCH -- the
    CadQuery `rarray` is the stand-in for the SolidWorks linear-pattern feature.
    """
    plate = cq.Solid.makeBox(
        PLATE_W, PLATE_T, PLATE_L, cq.Vector(0, -PLATE_T / 2.0, -PLATE_L / 2.0)
    )
    body = cq.Workplane(obj=plate)
    # rarray a 1xHOLE_COUNT grid of through-holes along Z, centred on the field.
    z_centre = (HOLE_Z[0] + HOLE_Z[-1]) / 2.0
    holes = (
        cq.Workplane(_xz_plane())
        .center(HOLE_X, z_centre)
        .rarray(1.0, CHANNEL_PITCH, 1, HOLE_COUNT)
        .circle(HOLE_DIA / 2.0)
        .extrude(PLATE_T + 2.0, both=True)
    )
    return body.cut(holes)


def _hex_knife_edge(flip: bool) -> cq.Solid:
    """Feature 3: one vertex-up hexagonal trunnion protruding past a body end."""
    w2, h2, h4 = HEX_W / 2.0, HEX_H / 2.0, HEX_H / 4.0
    verts = [
        (0.0, h2), (-w2, h4), (-w2, -h4), (0.0, -h2), (w2, -h4), (w2, h4),
    ]
    sign = -1.0 if flip else 1.0
    z0 = sign * HEX_Z_INNER
    wp = cq.Workplane("XY", origin=(0, 0, z0)).polyline(verts).close()
    return wp.extrude(sign * HEX_DEPTH).val()


def _edge_rib(flip: bool) -> cq.Solid:
    """Feature 4: a Front-plane (XY) lobe -- +X tip + a semicircle wrapping the
    cylinder on -X -- extruded RIB_T along Z at the +-RIB_OFFSET plate end."""
    a = (0.0, ARC_R)
    b = (SX * -PLATE_W, 0.0)  # +X tip
    c = (0.0, -ARC_R)
    interior = (SX * ARC_R, 0.0)  # -X point the wrap arc passes through
    sign = -1.0 if flip else 1.0
    z0 = sign * RIB_OFFSET
    depth = sign * RIB_T
    wp = (
        cq.Workplane("XY", origin=(0, 0, z0))
        .moveTo(*a)
        .lineTo(*b)
        .lineTo(*c)
        .threePointArc(interior, a)
        .close()
    )
    return wp.extrude(depth).val()


def _summation_leaf() -> cq.Solid:
    """Feature 5: the organic -X leaf -- vertical base edge, two three-point
    arcs, a short tip edge -- extruded both ways through the plate thickness."""
    A = (0.0, -SUM_BASE)
    B = (0.0, SUM_BASE)
    C = (TIP_X, ANCHOR_R)
    D = (TIP_X, -ANCHOR_R)
    top_int = (SX * SUM_H / 2.0, SUM_BASE / 2.0 - SUM_CURV)
    bot_int = (SX * SUM_H / 2.0, -(SUM_BASE / 2.0 - SUM_CURV))
    wp = (
        cq.Workplane(_xz_plane())
        .moveTo(*A)
        .lineTo(*B)
        .threePointArc(top_int, C)
        .lineTo(*D)
        .threePointArc(bot_int, A)
        .close()
    )
    return wp.extrude(PLATE_T, both=True).val()


def _summation_anchor() -> cq.Solid:
    """Feature 6: the counter-spring eye -- a bored ring at the -X tip."""
    outer = cq.Solid.makeCylinder(
        ANCHOR_R, ANCHOR_H, cq.Vector(TIP_X, -ANCHOR_H / 2.0, 0), cq.Vector(0, 1, 0)
    )
    bore = cq.Solid.makeCylinder(
        ANCHOR_BORE_R, ANCHOR_H + 2.0,
        cq.Vector(TIP_X, -(ANCHOR_H + 2.0) / 2.0, 0), cq.Vector(0, 1, 0),
    )
    return cq.Workplane(obj=outer).cut(cq.Workplane(obj=bore)).val()


def _middle_rib() -> cq.Solid:
    """Feature 7: the elongated diamond spanning the lever -- two tangent lines
    per side meeting two coradial arcs wrapping the cylinder (radius ARC_R)."""
    left = (SX * -MID_RIB_PLATE_REACH, 0.0)  # +X vertex, short of the hole column
    right = (TIP_X, 0.0)                      # -X summation-tip vertex
    r = ARC_R
    tx_l = (r * r) / left[0]
    ty_l = r * math.sqrt(1.0 - (r * r) / (left[0] ** 2))
    tx_r = (r * r) / right[0]
    ty_r = r * math.sqrt(1.0 - (r * r) / (right[0] ** 2))
    wp = (
        cq.Workplane("XY")
        .moveTo(*left)
        .lineTo(tx_l, ty_l)
        .threePointArc((0.0, r), (tx_r, ty_r))
        .lineTo(*right)
        .lineTo(tx_r, -ty_r)
        .threePointArc((0.0, -r), (tx_l, -ty_l))
        .close()
    )
    return wp.extrude(RIB_T / 2.0, both=True).val()


def build() -> cq.Workplane:
    """Fuse the seven features into the summing-lever solid."""
    result = _coefficients_plate()
    for solid in (
        _pivot_cylinder(),
        _hex_knife_edge(flip=False),
        _hex_knife_edge(flip=True),
        _edge_rib(flip=False),
        _edge_rib(flip=True),
        _summation_leaf(),
        _summation_anchor(),
        _middle_rib(),
    ):
        result = result.union(cq.Workplane(obj=solid))
    return result


def render(result: cq.Workplane, out_png: Path, size: tuple[int, int] = (1600, 1000)) -> None:
    """Offscreen VTK isometric render to PNG (wrap the call in xvfb-run if
    headless). Tessellates the solid, shades it, and draws the feature edges so
    the patterned hole field reads clearly."""
    import tempfile

    import vtk

    out_png.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        stl_path = tmp.name
    cq.exporters.export(result, stl_path, tolerance=0.05, angularTolerance=0.1)

    reader = vtk.vtkSTLReader()
    reader.SetFileName(stl_path)
    reader.Update()

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(reader.GetOutputPort())
    normals.SetFeatureAngle(45)
    normals.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(normals.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(0.62, 0.64, 0.67)
    actor.GetProperty().SetSpecular(0.3)
    actor.GetProperty().SetSpecularPower(20)

    edges = vtk.vtkFeatureEdges()
    edges.SetInputConnection(normals.GetOutputPort())
    edges.BoundaryEdgesOn()
    edges.FeatureEdgesOn()
    edges.SetFeatureAngle(30)
    edges.ManifoldEdgesOff()
    edges.NonManifoldEdgesOff()
    edges.Update()
    edge_mapper = vtk.vtkPolyDataMapper()
    edge_mapper.SetInputConnection(edges.GetOutputPort())
    edge_mapper.ScalarVisibilityOff()
    edge_actor = vtk.vtkActor()
    edge_actor.SetMapper(edge_mapper)
    edge_actor.GetProperty().SetColor(0.1, 0.1, 0.12)
    edge_actor.GetProperty().SetLineWidth(1.2)

    ren = vtk.vtkRenderer()
    ren.AddActor(actor)
    ren.AddActor(edge_actor)
    ren.SetBackground(1, 1, 1)
    cam = ren.GetActiveCamera()
    cam.SetPosition(1, 0.8, 1)
    cam.SetViewUp(0, 1, 0)

    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.AddRenderer(ren)
    rw.SetSize(*size)
    ren.ResetCamera()
    cam.Zoom(2.0)
    rw.Render()

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(out_png))
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()
    Path(stl_path).unlink(missing_ok=True)
    print(f"wrote {out_png} ({out_png.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    default = Path(__file__).resolve().parents[1] / "out" / "png" / "summing-lever" / "summing-lever_cadquery_iso.png"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    model = build()
    print(f"built summing-lever stand-in: {len(model.val().Solids())} solid(s), "
          f"{HOLE_COUNT} patterned holes @ {CHANNEL_PITCH:g} mm pitch")
    render(model, out)
