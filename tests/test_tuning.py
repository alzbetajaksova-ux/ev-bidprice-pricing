# Vytvorené s pomocou Claude, upravil: Člen B
import csv

import numpy as np
import pytest

from mpo_ev.instances import load_base, make_config
from mpo_ev.tuning import (
    DEFAULT,
    LOWER,
    NAMES,
    UPPER,
    Evaluator,
    grid_points,
    load_theta,
    make_policy,
    resolve_every,
    save_history,
    save_result,
    to_theta,
    to_unit,
    tune_cma,
    tune_grid,
    tune_random,
)


def test_theta_roundtrip_and_bounds():
    theta = {"alpha_am": 0.8, "alpha_pm": 1.2, "gamma": 1.1, "resolves_per_day": 12.0}
    assert to_theta(to_unit(theta)) == pytest.approx(theta)
    assert list(to_theta([0, 0, 0, 0]).values()) == pytest.approx(LOWER)
    assert list(to_theta([1, 1, 1, 1]).values()) == pytest.approx(UPPER)
    # body mimo [0, 1] sa orežú na hranice
    assert list(to_theta([-1, 2, 0.5, 0.5]).values())[:2] == pytest.approx([LOWER[0], UPPER[1]])


def test_resolve_every_transformation():
    theta = dict(DEFAULT)
    assert resolve_every(theta, 96) is None
    theta["resolves_per_day"] = 0.4
    assert resolve_every(theta, 96) is None
    theta["resolves_per_day"] = 12
    assert resolve_every(theta, 96) == 8
    theta["resolves_per_day"] = 48
    assert resolve_every(theta, 24) == 1  # nikdy menej ako 1


def test_make_policy_uses_theta():
    theta = {"alpha_am": 0.5, "alpha_pm": 1.5, "gamma": 1.2, "resolves_per_day": 4}
    policy = make_policy(theta, 96)
    assert policy.alphas.tolist() == [0.5, 1.5]
    assert policy.gamma == 1.2
    assert policy.resolve_every == 24
    assert policy.resolve_on_sale


def _quadratic(target):
    # F(θ) = −||x − x*||² v normalizovanom priestore, maximum 0 v x*
    def evaluate(thetas):
        return [-float(np.sum((to_unit(t) - target) ** 2)) for t in thetas]
    return evaluate


def test_cma_finds_optimum_of_simple_function():
    target = np.array([0.2, 0.7, 0.4, 0.9])
    result = tune_cma(_quadratic(target), budget=600, seed=0)
    assert to_unit(result.best_theta) == pytest.approx(target, abs=0.05)
    assert result.best_value > -0.005


def test_cma_respects_budget_and_records_history():
    target = np.full(4, 0.5)
    result = tune_cma(_quadratic(target), budget=23, seed=3)
    assert result.n_evals == 23
    assert len(result.history) == 23
    best = [h["best"] for h in result.history]
    assert best == sorted(best)
    assert best[-1] == pytest.approx(result.best_value)


def test_cma_is_reproducible_for_same_seed():
    evaluate = _quadratic(np.array([0.3, 0.3, 0.6, 0.1]))
    a = tune_cma(evaluate, budget=40, seed=5)
    b = tune_cma(evaluate, budget=40, seed=5)
    assert [h["value"] for h in a.history] == [h["value"] for h in b.history]


def test_grid_uses_at_most_budget_points():
    assert len(grid_points(100)) == 81  # 3 úrovne v každom zo 4 smerov
    assert len(grid_points(16)) == 16
    assert len(grid_points(5)) == 1
    result = tune_grid(_quadratic(np.full(4, 0.5)), budget=81)
    assert result.n_evals == 81
    assert to_unit(result.best_theta) == pytest.approx(np.full(4, 0.5))


def test_evaluator_fitness_deterministic_and_parallel_equal():
    base = load_base()
    config = make_config(4, 96, 18.98, base)
    thetas = [DEFAULT, {**DEFAULT, "alpha_pm": 0.6, "resolves_per_day": 8.0}]
    serial = Evaluator(config, range(5), base, jobs=1)
    a = serial(thetas)
    assert serial(thetas) == a
    parallel = Evaluator(config, range(5), base, jobs=2)
    try:
        assert parallel(thetas) == a
    finally:
        parallel.close()


def test_save_and_load(tmp_path):
    result = tune_grid(_quadratic(np.full(4, 0.5)), budget=16)
    path = save_result(result, "4s", tmp_path)
    assert load_theta(path) == pytest.approx(result.best_theta)
    save_history([result], "4s", tmp_path / "h.csv")
    with open(tmp_path / "h.csv", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 16
    assert set(rows[0]) == {"config_id", "method", "run_seed", "eval", "value", "best"}
    assert set(NAMES) == set(load_theta(path))


def test_random_search_budget_seed_and_default():
    evaluate = _quadratic(np.full(4, 0.5))
    a = tune_random(evaluate, budget=30, seed=1)
    b = tune_random(evaluate, budget=30, seed=1)
    assert a.n_evals == 30
    assert [h["value"] for h in a.history] == [h["value"] for h in b.history]
    assert a.history[0]["value"] == evaluate([DEFAULT])[0]  # prvý bod je predvolené θ
