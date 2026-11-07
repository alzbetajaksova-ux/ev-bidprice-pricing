# Vytvorené s pomocou Claude, upravil: Člen C
import functools
import itertools

import numpy as np
import pytest

from mpo_ev.bounds import lp_upper_bound
from mpo_ev.demand import EmpiricalDemandModel, demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config
from mpo_ev.interfaces import REJECT, Product, State
from mpo_ev.policies.vi import ValueIteration, VIPolicy
from mpo_ev.simulator import run_episode

BASE = load_base()
# Kontrolné hodnoty presnej DP Člena A (team/CLEN_C.md, 3.6) a LP hranice
REFERENCE = {2: (48, 9.00, 40.97, 48.71), 3: (72, 13.94, 36.32, 44.20),
             4: (96, 18.98, 36.17, 43.82)}


@functools.cache
def solved(n_slots):
    n_steps, lam, _, _ = REFERENCE[n_slots]
    config = make_config(n_slots, n_steps, lam, BASE)
    demand = demand_from_base(config, BASE)
    return config, demand, ValueIteration(config, demand)


@pytest.mark.parametrize("n_slots", [2, 3, 4])
def test_value_matches_reference_dp(n_slots):
    _, _, vi = solved(n_slots)
    assert vi.value == pytest.approx(REFERENCE[n_slots][2], abs=0.01)


@pytest.mark.parametrize("n_slots", [2, 3, 4])
def test_value_below_lp_bound(n_slots):
    config, demand, vi = solved(n_slots)
    assert vi.value <= lp_upper_bound(config, demand) + 1e-6


def test_value_monotone_in_time_and_capacity():
    config, _, vi = solved(3)
    W = vi.W
    assert (np.diff(W, axis=0) <= 1e-9).all()  # menej zostávajúceho času = menej tržieb
    for j in range(config.n_slots):  # viac kapacity v slote j = aspoň rovnaké tržby
        has = vi.digits[:, j] < config.capacity
        more = np.flatnonzero(has) + vi.weights[j]
        assert (W[:, more] >= W[:, np.flatnonzero(has)] - 1e-9).all()


def test_policy_simulation_matches_value():
    # Simulátor s politikou VI musí v priemere dať V₀ (nezávislá kontrola simulátora).
    config, demand, vi = solved(2)
    policy = VIPolicy()
    revenues = [run_episode(policy, i, demand).revenue
                for i in generate_instances(config, range(5000, 9000))]
    se = np.std(revenues) / np.sqrt(len(revenues))
    assert abs(np.mean(revenues) - vi.value) < 4 * se


def test_policy_returns_grid_or_reject():
    config, demand, _ = solved(4)
    policy = VIPolicy()
    policy.reset(config, demand, 0)
    capacity = np.full(config.n_slots, config.capacity)
    for p, step in itertools.product(demand.product_probs(0), [0, 10, 20]):
        if config.is_sellable(p, step):
            rate = policy.price(State(step, capacity, p))
            assert rate == REJECT or rate in config.price_grid


def test_matches_brute_force_on_tiny_instance():
    """Rekurzia priamo nad stavom (t, c, p) z článku na 2 slotoch s kapacitou 1."""
    config = make_config(2, 8, 4.0, BASE)
    config = type(config)(**{**config.__dict__, "capacity": 1})
    demand = EmpiricalDemandModel(config, samples=20_000)
    vi = ValueIteration(config, demand)

    @functools.cache
    def W(t, c):
        if t == config.n_steps:
            return 0.0
        probs = demand.product_probs(t)
        value = (1 - sum(probs.values())) * W(t + 1, c)
        for p, prob in probs.items():
            best = W(t + 1, c)  # odmietnutie
            if all(c[j] >= 1 for j in p.slots()):
                after = tuple(c[j] - (j in p.slots()) for j in range(len(c)))
                for a in config.price_grid:
                    q = demand.acceptance_prob(p, a)
                    best = max(best, q * (demand.revenue(p, a) + W(t + 1, after))
                               + (1 - q) * W(t + 1, c))
            value += prob * best
        return value

    assert vi.value == pytest.approx(W(0, (1, 1)), rel=1e-10)


def test_too_many_states_raises():
    config = make_config(9, 216, 40.0, BASE)
    with pytest.raises(ValueError):
        ValueIteration(config, EmpiricalDemandModel(config, samples=10_000))


def test_reset_reuses_solution_for_same_model():
    config, demand, _ = solved(2)
    policy = VIPolicy()
    policy.reset(config, demand, 0)
    first = policy.solver
    policy.reset(config, demand, 1)
    assert policy.solver is first
    assert policy.price(State(0, np.full(2, 3), Product(0, 1))) in (*config.price_grid, REJECT)
