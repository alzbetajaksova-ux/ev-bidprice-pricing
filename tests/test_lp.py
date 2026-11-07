# Vytvorené s pomocou Claude, upravil: Člen B
import numpy as np
import pytest

from mpo_ev.demand import EmpiricalDemandModel, demand_from_base
from mpo_ev.instances import load_base, make_config
from mpo_ev.interfaces import Product
from mpo_ev.lp import lp_inputs, solve_dlp

P0 = Product(0, 0)


def _single(capacity, volume, rates):
    """Jeden produkt na jednom slote; rates = {sadzba: (q, r)}."""
    q = {(P0, a): v[0] for a, v in rates.items()}
    r = {(P0, a): v[1] for a, v in rates.items()}
    return solve_dlp(np.array([capacity]), {P0: volume}, q, r, [P0])


def test_capacity_binding_single_product():
    # 10 požiadaviek, 1 miesto: LP predá celú kapacitu za najvyššiu tržbu na jednotku.
    value, mu = _single(1.0, 10.0, {1.0: (0.8, 1.0), 2.0: (0.3, 2.0)})
    assert value == pytest.approx(2.0)
    assert mu[0] == pytest.approx(2.0)


def test_capacity_slack_gives_zero_value_of_slot():
    # Kapacita nestačí obmedziť: zvolí sa sadzba s max r·q a slot má nulovú hodnotu.
    value, mu = _single(100.0, 10.0, {1.0: (0.8, 1.0), 2.0: (0.3, 2.0)})
    assert value == pytest.approx(10 * 0.8)
    assert mu[0] == pytest.approx(0.0)


def test_empty_and_missing_products():
    value, mu = solve_dlp(np.array([3.0, 3.0]), {}, {}, {}, [Product(0, 1)])
    assert value == 0.0
    assert mu.tolist() == [0.0, 0.0]


def test_product_outside_slots_raises():
    with pytest.raises(ValueError):
        solve_dlp(np.array([3.0]), {Product(0, 1): 1.0},
                  {(Product(0, 1), 1.0): 0.5}, {(Product(0, 1), 1.0): 1.0}, [Product(0, 1)])


@pytest.fixture(scope="module")
def four_slots():
    base = load_base()
    config = make_config(4, 96, 18.98, base)
    return config, demand_from_base(config, base)


def test_control_value_four_slots(four_slots):
    # Kontrolná hodnota od Člena A (team/CLEN_B.md).
    config, demand = four_slots
    value, _ = solve_dlp(np.full(4, 3.0), *lp_inputs(demand, config.price_grid))
    assert value == pytest.approx(43.82, abs=0.005)


def test_strong_duality(four_slots):
    # Duál: min Σ_j c_j μ_j + Σ_p Λ_p · max(0, max_a q·(r − Σ_{j∈p} μ_j)).
    # Rovnosť s primárom potvrdzuje, že μ sú správne duálne ceny.
    config, demand = four_slots
    capacity = np.full(4, 3.0)
    volumes, q, r, products = lp_inputs(demand, config.price_grid)
    value, mu = solve_dlp(capacity, volumes, q, r, products)
    dual = capacity @ mu
    for p in products:
        cost = sum(mu[j] for j in p.slots())
        best = max(q[(p, a)] * (r[(p, a)] - cost) for a in config.price_grid)
        dual += volumes[p] * max(0.0, best)
    assert dual == pytest.approx(value, rel=1e-6)


def test_mu_matches_finite_difference(four_slots):
    config, demand = four_slots
    inputs = lp_inputs(demand, config.price_grid)
    capacity = np.full(4, 3.0)
    value, mu = solve_dlp(capacity, *inputs)
    j = int(np.argmax(mu))
    eps = 1e-3
    up, _ = solve_dlp(capacity + eps * np.eye(4)[j], *inputs)
    assert (up - value) / eps == pytest.approx(mu[j], rel=1e-3)


def test_mu_nonnegative_and_value_monotone_in_capacity(four_slots):
    config, demand = four_slots
    inputs = lp_inputs(demand, config.price_grid)
    v2, mu = solve_dlp(np.full(4, 2.0), *inputs)
    v3, _ = solve_dlp(np.full(4, 3.0), *inputs)
    assert (mu >= 0).all()
    assert v2 <= v3 + 1e-9


def test_lp_inputs_respects_step_and_gamma():
    base = load_base()
    config = make_config(4, 96, 18.98, base)
    demand = EmpiricalDemandModel(config, samples=20_000)
    v1, q, r, products = lp_inputs(demand, config.price_grid, step=50)
    v2, *_ = lp_inputs(demand, config.price_grid, step=50, gamma=0.5)
    expected = demand.expected_remaining(50)
    assert set(products) == set(expected)
    for p in products:
        assert v1[p] == pytest.approx(expected[p])
        assert v2[p] == pytest.approx(0.5 * expected[p])
    assert len(q) == len(r) == len(products) * len(config.price_grid)
