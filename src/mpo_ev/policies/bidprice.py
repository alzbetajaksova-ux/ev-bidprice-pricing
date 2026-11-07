# Vytvorené s pomocou Claude, upravil: Člen B
"""Bid-price politika z deterministického LP (úloha 4.3).

Hodnoty slotov μ_j sú duálne ceny kapacitných obmedzení LP (`mpo_ev.lp`). Pri požiadavke
na produkt p politika ponúkne sadzbu

    a* = argmax_a  q(p,a) · ( r(p,a) − α(t) · Σ_{j ∈ p} μ_j )

a odmietne, ak je maximum ≤ 0. Σ μ_j je „náklad príležitosti“: o koľko by klesli
očakávané budúce tržby, keby sme sloty produktu predali teraz.

Parametre θ, ktoré neskôr ladí CMA-ES (úloha 4.4):
- `alpha`: škálovanie μ, jedno číslo alebo hodnota pre každú rovnakú časť dňa,
- `gamma`: korekcia očakávaného dopytu Λ_p v LP,
- `resolve_every`: prepočet LP každých N krokov (None = nikdy),
- `resolve_on_sale`: prepočet LP, keď sa od posledného riešenia zmenila kapacita.

Bez prepočtu (predvolené) sa μ počítajú raz pri `reset`; tento režim používa hybrid MCTS.
Politika berie pravdepodobnosti len z `demand`; z `config` používa len sloty, kroky,
kapacitu a mriežku (férovosť v E4).
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from mpo_ev.interfaces import REJECT, Config, DemandModel, Product, State
from mpo_ev.lp import Key, solve_dlp


class BidPricePolicy:
    def __init__(
        self,
        alpha: float | Sequence[float] = 1.0,
        gamma: float = 1.0,
        resolve_every: int | None = None,
        resolve_on_sale: bool = False,
        name: str = "bidprice",
    ) -> None:
        self.alphas = np.atleast_1d(np.asarray(alpha, dtype=float))
        if self.alphas.ndim != 1 or len(self.alphas) == 0:
            raise ValueError("alpha musí byť číslo alebo neprázdna postupnosť")
        if gamma <= 0:
            raise ValueError("gamma musí byť kladné")
        if resolve_every is not None and resolve_every < 1:
            raise ValueError("resolve_every musí byť aspoň 1 alebo None")
        self.gamma = float(gamma)
        self.resolve_every = resolve_every
        self.resolve_on_sale = resolve_on_sale
        self.name = name
        self.n_solves = 0  # počet riešení LP v poslednej epizóde (diagnostika)

    # --- rozhranie Policy -------------------------------------------------------------

    def reset(self, config: Config, demand: DemandModel, seed: int) -> None:
        self._n_steps = config.n_steps
        self._grid = np.asarray(config.price_grid, dtype=float)
        self._demand = demand
        self._tables: dict[Product, tuple[np.ndarray, np.ndarray]] = {}

        # q a r pre LP sa nemenia počas dňa, pripravíme ich raz pre všetky produkty modelu
        self._lp_q: dict[Key, float] = {}
        self._lp_r: dict[Key, float] = {}
        self._lp_products = set(demand.expected_remaining(0))
        for p in self._lp_products:
            q_row, r_row = self._table(p)
            for a, qa, ra in zip(config.price_grid, q_row, r_row, strict=True):
                self._lp_q[(p, a)] = qa
                self._lp_r[(p, a)] = ra

        self.n_solves = 0
        self._solve(np.full(config.n_slots, config.capacity, dtype=float), step=0)

    def price(self, state: State) -> float:
        if self._needs_resolve(state):
            # aktuálna požiadavka je známa, budúci dopyt začína v ďalšom kroku
            self._solve(np.asarray(state.capacity, dtype=float), step=state.step + 1)
        p = state.product
        cost = self._alpha(state.step) * (self._cum_mu[p.last_slot + 1] - self._cum_mu[p.first_slot])
        return self.best_rate(p, cost)

    # --- pomocné metódy ---------------------------------------------------------------

    @property
    def mu(self) -> np.ndarray:
        """Aktuálne hodnoty slotov (kópia)."""
        return self._mu.copy()

    def best_rate(self, product: Product, cost: float) -> float:
        """Sadzba s najväčším q·(r − cost), alebo REJECT, ak je maximum ≤ 0."""
        q_row, r_row = self._table(product)
        values = q_row * (r_row - cost)
        i = int(np.argmax(values))
        return float(self._grid[i]) if values[i] > 0.0 else REJECT

    def _table(self, product: Product) -> tuple[np.ndarray, np.ndarray]:
        # Produkt môže v modeli chýbať (zriedkavý), q a r sa dajú spočítať aj tak.
        if product not in self._tables:
            q_row = np.array([self._demand.acceptance_prob(product, a) for a in self._grid])
            r_row = np.array([self._demand.revenue(product, a) for a in self._grid])
            self._tables[product] = (q_row, r_row)
        return self._tables[product]

    def _alpha(self, step: int) -> float:
        part = min(step * len(self.alphas) // self._n_steps, len(self.alphas) - 1)
        return float(self.alphas[part])

    def _needs_resolve(self, state: State) -> bool:
        if self.resolve_every is not None and state.step - self._solved_step >= self.resolve_every:
            return True
        return self.resolve_on_sale and not np.array_equal(state.capacity, self._solved_capacity)

    def _solve(self, capacity: np.ndarray, step: int) -> None:
        volumes = {
            p: self.gamma * v
            for p, v in self._demand.expected_remaining(min(step, self._n_steps)).items()
        }
        products = [p for p in volumes if p in self._lp_products]
        _, mu = solve_dlp(capacity, volumes, self._lp_q, self._lp_r, products)
        self._mu = mu
        self._cum_mu = np.concatenate([[0.0], np.cumsum(mu)])
        self._solved_step = step
        self._solved_capacity = capacity.copy()
        self.n_solves += 1
