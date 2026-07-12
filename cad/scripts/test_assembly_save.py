from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from _assembly import _save_new_assembly_with_references


class _Model:
    def __init__(self) -> None:
        self.options: int | None = None

    def SaveAs3(self, path: str, version: int, options: int) -> int:
        self.options = options
        Path(path).write_bytes(b"assembly")
        return 0


class _App:
    @staticmethod
    def CloseDoc(path: str) -> None:
        return None


class _Adapter:
    def __init__(self) -> None:
        self.currentModel = _Model()
        self.swApp = _App()

    @staticmethod
    def _attempt(call: Callable[[], Any], default: Any = None) -> Any:
        try:
            return call()
        except Exception:
            return default


def test_new_assembly_save_is_silent_and_saves_references(tmp_path: Path) -> None:
    target = tmp_path / "patterned.SLDASM"
    target.write_bytes(b"stale")
    adapter = _Adapter()

    _save_new_assembly_with_references(adapter, target)

    assert adapter.currentModel.options == 1 | 4 | 8
    assert target.read_bytes() == b"assembly"
