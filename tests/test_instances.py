import itertools
import math

import numpy as np
import pytest
from scipy.stats import norm, poisson

from mpo_ev.instances import (
    err2,
    generate_instance,
    generate_instances,
    load_base,
    make_config,
    quantile_price_grid,
    required_steps,
    seed_range,
    sessions_to_slots,
)

# sloty, K a lambda z Tab. 2, chyba pri K z Tab. 2, K pri chybe 0,06
TABLE_2 = [
    (2, 48, 9.00, 0.088, 72),
    (3, 72, 13.94, 0.091, 112),
    (4, 96, 18.98, 0.093, 152),
    (8, 192, 36.67, 0.090, 294),
    (12, 288, 49.95, 0.082, 400),
    (24, 576, 76.28, 0.063, 610),
    (36, 864, 92.86, 0.052, 743),
    (72, 1728, 123.96, 0.035, 992),
]


def test_grid_contains_flat_rates_from_table_2():
    grid = quantile_price_grid(0.05, 0.95, 0.05, 1.0, 0.5)
    assert len(grid) == 19
    assert grid[6] == pytest.approx(39.33 / 48.72, abs=2e-4)   # q = 0,35
    assert grid[7] == pytest.approx(40.14 / 45.96, abs=2e-4)   # q = 0,40
    assert grid[9] == pytest.approx(1.0)


def test_grid_is_increasing_and_positive():
    grid = quantile_price_grid(0.05, 0.95, 0.05, 1.0, 0.5)
    assert grid[0] > 0
    assert all(a < b for a, b in itertools.pairwise(grid))


def test_grid_step_does_not_lose_levels_to_rounding():
    assert len(quantile_price_grid(0.1, 0.9, 0.1, 1.0, 0.5)) == 9
    assert len(quantile_price_grid(0.025, 0.975, 0.025, 1.0, 0.5)) == 39


def test_err2_matches_direct_poisson_sum():
    k, lam = 96, 18.98
    jumps = np.arange(2, 60)
    direct = k * np.sum((jumps - 1) * poisson.pmf(jumps, lam / k))
    assert err2(k, lam) == pytest.approx(direct)


def test_err2_limits():
    assert err2(10_000_000, 20.0) == pytest.approx(0.0, abs=1e-4)
    assert err2(1, 20.0) == pytest.approx(19.0, abs=1e-6)


@pytest.mark.parametrize("n_slots,k,lam,relative_error,steps", TABLE_2)
def test_table_2_discretization(n_slots, k, lam, relative_error, steps):
    assert err2(k, lam) / lam == pytest.approx(relative_error, abs=5e-4)
    assert required_steps(lam) == steps


@pytest.mark.parametrize("lam", [0.5, 6.0, 24.0, 76.28, 240.0, 288.0])
def test_required_steps_is_smallest_valid_value(lam):
    k = required_steps(lam)
    assert err2(k, lam) / lam <= 0.06
    assert k == math.ceil(lam) or err2(k - 1, lam) / lam > 0.06


@pytest.mark.parametrize("lam,steps", [(2.0, 16), (96.0, 768), (24.0, 192), (240.0, 1920)])
def test_required_steps_reproduces_ranges_from_text(lam, steps):
    # č. 6.3.2: 16 až 768 krokov, č. 6.3.3: 192 až 1920 krokov.
    assert required_steps(lam) == steps


def test_base_yaml_builds_config():
    base = load_base()
    config = make_config(4, 96, 18.98, base)
    assert (config.n_slots, config.n_steps, config.capacity) == (4, 96, 3)
    assert config.expected_requests == 18.98
    assert config.duration_mean_h == 3.0
    assert config.price_grid[9] == pytest.approx(norm.ppf(0.5, 1.0, 0.5))


@pytest.mark.parametrize(
    "start,duration,first,last",
    [
        (13.0, 2.0, 2, 2),    # vo vnútri slotu 12-18
        (11.0, 2.0, 1, 2),    # cez hranicu 12:00
        (10.0, 2.0, 1, 1),    # koniec presne na hranici slot nepridá
        (12.0, 0.0, 2, 2),    # nulová dĺžka zostane v jednom slote
        (-1.0, 2.0, 0, 0),    # začiatok pred polnocou
        (-5.0, 1.0, 0, 0),    # celé pred polnocou
        (22.0, 5.0, 3, 3),    # orezanie po polnoci
        (25.0, 1.0, 3, 3),    # začiatok až po polnoci
    ],
)
def test_sessions_to_slots(start, duration, first, last):
    f, l = sessions_to_slots(np.array([start]), np.array([duration]), 4)
    assert (f[0], l[0]) == (first, last)


def real_config(n_slots=4, n_steps=96, lam=18.98):
    return make_config(n_slots, n_steps, lam, load_base())


def test_generator_is_deterministic():
    config = real_config()
    assert generate_instance(config, 5) == generate_instance(config, 5)
    assert generate_instance(config, 5) != generate_instance(config, 6)


def test_generator_expected_number_of_requests():
    config = real_config()
    sizes = [len(i.requests) for i in generate_instances(config, range(3000))]
    assert np.mean(sizes) == pytest.approx(18.98, abs=0.25)


@pytest.mark.parametrize("n_slots,n_steps,lam", [(4, 96, 18.98), (72, 1728, 123.96)])
def test_generated_requests_are_valid(n_slots, n_steps, lam):
    config = real_config(n_slots, n_steps, lam)
    for instance in generate_instances(config, range(50)):
        for request in instance.requests:
            assert 0 <= request.step < n_steps
            assert 0 <= request.product.first_slot <= request.product.last_slot < n_slots


def test_generated_budgets_follow_table_1():
    config = real_config(72, 1728, 123.96)
    budgets = [r.budget_rate for i in generate_instances(config, range(300)) for r in i.requests]
    assert np.mean(budgets) == pytest.approx(1.0, abs=0.01)
    assert np.std(budgets) == pytest.approx(0.5, abs=0.01)


def test_generated_lengths_follow_table_1():
    # Pri jemných slotoch je dĺžka produktu približne dĺžka nabíjania + dĺžka slotu.
    config = real_config(240, 2400, 200.0)
    lengths = [
        config.duration_h(r.product)
        for i in generate_instances(config, range(300))
        for r in i.requests
    ]
    assert np.mean(lengths) == pytest.approx(3.0 + config.slot_length_h, abs=0.15)


def test_train_and_test_seeds_do_not_overlap():
    base = load_base()
    train, test = seed_range(base, "train"), seed_range(base, "test")
    assert (len(train), len(test)) == (200, 100)
    assert not set(train) & set(test)
    assert set(seed_range(base, "pilot")) <= set(test)
