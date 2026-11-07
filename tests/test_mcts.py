# Vytvorené s pomocou Claude, upravil: Člen C
import numpy as np
import pytest

from mpo_ev.demand import EmpiricalDemandModel
from mpo_ev.instances import generate_instances, load_base, make_config
from mpo_ev.interfaces import REJECT, Product, State
from mpo_ev.policies.bidprice import BidPricePolicy
from mpo_ev.policies.hybrid_mcts import HybridMCTSPolicy
from mpo_ev.policies.mcts import MCTSPolicy
from mpo_ev.policies.oracle import oracle_episode
from mpo_ev.simulator import run_episode

BASE = load_base()


@pytest.fixture(scope="module")
def setup4():
    config = make_config(4, 96, 18.98, BASE)
    demand = EmpiricalDemandModel(config, samples=50_000)
    return config, demand


def full(config):
    return np.full(config.n_slots, config.capacity)


@pytest.mark.parametrize("cls", [MCTSPolicy, HybridMCTSPolicy])
def test_returns_grid_or_reject(setup4, cls):
    config, demand = setup4
    policy = cls(n_iter=50)
    policy.reset(config, demand, seed=1)
    for p in list(demand.product_probs(0))[:5]:
        rate = policy.price(State(0, full(config), p))
        assert rate == REJECT or rate in config.price_grid


@pytest.mark.parametrize("cls", [MCTSPolicy, HybridMCTSPolicy])
def test_same_seed_same_episode(setup4, cls):
    config, demand = setup4
    instance = generate_instances(config, range(1000, 1001))[0]
    a = run_episode(cls(n_iter=60), instance, demand, seed=7)
    b = run_episode(cls(n_iter=60), instance, demand, seed=7)
    assert (a.revenue, a.n_accepted) == (b.revenue, b.n_accepted)


def test_product_missing_from_model_does_not_crash(setup4):
    config, demand = setup4
    policy = MCTSPolicy(n_iter=30)
    policy.reset(config, demand, seed=0)
    rare = Product(0, 3)
    probs = demand.product_probs(0)
    rate = policy.price(State(0, full(config), rare))
    assert rate == REJECT or rate in config.price_grid
    assert rare in probs or rare in policy._index


def test_last_decision_is_myopic(setup4):
    # V poslednom kroku už nič nepríde, Q(a) = q(a)·r(a); veľa iterácií nájde takmer optimum.
    config, demand = setup4
    p = Product(3, 3)
    step = config.n_steps - 1
    assert config.is_sellable(p, step)
    policy = MCTSPolicy(n_iter=6000, depth=1, c=2.0)
    policy.reset(config, demand, seed=3)
    rate = policy.price(State(step, full(config), p))
    value = {a: demand.acceptance_prob(p, a) * demand.revenue(p, a) for a in config.price_grid}
    assert rate != REJECT
    assert value[rate] >= 0.95 * max(value.values())


def test_offer_sampling_matches_demand(setup4):
    # Počet ponúk za deň pri neobmedzenej kapacite = Σ_t Σ_p product_probs(t).
    config, demand = setup4
    policy = MCTSPolicy()
    policy.reset(config, demand, seed=11)
    cap = [10**6] * config.n_slots
    expected = sum(sum(demand.product_probs(t).values()) for t in range(config.n_steps))
    counts = []
    for _ in range(4000):
        step, n = -1, 0
        while (offer := policy._next_offer(step, cap)) is not None:
            step, n = offer[0], n + 1
            assert config.is_sellable(policy._products[offer[1]], step)
        counts.append(n)
    assert abs(np.mean(counts) - expected) < 4 * np.std(counts) / np.sqrt(len(counts))


def test_tree_is_reused_between_steps(setup4):
    config, demand = setup4
    policy = MCTSPolicy(n_iter=100)
    policy.reset(config, demand, seed=0)
    policy.price(State(0, full(config), Product(1, 2)))
    size = len(policy._tree)
    assert size > 1
    policy.price(State(5, full(config), Product(2, 2)))
    assert len(policy._tree) > size
    fresh = MCTSPolicy(n_iter=100, reuse_tree=False)
    fresh.reset(config, demand, seed=0)
    fresh.price(State(0, full(config), Product(1, 2)))
    fresh.price(State(5, full(config), Product(2, 2)))
    assert len(fresh._tree) <= size + 1


def test_hybrid_rollout_uses_bidprice_rates(setup4):
    config, demand = setup4
    policy = HybridMCTSPolicy(n_iter=10, alpha=[0.5, 1.2])
    policy.reset(config, demand, seed=0)
    reference = BidPricePolicy(alpha=[0.5, 1.2])
    reference.reset(config, demand, seed=0)
    for j, p in enumerate(policy._products):
        cost = reference.mu[p.first_slot:p.last_slot + 1].sum()
        for step in (0, config.n_steps - 1):
            alpha = 0.5 if step < config.n_steps // 2 else 1.2
            assert policy._rates[policy._rollout_action(step, j)] == reference.best_rate(
                p, alpha * cost)


@pytest.mark.parametrize("cls", [MCTSPolicy, HybridMCTSPolicy])
def test_revenue_not_above_oracle(setup4, cls):
    config, demand = setup4
    for instance in generate_instances(config, range(1000, 1004)):
        result = run_episode(cls(n_iter=50), instance, demand)
        assert 0 <= result.revenue <= oracle_episode(instance).revenue + 1e-9


def test_invalid_parameters():
    with pytest.raises(ValueError):
        MCTSPolicy(n_iter=0)
    with pytest.raises(ValueError):
        MCTSPolicy(depth=0)
