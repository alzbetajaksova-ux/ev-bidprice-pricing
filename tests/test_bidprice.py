# Vytvorené s pomocou Claude, upravil: Člen B
import numpy as np
import pytest

from mpo_ev.demand import EmpiricalDemandModel
from mpo_ev.instances import generate_instances, load_base, make_config
from mpo_ev.interfaces import REJECT, Product, State
from mpo_ev.policies.bidprice import BidPricePolicy
from mpo_ev.simulator import run_episode


@pytest.fixture(scope="module")
def setup4():
    base = load_base()
    config = make_config(4, 96, 18.98, base)
    demand = EmpiricalDemandModel(config, samples=50_000)
    return config, demand


def _state(config, step, product, capacity=None):
    cap = np.full(config.n_slots, config.capacity) if capacity is None else np.asarray(capacity)
    return State(step, cap, product)


def test_returns_grid_rate_or_reject(setup4):
    config, demand = setup4
    policy = BidPricePolicy()
    policy.reset(config, demand, seed=0)
    for p in demand.expected_remaining(0):
        rate = policy.price(_state(config, 0, p))
        assert rate == REJECT or rate in config.price_grid


def test_zero_cost_gives_myopic_rate(setup4):
    # Bez nákladu príležitosti sa maximalizuje q·r, teda sadzba · P(rozpočet > sadzba).
    config, demand = setup4
    policy = BidPricePolicy()
    policy.reset(config, demand, seed=0)
    p = Product(0, 0)
    expected = max(config.price_grid, key=lambda a: a * demand.acceptance_prob(p, a))
    assert policy.best_rate(p, 0.0) == expected


def test_alpha_zero_ignores_slot_values(setup4):
    config, demand = setup4
    myopic = BidPricePolicy(alpha=0.0)
    myopic.reset(config, demand, seed=0)
    p = Product(2, 2)  # slot so špičkou, μ > 0
    assert myopic.mu[2] > 0
    assert myopic.price(_state(config, 0, p)) == myopic.best_rate(p, 0.0)


def test_rate_nondecreasing_in_cost_and_reject_when_cost_huge(setup4):
    config, demand = setup4
    policy = BidPricePolicy()
    policy.reset(config, demand, seed=0)
    p = Product(1, 2)
    rates = [policy.best_rate(p, c) for c in np.linspace(0.0, 20.0, 41)]
    finite = [r for r in rates if r != REJECT]
    assert finite == sorted(finite)
    huge = max(config.price_grid) * config.duration_h(p) + 1.0
    assert policy.best_rate(p, huge) == REJECT


def test_peak_slot_priced_higher(setup4):
    # Rovnako dlhý produkt v špičke (slot 2, μ > 0) má vyššiu sadzbu ako ráno (slot 0).
    config, demand = setup4
    policy = BidPricePolicy()
    policy.reset(config, demand, seed=0)
    assert policy.mu[0] == pytest.approx(0.0)
    morning = policy.price(_state(config, 0, Product(0, 0)))
    peak = policy.price(_state(config, 0, Product(2, 2)))
    assert peak > morning


def test_alpha_by_part_of_day(setup4):
    config, demand = setup4
    policy = BidPricePolicy(alpha=[0.0, 10.0])
    policy.reset(config, demand, seed=0)
    assert policy._alpha(0) == 0.0
    assert policy._alpha(config.n_steps // 2 - 1) == 0.0
    assert policy._alpha(config.n_steps // 2) == 10.0
    assert policy._alpha(config.n_steps - 1) == 10.0


def test_resolve_every_and_on_sale(setup4):
    config, demand = setup4
    p = Product(2, 2)
    fixed = BidPricePolicy()
    fixed.reset(config, demand, seed=0)
    for step in range(0, 40, 5):
        fixed.price(_state(config, step, p))
    assert fixed.n_solves == 1

    periodic = BidPricePolicy(resolve_every=10)
    periodic.reset(config, demand, seed=0)
    for step in range(0, 40, 5):
        periodic.price(_state(config, step, p))
    assert periodic.n_solves > 1

    on_sale = BidPricePolicy(resolve_on_sale=True)
    on_sale.reset(config, demand, seed=0)
    on_sale.price(_state(config, 3, p))
    assert on_sale.n_solves == 1  # kapacita sa nezmenila
    on_sale.price(_state(config, 4, p, capacity=[3, 3, 2, 3]))
    assert on_sale.n_solves == 2


def test_resolve_with_scarce_capacity_raises_slot_value(setup4):
    config, demand = setup4
    policy = BidPricePolicy(resolve_on_sale=True)
    policy.reset(config, demand, seed=0)
    before = policy.mu[2]
    policy.price(_state(config, 1, Product(2, 2), capacity=[3, 3, 1, 3]))
    assert policy.mu[2] >= before


def test_unknown_product_does_not_crash(setup4):
    config, demand = setup4
    policy = BidPricePolicy()
    policy.reset(config, demand, seed=0)
    # dlhý produkt cez celý deň takmer určite v modeli s 50 000 vzorkami chýba
    rate = policy.price(_state(config, 0, Product(0, 3)))
    assert rate == REJECT or rate in config.price_grid


def test_invalid_parameters():
    with pytest.raises(ValueError):
        BidPricePolicy(gamma=0.0)
    with pytest.raises(ValueError):
        BidPricePolicy(resolve_every=0)
    with pytest.raises(ValueError):
        BidPricePolicy(alpha=[])


def test_runs_in_simulator_deterministically(setup4):
    config, demand = setup4
    instances = generate_instances(config, range(2000, 2005))
    for policy in (BidPricePolicy(), BidPricePolicy(resolve_every=8, resolve_on_sale=True)):
        a = [run_episode(policy, i, demand).revenue for i in instances]
        b = [run_episode(policy, i, demand).revenue for i in instances]
        assert a == b
        assert all(v >= 0 for v in a)
