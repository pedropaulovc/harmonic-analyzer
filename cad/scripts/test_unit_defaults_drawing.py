"""Offline call-shape/checkpoint tests, not proof of native unit transitions."""

from diagnostics import probe_drawing_unit_defaults as probe


def test_exact_adapter_setter_order_and_each_native_readback_is_retained():
    calls, rows, checkpoints = [], [], []

    class Model:
        values = {263: 3, 47: 3, 49: 3}

        def GetUserPreferenceIntegerValue(self, key):
            return self.values[key]

        def SetUserPreferenceIntegerValue(self, key, value):
            calls.append((key, value))
            self.values[key] = value
            return True

    probe.trace_setters(Model(), 2, rows, lambda: checkpoints.append(len(rows)))
    assert calls == [(263, 5), (47, 0), (49, 2)]
    assert checkpoints == [1, 1, 2, 2, 3, 3]
    assert rows[0]["readback"] == {"system": 5, "linear": 3, "decimals": 3}
    assert rows[1]["readback"] == {"system": 5, "linear": 0, "decimals": 3}
    assert rows[2]["readback"] == {"system": 5, "linear": 0, "decimals": 2}
    assert all(row["returned"] is True for row in rows)


def test_rejected_setter_return_is_not_discarded_by_the_probe():
    rows = []

    class Model:
        def GetUserPreferenceIntegerValue(self, key):
            return 17

        def SetUserPreferenceIntegerValue(self, key, value):
            return False

    probe.trace_setters(Model(), 3, rows, lambda: None)
    assert len(rows) == 3
    assert all(row["returned"] is False for row in rows)
    assert all(row["readback"]["system"] == 17 for row in rows)
