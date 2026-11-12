"""Drawing-precision lookups issue their COM calls in an order of their own."""

from __future__ import annotations

from types import SimpleNamespace

import _drawing_precision


class _Unsorted(set):
    """A set that iterates in reverse name order, as string hashing may."""

    def __iter__(self):
        return iter(sorted(super().__iter__(), reverse=True))


def test_named_dimensions_bind_in_sorted_name_order_whatever_the_set_order(
    monkeypatch,
):
    names = ("Width", "Depth", "Height", "Bore")
    dimensions = [
        SimpleNamespace(Name=name, display=f"display:{name}") for name in names
    ]
    feature = SimpleNamespace(Name="Boss")
    bound = []

    def invoke(target, _interface, member, *_args):
        if member == "GetDimension2":
            return next(d for d in dimensions if d.display == target)
        return target.Name

    monkeypatch.setattr(_drawing_precision, "_feature_tree", lambda root: [root])
    monkeypatch.setattr(
        _drawing_precision,
        "_feature_display_dimensions",
        lambda current: [d.display for d in dimensions],
    )
    monkeypatch.setattr(_drawing_precision, "_com_invoke", invoke)
    monkeypatch.setattr(_drawing_precision, "_dim_owner_feature", lambda _d: "Boss")
    monkeypatch.setattr(
        _drawing_precision,
        "_bind",
        lambda target, interface: bound.append((interface, target)) or target,
    )

    wanted = _Unsorted(names)
    assert list(wanted) != sorted(names)
    resolved = _drawing_precision._named_dimensions(
        None, "Boss", wanted, feature=feature
    )

    assert list(resolved) == sorted(names)
    assert [
        target for interface, target in bound if interface == "IDisplayDimension"
    ] == [f"display:{name}" for name in sorted(names)]


def test_precision_is_applied_in_sorted_feature_and_name_order(monkeypatch):
    # Specs build DRAWING_PRECISION from sets (dict.fromkeys(names, 2)), so
    # its insertion order is the hash order: here the reverse of sorted.
    precision = {"Rib": {"Width": 2, "Depth": 3}, "Boss": {"Height": 2, "Bore": 3}}
    applied = []
    monkeypatch.setattr(
        _drawing_precision,
        "_iter_features",
        lambda _adapter: [SimpleNamespace(Name=name) for name in ("Rib", "Boss")],
    )
    monkeypatch.setattr(
        _drawing_precision, "_com_invoke", lambda target, *_args: target.Name
    )
    monkeypatch.setattr(
        _drawing_precision,
        "_named_dimensions",
        lambda _adapter, owner, names, **_kwargs: {
            name: (f"{name}@{owner}", None) for name in names
        },
    )
    monkeypatch.setattr(
        _drawing_precision,
        "set_dimension_display_precision",
        lambda _adapter, feature, name, decimals, *, display: applied.append(
            (display, decimals)
        ),
    )

    _drawing_precision.apply_drawing_precision(None, precision)

    assert applied == [
        ("Bore@Boss", 3),
        ("Height@Boss", 2),
        ("Depth@Rib", 3),
        ("Width@Rib", 2),
    ]
