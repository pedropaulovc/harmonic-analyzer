"""FreeCAD-side as-machined simulation. Runs INSIDE ``freecadcmd``, never on the host.

``_as_machined.py`` launches ``freecadcmd _freecad_as_machined.py`` with the
path of a JSON spec in ``$HARMONIC_AS_MACHINED_SPEC`` (the spec travels in the
environment: ``freecadcmd`` opens every extra argument as a document). Per
part and per blank length: the blank (its prisms' union), then every posted move that can
reach it, in program order, as the solid its tool sweeps (the tool's
half-profile ``r(h)`` revolved standing, swept along a flat segment or around
a flat arc), moved into model coordinates by the setup's frame and cut from
the part with OCC booleans. Each move's removed volume is the part's volume
before less after. Then the as-machined solid against the CAD STEP: volume,
centre of mass, bound box, the material left (as-machined less CAD) and the
gouges (CAD less as-machined), each region's volume and thickness (the
farthest tessellation point of the region from the other solid). It prints
one marker line of JSON: the results, or the traceback.

Measured on FreeCAD 1.1.4 headless (the column clamp trial, 2026-11-25):

- ``Shape.transformGeometry`` turns analytic cylinders into B-spline
  approximations: a 7.25 mm3 false gouge in the clamp's bore, loose bound
  boxes and 30x the boolean time. ``transformShape`` with a rigid matrix
  keeps the surfaces exact, so the frames here are rigid (the host refuses
  any other).
- The CAM workbench's ``PathSimulator.PathSim`` runs headless but returns an
  open mesh (``isSolid`` False), not a solid to measure.
"""

import json
import math
import os
import time
import traceback

import FreeCAD
import MeshPart
import Part

SPEC_ENV = "HARMONIC_AS_MACHINED_SPEC"  # _as_machined.SPEC_ENV
V = FreeCAD.Vector
# A cut removing less than this changed nothing: boolean round-off.
REMOVED_EPS_MM3 = 1e-6
# Regions below this volume are summed as slivers, not measured one by one.
REGION_MIN_MM3 = 1e-3
# The largest regions measured one by one, per side.
REGION_CAP = 40
# Tessellation points per region whose distance to the other solid is measured.
THICKNESS_POINTS = 400
# Points sampled across each region face, per parameter direction.
FACE_GRID = 3
# The lattice inside each region: cells of LATTICE_MM (a plugged 1.85 mm
# pilot hole gets ~200), coarser where that would make more than about
# LATTICE_CELLS (each inside cell costs a distance query).
LATTICE_MM = 0.5
LATTICE_CELLS = 2000


def _clean(points):
    out = []
    for p in points:
        if not out or (p - out[-1]).Length > 1e-9:
            out.append(p)
    if len(out) > 1 and (out[0] - out[-1]).Length <= 1e-9:
        out.pop()
    return out


def _profile(profile, height):
    """The tool's (r, h) half-profile from its tip, its last radius carried up
    to ``height`` above the tip."""
    pts = [(r, h) for r, h in profile if h < height]
    return pts + [(profile[-1][0] if not pts else pts[-1][0], height)]


def standing(profile, x, y, z, top):
    prof = _profile(profile, top - z)
    pts = _clean([V(0, 0, z)] + [V(r, 0, z + h) for r, h in prof] + [V(0, 0, z + prof[-1][1])])
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    solid = face.revolve(V(0, 0, 0), V(0, 0, 1), 360)
    solid.translate(V(x, y, 0))
    return solid


def segment(profile, a, b, z, top, caps=(True, True)):
    (ax, ay), (bx, by) = a, b
    length = math.hypot(bx - ax, by - ay)
    if length < 1e-6:
        return [standing(profile, ax, ay, z, top)]
    ends = [standing(profile, x, y, z, top) for cap, (x, y) in zip(caps, (a, b)) if cap]
    nx, ny = -(by - ay) / length, (bx - ax) / length
    prof = _profile(profile, top - z)
    pts = [V(ax - nx * r, ay - ny * r, z + h) for r, h in reversed(prof)]
    pts += [V(ax + nx * r, ay + ny * r, z + h) for r, h in prof]
    face = Part.Face(Part.makePolygon(_clean(pts) + [_clean(pts)[0]]))
    return ends + [face.extrude(V(bx - ax, by - ay, 0))]


def arc(profile, c, radius, a0, sweep, z, top):
    cx, cy = c
    prof = _profile(profile, top - z)
    inner = [(max(radius - r, 0.0), h) for r, h in prof]
    outer = [(radius + r, h) for r, h in prof]
    pts = _clean([V(cx + r, cy, z + h) for r, h in reversed(inner)] + [V(cx + r, cy, z + h) for r, h in outer])
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    degrees = min(math.degrees(abs(sweep)), 360.0)
    start = a0 if sweep > 0 else a0 + sweep
    solid = face.revolve(V(cx, cy, 0), V(0, 0, 1), degrees)
    solid.rotate(V(cx, cy, 0), V(0, 0, 1), math.degrees(start))
    p0 = (cx + radius * math.cos(a0), cy + radius * math.sin(a0))
    p1 = (cx + radius * math.cos(a0 + sweep), cy + radius * math.sin(a0 + sweep))
    return [solid, standing(profile, *p0, z, top), standing(profile, *p1, z, top)]


def solids_of(piece, profile, top):
    kind = piece["kind"]
    if kind == "stand":
        return [standing(profile, piece["x"], piece["y"], piece["z"], top)]
    if kind == "seg":
        return segment(profile, piece["a"], piece["b"], piece["z"], top, piece["caps"])
    return arc(profile, piece["c"], piece["r"], piece["a0"], piece["sweep"], piece["z"], top)


def matrix(origin, axes):
    """Setup frame to model: p = origin + axes^T q (``axes`` rows are the
    frame's X, Y, Z in model coordinates)."""
    m = FreeCAD.Matrix()
    rows = [[axes[k][i] for k in range(3)] + [origin[i]] for i in range(3)]
    m.A11, m.A12, m.A13, m.A14 = rows[0]
    m.A21, m.A22, m.A23, m.A24 = rows[1]
    m.A31, m.A32, m.A33, m.A34 = rows[2]
    return m


def _bbox(shape):
    bb = shape.optimalBoundingBox() if hasattr(shape, "optimalBoundingBox") else shape.BoundBox
    return [[bb.XMin, bb.XMax], [bb.YMin, bb.YMax], [bb.ZMin, bb.ZMax]]


def _keep(shape, cad):
    """The cut's solid that is the part: the one sharing most volume with
    the CAD (a profile that cuts the part free leaves the frame beside it)."""
    solids = shape.Solids
    if len(solids) == 1:
        return solids[0], 0.0
    best = max(solids, key=lambda s: s.common(cad).Volume)
    return best, sum(s.Volume for s in solids if s is not best)


def _cutter(move, profiles, top, place):
    profile = profiles[str(move["tool"])]
    solids = []
    for piece in move["pieces"]:
        solids += solids_of(piece, profile, top)
    cutter = Part.makeCompound(solids)
    # A rigid move keeps the analytic surfaces exact.
    cutter.transformShape(place)
    return cutter


def _common(cutter, part):
    if not cutter.BoundBox.intersect(part.BoundBox):
        return 0.0
    return sum(part.common(solid).Volume for solid in cutter.Solids if solid.BoundBox.intersect(part.BoundBox))


def simulate(part, programs, profiles, cad, move_cap):
    """Cut every move from ``part`` in order. A program of at most ``move_cap``
    moves is cut move by move: each move's removed volume is exact. A longer
    one (engraving, long finishing) is cut in two booleans, its feed moves
    then its rapids; each probed move (a pass or a rapid, as the host marks
    them) is measured against the part before the program (a pass sharing
    nothing with it removed nothing) or after its feed moves (a rapid
    sharing material with that cut), bounds that miss only what the
    program's own earlier moves cleared. Per program: the moves' volumes
    (None where not measured), the total and the volume shed as loose
    offcuts."""
    out = []
    for program in programs:
        t0 = time.perf_counter()
        place = matrix(program["origin"], program["axes"])
        moves = program["moves"]
        removed, shed = [], 0.0
        start = before = part.Volume
        if len(moves) <= move_cap:
            for move in moves:
                cutter = _cutter(move, profiles, program["top"], place)
                if not cutter.BoundBox.intersect(part.BoundBox):
                    removed.append(0.0)
                    continue
                cut = part.cut(cutter.Solids)
                if not cut.Solids:
                    raise RuntimeError(f"{program['name']} move {move['index']} cut the whole part away")
                kept, loose = _keep(cut, cad)
                after = kept.Volume  # OCC recomputes it on every access
                gone = before - after
                if gone > REMOVED_EPS_MM3:
                    part, before, shed = kept, after, shed + loose
                    removed.append(gone)
                else:
                    removed.append(0.0)
            accounting = "per move"
        else:
            # Feed moves first: material still there after all of them was
            # there when any rapid of the program passed; then the rapids.
            cutters = [_cutter(move, profiles, program["top"], place) for move in moves]
            initial = part
            for rapid in (False, True):
                solids = [solid for move, cutter in zip(moves, cutters) if (move.get("probe") == "rapid") == rapid
                          for solid in cutter.Solids]
                if rapid:
                    fed = part
                if solids:
                    cut = part.cut(solids)
                    if not cut.Solids:
                        raise RuntimeError(f"{program['name']} cut the whole part away")
                    part, loose = _keep(cut, cad)
                    shed += loose
            for move, cutter in zip(moves, cutters):
                if move.get("probe") == "pass":
                    removed.append(_common(cutter, initial))
                elif move.get("probe") == "rapid":
                    removed.append(_common(cutter, fed))
                else:
                    removed.append(None)
            accounting = f"batched ({len(moves)} moves > {move_cap})"
        part = part.removeSplitter()
        out.append({"name": program["name"], "removed_mm3": removed, "total_mm3": start - part.Volume,
                    "shed_mm3": shed, "accounting": accounting, "seconds": time.perf_counter() - t0})
    return part, out


def _strided(points, cap):
    if len(points) <= cap:
        return points
    step = len(points) / cap
    return [points[int(k * step)] for k in range(cap)]


def _lattice(region):
    """Cell centres of a lattice over the region's bound box (LATTICE_MM
    cells or about LATTICE_CELLS cubic cells, whichever is coarser, at least
    3 along every side) that lie inside the region."""
    bb = region.BoundBox
    spans = [(bb.XMin, bb.XLength), (bb.YMin, bb.YLength), (bb.ZMin, bb.ZLength)]
    step = max(LATTICE_MM, max(length for _lo, length in spans) / 64,
               (bb.XLength * bb.YLength * bb.ZLength / LATTICE_CELLS) ** (1 / 3))
    counts = [max(3, round(length / step)) for _lo, length in spans]
    while counts[0] * counts[1] * counts[2] > 3 * LATTICE_CELLS:
        step *= 1.25
        counts = [max(3, round(length / step)) for _lo, length in spans]
    inside = []
    for i in range(counts[0]):
        for j in range(counts[1]):
            for k in range(counts[2]):
                p = V(*(lo + length * (n + 0.5) / count for (lo, length), n, count in zip(spans, (i, j, k), counts)))
                if region.isInside(p, 1e-6, True):
                    inside.append(p)
    return inside


def _near(other, region):
    """``other``'s faces within reach of the region. The region (outside
    ``other``) touches it, so no point of the region is farther from it than
    the region's bound box diagonal: faces beyond that cannot be nearest."""
    reach = region.BoundBox.DiagonalLength + 1e-3
    box = FreeCAD.BoundBox(region.BoundBox)
    box.enlarge(reach)
    faces = [f for f in other.Faces if f.BoundBox.intersect(box)]
    return Part.makeCompound(faces) if faces else other


def thickness(region, whole, other):
    """The region's (of ``whole`` less ``other``) farthest sampled point from
    ``other``. Sampled at the mesh vertices and on a FACE_GRID x FACE_GRID
    grid inside every face: a cylinder's mesh has vertices on its edges
    only, and a plugged hole or a ring left in a groove touches ``other``
    along every edge (its depth shows at the middle of its cap). And on a
    lattice inside it (cells of LATTICE_MM where that makes fewer than
    LATTICE_CELLS): a plugged hole under a thin strip left over it has no
    cap of its own. A lattice point that would set the depth must be in
    ``whole`` and not in ``other``: the region's own inside test misplaced
    the bracket's tap-mouth rings' lattice into the metal around the hole."""
    grid = []
    for face in region.Faces:
        u0, u1, v0, v1 = face.ParameterRange
        for i in range(FACE_GRID):
            for j in range(FACE_GRID):
                u = u0 + (u1 - u0) * (i + 0.5) / FACE_GRID
                v = v0 + (v1 - v0) * (j + 0.5) / FACE_GRID
                if face.isPartOfDomain(u, v):
                    grid.append(face.valueAt(u, v))
    mesh = MeshPart.meshFromShape(Shape=region, LinearDeflection=0.01, AngularDeflection=0.2, Relative=False)
    pts = _strided(grid, 2 * THICKNESS_POINTS) + _strided([V(*p) for p in mesh.Topology[0]], THICKNESS_POINTS)
    near = _near(other, region)
    best, where = 0.0, None
    for lattice, sample in ((False, pts), (True, _lattice(region))):
        for p in sample:
            d = near.distToShape(Part.Vertex(p))[0]
            if d > best and (not lattice or whole.isInside(p, 1e-6, False) and not other.isInside(p, 1e-6, True)):
                best, where = d, [p.x, p.y, p.z]
    return best, where


def regions(whole, other):
    solids = sorted(whole.cut(other).Solids, key=lambda s: -s.Volume)
    big = [s for s in solids if s.Volume >= REGION_MIN_MM3]
    measured = []
    for s in big[:REGION_CAP]:
        t, at = thickness(s, whole, other)
        measured.append({"volume_mm3": s.Volume, "thickness_mm": t, "at_mm": at, "extent_mm": _bbox(s)})
    return measured, {
        "unmeasured_regions": len(big) - len(measured),
        "unmeasured_mm3": sum(s.Volume for s in big[REGION_CAP:]),
        "slivers_mm3": sum(s.Volume for s in solids if s.Volume < REGION_MIN_MM3),
    }, big


def _triangles(shape, deflection):
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=deflection, AngularDeflection=0.3, Relative=False)
    points, facets = mesh.Topology
    return [[list(points[i]) for i in facet] for facet in facets]


def run_part(spec_part, noise_mm, mesh_dir, move_cap):
    cad = Part.Shape()
    cad.read(spec_part["step"])
    if len(cad.Solids) != 1:
        raise RuntimeError(f"{spec_part['step']} holds {len(cad.Solids)} solids, not one")
    cad = cad.Solids[0]
    profiles = spec_part["profiles"]
    variants = []
    for variant in spec_part["variants"]:
        t0 = time.perf_counter()
        prisms = []
        for prism in variant["blank"]:
            base = [V(*p) for p in prism["base"]]
            prisms.append(Part.Face(Part.makePolygon(base + [base[0]])).extrude(V(*prism["dir"])))
        blank = prisms[0] if len(prisms) == 1 else prisms[0].fuse(prisms[1:]).removeSplitter()
        if len(blank.Solids) != 1:
            raise RuntimeError(f"the blank's prisms make {len(blank.Solids)} solids, not one")
        blank = blank.Solids[0]
        part, programs = simulate(blank, variant["programs"], profiles, cad, move_cap)
        t1 = time.perf_counter()
        left, left_rest, left_solids = regions(part, cad)
        gouge, gouge_rest, gouge_solids = regions(cad, part)
        t2 = time.perf_counter()
        meshes = None
        over = [r for r in left + gouge if r["thickness_mm"] > noise_mm]
        if over and mesh_dir:
            meshes = os.path.join(mesh_dir, f"{spec_part['id'] or 'part'}-{variant['name']}.json")
            with open(meshes, "w", encoding="utf-8") as handle:
                json.dump({
                    "cad": _triangles(cad, 0.05),
                    "left": [_triangles(s, 0.02) for s, r in zip(left_solids, left) if r["thickness_mm"] > noise_mm],
                    "gouge": [_triangles(s, 0.02) for s, r in zip(gouge_solids, gouge) if r["thickness_mm"] > noise_mm],
                }, handle)
        variants.append({
            "name": variant["name"],
            "blank_mm3": blank.Volume,
            "am": {"volume_mm3": part.Volume, "cog_mm": list(part.CenterOfMass), "bbox_mm": _bbox(part),
                   "solids": len(part.Solids)},
            "programs": programs,
            "left": left, "left_rest": left_rest,
            "gouge": gouge, "gouge_rest": gouge_rest,
            "meshes": meshes,
            "seconds": {"simulate": t1 - t0, "compare": t2 - t1},
        })
    return {"id": spec_part["id"], "cad": {"volume_mm3": cad.Volume, "cog_mm": list(cad.CenterOfMass),
                                           "bbox_mm": _bbox(cad)}, "variants": variants}


def main():
    with open(os.environ[SPEC_ENV], encoding="utf-8") as handle:
        spec = json.load(handle)
    try:
        parts = [run_part(p, spec["noise_mm"], spec.get("mesh_dir"), spec["move_cap"]) for p in spec["parts"]]
        result = {"freecad_version": ".".join(FreeCAD.Version()[:3]), "parts": parts}
    except Exception:  # noqa: BLE001 -- the traceback is the host's report
        result = {"error": traceback.format_exc()}
    print(spec["marker"] + json.dumps(result), flush=True)


main()
