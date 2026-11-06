from dataclasses import replace

import pytest

from mpo_ev.demand import EmpiricalDemandModel
from mpo_ev.instances import generate_instance, load_base, make_config
from mpo_ev.interfaces import REJECT, Instance, Product, Request
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.simulator import run_episode

BASE = load_base()


class SpyPolicy:
    """Zaznamená, čo dostala, a ponúkne pevnú sadzbu."""

    name = "spy"

    def __init__(self, rate):
        self.rate = rate
        self.capacities = []
        self.last_state = None
        self.seed = None
        self.demand = None

    def reset(self, config, demand, seed):
        self.seed = seed
        self.demand = demand

    def price(self, state):
        self.capacities.append(state.capacity.copy())
        self.last_state = state
        return self.rate


def setup(n_slots=4, n_steps=96, lam=19.0, capacity=3):
    config = replace(make_config(n_slots, n_steps, lam, BASE), capacity=capacity)
    return config, EmpiricalDemandModel(config, samples=20_000)


def test_sale_updates_revenue_and_utilization():
    config, demand = setup()
    rate = config.price_grid[9]  # 1,0
    instance = Instance(config, (Request(0, Product(1, 2), 1.5),), seed=0)
    result = run_episode(FlatRatePolicy(rate), instance, demand)
    assert result.revenue == pytest.approx(rate * 12)
    assert result.utilization_h == 12.0
    assert (result.n_requests, result.n_accepted) == (1, 1)


def test_budget_must_be_strictly_greater_than_rate():
    config, demand = setup()
    rate = config.price_grid[9]
    instance = Instance(config, (Request(0, Product(1, 1), rate),), seed=0)
    assert run_episode(FlatRatePolicy(rate), instance, demand).n_accepted == 0


def test_reject_earns_nothing():
    config, demand = setup()
    instance = Instance(config, (Request(0, Product(1, 1), 5.0),), seed=0)
    result = run_episode(FlatRatePolicy(REJECT), instance, demand)
    assert (result.revenue, result.n_accepted) == (0.0, 0)


def test_rate_outside_grid_is_an_error():
    config, demand = setup()
    instance = Instance(config, (Request(0, Product(1, 1), 5.0),), seed=0)
    with pytest.raises(ValueError):
        run_episode(FlatRatePolicy(0.123), instance, demand)


def test_late_request_is_counted_but_policy_is_not_called():
    config, demand = setup()
    instance = Instance(config, (Request(24, Product(0, 0), 5.0),), seed=0)  # slot skončil
    spy = SpyPolicy(config.price_grid[0])
    result = run_episode(spy, instance, demand)
    assert (result.n_requests, result.n_accepted, spy.capacities) == (1, 0, [])


def test_policy_is_not_called_without_capacity():
    config, demand = setup(capacity=1)
    requests = (Request(0, Product(1, 2), 5.0), Request(1, Product(2, 2), 5.0))
    spy = SpyPolicy(config.price_grid[0])
    result = run_episode(spy, Instance(config, requests, seed=0), demand)
    assert result.n_accepted == 1
    assert len(spy.capacities) == 1


def test_state_capacity_reflects_sales_and_is_read_only():
    config, demand = setup()
    requests = (Request(0, Product(1, 2), 5.0), Request(1, Product(2, 2), 5.0))
    spy = SpyPolicy(config.price_grid[0])
    run_episode(spy, Instance(config, requests, seed=0), demand)
    assert spy.capacities[0].tolist() == [3, 3, 3, 3]
    assert spy.capacities[1].tolist() == [3, 2, 2, 3]
    with pytest.raises(ValueError):
        spy.last_state.capacity[0] = 0


@pytest.mark.parametrize("n_slots,n_steps,lam", [(4, 96, 19.0), (24, 576, 76.0)])
def test_capacity_is_never_exceeded(n_slots, n_steps, lam):
    config, demand = setup(n_slots, n_steps, lam)
    for seed in range(50):
        spy = SpyPolicy(config.price_grid[0])
        result = run_episode(spy, generate_instance(config, seed), demand)
        assert all((capacity >= 0).all() for capacity in spy.capacities)
        assert result.utilization_h <= config.capacity * 24


def test_same_seed_gives_same_result():
    config, demand = setup()
    rate = config.price_grid[8]
    first = run_episode(FlatRatePolicy(rate), generate_instance(config, 3), demand)
    second = run_episode(FlatRatePolicy(rate), generate_instance(config, 3), demand)
    assert (first.revenue, first.n_accepted) == (second.revenue, second.n_accepted)


def test_policy_gets_given_demand_and_default_seed():
    config, demand = setup()
    _, wrong_demand = setup(lam=5.0)
    instance = generate_instance(config, 3)
    spy = SpyPolicy(config.price_grid[0])
    run_episode(spy, instance, wrong_demand)
    assert spy.demand is wrong_demand
    assert spy.seed == 50_003
    run_episode(spy, instance, demand, seed=1)
    assert spy.seed == 1
