import pytest

from mpo_ev.demand import EmpiricalDemandModel
from mpo_ev.instances import generate_instances, load_base, make_config
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.simulator import run_episode


@pytest.fixture(scope="module")
def trained():
    config = make_config(4, 96, 18.98, load_base())
    demand = EmpiricalDemandModel(config, samples=100_000)
    policy = FlatRatePolicy()
    policy.fit(generate_instances(config, range(200)), demand)
    return config, demand, policy


def test_fit_selects_best_rate_from_grid(trained):
    config, _, policy = trained
    assert policy.rate in config.price_grid
    assert set(policy.train_revenue) == set(config.price_grid)
    assert policy.train_revenue[policy.rate] == max(policy.train_revenue.values())


def test_fit_is_deterministic(trained):
    config, demand, policy = trained
    again = FlatRatePolicy()
    again.fit(generate_instances(config, range(200)), demand)
    assert again.rate == policy.rate


def test_extreme_rates_are_worse_than_selected(trained):
    config, _, policy = trained
    best = policy.train_revenue[policy.rate]
    assert policy.train_revenue[config.price_grid[0]] < best
    assert policy.train_revenue[config.price_grid[-1]] < best


def test_policy_always_offers_the_same_rate(trained):
    config, demand, policy = trained
    result = run_episode(policy, generate_instances(config, range(1000, 1001))[0], demand)
    assert result.revenue == pytest.approx(policy.rate * result.utilization_h)


def test_unfitted_policy_is_refused(trained):
    config, demand, _ = trained
    with pytest.raises(ValueError):
        FlatRatePolicy().reset(config, demand, 0)
