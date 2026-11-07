# Vytvorené s pomocou Claude, upravil: Člen C
"""MCTS autorov článku (úloha 3.7, č. 5, Algoritmy 1 a 2).

UCT: v uzle sa najprv vyskúša každá akcia raz, potom sa vyberá podľa UCB1
    a = argmax_a  Q(s,a) + c · sqrt(ln N(s) / N(s,a)).
Výber končí na hĺbke d_max, v koncovom stave alebo po prvej nevyskúšanej akcii
(prehľadávanie do šírky, riadok 23). Potom sa hodnota odhadne rolloutom a súčet odmien
pod každou úrovňou sa spriemeruje do Q (riadok 27). Akcia v koreni = argmax Q.

Stav uzla je (krok, kapacita, produkt), teda len rozhodovacie stavy. Prechod T(s, a)
najprv vyhodnotí nákup (pravdepodobnosť q(p, a) z modelu), potom vzorkuje ďalšiu
ponuku. Prázdne kroky, nepredajné produkty a produkty bez kapacity simulátor odmieta
bez ponuky, preto ich preskakujeme (rozhodnutie Člena C; článok to explicitne neuvádza,
v POMDPs.jl by prázdne kroky tvorili ďalšie úrovne stromu len s jedinou akciou).

Čas do ďalšej požiadavky (team/CLEN_C.md, 3.7):
1. p0 = Σ demand.product_probs(0) je pravdepodobnosť príchodu v kroku,
2. ďalší príchod je o Geom(p0) krokov,
3. produkt sa vyberie úmerne pravdepodobnostiam z kroku 0; ak už v danom kroku nie je
   predajný, ponuka nevzniká. Je to presne rozdelenie product_probs(s), lebo pre predajný
   produkt sa pravdepodobnosť v čase nemení.

Strom sa medzi skutočnými krokmi epizódy znovu používa (č. 5.2.1): uzly sú v slovníku
podľa stavu, takže koreň ďalšej požiadavky môže mať už nazbierané štatistiky.

Akcie: 19 sadzieb z mriežky + odmietnutie (∞). Náhodnosť len z np.random.default_rng(seed),
čísla sa ťahajú v dávkach kvôli rýchlosti.
"""
from __future__ import annotations

import bisect
import math

import numpy as np

from mpo_ev.interfaces import REJECT, Config, DemandModel, Product, State

_BATCH = 1 << 16
_PRUNE_AT = 300_000  # počet uzlov, nad ktorým sa zahodia uzly z minulých krokov


class _Node:
    __slots__ = ("n", "n_a", "q_a")

    def __init__(self, n_actions: int) -> None:
        self.n = 0
        self.n_a = [0] * n_actions
        self.q_a = [0.0] * n_actions


class MCTSPolicy:
    """UCT s náhodným rolloutom. Predvolené parametre sú z č. 5.2.1 článku."""

    def __init__(
        self,
        n_iter: int = 800,
        depth: int = 3,
        c: float = 1.0,
        reuse_tree: bool = True,
        name: str = "mcts",
    ) -> None:
        if n_iter < 1 or depth < 1 or c < 0:
            raise ValueError("n_iter a depth musia byť aspoň 1, c nezáporné")
        self.n_iter = n_iter
        self.depth = depth
        self.c = c
        self.reuse_tree = reuse_tree
        self.name = name

    # --- rozhranie Policy -------------------------------------------------------------

    def reset(self, config: Config, demand: DemandModel, seed: int) -> None:
        self._rng = np.random.default_rng(seed)
        self._buf: list[float] = []
        self._pos = 0
        self._n_steps = config.n_steps
        self._n_slots = config.n_slots
        self._demand = demand
        self._rates = list(config.price_grid) + [REJECT]
        self._n_actions = len(self._rates)

        probs = demand.product_probs(0)
        self._products: list[Product] = []
        self._index: dict[Product, int] = {}
        self._first: list[int] = []
        self._last: list[int] = []
        self._last_sale: list[int] = []
        self._q: list[list[float]] = []
        self._r: list[list[float]] = []
        for p in probs:
            self._add_product(p, config, extend_rollout=False)
        self._n_model = len(self._products)  # produkty, ktoré sa dajú vzorkovať

        weights = np.array([probs[p] for p in self._products[: self._n_model]])
        self._p0 = float(weights.sum())
        self._cum = (np.cumsum(weights) / self._p0).tolist() if self._p0 > 0 else []
        # ln(1 − p0) pre inverznú transformáciu geometrického rozdelenia
        self._log_miss = math.log1p(-self._p0) if 0 < self._p0 < 1 else -math.inf
        self._config = config
        self._tree: dict[tuple, _Node] = {}
        self._prepare_rollout(config, demand)

    def price(self, state: State) -> float:
        if not self.reuse_tree:
            self._tree.clear()
        elif len(self._tree) > _PRUNE_AT:
            self._tree = {k: v for k, v in self._tree.items() if k[0] >= state.step}
        p = state.product
        if p not in self._index:  # zriedkavý produkt, ktorý v modeli chýba
            self._add_product(p, self._config)
        root = (state.step, tuple(int(x) for x in state.capacity), self._index[p])
        for _ in range(self.n_iter):
            self._iterate(root)
        node = self._tree[root]
        best = max(range(self._n_actions), key=lambda a: (node.n_a[a] > 0, node.q_a[a]))
        return self._rates[best]

    # --- príprava -----------------------------------------------------------------------

    def _add_product(self, p: Product, config: Config, extend_rollout: bool = True) -> None:
        self._index[p] = len(self._products)
        self._products.append(p)
        self._first.append(p.first_slot)
        self._last.append(p.last_slot + 1)
        self._last_sale.append(config.last_sale_step(p))
        q = [self._demand.acceptance_prob(p, a) for a in self._rates[:-1]] + [0.0]
        r = [self._demand.revenue(p, a) for a in self._rates[:-1]] + [0.0]
        self._q.append(q)
        self._r.append(r)
        if extend_rollout:
            self._extend_rollout(len(self._products) - 1)

    def _prepare_rollout(self, config: Config, demand: DemandModel) -> None:
        """Háčik pre podtriedy (hybrid): príprava rollout politiky pre produkty modelu."""

    def _extend_rollout(self, j: int) -> None:
        """Háčik pre podtriedy: rollout údaje pre produkt j pridaný počas epizódy."""

    # --- náhodnosť ----------------------------------------------------------------------

    def _u(self) -> float:
        if self._pos >= len(self._buf):
            self._buf = self._rng.random(_BATCH).tolist()
            self._pos = 0
        u = self._buf[self._pos]
        self._pos += 1
        return u

    # --- model MDP ----------------------------------------------------------------------

    def _next_offer(self, step: int, cap: list[int]) -> tuple[int, int] | None:
        """Ďalšia ponuka po kroku `step`: (krok, index produktu), alebo None = koniec dňa."""
        if self._p0 <= 0.0:
            return None
        n_steps, log_miss = self._n_steps, self._log_miss
        cum, last_sale, first, last = self._cum, self._last_sale, self._first, self._last
        while True:
            if log_miss == -math.inf:
                step += 1
            else:
                # 1 − u ∈ (0, 1], takže logaritmus je konečný
                step += 1 + int(math.log(1.0 - self._u()) / log_miss)
            if step >= n_steps:
                return None
            j = bisect.bisect_left(cum, self._u())
            if j >= len(cum):
                j = len(cum) - 1
            if last_sale[j] < step:
                continue  # produkt už nie je predajný, ponuka nevzniká
            if min(cap[first[j]:last[j]]) < 1:
                continue  # bez kapacity simulátor odmieta bez ponuky
            return step, j

    def _apply(self, cap: list[int], j: int, a: int) -> float:
        """Vykoná akciu a pre produkt j, vráti odmenu a prípadne zníži kapacitu."""
        if self._u() < self._q[j][a]:
            for k in range(self._first[j], self._last[j]):
                cap[k] -= 1
            return self._r[j][a]
        return 0.0

    # --- MCTS ---------------------------------------------------------------------------

    def _iterate(self, root: tuple) -> None:
        tree, c = self._tree, self.c
        step, cap_t, j = root
        cap = list(cap_t)
        path: list[tuple[_Node, int, float]] = []
        reward = 0.0
        terminal = False
        key = root
        for _ in range(self.depth):
            node = tree.get(key)
            if node is None:  # expanzia
                node = _Node(self._n_actions)
                tree[key] = node
            untried = node.n_a.index(0) if 0 in node.n_a else -1
            if untried >= 0:
                a = untried
            else:
                log_n = math.log(node.n)
                n_a, q_a = node.n_a, node.q_a
                a = max(range(self._n_actions),
                        key=lambda i: q_a[i] + c * math.sqrt(log_n / n_a[i]))
            path.append((node, a, reward))
            reward += self._apply(cap, j, a)
            offer = self._next_offer(step, cap)
            if offer is None:
                terminal = True
                break
            step, j = offer
            key = (step, tuple(cap), j)
            if untried >= 0:
                break
        if not terminal:
            reward += self._rollout(step, cap, j)
        for node, a, before in path:  # spätné šírenie
            node.n += 1
            node.n_a[a] += 1
            node.q_a[a] += (reward - before - node.q_a[a]) / node.n_a[a]

    def _rollout_action(self, step: int, j: int) -> int:
        """Náhodná akcia z A vrátane odmietnutia (Algoritmus 2, riadok 5)."""
        return min(int(self._u() * self._n_actions), self._n_actions - 1)

    def _rollout(self, step: int, cap: list[int], j: int) -> float:
        total = 0.0
        while True:
            total += self._apply(cap, j, self._rollout_action(step, j))
            offer = self._next_offer(step, cap)
            if offer is None:
                return total
            step, j = offer
