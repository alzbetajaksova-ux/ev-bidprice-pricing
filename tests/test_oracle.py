# Vytvorené s pomocou Claude, upravil: Člen B
from dataclasses import replace

import numpy as np
import pytest

from mpo_ev.demand import EmpiricalDemandModel
from mpo_ev.instances import generate_instances, load_base, make_config
from mpo_ev.interfaces import Instance, Product, Request
from mpo_ev.policies.bidprice import BidPricePolicy
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.policies.oracle import (
    evaluate_oracle,
    floor_rate,
    oracle_allocation,
    oracle_episode,
)
from mpo_ev.robustness import COLUMNS
from mpo_ev.simulator import run_episode


@pytest.fixture(scope="module")
def base():
    return load_base()


@pytest.fixture(scope="module")
def config4(base):
    return make_config(4, 96, 18.98, base)


def test_floor_rate_is_strictly_below_budget():
    grid = [0.5, 1.0, 1.5]
    assert floor_rate(1.2, grid) == 1.0
    assert floor_rate(1.0, grid) == 0.5  # rovnosť nestačí, simulátor predá len pri b > a
    assert floor_rate(0.4, grid) is None
    assert floor_rate(9.0, grid) == 1.5


def test_small_instance_by_hand(config4):
    # Kapacita 1, dvaja chcú slot 1: Oracle vezme toho, kto zaplatí viac.
    config = replace(config4, capacity=1)
    grid = config.price_grid
    cheap = Request(0, Product(1, 1), budget_rate=grid[5] + 1e-6)
    rich = Request(1, Product(1, 1), budget_rate=grid[15] + 1e-6)
    other = Request(2, Product(0, 0), budget_rate=grid[10] + 1e-6)
    instance = Instance(config, (cheap, rich, other), seed=0)
    accepted = dict(oracle_allocation(instance))
    assert set(accepted) == {rich, other}
    assert accepted[rich] == grid[15]

    result = oracle_episode(instance)
    hours = config.slot_length_h
    assert result.revenue == pytest.approx((grid[15] + grid[10]) * hours)
    assert result.n_accepted == 2
    assert result.utilization_h == pytest.approx(2 * hours)
    assert result.n_requests == 3


def test_unsellable_requests_are_skipped(config4):
    # Slot 0 končí v kroku 23 (96 krokov / 4 sloty); neskoršia požiadavka sa nepredá.
    late = Request(config4.last_sale_step(Product(0, 0)) + 1, Product(0, 0), budget_rate=5.0)
    instance = Instance(config4, (late,), seed=0)
    assert oracle_allocation(instance) == []
    assert oracle_episode(instance).revenue == 0.0


def test_capacity_respected(config4):
    for instance in generate_instances(config4, range(2000, 2020)):
        load = np.zeros(config4.n_slots)
        for req, rate in oracle_allocation(instance):
            load[req.product.first_slot : req.product.last_slot + 1] += 1
            assert rate < req.budget_rate
            assert config4.is_sellable(req.product, req.step)
        assert (load <= config4.capacity).all()


@pytest.mark.parametrize("n_slots,n_steps,lam", [(4, 96, 18.98), (12, 288, 49.95)])
def test_oracle_dominates_policies_on_every_instance(base, n_slots, n_steps, lam):
    config = make_config(n_slots, n_steps, lam, base)
    demand = EmpiricalDemandModel(config, samples=50_000)
    instances = generate_instances(config, range(2000, 2015))
    policies = [FlatRatePolicy(rate) for rate in config.price_grid[::4]]
    policies.append(BidPricePolicy(resolve_on_sale=True))
    for instance in instances:
        best = oracle_episode(instance).revenue
        for policy in policies:
            assert run_episode(policy, instance, demand).revenue <= best + 1e-9


def test_control_value_four_slots(base, config4):
    # Kontrolná hodnota od Člena A (team/CLEN_B.md) na testovacích inštanciách 1000–1099.
    instances = generate_instances(config4, range(1000, 1100))
    mean = np.mean([oracle_episode(i).revenue for i in instances])
    assert mean == pytest.approx(54.13, abs=0.005)


def test_evaluate_oracle_rows(base, config4):
    instances = generate_instances(config4, range(2000, 2003))
    rows = evaluate_oracle(instances, base, "E1", "s4")
    assert len(rows) == 3
    assert list(rows[0]) == COLUMNS
    assert rows[0]["method"] == "oracle"
    assert rows[0]["instance_seed"] == 2000
