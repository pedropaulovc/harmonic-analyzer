r"""CadQuery stand-in for ``build_rocker_arm.py`` (book ch. 14, pp. 26-29).

The production part is authored against the SolidWorks MCP adapter, which
needs a live SolidWorks session. This module reproduces the *same* rocker-arm
geometry with CadQuery so the part can be built, exported (STEP/STL) and
rendered head-less -- e.g. to eyeball the p.29-rederived 4.5" half-length.

Geometry mirrors the SolidWorks script exactly:
  * Front-plane profile = two concentric arcs (top R=800, bottom R=816, shared
    centre 816 mm above the pivot) closed by two radial end lines, giving a
    uniform 16 mm depth.
  * Extruded 2.5 mm about the mid-plane (Z).
  * Pivot bore (Ø6.5) at the origin and rod-pin bore (Ø2.0) at +25.4 mm,
    each at the local vertical mid-height, cut through the thickness.

Run::

    /path/to/cqenv/bin/python cad/scripts/rocker_arm_cadquery.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import cadquery as cq

# --- dimensions (kept in sync with build_rocker_arm.py) ----------------------
CURVE_RADIUS = 800.0  # ch14: = amplitude bar length (stated)
ARM_DEPTH = 16.0  # ch14: p.29 end-face callout (annotated)
ARM_THICKNESS = 2.5  # ch14: p.27 callout (annotated)
ROD_SPAN = 114.3  # pivot -> rod-side end = 4.5" (p.29 broadside photo)
TAIL_SPAN = 114.3  # pivot -> opposite end, symmetric seesaw (ch.15)
PIVOT_HOLE_DIA = 6.5  # rides the Ø6.35 pivot shaft
ROD_HOLE_DIA = 2.0  # connecting-rod pin
ROD_HOLE_X = 25.4  # rod pin 1" from the pivot, +X side

CENTER_Y = CURVE_RADIUS + ARM_DEPTH
R_TOP = CURVE_RADIUS
R_BOTTOM = CURVE_RADIUS + ARM_DEPTH


def _bottom_point(x: float) -> tuple[float, float]:
    return (x, CENTER_Y - math.sqrt(R_BOTTOM**2 - x * x))


def _top_point_radial(x: float) -> tuple[float, float]:
    """Top-edge point on the same radial ray as the bottom point at ``x``."""
    bx, by = _bottom_point(x)
    scale = R_TOP / R_BOTTOM
    return (bx * scale, CENTER_Y - (CENTER_Y - by) * scale)


def _mid_y(x: float) -> float:
    by = _bottom_point(x)[1]
    ty = CENTER_Y - math.sqrt(R_TOP**2 - x * x)
    return (by + ty) / 2.0


def build() -> cq.Workplane:
    tail_b = _bottom_point(-TAIL_SPAN)
    rod_b = _bottom_point(ROD_SPAN)
    tail_t = _top_point_radial(-TAIL_SPAN)
    rod_t = _top_point_radial(ROD_SPAN)
    bottom_mid = (0.0, CENTER_Y - R_BOTTOM)  # (0, 0)
    top_mid = (0.0, CENTER_Y - R_TOP)  # (0, 16)

    # Closed strap profile: bottom arc -> rod end line -> top arc -> tail line.
    profile = (
        cq.Workplane("XY")
        .moveTo(*tail_b)
        .threePointArc(bottom_mid, rod_b)
        .lineTo(*rod_t)
        .threePointArc(top_mid, tail_t)
        .close()
    )

    strap = profile.extrude(ARM_THICKNESS / 2.0, both=True)

    # Two distinct bores at the local vertical mid-height, axis along Z, cut
    # through the full thickness. Built as explicit through-cylinders at global
    # (x, y) so placement does not depend on a face-workplane origin.
    for cx, dia in ((0.0, PIVOT_HOLE_DIA), (ROD_HOLE_X, ROD_HOLE_DIA)):
        cutter = (
            cq.Workplane("XY")
            .center(cx, _mid_y(cx))
            .circle(dia / 2.0)
            .extrude(ARM_THICKNESS, both=True)
        )
        strap = strap.cut(cutter)
    return strap


def render_vtk(stl_path: Path, png_path: Path) -> None:
    """Shaded VTK render (CadQuery bundles VTK). Needs a GL context -- works
    under Xvfb (``xvfb-run python rocker_arm_cadquery.py``); raises otherwise,
    so ``main`` can fall back to matplotlib."""
    import vtk  # noqa: E402

    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(stl_path))
    reader.Update()
    norms = vtk.vtkPolyDataNormals()
    norms.SetInputConnection(reader.GetOutputPort())
    norms.SetFeatureAngle(45)
    norms.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(norms.GetOutputPort())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(0.61, 0.64, 0.68)
    prop.SetDiffuse(0.85)
    prop.SetAmbient(0.22)
    prop.SetSpecular(0.55)
    prop.SetSpecularPower(45)

    fe = vtk.vtkFeatureEdges()
    fe.SetInputConnection(norms.GetOutputPort())
    fe.BoundaryEdgesOn()
    fe.FeatureEdgesOn()
    fe.SetFeatureAngle(28)
    fe.ManifoldEdgesOff()
    fe.NonManifoldEdgesOff()
    fe.Update()
    edge_mapper = vtk.vtkPolyDataMapper()
    edge_mapper.SetInputConnection(fe.GetOutputPort())
    edges = vtk.vtkActor()
    edges.SetMapper(edge_mapper)
    edges.GetProperty().SetColor(0.12, 0.12, 0.14)
    edges.GetProperty().SetLineWidth(1.4)

    ren = vtk.vtkRenderer()
    ren.AddActor(actor)
    ren.AddActor(edges)
    ren.GradientBackgroundOn()
    ren.SetBackground(0.97, 0.98, 1.0)
    ren.SetBackground2(0.80, 0.85, 0.92)
    rw = vtk.vtkRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.AddRenderer(ren)
    rw.SetSize(1800, 640)

    cam = ren.GetActiveCamera()
    cam.SetFocalPoint(0, 12, 0)  # part centre (Y 0..24)
    cam.SetViewUp(0, 1, 0)
    cam.SetPosition(40, 70, 360)  # mostly +Z (look at the broad face), slight 3/4 tilt
    ren.ResetCamera()
    cam.Zoom(1.95)
    ren.ResetCameraClippingRange()
    rw.Render()
    if not rw.GetNeverRendered() and rw.SupportsOpenGL() == 0:
        raise RuntimeError("no usable OpenGL context")

    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.SetScale(2)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(png_path))
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()
    print(f"wrote {png_path} (vtk)")


def render_mpl(stl_path: Path, png_path: Path) -> None:
    """Shaded matplotlib render (head-less): face-on elevation + 3/4 iso."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: E402
    import numpy as np  # noqa: E402
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402
    from stl import mesh as stlmesh  # noqa: E402

    m = stlmesh.Mesh.from_file(str(stl_path))
    tris = m.vectors
    n = m.normals.astype(float).copy()
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    n /= ln
    light = np.array([0.3, -0.4, 0.85])
    light /= np.linalg.norm(light)
    inten = np.clip(np.abs(n @ light), 0, 1) * 0.75 + 0.25
    colors = np.clip(inten[:, None] * np.array([0.6, 0.62, 0.66]), 0, 1)

    # Part axes: X = length (±114), Y = height (0..24), Z = thickness (±1.25).
    def panel(ax, elev, azim, title, ylim, zlim, box):
        ax.add_collection3d(
            Poly3DCollection(
                tris, facecolors=colors, edgecolors=(0, 0, 0, 0.12), linewidths=0.1
            )
        )
        ax.set_title(title, fontsize=9)
        ax.view_init(elev=elev, azim=azim)
        ax.set_xlim(-125, 125)
        ax.set_ylim(*ylim)
        ax.set_zlim(*zlim)
        ax.set_box_aspect(box)
        ax.set_xlabel("X (mm)", fontsize=7)
        ax.tick_params(labelsize=6)

    fig = plt.figure(figsize=(12, 6.5), dpi=140)
    a1 = fig.add_subplot(2, 1, 1, projection="3d")
    panel(
        a1, 90, -90,
        'face-on elevation (true aspect) — concave-up top R800 / bottom R816, '
        '16 mm depth, ±114.3 mm (4.5") half-length, Ø6.5 pivot + Ø2 rod bore',
        ylim=(-18, 42), zlim=(-30, 30), box=(250, 60, 60),
    )
    a1.set_zticks([])
    a1.set_ylabel("Y (mm)", fontsize=7)
    a2 = fig.add_subplot(2, 1, 2, projection="3d")
    panel(
        a2, 20, -70, "3/4 iso (2.5 mm plate, thickness exaggerated by the Z framing)",
        ylim=(-40, 50), zlim=(-45, 45), box=(250, 90, 90),
    )
    fig.tight_layout()
    fig.savefig(str(png_path), bbox_inches="tight", facecolor="white")
    print(f"wrote {png_path} (matplotlib)")


def render(stl_path: Path, png_path: Path) -> None:
    """Best available render: VTK when an X display is present (e.g. under
    ``xvfb-run``), else the head-less matplotlib path. VTK fails hard (not a
    Python exception) without a GL context, so gate on ``DISPLAY`` rather than
    catch."""
    import os

    if os.environ.get("DISPLAY"):
        try:
            render_vtk(stl_path, png_path)
            return
        except Exception as exc:
            print(f"vtk render failed ({exc}); using matplotlib")
    else:
        print("no DISPLAY; using matplotlib (run under xvfb-run for the VTK render)")
    render_mpl(stl_path, png_path)


def main() -> int:
    out = Path(__file__).resolve().parent.parent / "out" / "rocker-arm-cq"
    out.parent.mkdir(parents=True, exist_ok=True)
    part = build()

    vol = part.val().Volume()
    bb = part.val().BoundingBox()
    print(f"volume: {vol:,.1f} mm^3")
    print(
        f"bbox: X {bb.xmin:.1f}..{bb.xmax:.1f} ({bb.xlen:.1f})  "
        f"Y {bb.ymin:.1f}..{bb.ymax:.1f} ({bb.ylen:.1f})  "
        f"Z {bb.zmin:.1f}..{bb.zmax:.1f} ({bb.zlen:.1f})"
    )

    cq.exporters.export(part, str(out.with_suffix(".step")))
    # Fine tessellation so the arcs/bores render smooth.
    cq.exporters.export(
        part, str(out.with_suffix(".stl")), tolerance=0.004, angularTolerance=0.015
    )
    print(f"wrote {out.with_suffix('.step')} and .stl")
    render(out.with_suffix(".stl"), out.with_suffix(".png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
