from collections import Counter
from dataclasses import replace

import numpy as np
import pytest
from scipy.stats import norm

from mpo_ev.demand import EmpiricalDemandModel, demand_from_base
from mpo_ev.instances import generate_instance, generate_instances, load_base, make_config
from mpo_ev.interfaces import Product
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.simulator import run_episode

BASE = load_base()
LAMBDA_4 = 18.98


@pytest.fixture(scope="module")
def config():
    return make_config(4, 96, LAMBDA_4, BASE)


@pytest.fixture(scope="module")
def demand(config):
    return demand_from_base(config, BASE)


@pytest.fixture(scope="module")
def instances(config):
    return generate_instances(config, range(10_000))


def test_model_is_deterministic(config):
    first = EmpiricalDemandModel(config, 100_000, seed=1)
    second = EmpiricalDemandModel(config, 100_000, seed=1)
    assert first.product_probs(0) == second.product_probs(0)


def test_step_probs_sum_to_arrival_probability(config, demand):
    assert sum(demand.product_probs(0).values()) == pytest.approx(LAMBDA_4 / 96)


def test_product_probs_contain_only_sellable_products(config, demand):
    for step in (0, 23, 24, 71, 72, 95):
        assert all(config.is_sellable(p, step) for p in demand.product_probs(step))
    assert Product(1, 1) in demand.product_probs(47)
    assert Product(1, 1) not in demand.product_probs(48)


@pytest.mark.parametrize("step", [0, 30, 95])
def test_expected_remaining_is_sum_of_step_probs(config, demand, step):
    total = Counter()
    for s in range(step, config.n_steps):
        total.update(demand.product_probs(s))
    assert demand.expected_remaining(step) == pytest.approx(dict(total))


def test_nothing_remains_after_last_step(config, demand):
    assert demand.expected_remaining(config.n_steps) == {}


def test_acceptance_matches_budget_distribution(config, demand):
    for rate in config.price_grid:
        expected = norm.sf(rate, 1.0, 0.5)
        assert demand.acceptance_prob(Product(0, 0), rate) == pytest.approx(expected)


def test_revenue_uses_product_length(demand):
    assert demand.duration_h(Product(1, 2)) == 12.0
    assert demand.revenue(Product(1, 2), 0.5) == pytest.approx(6.0)


def test_empty_steps_match_generator(config, instances):
    empirical = sum(len(i.requests) for i in instances) / (len(instances) * config.n_steps)
    p = LAMBDA_4 / 96
    error = 4 * np.sqrt(p * (1 - p) / (len(instances) * config.n_steps))
    assert empirical == pytest.approx(p, abs=error)


def test_product_shares_match_generator(demand, instances):
    counts = Counter(r.product for i in instances for r in i.requests)
    total = sum(counts.values())
    for product, share in zip(demand.products, demand.shares):
        error = 4 * np.sqrt(share * (1 - share) / total) + 1e-4
        assert counts[product] / total == pytest.approx(float(share), abs=error)


@pytest.mark.parametrize("step", [10, 30, 60, 90])
def test_sellable_requests_per_step_match_generator(config, demand, instances, step):
    hits = sum(
        any(r.step == step and config.is_sellable(r.product, step) for r in i.requests)
        for i in instances
    )
    p = sum(demand.product_probs(step).values())
    error = 4 * np.sqrt(p * (1 - p) / len(instances))
    assert hits / len(instances) == pytest.approx(p, abs=error)


@pytest.mark.parametrize("n_slots,n_steps,lam", [(4, 96, LAMBDA_4), (24, 576, 76.28)])
@pytest.mark.parametrize("quantile_index", [3, 7, 13])
def test_revenue_matches_formula_without_capacity_limit(n_slots, n_steps, lam, quantile_index):
    # Nezávislý test celého reťazca: sum_p Lambda_p * q(p, a) * r(p, a).
    config = replace(make_config(n_slots, n_steps, lam, BASE), capacity=200)
    demand = demand_from_base(config, BASE)
    rate = config.price_grid[quantile_index]
    expected = sum(
        volume * demand.acceptance_prob(p, rate) * demand.revenue(p, rate)
        for p, volume in demand.expected_remaining(0).items()
    )
    revenues = [
        run_episode(FlatRatePolicy(rate), instance, demand).revenue
        for instance in generate_instances(config, range(4000))
    ]
    error = 4 * np.std(revenues) / np.sqrt(len(revenues))
    assert np.mean(revenues) == pytest.approx(expected, abs=error)


def test_real_capacity_binds_and_is_never_exceeded(config, demand):
    rate = config.price_grid[0]
    limited = [
        run_episode(FlatRatePolicy(rate), generate_instance(config, s), demand)
        for s in range(300)
    ]
    assert all(r.utilization_h <= 3 * 24 for r in limited)
    free = replace(config, capacity=200)
    unlimited = [
        run_episode(FlatRatePolicy(rate), generate_instance(free, s), demand)
        for s in range(300)
    ]
    assert np.mean([r.revenue for r in limited]) < np.mean([r.revenue for r in unlimited])


def test_distorted_config_changes_model_but_not_simulation(config, demand):
    # E4: politika dostane nesprávny model, inštancia a simulátor zostávajú.
    wrong_config = replace(config, expected_requests=0.7 * LAMBDA_4, budget_mean=0.8)
    wrong = demand_from_base(wrong_config, BASE)
    product = Product(2, 2)
    assert wrong.product_probs(0)[product] == pytest.approx(0.7 * demand.product_probs(0)[product])
    assert wrong.acceptance_prob(product, 1.0) < demand.acceptance_prob(product, 1.0)

    rate = config.price_grid[7]
    instance = generate_instance(config, 1000)
    true_result = run_episode(FlatRatePolicy(rate), instance, demand)
    wrong_result = run_episode(FlatRatePolicy(rate), instance, wrong)
    assert true_result.revenue == wrong_result.revenue
