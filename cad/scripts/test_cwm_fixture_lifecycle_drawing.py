"""Exercise actual pose fixtures under pytest, not by calling their wrappers."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


_AUDIT = r'''
import ast
import importlib
import json
from pathlib import Path
import sys
import pytest

source, mode = Path(sys.argv[1]), sys.argv[2]
tree = ast.parse(source.read_text(encoding="utf-8"))
names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)
         and node.name.startswith("test_")
         and any(arg.arg == "pose_bank" for arg in node.args.args)]
assert names, "no actual pose fixture consumers exercised"

class Audit:
    module_name = "solidworks_mcp.adapters.solidworks.assembly"

    def pytest_sessionstart(self, session):
        self.original = importlib.import_module(self.module_name)
        self.members = dict(vars(self.original))
        self.events = []
        self.reports = []

    def unchanged(self):
        assert vars(self.original) == self.members, "real adapter namespace changed"

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_setup(self, item):
        assert sys.modules[self.module_name] is self.original
        self.unchanged()
        yield
        assert "_patch" in item.fixturenames
        local = sys.modules[self.module_name]
        assert local is not self.original, "autouse fixture did not isolate the module"
        assert callable(local._create_math_transform)
        if mode == "real_module_leak":
            # Negative control: reproduce the review's alleged mutation, only
            # inside this throwaway Python process, not in the parent suite.
            self.original._create_math_transform = local._create_math_transform
        self.unchanged()
        self.events.append([item.name, "setup"])

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_call(self, item):
        yield
        self.unchanged()
        if mode == "body_failure" and item.name == names[0]:
            raise RuntimeError("injected failure after the real pose assertions")

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_teardown(self, item, nextitem):
        yield
        assert sys.modules[self.module_name] is self.original, "module not restored"
        self.unchanged()
        self.events.append([item.name, "teardown"])

    def pytest_runtest_logreport(self, report):
        self.reports.append([report.nodeid.rsplit("::", 1)[1], report.when, report.outcome])

audit = Audit()
status = pytest.main(["-q", *[f"{source}::{name}" for name in names]], plugins=[audit])
if mode == "real_module_leak":
    assert status == 1
    assert any(phase == "setup" and outcome == "failed" for _, phase, outcome in audit.reports)
    assert vars(audit.original) != audit.members
    print("AUDIT " + json.dumps({"mode": mode, "outcome": "leak_detected"}))
    raise SystemExit(0)
assert status == (1 if mode == "body_failure" else 0)
assert audit.events == [[name, stage] for name in names for stage in ("setup", "teardown")]
assert [name for name, phase, outcome in audit.reports if outcome == "failed"] == (
    [names[0]] if mode == "body_failure" else [])
assert sys.modules[audit.module_name] is audit.original
audit.unchanged()
print("AUDIT " + json.dumps({"mode": mode, "outcome": "restored", "consumers": names}))
'''


@pytest.mark.parametrize("mode", ["normal", "body_failure", "real_module_leak"])
def test_real_pose_fixture_setup_and_teardown_preserve_adapter_module(tmp_path, mode):
    source = Path(__file__).with_name("test_cwm_mate_guard.py").resolve()
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        [sys.executable, "-c", _AUDIT, str(source), mode],
        cwd=source.parents[2], env=environment,
        capture_output=True, text=True, encoding="utf-8", timeout=45,
    )
    output = result.stdout + result.stderr
    (tmp_path / "fixture-lifecycle.txt").write_text(output, encoding="utf-8")
    assert result.returncode == 0, output
    receipt, = [json.loads(line.removeprefix("AUDIT ")) for line in result.stdout.splitlines() if line.startswith("AUDIT ")]
    assert receipt["mode"] == mode
    assert receipt["outcome"] == ("leak_detected" if mode == "real_module_leak" else "restored")
    if mode != "real_module_leak":
        assert len(receipt["consumers"]) == 5
    if mode == "real_module_leak":
        assert "real adapter namespace changed" in output
