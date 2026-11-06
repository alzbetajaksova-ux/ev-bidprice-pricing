import pytest

from mpo_ev.flat_baseline import summary_table


def test_summary_table_statistics():
    def row(revenue):
        return {
            "config_id": "4s", "method": "flat", "revenue": revenue, "n_accepted": 2,
            "utilization_h": 6.0, "n_requests": 5, "runtime_s": 0.1,
        }

    table = summary_table([row(10.0), row(20.0), row(60.0)]).iloc[0]
    assert table["mean"] == pytest.approx(30.0)
    assert table["median"] == 20.0
    assert (table["min"], table["max"]) == (10.0, 60.0)
    assert table["std"] == pytest.approx(26.4575, abs=1e-3)
