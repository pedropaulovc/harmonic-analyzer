"""Fusion-side CAM helpers. Runs INSIDE Autodesk Fusion, never on the host.

``fusion_cam.py`` sends this file's source, the part's CAM recipe and its
context as one script through the Fusion MCP server; the recipe reaches these
helpers as the module ``_fusion_cam_runtime``. Every length crossing this API is
in millimetres; Fusion's internal centimetres stay inside these functions.

Each helper encodes a behaviour verified against Fusion 2704 (Personal) while
programming the oblique base bar (2026-11-16):

- the CAM product exists only after the Manufacture workspace activates, which
  can take several event-loop turns;
- ``Setup.stockSolids`` takes an ``ObjectCollection``, not a list;
- a contour chain given one edge of a closed loop chains only that edge
  ("Closed contour has 0 area"); pass every loop edge;
- on a closed inner loop, ``isReverted`` decides whether the cutter runs inside
  the loop; the recipe states the side and the posted G-code is checked;
- a drill operation measures heights from the selected hole's top, which on a
  counterbored hole is the counterbore floor; ``from_stock_top`` re-references;
- library posts download lazily to the CAM cache; until the ``.cps`` exists,
  posting fails with unrelated errors, and Personal licences refuse to post a
  tool change, so each program must hold one tool.
"""

import json
import os
import time

import adsk.cam
import adsk.core
import adsk.fusion

MM = 0.1  # Fusion API lengths are centimetres.


def _pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        adsk.doEvents()
        time.sleep(0.05)


def new_design():
    app = adsk.core.Application.get()
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    return doc, design


def import_step(design, path):
    """Import a STEP file into its own component; return its single solid body."""
    app = adsk.core.Application.get()
    options = app.importManager.createSTEPImportOptions(path)
    occurrences = app.importManager.importToTarget2(options, design.rootComponent)
    bodies = [b for o in occurrences for b in o.component.bRepBodies if b.isSolid]
    if len(bodies) != 1:
        raise RuntimeError(f"{path}: expected one solid body, imported {len(bodies)}")
    for o in occurrences:
        o.isLightBulbOn = False
    return bodies[0]


def box(x, y, z):
    """Temporary box spanning the (min, max) mm ranges ``x``, ``y``, ``z``."""
    centre = adsk.core.Point3D.create(sum(x) / 2 * MM, sum(y) / 2 * MM, sum(z) / 2 * MM)
    obb = adsk.core.OrientedBoundingBox3D.create(
        centre, adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
        (x[1] - x[0]) * MM, (y[1] - y[0]) * MM, (z[1] - z[0]) * MM,
    )
    return adsk.fusion.TemporaryBRepManager.get().createBox(obb)


def in_frame(body, origin, axes):
    """Temporary copy of ``body`` expressed in a setup frame.

    ``origin`` is the frame origin in model mm; ``axes`` are the model-space unit
    vectors that become the frame's X, Y and Z. A model point p maps to
    ``axes · (p - origin)``, so the frame origin becomes the world origin and the
    setup's model-origin WCS lands on it.
    """
    manager = adsk.fusion.TemporaryBRepManager.get()
    copy = manager.copy(body)
    matrix = adsk.core.Matrix3D.create()
    for row, axis in enumerate(axes):
        for col in range(3):
            matrix.setCell(row, col, axis[col])
        matrix.setCell(row, 3, -sum(axis[i] * origin[i] for i in range(3)) * MM)
    if not manager.transform(copy, matrix):
        raise RuntimeError("transform failed")
    return copy


def add_body(design, name, temporary):
    """Add a temporary body as a hidden component named ``name``."""
    occurrence = design.rootComponent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    component = occurrence.component
    component.name = name
    feature = component.features.baseFeatures.add()
    feature.startEdit()
    component.bRepBodies.add(temporary, feature)
    feature.finishEdit()
    body = component.bRepBodies.item(0)
    body.name = name
    occurrence.isLightBulbOn = False
    return body


def cam_product(doc):
    adsk.core.Application.get().userInterface.workspaces.itemById("CAMEnvironment").activate()
    for _ in range(200):
        if any(p.productType == "CAMProductType" for p in doc.products):
            return adsk.cam.CAM.cast(doc.products.itemByProductType("CAMProductType"))
        _pump(0.1)
    raise RuntimeError("the Manufacture workspace did not create a CAM product")


def setup(cam, name, model, stock):
    """Milling setup whose WCS is the model origin, i.e. the frame ``in_frame`` built."""
    inp = cam.setups.createInput(adsk.cam.OperationTypes.MillingOperation)
    inp.models = [model]
    inp.name = name
    result = cam.setups.add(inp)
    result.stockMode = adsk.cam.SetupStockModes.SolidStock
    solids = adsk.core.ObjectCollection.create()
    solids.add(stock)
    result.stockSolids = solids
    set_params(result, {"wcs_orientation_mode": "'modelOrientation'", "wcs_origin_mode": "'modelOrigin'"})
    return result


def _library_tools():
    libraries = adsk.cam.CAMManager.get().libraryManager.toolLibraries
    root = libraries.urlByLocation(adsk.cam.LibraryLocations.Fusion360LibraryLocation)
    for url in libraries.childAssetURLs(root):
        for t in libraries.toolLibraryAtURL(url):
            yield t


def tool(kind, number, description, mm, extra=None):
    """A tool cloned from the first Fusion sample of ``kind`` (e.g. 'flat end mill',
    'drill', 'center drill'), with its geometry overridden. ``mm`` maps Fusion tool
    parameter names to millimetre values; ``extra`` to raw expressions."""
    prototype = next((t for t in _library_tools() if t.parameters.itemByName("tool_type").value.value == kind), None)
    if prototype is None:
        raise RuntimeError(f"no sample tool of type {kind!r}")
    result = adsk.cam.Tool.createFromJson(prototype.toJson())
    params = result.parameters
    params.itemByName("tool_number").expression = str(number)
    params.itemByName("tool_description").expression = json.dumps(description)
    for key, value in mm.items():
        params.itemByName(key).expression = f"{value} mm"
    for key, value in (extra or {}).items():
        params.itemByName(key).expression = value
    return result


def set_params(target, values):
    for key, value in values.items():
        parameter = target.parameters.itemByName(key)
        if parameter is None:
            raise RuntimeError(f"{target.name}: no parameter {key!r}")
        parameter.expression = value


def operation(target_setup, strategy, chosen_tool, name, rpm, feed, plunge):
    inp = target_setup.operations.createInput(strategy)
    inp.tool = chosen_tool
    inp.displayName = name
    op = target_setup.operations.add(inp)
    values = {"tool_spindleSpeed": f"{rpm} rpm"}
    for key in ("tool_feedCutting", "tool_feedEntry", "tool_feedExit", "tool_feedTransition"):
        if op.parameters.itemByName(key):
            values[key] = f"{feed} mm/min"
    for key in ("tool_feedPlunge", "tool_feedRamp"):
        if op.parameters.itemByName(key):
            values[key] = f"{plunge} mm/min"
    set_params(op, values)
    return op


def _near(a, b):
    return abs(a - b) < 1e-3


def straight_edge(body, **coords):
    """The single straight edge whose both ends lie at the given mm coordinates,
    e.g. ``straight_edge(b, y=0, z=-12.7)``."""
    index = {"x": 0, "y": 1, "z": 2}
    found = []
    for edge in body.edges:
        ends = [edge.startVertex.geometry, edge.endVertex.geometry]
        if all(_near(p.asArray()[index[k]] / MM, v) for p in ends for k, v in coords.items()):
            found.append(edge)
    if len(found) != 1:
        raise RuntimeError(f"{body.name}: {len(found)} edges at {coords}")
    return found[0]


def inner_loop_at(body, z, x, y):
    """Edges of the inner loop of the planar face at height ``z`` that encloses (x, y)."""
    for face in body.faces:
        if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType or not _near(face.centroid.z / MM, z):
            continue
        for loop in face.loops:
            if loop.isOuter:
                continue
            bb = loop.boundingBox
            if bb.minPoint.x / MM <= x <= bb.maxPoint.x / MM and bb.minPoint.y / MM <= y <= bb.maxPoint.y / MM:
                return [e for e in loop.edges]
    raise RuntimeError(f"{body.name}: no inner loop at z={z} around ({x}, {y})")


def chain(op, edges, is_open, reverted=False):
    selections = op.parameters.itemByName("contours").value.getCurveSelections()
    selection = selections.createNewChainSelection()
    selection.inputGeometry = list(edges)
    selection.isOpen = is_open
    selection.isReverted = reverted
    op.parameters.itemByName("contours").value.applyCurveSelections(selections)


def holes(body, diameter, centres):
    """Cylinder faces of ``diameter`` (mm) whose axes pass through the given (x, y)."""
    faces = []
    for x, y in centres:
        match = [
            f for f in body.faces
            if f.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType
            and abs(f.geometry.radius * 2 / MM - diameter) < 1e-3
            and abs(f.geometry.origin.x / MM - x) < 1e-2 and abs(f.geometry.origin.y / MM - y) < 1e-2
        ]
        if not match:
            raise RuntimeError(f"{body.name}: no Ø{diameter} hole at ({x}, {y})")
        faces.extend(match)
    return faces


def drill(target_setup, chosen_tool, name, rpm, feed, faces, values):
    op = operation(target_setup, "drill", chosen_tool, name, rpm, feed, feed)
    op.parameters.itemByName("holeFaces").value.value = faces
    # A counterbored hole's top is its counterbore floor; feed and retract
    # heights must start from the stock top the tool actually meets first.
    set_params(op, {"topHeight_mode": "'from stock top'", "topHeight_offset": "0 mm", **values})
    return op


def generate(cam):
    future = cam.generateAllToolpaths(False)
    start = time.time()
    while not future.isGenerationCompleted:
        if time.time() - start > 600:
            raise RuntimeError("toolpath generation exceeded 600 s")
        _pump(0.2)
    bad = [
        f"{s.name} / {op.name}: {op.error if op.hasError else op.warning}"
        for s in cam.setups for op in s.operations
        if not op.isToolpathValid or op.hasError or op.hasWarning
    ]
    if bad:
        raise RuntimeError("toolpaths not clean: " + "; ".join(bad))


def _library_post_assets(library, folder):
    for url in library.childAssetURLs(folder):
        yield url, library.postConfigurationAtURL(url)
    for child in library.childFolderURLs(folder):
        yield from _library_post_assets(library, child)


def library_post(cam, description):
    """Path of the Fusion library post whose description is ``description``,
    downloaded into the CAM cache if it is not there yet. A ``PostConfiguration``
    has no URL; its library asset URL (``system://grbl.cps``) names the cache file."""
    library = adsk.cam.CAMManager.get().libraryManager.postLibrary
    root = library.urlByLocation(adsk.cam.LibraryLocations.Fusion360LibraryLocation)
    found = [(u, c) for u, c in _library_post_assets(library, root) if c is not None and c.description == description]
    if len(found) != 1:
        raise RuntimeError(f"{len(found)} library posts described {description!r}")
    url, configuration = found[0]
    cache = os.path.join(os.environ["LOCALAPPDATA"], "Autodesk", "Autodesk Fusion 360", "CAM", "cache", "posts")
    path = os.path.join(cache, url.toString().split("://", 1)[1])
    if not os.path.exists(path):
        # Assigning the configuration to an NC program is what downloads it.
        inp = cam.ncPrograms.createInput()
        program = cam.ncPrograms.add(inp)
        program.postConfiguration = configuration
        _pump(2.0)
        program.deleteMe()
    if not os.path.exists(path):
        raise RuntimeError(f"post {description!r} did not download to {path}")
    return path


def post(cam, operations, name, post_path, out_dir, comment):
    targets = adsk.core.ObjectCollection.create()
    for op in operations:
        targets.add(op)
    inp = adsk.cam.PostProcessInput.create(name, post_path, out_dir, adsk.cam.PostOutputUnitOptions.MillimetersOutput)
    inp.isOpenInEditor = False
    inp.programComment = comment
    if not cam.postProcess(targets, inp):
        raise RuntimeError(f"post {name} returned False")
    path = os.path.join(out_dir, name + ".nc")
    if not os.path.exists(path):
        raise RuntimeError(f"post {name} wrote no {path}")
    return path
