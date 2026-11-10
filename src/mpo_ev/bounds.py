# Vytvorené s pomocou Claude, upravil: Alžbeta Jakšová (Člen A)
"""Horná hranica očakávaných tržieb z LP na začiatku dňa (úloha 4.6)."""
from __future__ import annotations

import numpy as np

from mpo_ev.interfaces import Config, DemandModel


def lp_upper_bound(config: Config, demand: DemandModel) -> float:
    """Hodnota LP pri plnej kapacite a dopyte celého dňa.

    Vyžaduje `solve_dlp` z lp.py (Člen B). Lambda, q a r sú slovníky, q a r s kľúčom
    (produkt, sadzba). Musí dostať pravdivý model dopytu, nie skreslený model z E4.
    """
    from mpo_ev.lp import solve_dlp

    capacity = np.full(config.n_slots, config.capacity, dtype=float)
    volumes = demand.expected_remaining(0)
    products = list(volumes)
    pairs = [(p, rate) for p in products for rate in config.price_grid]
    q = {(p, rate): demand.acceptance_prob(p, rate) for p, rate in pairs}
    r = {(p, rate): demand.revenue(p, rate) for p, rate in pairs}
    value, _ = solve_dlp(capacity, volumes, q, r, products)
    return value


def gap_to_bound(revenue: float, bound: float) -> float:
    """Medzera metódy k hornej hranici v percentách."""
    return 100 * (1 - revenue / bound)
