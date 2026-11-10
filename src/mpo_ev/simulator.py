# Vytvorené s pomocou Claude, upravil: Alžbeta Jakšová (Člen A)
"""Simulácia jednej epizódy (jedného dňa požiadaviek)."""
from __future__ import annotations

from time import perf_counter

import numpy as np

from mpo_ev.interfaces import REJECT, DemandModel, EpisodeResult, Instance, Policy, State


def run_episode(
    policy: Policy,
    instance: Instance,
    demand: DemandModel,
    seed: int | None = None,
) -> EpisodeResult:
    """Prejde požiadavky inštancie a vráti výsledok epizódy.

    `demand` je model, ktorý dostane politika. Simulátor ho nepoužíva, pravdou sú
    rozpočty v inštancii, takže E4 môže odovzdať nesprávny model. Predvolený `seed`
    politiky je seed inštancie + 50 000.
    """
    config = instance.config
    capacity = np.full(config.n_slots, config.capacity, dtype=np.int64)
    capacity_view = capacity.view()
    capacity_view.flags.writeable = False
    grid = frozenset(config.price_grid)
    policy_seed = instance.seed + 50_000 if seed is None else seed

    start = perf_counter()
    policy.reset(config, demand, policy_seed)
    runtime_s = perf_counter() - start

    revenue = 0.0
    utilization_h = 0.0
    n_accepted = 0
    for request in instance.requests:
        product = request.product
        if not config.is_sellable(product, request.step):
            continue  # po T_p predávajúci odmieta bez ponuky ceny
        begin, end = product.first_slot, product.last_slot + 1
        if (capacity[begin:end] < 1).any():
            continue  # bez kapacity predávajúci odmieta bez ponuky ceny

        state = State(request.step, capacity_view, product)
        start = perf_counter()
        rate = policy.price(state)
        runtime_s += perf_counter() - start

        if rate == REJECT:
            continue
        if rate not in grid:
            raise ValueError(f"{policy.name}: sadzba {rate} nie je v price_grid")
        if request.budget_rate > rate:
            capacity[begin:end] -= 1
            duration = config.duration_h(product)
            revenue += rate * duration
            utilization_h += duration
            n_accepted += 1

    return EpisodeResult(
        revenue=revenue,
        utilization_h=utilization_h,
        n_requests=len(instance.requests),
        n_accepted=n_accepted,
        runtime_s=runtime_s,
    )
