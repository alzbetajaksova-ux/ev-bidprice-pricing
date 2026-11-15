# Vytvorené s pomocou Claude, upravil: Alžbeta Jakšová (Člen A)
"""Horná hranica očakávaných tržieb z LP na začiatku dňa (úloha 4.6)."""
from __future__ import annotations

import numpy as np

from mpo_ev.interfaces import Config, DemandModel
from mpo_ev.lp import lp_inputs, solve_dlp


def lp_upper_bound(config: Config, demand: DemandModel) -> float:
    """Hodnota LP pri plnej kapacite a dopyte celého dňa.

    Musí dostať pravdivý model dopytu, nie skreslený model z E4.
    """
    capacity = np.full(config.n_slots, config.capacity, dtype=float)
    value, _ = solve_dlp(capacity, *lp_inputs(demand, config.price_grid))
    return value


def gap_to_bound(revenue: float, bound: float) -> float:
    """Medzera metódy k hornej hranici v percentách."""
    return 100 * (1 - revenue / bound)
