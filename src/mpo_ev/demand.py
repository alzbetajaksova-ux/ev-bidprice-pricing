# Vytvorené s pomocou Claude, upravil: Alžbeta Jakšová (Člen A)
"""Model dopytu pre LP, VI a MCTS, konzistentný s generátorom inštancií."""
from __future__ import annotations

import math

import numpy as np

from mpo_ev.instances import sessions_to_slots
from mpo_ev.interfaces import Config, Product


class EmpiricalDemandModel:
    """Podiely produktov odhadnuté Monte Carlom z rozdelení v `config`.

    Veľmi zriedkavé produkty sa vo vzorke nemusia objaviť a v slovníkoch potom chýbajú;
    v inštancii sa objaviť môžu. Pre E4 stačí odovzdať `config` so skresleným lambda
    alebo priemerom rozpočtu.
    """

    def __init__(self, config: Config, samples: int = 1_000_000, seed: int = 0) -> None:
        self.config = config
        rng = np.random.default_rng(seed)
        start_h = rng.normal(config.start_mean_h, config.start_std_h, size=samples)
        duration_h = rng.exponential(config.duration_mean_h, size=samples)
        first, last = sessions_to_slots(start_h, duration_h, config.n_slots)
        codes, counts = np.unique(first * config.n_slots + last, return_counts=True)

        self.products = [
            Product(int(code) // config.n_slots, int(code) % config.n_slots) for code in codes
        ]
        self.shares = counts / samples  # lambda_p / lambda
        # lambda_p / K: pravdepodobnosť požiadavky na p v jednom kroku
        self._step_probs = self.shares * config.expected_requests / config.n_steps
        self._last_steps = np.array([config.last_sale_step(p) for p in self.products])
        self._cache: dict[int, dict[Product, float]] = {}

    def product_probs(self, step: int) -> dict[Product, float]:
        if step not in self._cache:
            self._cache[step] = self._select(self._last_steps >= step, self._step_probs)
        return self._cache[step]

    def expected_remaining(self, step: int) -> dict[Product, float]:
        steps_left = self._last_steps - step + 1
        return self._select(steps_left > 0, self._step_probs * steps_left)

    def acceptance_prob(self, product: Product, rate: float) -> float:
        # P(rozpočet > sadzba); sadzby sú kladné, takže záporný rozpočet nikdy nekúpi.
        z = (rate - self.config.budget_mean) / self.config.budget_std
        return 0.5 * math.erfc(z / math.sqrt(2))

    def revenue(self, product: Product, rate: float) -> float:
        return rate * self.duration_h(product)

    def duration_h(self, product: Product) -> float:
        return self.config.duration_h(product)

    def _select(self, mask: np.ndarray, values: np.ndarray) -> dict[Product, float]:
        return {
            self.products[i]: float(values[i]) for i in np.flatnonzero(mask).tolist()
        }


def demand_from_base(config: Config, base: dict) -> EmpiricalDemandModel:
    settings = base["demand"]
    return EmpiricalDemandModel(config, settings["mc_samples"], settings["mc_seed"])
