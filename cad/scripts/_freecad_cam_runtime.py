"""FreeCAD-side CAM helpers and entry point. Runs INSIDE ``freecadcmd``, never on the host.

``cam_nc.py`` launches ``freecadcmd _freecad_cam_runtime.py`` with the path of
a JSON job spec in ``$HARMONIC_CAM_SPEC`` (``_cam_programs.SPEC_ENV``): the
recipe's path, its context, its programs, the output directory and the result
marker. This file loads the recipe, calls its ``build(ctx, rt)`` with these
helpers as ``rt``, posts one file per program and prints one marker line of
JSON: the files and FreeCAD version, or the traceback. Every length crossing
these helpers is in millimetres, every feed in mm/min.

Each helper encodes a behaviour measured on FreeCAD 1.1.4 headless while
programming the oblique base bar (2026-11-16):

- ``freecadcmd`` opens every extra command-line argument as a document
  ("File format not supported"), so the spec travels in the environment; the
  script runs with ``__name__`` set to its file stem, never ``"__main__"``.
- a new Job carries a default tool controller, and creating an operation while
  a job holds two controllers and no earlier operation raises inside
  ``PathUtils.findToolController`` (it asks a GUI to choose). :func:`job`
  removes the default; :func:`_operation` adds each controller just before
  its first operation, after which a new operation inherits the previous one's.
- an operation's depths and heights are expressions bound to its ``Op*``
  values; a number assigned without clearing the expression is overwritten at
  the next recompute.
- a tool controller's feed given as a bare number is mm/s; it takes
  ``"N mm/min"``.
- MillFace (a pocket) generates nothing without a ``Base`` face.
- Profile on an open edge cuts along the edge from end to end at the side's
  offset, one pass per ``NumPasses`` station outermost first, depth level by
  depth level, retracting to the clearance height between passes;
  ``Direction`` "CCW" runs anticlockwise round the model, i.e. conventional
  outside the part with a clockwise spindle.
- the ``grbl`` post expands G81/G82/G83 into G0/G1 (GRBL has no canned
  cycles) but leaves G73 chip-breaking as a G73 block GRBL rejects, so pecks
  are full-retract G83.
"""

import importlib.util
import inspect
import json
import os
import traceback
import types

import FreeCAD
import Part
import Path
import Path.Main.Job as PathJob
import Path.Main.Stock as PathStock
import Path.Op.Drilling as PathDrilling
import Path.Op.MillFace as PathMillFace
import Path.Op.Profile as PathProfile
import Path.Tool.Controller as PathToolController
from Path.Post.Processor import PostProcessorFactory
from PathScripts import PathUtils
from Path.Tool.toolbit import ToolBit

SPEC_ENV = "HARMONIC_CAM_SPEC"  # _cam_programs.SPEC_ENV
POST = "grbl"
# No header: its output timestamp would make every post of the same toolpath differ.
POST_ARGS = "--no-header --no-show-editor --precision 3"
_TOL = 1e-3
# Commands that move the tool at feed: a toolpath without one cut nothing.
_MOTION = {"G1", "G01", "G2", "G02", "G3", "G03", "G81", "G82", "G83"}
# Path.Area fits arcs to its offset polygons within 0.01 mm by default: the
# base-bar slot's 0.381 mm cutter-centre end arcs came out as three arcs up to
# 0.023 mm off the true offset (and 0.002 mm at 0.001). The posted checks
# hold positions to 0.002 mm.
AREA_ACCURACY_MM = 0.0001

def document():
    Path.Area.setDefaultParams(Accuracy=AREA_ACCURACY_MM)
    return FreeCAD.newDocument("cam")


def _feature(doc, name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj


def import_step(doc, name, path, origin, axes):
    """The STEP's single solid expressed in a setup frame: ``origin`` is the frame
    origin in model mm and ``axes`` the model-space unit vectors that become the
    frame's X, Y and Z, so a model point p maps to ``axes · (p - origin)``."""
    shape = Part.Shape()
    shape.read(path)
    if len(shape.Solids) != 1:
        raise RuntimeError(f"{path}: expected one solid, read {len(shape.Solids)}")
    rows = [list(axis) + [-sum(axis[i] * origin[i] for i in range(3))] for axis in axes]
    matrix = FreeCAD.Matrix(*rows[0], *rows[1], *rows[2], 0, 0, 0, 1)
    moved = shape.Solids[0].copy()
    moved.transformShape(matrix)
    return _feature(doc, name, moved)


def box(doc, name, x, y, z):
    """Box spanning the (min, max) mm ranges ``x``, ``y``, ``z``."""
    return _feature(doc, name, Part.makeBox(x[1] - x[0], y[1] - y[0], z[1] - z[0], FreeCAD.Vector(x[0], y[0], z[0])))


def job(doc, label, models, stock):
    """A Job over ``models`` whose stock is the box spanning ``stock``'s
    (min, max) ranges, with no tool controller yet. Its WCS is the model
    origin, i.e. the setup frame the models were built in."""
    result = PathJob.Create(label, models)
    (x0, x1), (y0, y1), (z0, z1) = stock
    default = result.Stock
    result.Stock = PathStock.CreateBox(
        result, extent=FreeCAD.Vector(x1 - x0, y1 - y0, z1 - z0),
        placement=FreeCAD.Placement(FreeCAD.Vector(x0, y0, z0), FreeCAD.Rotation()),
    )
    doc.removeObject(default.Name)
    for tc in list(result.Tools.Group):
        result.Tools.removeObject(tc)
        doc.removeObject(tc.Name)
    result.PostProcessor = POST
    result.PostProcessorArgs = POST_ARGS
    return result


def model(target_job, index=0):
    """The job's copy of its ``index``-th model: operations select its sub-shapes."""
    return target_job.Model.Group[index]


def tool_controller(doc, label, number, shape, diameter, rpm, feed, plunge, flutes=None, tip_angle=None):
    """A controller for a ``shape`` bit (``endmill``, ``drill``, ...) of ``diameter``
    at ``rpm``, cutting at ``feed`` and plunging at ``plunge`` (mm/min)."""
    tool = ToolBit.from_shape_id(f"{shape}.fcstd").attach_to_doc(doc=doc)
    tool.Label = label
    tool.Diameter = f"{diameter} mm"
    if flutes is not None:
        tool.Flutes = flutes
    if tip_angle is not None:
        tool.TipAngle = f"{tip_angle} deg"
    tc = PathToolController.Create(f"T{number} {label}", tool, number, assignViewProvider=False)
    tc.SpindleSpeed = float(rpm)
    tc.HorizFeed = f"{feed} mm/min"
    tc.VertFeed = f"{plunge} mm/min"
    return tc


def _set(op, **values):
    """Assign lengths, clearing the expression that would otherwise overwrite them."""
    for key, value in values.items():
        op.setExpression(key, None)
        setattr(op, key, value)


def _operation(module, target_job, tc, label):
    if tc not in target_job.Tools.Group:
        target_job.Proxy.addToolController(tc)
    op = module.Create(label, parentJob=target_job)
    op.ToolController = tc
    return op


def _near(a, b):
    return abs(a - b) < _TOL


def _name(shape, kind, sub):
    items = shape.Edges if kind == "Edge" else shape.Faces
    for index, item in enumerate(items):
        if item.isSame(sub):
            return f"{kind}{index + 1}"
    raise RuntimeError(f"{kind} not found in its shape")


def straight_edge(target, **coords):
    """``(model, [name])`` of the single straight edge whose both ends lie at the
    given mm coordinates, e.g. ``straight_edge(m, y=0, z=0)``."""
    index = {"x": 0, "y": 1, "z": 2}
    found = [
        f"Edge{i + 1}" for i, edge in enumerate(target.Shape.Edges)
        if isinstance(edge.Curve, Part.Line)
        and all(_near(v.Point[index[k]], value) for v in edge.Vertexes for k, value in coords.items())
    ]
    if len(found) != 1:
        raise RuntimeError(f"{target.Label}: {len(found)} straight edges at {coords}")
    return (target, found)


def inner_loop(target, z, x, y):
    """``(model, edge names)`` of the inner loop of the horizontal planar face at
    height ``z`` that encloses (x, y)."""
    shape = target.Shape
    for face in shape.Faces:
        bb = face.BoundBox
        if not isinstance(face.Surface, Part.Plane) or not (_near(bb.ZMin, z) and _near(bb.ZMax, z)):
            continue
        for wire in face.Wires:
            if wire.isSame(face.OuterWire):
                continue
            wb = wire.BoundBox
            if wb.XMin <= x <= wb.XMax and wb.YMin <= y <= wb.YMax:
                return (target, [_name(shape, "Edge", e) for e in wire.Edges])
    raise RuntimeError(f"{target.Label}: no inner loop at z={z} around ({x}, {y})")


def top_face(target, z):
    """``(model, [name])`` of the single horizontal planar face at height ``z``."""
    found = [
        f"Face{i + 1}" for i, face in enumerate(target.Shape.Faces)
        if isinstance(face.Surface, Part.Plane) and _near(face.BoundBox.ZMin, z) and _near(face.BoundBox.ZMax, z)
    ]
    if len(found) != 1:
        raise RuntimeError(f"{target.Label}: {len(found)} horizontal faces at z={z}")
    return (target, found)


def holes(target, diameter, centres):
    """``(model, face names)``: one vertical cylinder face of ``diameter`` per
    (x, y) centre. A hole exported as several patches yields its first, so each
    centre is drilled once."""
    names = []
    for x, y in centres:
        match = [
            f"Face{i + 1}" for i, face in enumerate(target.Shape.Faces)
            if isinstance(face.Surface, Part.Cylinder)
            and abs(face.Surface.Radius * 2 - diameter) < _TOL
            and abs(abs(face.Surface.Axis.z) - 1) < 1e-9
            and abs(face.Surface.Center.x - x) < 1e-2 and abs(face.Surface.Center.y - y) < 1e-2
        ]
        if not match:
            raise RuntimeError(f"{target.Label}: no Ø{diameter} hole at ({x}, {y})")
        names.append(match[0])
    return (target, names)


def profile(target_job, tc, label, base, side, direction, start, final, step,
            clearance=None, safe=None, offset=0.0, passes=1, stepover=0.0, start_point=None):
    """Profile ``base`` (edges) on ``side`` running ``direction`` from ``start``
    down to ``final`` in levels of at most ``step``. ``offset`` moves the pass
    beyond the cutter-radius offset; ``passes`` stations ``stepover`` apart run
    outermost first. ``start_point`` (x, y) picks where a closed loop is entered."""
    op = _operation(PathProfile, target_job, tc, label)
    op.Base = [base]
    op.Side = side
    op.Direction = direction
    op.UseComp = True
    op.NumPasses = passes
    op.Stepover = stepover
    op.OffsetExtra = offset
    heights = {"ClearanceHeight": clearance} if clearance is not None else {}
    if safe is not None:
        heights["SafeHeight"] = safe
    _set(op, StartDepth=start, FinalDepth=final, StepDown=step, **heights)
    if start_point is not None:
        op.UseStartPoint = True
        op.StartPoint = FreeCAD.Vector(start_point[0], start_point[1], start)
    return op


def face(target_job, tc, label, base, start, final, stepover, safe=None):
    """Zigzag facing of ``base`` (a face) from ``start`` to ``final`` in one level:
    straight passes along X, alternate passes reversed, at most ``stepover``
    apart, the cutter kept inside the face's bounding box. ``safe`` is the
    height each plunge starts from."""
    op = _operation(PathMillFace, target_job, tc, label)
    op.Base = [base]
    op.BoundaryShape = "Boundbox"
    op.ClearEdges = False
    op.ClearingPattern = "ZigZag"
    op.ZigZagAngle = 0.0
    # StepOver is a whole percentage of the cutter diameter: round down.
    op.StepOver = int(100 * stepover / float(tc.Tool.Diameter))
    _set(op, StartDepth=start, FinalDepth=final, StepDown=start - final, **({"SafeHeight": safe} if safe is not None else {}))
    return op


def drill(target_job, tc, label, base, top, final, retract, peck=None):
    """Drill every hole face in ``base`` from the stock top ``top`` to ``final``
    (the tool's tip, no tip allowance added), from the R plane ``retract``;
    ``peck`` gives full-retract pecks of that depth."""
    op = _operation(PathDrilling, target_job, tc, label)
    op.Base = [base]
    op.ExtraOffset = "None"
    op.KeepToolDown = False
    op.DwellEnabled = False
    op.chipBreakEnabled = False
    op.PeckEnabled = peck is not None
    if peck is not None:
        _set(op, PeckDepth=peck)
    _set(op, StartDepth=top, FinalDepth=final, RetractHeight=retract)
    return op


def generate(doc):
    """Recompute every toolpath; fail when an operation is invalid or cut nothing."""
    doc.recompute()
    bad = []
    for target_job in [o for o in doc.Objects if isinstance(getattr(o, "Proxy", None), PathJob.ObjectJob)]:
        for op in target_job.Operations.Group:
            if "Invalid" in op.State or not any(c.Name in _MOTION for c in op.Path.Commands):
                bad.append(f"{target_job.Label} / {op.Label}: {list(op.State) or 'no feed move'}")
    if bad:
        raise RuntimeError("toolpaths not clean: " + "; ".join(bad))


def _flatten(items):
    for item in items:
        if isinstance(item, (list, tuple)):
            yield from _flatten(item)
        else:
            yield item


def post(ops, path, name, comment):
    """Post ``ops`` (one Job's operations, all of them, in order) to ``path`` with
    a header naming the program and its tools. Returns the path and the file of
    the post the factory loaded: FreeCAD searches user post directories before
    its own, so the name alone does not say which file posted."""
    jobs = {PathUtils.findParentJob(op).Name: PathUtils.findParentJob(op) for op in ops}
    if len(jobs) != 1:
        raise RuntimeError(f"{name}: operations from jobs {sorted(jobs)}; a program is one job")
    (target_job,) = jobs.values()
    if [op.Name for op in target_job.Operations.Group] != [op.Name for op in ops]:
        raise RuntimeError(f"{name}: job {target_job.Label} holds operations the program does not list")
    processor = PostProcessorFactory.get_post_processor(target_job, POST)
    source = getattr(processor, "script_path", None) or inspect.getfile(type(processor))
    sections = processor.export()
    if len(sections) != 1:
        raise RuntimeError(f"{name}: post returned {len(sections)} sections")
    tools = sorted({(tc.ToolNumber, float(tc.Tool.Diameter), tc.Tool.Label) for tc in target_job.Tools.Group})
    header = [f"({name})", f"({comment})"] + [f"(T{n} D={d:.3f} {label})" for n, d, label in tools]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(header) + "\n" + sections[0][1])
    return path, os.path.abspath(source)


def _load_recipe(path):
    spec = importlib.util.spec_from_file_location("cam_recipe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    with open(os.environ[SPEC_ENV], encoding="utf-8") as handle:
        spec = json.load(handle)
    try:
        rt = types.ModuleType("_freecad_cam_runtime")
        rt.__dict__.update({k: v for k, v in globals().items() if not k.startswith("__")})
        built = _load_recipe(spec["recipe"]).build(spec["ctx"], rt)
        posted = [
            post(list(_flatten(built["ops"][key] for key in keys)), os.path.join(spec["out_dir"], f"{name}.nc"), name, spec["ctx"]["comment"])
            for name, keys in spec["programs"]
        ]
        sources = sorted({source for _path, source in posted})
        if len(sources) != 1:
            raise RuntimeError(f"programs posted by several post files: {sources}")
        result = {"freecad_version": ".".join(FreeCAD.Version()[:3]), "post": sources[0], "files": [p for p, _s in posted]}
    except Exception:  # noqa: BLE001 -- the traceback is the host's error report
        result = {"error": traceback.format_exc()}
    print(spec["marker"] + json.dumps(result), flush=True)


main()
