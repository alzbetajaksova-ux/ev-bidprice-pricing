import sys
from types import ModuleType

import numpy as np
import pytest

from mpo_ev.bounds import gap_to_bound, lp_upper_bound
from mpo_ev.demand import EmpiricalDemandModel
from mpo_ev.instances import load_base, make_config
from mpo_ev.interfaces import Product


def test_lp_upper_bound_passes_whole_day_inputs(monkeypatch):
    calls = {}

    def solve_dlp(capacity, volumes, q, r, products):
        calls.update(capacity=capacity, volumes=volumes, q=q, r=r, products=products)
        return 42.0, np.zeros(len(capacity))

    fake = ModuleType("mpo_ev.lp")
    fake.solve_dlp = solve_dlp
    monkeypatch.setitem(sys.modules, "mpo_ev.lp", fake)

    config = make_config(4, 96, 18.98, load_base())
    demand = EmpiricalDemandModel(config, samples=20_000)
    assert lp_upper_bound(config, demand) == 42.0

    assert calls["capacity"].tolist() == [3, 3, 3, 3]
    assert sum(calls["volumes"].values()) == pytest.approx(sum(demand.expected_remaining(0).values()))
    assert len(calls["q"]) == len(calls["products"]) * len(config.price_grid)
    rate = config.price_grid[9]
    assert calls["q"][(Product(1, 2), rate)] == pytest.approx(0.5)
    assert calls["r"][(Product(1, 2), rate)] == pytest.approx(rate * 12)


def test_gap_to_bound():
    assert gap_to_bound(75.0, 100.0) == pytest.approx(25.0)
    assert gap_to_bound(100.0, 100.0) == 0.0
