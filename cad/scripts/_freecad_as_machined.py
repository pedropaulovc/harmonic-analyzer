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
import numpy
import Part
import scipy.spatial

SPEC_ENV = "HARMONIC_AS_MACHINED_SPEC"  # _as_machined.SPEC_ENV
V = FreeCAD.Vector
# A cut removing less than this changed nothing: boolean round-off.
REMOVED_EPS_MM3 = 1e-6
# Regions below this volume are summed as slivers, not measured one by one.
REGION_MIN_MM3 = 1e-3
# The largest regions measured one by one, per side.
REGION_CAP = 40
# Solids fused at once when a long program's moves are joined (_union).
UNION_CHUNK = 50
# Tessellation points per region whose distance to the other solid is measured.
THICKNESS_POINTS = 400
# Points sampled across each region face, per parameter direction.
FACE_GRID = 3
# Points sampled across each face of the solid a region is measured
# against, per parameter direction: with its mesh vertices, the bound that
# picks the faces a point's distance is measured to (_Faces).
CLOUD_GRID = 6
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
    """The tool's (r, h) half-profile from its tip up to ``height`` above it:
    the radius at ``height`` interpolated on the profile's segment that
    crosses it, its last radius carried up past its end."""
    if height <= 0:
        raise ValueError(f"a piece {-height:.3f} mm above the tool's envelope (the host drops those)")
    pts = [(r, h) for r, h in profile if h < height]
    if len(pts) == len(profile):
        return pts + [(profile[-1][0], height)]
    (r0, h0), (r1, h1) = profile[len(pts) - 1], profile[len(pts)]
    return pts + [(r0 + (r1 - r0) * (height - h0) / (h1 - h0), height)]


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
    # The inner side's radius, clamped at the axis; where the tool's radius
    # crosses the arc's on a profile segment, the point it reaches the axis.
    inner = []
    for k, (r, h) in enumerate(prof):
        if k and (prof[k - 1][0] - radius) * (r - radius) < 0:
            r0, h0 = prof[k - 1]
            inner.append((0.0, h0 + (h - h0) * (radius - r0) / (r - r0)))
        inner.append((max(radius - r, 0.0), h))
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


def _union(cutters, part):
    """The union of the cutters' solids that reach ``part``'s bound box:
    UNION_CHUNK at a time, then the chunks pairwise. One boolean of them all
    meets every stroke's neighbours at once; ms_stick's 540 numeral strokes:
    one cut each 300 s, in chunks of 20 moves 57 s, as this union 43 s."""
    solids = [s for c in cutters for s in c.Solids if s.BoundBox.intersect(part.BoundBox)]
    level = [solids[k].fuse(solids[k + 1:k + UNION_CHUNK]) if len(solids[k:k + UNION_CHUNK]) > 1 else solids[k]
             for k in range(0, len(solids), UNION_CHUNK)]
    while len(level) > 1:
        level = [level[i].fuse(level[i + 1]) if i + 1 < len(level) else level[i] for i in range(0, len(level), 2)]
    return level[0] if level else None


def simulate(part, programs, profiles, cad, move_cap):
    """Cut every move from ``part`` in order. A program of at most ``move_cap``
    moves is cut move by move: each move's removed volume is exact. A longer
    one (engraving) is cut as two unions (:func:`_union`), its feed moves
    then its rapids, and each probed move (a pass or a rapid, as the host
    marks them) is measured on its own: a pass against the part before the
    program (one sharing nothing with it removed nothing), a rapid against
    the part after all the program's feed moves. So such a program's rapid
    check misses a rapid through material any of its feed moves cleared,
    earlier or later. Per program: the moves' volumes (None where not
    measured), the total and the volume shed as loose offcuts."""
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
                if rapid:
                    fed = part
                union = _union([c for move, c in zip(moves, cutters) if (move.get("probe") == "rapid") == rapid], part)
                if union is not None:
                    cut = part.cut(union)
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


class _Faces:
    """A solid's faces, their bound boxes and points on them: a point's
    distance to the solid is measured to the few faces that can hold its
    nearest point, those whose box comes within the distance to the nearest
    of those points, not to every face (12.6 ms a point against ms_stick's
    engraved CAD)."""

    def __init__(self, shape):
        self.faces = shape.Faces
        boxes = [f.BoundBox for f in self.faces]
        self.lo = numpy.array([[b.XMin, b.YMin, b.ZMin] for b in boxes])
        self.hi = numpy.array([[b.XMax, b.YMax, b.ZMax] for b in boxes])
        cloud = list(MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05, AngularDeflection=0.3,
                                            Relative=False).Topology[0])
        for face in self.faces:
            u0, u1, v0, v1 = face.ParameterRange
            for i in range(CLOUD_GRID):
                for j in range(CLOUD_GRID):
                    u = u0 + (u1 - u0) * (i + 0.5) / CLOUD_GRID
                    v = v0 + (v1 - v0) * (j + 0.5) / CLOUD_GRID
                    if face.isPartOfDomain(u, v):
                        cloud.append(face.valueAt(u, v))
        self.cloud = scipy.spatial.cKDTree(numpy.array([[p.x, p.y, p.z] for p in cloud]))

    def bounds(self, points):
        """Per point, at least its distance to the solid: to the nearest
        point known on it."""
        return self.cloud.query(points)[0]

    def distance(self, point, bound):
        """The point's distance to the solid, at most ``bound``: to the faces
        whose box comes within ``bound`` of it."""
        gap = numpy.maximum(self.lo - point, 0.0) + numpy.maximum(point - self.hi, 0.0)
        near = numpy.nonzero(numpy.sqrt((gap ** 2).sum(-1)) <= bound + 1e-9)[0]
        shape = self.faces[near[0]] if len(near) == 1 else Part.makeCompound([self.faces[i] for i in near])
        return shape.distToShape(Part.Vertex(V(*point)))[0]


def thickness(region, whole, other, faces):
    """The region's (of ``whole`` less ``other``, whose :class:`_Faces` are
    ``faces``) farthest sampled point from ``other``. Sampled at the mesh
    vertices and on a FACE_GRID x FACE_GRID grid inside every face: a
    cylinder's mesh has vertices on its edges only, and a plugged hole or a
    ring left in a groove touches ``other`` along every edge (its depth
    shows at the middle of its cap). And on a lattice inside it (cells of
    LATTICE_MM where that makes fewer than LATTICE_CELLS): a plugged hole
    under a thin strip left over it has no cap of its own. A lattice point
    that would set the depth must be in ``whole`` and not in ``other``: the
    region's own inside test misplaced the bracket's tap-mouth rings'
    lattice into the metal around the hole. The points are measured from
    the farthest bound down, until no bound beats the depth found."""
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
    surface = _strided(grid, 2 * THICKNESS_POINTS) + _strided([V(*p) for p in mesh.Topology[0]], THICKNESS_POINTS)
    points = numpy.array([[p.x, p.y, p.z] for p in surface + _lattice(region)])
    bounds = faces.bounds(points)
    best, where = 0.0, None
    for i in numpy.argsort(-bounds):
        if bounds[i] <= best:
            break
        d = faces.distance(points[i], bounds[i])
        p = V(*points[i])
        if d > best and (i < len(surface) or whole.isInside(p, 1e-6, False) and not other.isInside(p, 1e-6, True)):
            best, where = d, [p.x, p.y, p.z]
    return best, where


def regions(whole, other):
    solids = sorted(whole.cut(other).Solids, key=lambda s: -s.Volume)
    big = [s for s in solids if s.Volume >= REGION_MIN_MM3]
    faces = _Faces(other) if big else None
    measured = []
    for s in big[:REGION_CAP]:
        t, at = thickness(s, whole, other, faces)
        measured.append({"volume_mm3": s.Volume, "thickness_mm": t, "at_mm": at, "extent_mm": _bbox(s)})
    return measured, {
        "unmeasured_regions": len(big) - len(measured),
        "unmeasured_mm3": sum(s.Volume for s in big[REGION_CAP:]),
        "unmeasured": [{"volume_mm3": s.Volume, "extent_mm": _bbox(s)} for s in big[REGION_CAP:]],
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
