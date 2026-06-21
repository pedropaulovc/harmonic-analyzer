"""Offline tests for the fine-grained config-dependency layer (``check:cfgdeps``).

Two halves, no SolidWorks:

* the RECORDING hook in ``_config.py`` -- every accessor logs the exact
  ``(yaml_file, key_path)`` it reads when ``HARM_CONFIG_TRACE`` is armed; and
* the DIGEST / UPTODATE / PROMOTE logic in ``dodo.py`` -- which turns a recorded
  read-set into a key-level staleness decision.

The selective-invalidation matrix is proven on synthetic-but-realistic read-sets
(modelling the documented reads of representative parts) against a throwaway
config dir, so it never touches real ``cad/config`` values or runs a build.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parents[1]
CONFIG_DIR = SCRIPTS_DIR.parent / "config"


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------
# 1. The _config.py recording hook
# --------------------------------------------------------------------------

def _trace_child(body: str, tmp_path: Path) -> list:
    """Run ``body`` in a fresh interpreter with read-set tracing armed; return
    the flushed trace as a list of ``[file, [segment, ...]]`` pairs."""
    trace = tmp_path / "trace.json"
    code = textwrap.dedent(
        f"import sys; sys.path.insert(0, {str(SCRIPTS_DIR)!r})\n"
        "import _config\n"
    ) + textwrap.dedent(body)
    env = {**os.environ, "HARM_CONFIG_TRACE": str(trace)}
    subprocess.run([sys.executable, "-c", code], env=env, check=True,
                   cwd=str(SCRIPTS_DIR))
    return json.loads(trace.read_text(encoding="utf-8"))


def _as_set(trace) -> set:
    return {(f, tuple(seg)) for f, seg in trace}


def test_accessors_record_exact_keypaths(tmp_path):
    """Each accessor logs the precise key-path it reads against the REAL config."""
    trace = _as_set(_trace_child(
        """
        _config.machine("gear_train", "diametral_pitch")
        _config.fit("gear_mesh", "rack_backlash_mm")
        _config.parts("cone-gear")
        _config.palette("muntz_yellow")
        """,
        tmp_path,
    ))
    assert ("machine.yaml", ("gear_train", "diametral_pitch")) in trace
    assert ("tolerances.yaml", ("fits", "gear_mesh", "rack_backlash_mm")) in trace
    # a part reads ONLY its own row (+ the shared defaults) -> per-part decoupling
    assert ("parts.yaml", ("parts", "cone-gear")) in trace
    assert ("parts.yaml", ("defaults",)) in trace
    assert ("materials.yaml", ("palette", "muntz_yellow")) in trace
    # ... and nothing it didn't touch
    assert not any(seg == ("parts", "frame") for f, seg in trace if f == "parts.yaml")


def test_amplitude_and_cone_teeth_are_distinct_projections(tmp_path):
    """The two channels.yaml projections stay decoupled: an amplitude reader and
    a cone-teeth reader record different key-paths, so editing one field does not
    invalidate the other's consumers (the core of the channel/gear split)."""
    amp = _as_set(_trace_child("_config.amplitudes()", tmp_path))
    teeth = _as_set(_trace_child("_config.cone_teeth(0)", tmp_path))
    assert amp == {("channels.yaml", ("channels", "[*]", "amplitude_mm"))}
    assert teeth == {("channels.yaml", ("channels", "[*]", "cone_teeth"))}
    # neither pulls in the WHOLE channels subtree
    assert ("channels.yaml", ("channels",)) not in amp | teeth


def test_tracing_disarmed_by_default(tmp_path):
    """No HARM_CONFIG_TRACE -> nothing recorded, zero overhead (normal runs)."""
    trace = tmp_path / "trace.json"
    code = (f"import sys; sys.path.insert(0, {str(SCRIPTS_DIR)!r})\n"
            "import _config\n_config.machine('gear_train', 'diametral_pitch')\n")
    env = {k: v for k, v in os.environ.items() if k != "HARM_CONFIG_TRACE"}
    subprocess.run([sys.executable, "-c", code], env=env, check=True,
                   cwd=str(SCRIPTS_DIR))
    assert not trace.exists()


def test_no_build_or_helper_script_reads_yaml_directly():
    """Conservatism guard: the recorded read-set is COMPLETE only because every
    config read funnels through _config. If a build/helper script ever loaded a
    cad/config/*.yaml directly, tracing would miss it -> under-invalidation."""
    offenders = []
    for path in [*SCRIPTS_DIR.glob("build_*.py"), *SCRIPTS_DIR.glob("_*.py")]:
        if path.name in {"_config.py", "gen_dimensions.py"}:  # the sanctioned loaders
            continue
        src = path.read_text(encoding="utf-8")
        if "config" in src and ("safe_load" in src or "yaml.load" in src):
            offenders.append(path.name)
    assert not offenders, f"scripts bypass _config to read YAML: {offenders}"


# --------------------------------------------------------------------------
# 2. The dodo.py key-level digest / extract
# --------------------------------------------------------------------------

def test_extract_walks_paths_and_projects_lists():
    dodo = _load_dodo()
    doc = {"a": {"b": 1}, "rows": [{"x": 1, "y": 9}, {"x": 2, "y": 8}]}
    assert dodo._extract(doc, ["a", "b"]) == 1
    assert dodo._extract(doc, ["rows", "[*]", "x"]) == [1, 2]
    # a missing key is the MISSING sentinel (so deleting a key reads as a change)
    assert dodo._extract(doc, ["a", "nope"]) is dodo._MISSING
    assert dodo._extract(doc, ["rows", "[*]", "z"]) == [dodo._MISSING, dodo._MISSING]


def _write_yaml(d: Path, name: str, text: str) -> None:
    (d / name).write_text(textwrap.dedent(text), encoding="utf-8")


def _seed_config(d: Path) -> None:
    _write_yaml(d, "channels.yaml", """
        channels:
          - index: 0
            cone_teeth: 120
            amplitude_mm: 1.0
          - index: 1
            cone_teeth: 114
            amplitude_mm: 2.0
    """)
    _write_yaml(d, "machine.yaml", """
        gear_train:
          diametral_pitch: 49.82
        channels:
          active_count: 3
          station_z0_mm: -67.1
    """)
    _write_yaml(d, "parts.yaml", """
        defaults:
          revision: A
        parts:
          frame:
            number: F1
          cone-gear:
            number: G1
          rocker-arm:
            number: R1
          nameplate:
            number: N1
    """)


def test_digest_is_value_sensitive_and_noise_insensitive(tmp_path):
    dodo = _load_dodo()
    _seed_config(tmp_path)
    keys = {"channels.yaml": [["channels", "[*]", "amplitude_mm"]]}
    base = dodo._digest_cfgdeps(keys, config_dir=tmp_path)

    # comment / whitespace / numeric-reflow edit -> inert
    _write_yaml(tmp_path, "channels.yaml", """
        # a fresh comment, reflowed numbers, blank lines

        channels:
          - {index: 0, cone_teeth: 120, amplitude_mm: 1.00}
          - {index: 1, cone_teeth: 114, amplitude_mm: 2.0}
    """)
    assert dodo._digest_cfgdeps(keys, config_dir=tmp_path) == base, "noise must be inert"

    # a REAL amplitude value change -> flips
    _write_yaml(tmp_path, "channels.yaml", """
        channels:
          - {index: 0, cone_teeth: 120, amplitude_mm: 7.0}
          - {index: 1, cone_teeth: 114, amplitude_mm: 2.0}
    """)
    assert dodo._digest_cfgdeps(keys, config_dir=tmp_path) != base, "value change must flip"


def test_cone_teeth_edit_does_not_disturb_amplitude_digest(tmp_path):
    dodo = _load_dodo()
    _seed_config(tmp_path)
    amp_keys = {"channels.yaml": [["channels", "[*]", "amplitude_mm"]]}
    base = dodo._digest_cfgdeps(amp_keys, config_dir=tmp_path)
    _write_yaml(tmp_path, "channels.yaml", """
        channels:
          - {index: 0, cone_teeth: 999, amplitude_mm: 1.0}
          - {index: 1, cone_teeth: 114, amplitude_mm: 2.0}
    """)
    assert dodo._digest_cfgdeps(amp_keys, config_dir=tmp_path) == base


def _mk_sidecar(path: Path, keys: dict, cfgdir: Path):
    dodo = _load_dodo()
    digest = dodo._digest_cfgdeps(keys, config_dir=cfgdir)
    path.write_text(json.dumps({"keys": keys, "digest": digest}), encoding="utf-8")


def test_cfgdeps_uptodate_missing_present_changed_corrupt(tmp_path):
    dodo = _load_dodo()
    _seed_config(tmp_path)
    sidecar = tmp_path / ".x.cfgdeps.json"
    keys = {"machine.yaml": [["gear_train", "diametral_pitch"]]}

    # missing -> not up-to-date (force a recording rebuild)
    assert dodo._cfgdeps_uptodate(sidecar, config_dir=tmp_path) is False

    _mk_sidecar(sidecar, keys, tmp_path)
    assert dodo._cfgdeps_uptodate(sidecar, config_dir=tmp_path) is True

    # a read value changes -> stale
    _write_yaml(tmp_path, "machine.yaml", """
        gear_train:
          diametral_pitch: 30.0
        channels: {active_count: 3, station_z0_mm: -67.1}
    """)
    assert dodo._cfgdeps_uptodate(sidecar, config_dir=tmp_path) is False

    # corrupt sidecar -> not up-to-date (conservative)
    sidecar.write_text("{not json", encoding="utf-8")
    assert dodo._cfgdeps_uptodate(sidecar, config_dir=tmp_path) is False


def test_selective_invalidation_matrix(tmp_path):
    """The handoff matrix, on read-sets modelling representative parts."""
    dodo = _load_dodo()
    cfg = tmp_path / "config"
    cfg.mkdir()
    _seed_config(cfg)

    readsets = {
        # frame: only its own registry row (custom properties) -- no parametrics
        "frame": {"parts.yaml": [["defaults"], ["parts", "frame"]]},
        # a gear: train DP + cone tooth counts + its row
        "cone-gear": {
            "machine.yaml": [["gear_train", "diametral_pitch"]],
            "channels.yaml": [["channels", "[*]", "cone_teeth"]],
            "parts.yaml": [["defaults"], ["parts", "cone-gear"]],
        },
        # a channel-mechanism consumer: amplitude-bar stations + its row
        "rocker-arm": {
            "channels.yaml": [["channels", "[*]", "amplitude_mm"]],
            "parts.yaml": [["defaults"], ["parts", "rocker-arm"]],
        },
        # a plain registered part
        "nameplate": {"parts.yaml": [["defaults"], ["parts", "nameplate"]]},
    }
    sidecars = {stem: tmp_path / f".{stem}.cfgdeps.json" for stem in readsets}
    for stem, keys in readsets.items():
        _mk_sidecar(sidecars[stem], keys, cfg)

    def stale_after(edit_name: str, text: str) -> set:
        _seed_config(cfg)                      # reset to baseline
        _write_yaml(cfg, edit_name, text)      # apply the one edit
        return {stem for stem, sc in sidecars.items()
                if not dodo._cfgdeps_uptodate(sc, config_dir=cfg)}

    # 1. amplitude_mm edit -> only the amplitude consumer
    assert stale_after("channels.yaml", """
        channels:
          - {index: 0, cone_teeth: 120, amplitude_mm: 5.0}
          - {index: 1, cone_teeth: 114, amplitude_mm: 2.0}
    """) == {"rocker-arm"}

    # 2. gear_train.diametral_pitch edit -> only the gear (not nameplate/frame)
    assert stale_after("machine.yaml", """
        gear_train: {diametral_pitch: 30.0}
        channels: {active_count: 3, station_z0_mm: -67.1}
    """) == {"cone-gear"}

    # 3. one part's registry row -> only that part
    assert stale_after("parts.yaml", """
        defaults: {revision: A}
        parts:
          frame: {number: F2}
          cone-gear: {number: G1}
          rocker-arm: {number: R1}
          nameplate: {number: N1}
    """) == {"frame"}

    # 4. a key NO read-set lists -> nothing stale
    assert stale_after("machine.yaml", """
        gear_train: {diametral_pitch: 49.82}
        channels: {active_count: 3, station_z0_mm: -999.0}
    """) == set()

    # 5. comment/whitespace-only edit -> nothing stale
    assert stale_after("channels.yaml", """
        # reshuffled comment, flow style, same values
        channels:
          - {index: 0, cone_teeth: 120, amplitude_mm: 1.0}
          - {index: 1, cone_teeth: 114, amplitude_mm: 2.0}
    """) == set()

    # 6. a SHARED key (parts.yaml defaults) still couples ALL parts (correctness
    #    over speed -- every part reads defaults)
    assert stale_after("parts.yaml", """
        defaults: {revision: B}
        parts:
          frame: {number: F1}
          cone-gear: {number: G1}
          rocker-arm: {number: R1}
          nameplate: {number: N1}
    """) == set(readsets)


# --------------------------------------------------------------------------
# 3. Trace -> sidecar promotion
# --------------------------------------------------------------------------

def test_promote_writes_readset_then_roundtrips(tmp_path):
    """A successful build's trace becomes a sidecar that reads up-to-date against
    the (unchanged) real config."""
    dodo = _load_dodo()
    trace = tmp_path / ".p.cfgdeps.trace.json"
    sidecar = tmp_path / ".p.cfgdeps.json"
    # real-config key-paths, duplicated to prove dedup
    trace.write_text(json.dumps([
        ["parts.yaml", ["defaults"]],
        ["parts.yaml", ["parts", "cone-gear"]],
        ["parts.yaml", ["parts", "cone-gear"]],
        ["machine.yaml", ["gear_train", "diametral_pitch"]],
    ]), encoding="utf-8")

    dodo._promote_cfgdeps(str(trace), str(sidecar))

    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["keys"]["parts.yaml"] == [["defaults"], ["parts", "cone-gear"]]
    assert not trace.exists(), "trace consumed on success"
    assert dodo._cfgdeps_uptodate(sidecar) is True  # vs the real, unchanged config


def test_promote_without_trace_leaves_sidecar_untouched(tmp_path, capsys):
    """No trace dump (e.g. the build died before its atexit flush) must NOT
    overwrite a good sidecar with an empty/partial read-set."""
    dodo = _load_dodo()
    sidecar = tmp_path / ".p.cfgdeps.json"
    sidecar.write_text(json.dumps({"keys": {}, "digest": "deadbeef"}), encoding="utf-8")
    dodo._promote_cfgdeps(str(tmp_path / "absent.trace.json"), str(sidecar))
    assert json.loads(sidecar.read_text())["digest"] == "deadbeef"
    assert "not updated" in capsys.readouterr().out


def test_empty_readset_is_stable(tmp_path):
    """A config-free build records an empty read-set and then reads up-to-date wrt
    config forever (only its script/helpers can invalidate it)."""
    dodo = _load_dodo()
    trace = tmp_path / ".e.cfgdeps.trace.json"
    sidecar = tmp_path / ".e.cfgdeps.json"
    trace.write_text("[]", encoding="utf-8")
    dodo._promote_cfgdeps(str(trace), str(sidecar))
    assert json.loads(sidecar.read_text())["keys"] == {}
    assert dodo._cfgdeps_uptodate(sidecar) is True
