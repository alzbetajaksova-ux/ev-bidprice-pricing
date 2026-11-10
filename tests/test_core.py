# Vytvorené s pomocou Claude pri zjednotení vetiev do main, skontroloval: tím
"""Základné testy: overujú len vlastnosti, na ktorých stoja výsledky v reporte."""
from dataclasses import replace
from functools import cache

import numpy as np
import pandas as pd
import pytest

from mpo_ev.analysis import paired_comparison
from mpo_ev.bounds import lp_upper_bound
from mpo_ev.demand import EmpiricalDemandModel, demand_from_base
from mpo_ev.evaluation import COLUMNS, Scenario, believed_config, drop_table
from mpo_ev.experiments import Task, run_task, summarize
from mpo_ev.instances import (
    generate_instance,
    generate_instances,
    load_base,
    make_config,
    required_steps,
)
from mpo_ev.interfaces import REJECT
from mpo_ev.lp import lp_inputs, solve_dlp
from mpo_ev.policies.bidprice import BidPricePolicy
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.policies.hybrid_mcts import HybridMCTSPolicy
from mpo_ev.policies.mcts import MCTSPolicy
from mpo_ev.policies.oracle import oracle_episode
from mpo_ev.policies.vi import ValueIteration, VIPolicy
from mpo_ev.simulator import run_episode
from mpo_ev.tuning import DEFAULT, LOWER, UPPER, fitness, tune_cma

BASE = load_base()
SMALL_BASE = {
    **BASE,
    "demand": {"mc_samples": 20_000, "mc_seed": 1},
    "seeds": {**BASE["seeds"], "train": [0, 9], "test": [1000, 1009]},
}
# Konfigurácie E1 z Tab. 2 článku: počet slotov -> (K, λ)
E1 = {2: (48, 9.00), 3: (72, 13.94), 4: (96, 18.98)}


@cache
def setup(n_slots: int):
    n_steps, lam = E1[n_slots]
    config = make_config(n_slots, n_steps, lam, BASE)
    return config, demand_from_base(config, BASE)


# --- model a simulátor (Člen A) ----------------------------------------------------------

def test_discretization_matches_paper():
    # E2: ε₂/λ = 0,06 dáva presne 192 až 1920 krokov z textu článku (č. 6.3.3).
    assert required_steps(24) == 192
    assert required_steps(240) == 1920


def test_generator_is_deterministic_and_unbiased():
    config, _ = setup(4)
    assert generate_instance(config, 7) == generate_instance(config, 7)
    counts = [len(i.requests) for i in generate_instances(config, range(3000))]
    assert np.mean(counts) == pytest.approx(config.expected_requests, abs=0.2)


def test_simulator_revenue_matches_formula_without_capacity_limit():
    # Nezávislá kontrola generátora, modelu dopytu a simulátora: Σ_p Λ_p · q(p,a) · r(p,a).
    config = replace(setup(4)[0], capacity=200)
    demand = demand_from_base(config, BASE)
    rate = config.price_grid[9]
    expected = sum(v * demand.acceptance_prob(p, rate) * demand.revenue(p, rate)
                   for p, v in demand.expected_remaining(0).items())
    revenues = [run_episode(FlatRatePolicy(rate), i, demand).revenue
                for i in generate_instances(config, range(3000))]
    assert np.mean(revenues) == pytest.approx(expected, abs=4 * np.std(revenues) / np.sqrt(3000))


def test_capacity_is_never_exceeded():
    config, demand = setup(4)
    for instance in generate_instances(config, range(200)):
        result = run_episode(FlatRatePolicy(config.price_grid[0]), instance, demand)
        assert result.utilization_h <= config.capacity * 24 + 1e-9


def test_flat_rate_picks_best_training_rate():
    config, demand = setup(3)
    policy = FlatRatePolicy()
    policy.fit(generate_instances(config, range(20)), demand)
    assert policy.rate == max(policy.train_revenue, key=policy.train_revenue.get)


# --- referenčné metódy a hranice (Členovia A, B, C) --------------------------------------

@pytest.mark.parametrize("n_slots", [2, 3, 4])
def test_vi_matches_reference_dp_and_lp_bound(n_slots):
    # Hodnota VI (Člen C) sa zhoduje s nezávislou DP Člena A a neprekročí LP hranicu.
    config, demand = setup(n_slots)
    value = ValueIteration(config, demand).value
    assert value == pytest.approx({2: 40.97, 3: 36.32, 4: 36.17}[n_slots], abs=0.01)
    assert value <= lp_upper_bound(config, demand) + 1e-6


def test_vi_policy_in_simulator_reaches_value():
    # Validácia simulátora cez VI (míľnik M1).
    config, demand = setup(2)
    policy = VIPolicy()
    revenues = [run_episode(policy, i, demand).revenue
                for i in generate_instances(config, range(5000, 8000))]
    se = np.std(revenues) / np.sqrt(len(revenues))
    assert abs(np.mean(revenues) - policy.value) < 4 * se


def test_lp_pruning_keeps_value_and_duals_are_valid():
    config, demand = setup(4)
    inputs = lp_inputs(demand, config.price_grid)
    capacity = np.array([3.0, 1.0, 2.0, 3.0])
    full, _ = solve_dlp(capacity, *inputs, prune=False)
    pruned, mu = solve_dlp(capacity, *inputs, prune=True)
    assert pruned == pytest.approx(full, rel=1e-9)
    assert (mu >= 0).all()


def test_oracle_dominates_every_policy_on_every_instance():
    config, _ = setup(4)
    demand = EmpiricalDemandModel(config, samples=50_000)
    policies = [FlatRatePolicy(rate) for rate in config.price_grid[::4]]
    policies.append(BidPricePolicy(resolve_on_sale=True))
    for instance in generate_instances(config, range(2000, 2015)):
        best = oracle_episode(instance).revenue
        assert all(run_episode(p, instance, demand).revenue <= best + 1e-9 for p in policies)


# --- politiky a ladenie (Členovia B, C) --------------------------------------------------

@pytest.mark.parametrize("policy", [
    BidPricePolicy(),
    BidPricePolicy(alpha=[0.8, 1.2], gamma=1.2, resolve_every=10, resolve_on_sale=True),
    MCTSPolicy(n_iter=30, depth=2),
    HybridMCTSPolicy(n_iter=30, depth=2),
], ids=["bidprice", "bidprice_resolve", "mcts", "hybrid_mcts"])
def test_policy_is_valid_and_deterministic(policy):
    # Simulátor odmietne sadzbu mimo mriežky; rovnaký seed musí dať rovnaký deň.
    config, demand = setup(4)
    instance = generate_instance(config, 1000)
    first = run_episode(policy, instance, demand, seed=5)
    second = run_episode(policy, instance, demand, seed=5)
    assert first.revenue == second.revenue
    assert first.revenue <= oracle_episode(instance).revenue + 1e-9


def test_bidprice_rejects_when_cost_exceeds_revenue():
    config, demand = setup(4)
    policy = BidPricePolicy()
    policy.reset(config, demand, 0)
    product = next(iter(demand.product_probs(0)))
    assert policy.best_rate(product, cost=1e6) == REJECT


def test_cma_tuning_is_deterministic_and_within_bounds():
    config, demand = setup(3)
    instances = generate_instances(config, range(5))
    evaluate = lambda thetas: [fitness(t, instances, demand) for t in thetas]
    assert evaluate([DEFAULT]) == evaluate([DEFAULT])
    result = tune_cma(evaluate, budget=8, seed=0)
    values = np.array(list(result.best_theta.values()))
    assert result.n_evals == 8
    assert (values >= LOWER - 1e-12).all() and (values <= UPPER + 1e-12).all()
    assert result.best_value >= evaluate([DEFAULT])[0]  # CMA-ES štartuje v predvolenom θ


# --- runner a štatistika (Člen C) -------------------------------------------------------

def test_runner_rows_and_summary():
    config = make_config(3, 72, 13.94, BASE)
    seeds = (1000, 1001, 1002)
    rows = []
    for method in ["oracle", "flat", "bidprice"]:
        rows += run_task(Task("e1", config, method, seeds, "3s"), SMALL_BASE).rows
    assert all(list(row) == COLUMNS for row in rows)
    table = summarize(rows).set_index("method")
    assert table.loc["oracle", "ratio_oracle"] == pytest.approx(1.0)
    assert table.loc["flat", "ratio_flat"] == pytest.approx(1.0)
    pairs = paired_comparison(pd.DataFrame(rows), [("bidprice", "flat")])
    assert pairs.loc[0, "n"] == len(seeds)


def test_e4_scenario_changes_only_what_policy_believes():
    config, _ = setup(4)
    believed = believed_config(config, Scenario("x", lambda_factor=1.3, budget_mean=0.8))
    assert believed.expected_requests == pytest.approx(1.3 * config.expected_requests)
    assert believed.budget_mean == 0.8
    assert believed.price_grid == config.price_grid
    rows = [{"config_id": f"4s_{s}", "method": "flat", "instance_seed": i, "revenue": r}
            for s, r in [("nominal", 10.0), ("worse", 9.0)] for i in range(3)]
    table = drop_table(rows).set_index("scenario")
    assert table.loc["worse", "drop_pct"] == pytest.approx(10.0)
