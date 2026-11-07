# Vytvorené s pomocou Claude, upravil: Člen C
"""Value Iteration: optimálna politika MDP pre malé inštancie (úloha 3.6, č. 6.2.2 článku).

Konečný horizont, takže VI je jeden prechod spätnej indukcie od kroku K po 0. Namiesto
stavu (c, t, p) z článku ukladáme len W_t(c) = očakávané tržby od začiatku kroku t pri
kapacite c, ešte pred tým, než sa ukáže požiadavka. Produkt sa potom vystredí:

    W_t(c) = (1 − Σ_p P_t(p)) · W_{t+1}(c)
             + Σ_p P_t(p) · [ W_{t+1}(c) + max(0, max_a q(p,a) · (r(p,a) − Δ_{t+1}(c, p))) ]

kde Δ_{t+1}(c, p) = W_{t+1}(c) − W_{t+1}(c − 1_p) je náklad príležitosti predaja p
a P_t(p) = demand.product_probs(t). Produkty bez kapacity a nepredajné produkty
prispievajú ako prázdny krok (simulátor ich odmietne bez ponuky). W_K ≡ 0.

Stav kapacity kódujeme ako číslo v sústave so základom c₀ + 1, takže W_t je pole dĺžky
(c₀ + 1)^n. Pamäť je K · (c₀ + 1)^n hodnôt: pri 4 slotoch 96 · 256, pri 8 slotoch
192 · 65 536 (asi 100 MB). Článok ukladá aj produkt, preto mu VI nad 4 sloty nestačí.

Politika pri požiadavke na p v kroku t ponúkne a* = argmax_a q(p,a) · (r(p,a) − Δ_{t+1}),
alebo odmietne, ak je maximum ≤ 0. Pravdepodobnosti berie len z `demand`, z `config`
používa len sloty, kroky, kapacitu a mriežku.
"""
from __future__ import annotations

from time import perf_counter

import numpy as np

from mpo_ev.interfaces import REJECT, Config, DemandModel, Product, State

MAX_STATES = 70_000  # (c₀+1)^n; 4^8 = 65 536 sa ešte zmestí, 4^9 už nie


class ValueIteration:
    """Presná spätná indukcia. Výsledok sa ukladá pre posledný (config, demand)."""

    def __init__(self, config: Config, demand: DemandModel) -> None:
        n, cap = config.n_slots, config.capacity
        base = cap + 1
        n_states = base**n
        if n_states > MAX_STATES:
            raise ValueError(f"VI: {n_states} stavov kapacity je priveľa (max {MAX_STATES})")
        self.config = config
        self.demand = demand
        self.base = base
        self.weights = base ** np.arange(n)  # index = Σ_j c_j · base^j
        # číslice c_j pre každý index stavu, tvar (n_states, n)
        self.digits = (np.arange(n_states)[:, None] // self.weights[None, :]) % base
        self.full_index = int(cap * self.weights.sum())
        self.grid = np.asarray(config.price_grid, dtype=float)

        start = perf_counter()
        self.W = self._solve()  # tvar (K + 1, n_states)
        self.solve_time_s = perf_counter() - start

    # --- riešenie ---------------------------------------------------------------------

    def _product_data(self, products: list[Product]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Pre produkty: posun indexu pri predaji, maska stavov s kapacitou, tabuľky q a r."""
        shift = np.array([self.weights[list(p.slots())].sum() for p in products], dtype=np.int64)
        feasible = np.stack(
            [(self.digits[:, list(p.slots())] >= 1).all(axis=1) for p in products], axis=1
        )  # (n_states, P)
        q = np.array([[self.demand.acceptance_prob(p, a) for a in self.grid] for p in products])
        r = np.array([[self.demand.revenue(p, a) for a in self.grid] for p in products])
        return shift, feasible, np.stack([q, r])

    def _solve(self) -> np.ndarray:
        config = self.config
        K = config.n_steps
        n_states = len(self.digits)
        products = list(self.demand.product_probs(0))  # v kroku 0 sú predajné všetky
        shift, feasible, (q, r) = self._product_data(products)
        index = {p: i for i, p in enumerate(products)}
        states = np.arange(n_states)
        # po predaji: index − shift; pre neprípustné stavy ľubovoľný platný index (maskované)
        after = np.where(feasible, states[:, None] - shift[None, :], states[:, None])

        W = np.zeros((K + 1, n_states))
        for t in range(K - 1, -1, -1):
            nxt = W[t + 1]
            probs = self.demand.product_probs(t)
            if not probs:
                W[t] = nxt
                continue
            cols = np.array([index[p] for p in probs])
            pr = np.array(list(probs.values()))
            delta = nxt[:, None] - nxt[after[:, cols]]  # (n_states, P_t)
            # zisk z ponuky: max_a q·(r − Δ), najmenej 0 (odmietnutie)
            gain = (q[cols][None, :, :] * (r[cols][None, :, :] - delta[:, :, None])).max(axis=2)
            gain = np.where(feasible[:, cols], np.maximum(gain, 0.0), 0.0)
            W[t] = nxt + gain @ pr
        return W

    # --- použitie ---------------------------------------------------------------------

    @property
    def value(self) -> float:
        """V₀: optimálne očakávané tržby z plnej kapacity."""
        return float(self.W[0, self.full_index])

    def index_of(self, capacity: np.ndarray) -> int:
        return int(np.dot(np.asarray(capacity, dtype=np.int64), self.weights))

    def best_rate(self, step: int, capacity: np.ndarray, product: Product) -> float:
        nxt = self.W[step + 1]
        idx = self.index_of(capacity)
        delta = nxt[idx] - nxt[idx - int(self.weights[list(product.slots())].sum())]
        q = np.array([self.demand.acceptance_prob(product, a) for a in self.grid])
        r = np.array([self.demand.revenue(product, a) for a in self.grid])
        values = q * (r - delta)
        i = int(np.argmax(values))
        return float(self.grid[i]) if values[i] > 0.0 else REJECT


class VIPolicy:
    """Politika z VI. Tabuľku W počíta pri `reset`, pri rovnakom modeli ju znovu použije."""

    name = "vi"

    def __init__(self) -> None:
        self.solver: ValueIteration | None = None

    def reset(self, config: Config, demand: DemandModel, seed: int) -> None:
        solver = self.solver
        if solver is None or solver.config != config or solver.demand is not demand:
            self.solver = ValueIteration(config, demand)

    def price(self, state: State) -> float:
        assert self.solver is not None, "VIPolicy: najprv reset"
        return self.solver.best_rate(state.step, state.capacity, state.product)

    @property
    def value(self) -> float:
        assert self.solver is not None
        return self.solver.value
