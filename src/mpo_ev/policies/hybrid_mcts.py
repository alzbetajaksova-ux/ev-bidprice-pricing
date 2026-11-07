# Vytvorené s pomocou Claude, upravil: Člen C
"""Hybrid MCTS: náhodný rollout autorov nahradí bid-price politika (časť 4 návodu, bod 5).

Strom, UCB aj spätné šírenie sú rovnaké ako v `MCTSPolicy`. Iba v rolloute sa namiesto
náhodnej sadzby ponúkne sadzba bid-price politiky Člena B:

    a = argmax_a q(p,a) · (r(p,a) − α(t) · Σ_{j ∈ p} μ_j),  inak odmietnutie,

kde μ sú duálne ceny LP vypočítané raz pri `reset` (z plnej kapacity a dopytu celého
dňa, `BidPricePolicy` bez prepočtu). Sadzba závisí len od produktu a časti dňa, takže
ju predpočítame do tabuľky a rollout je rovnako rýchly ako náhodný.

Rollout je tak „rozumný“ odhad hodnoty stavu: náhodná politika často predáva pod cenou
alebo odmieta dobrých zákazníkov, takže jej odhad Q je silne zašumený a skreslený nadol.
"""
from __future__ import annotations

from collections.abc import Sequence

from mpo_ev.interfaces import REJECT, Config, DemandModel
from mpo_ev.policies.bidprice import BidPricePolicy
from mpo_ev.policies.mcts import MCTSPolicy


class HybridMCTSPolicy(MCTSPolicy):
    def __init__(
        self,
        n_iter: int = 800,
        depth: int = 3,
        c: float = 1.0,
        reuse_tree: bool = True,
        alpha: float | Sequence[float] = 1.0,
        gamma: float = 1.0,
        name: str = "hybrid_mcts",
    ) -> None:
        super().__init__(n_iter, depth, c, reuse_tree, name)
        self.alpha = alpha
        self.gamma = gamma

    def _prepare_rollout(self, config: Config, demand: DemandModel) -> None:
        self._bidprice = BidPricePolicy(alpha=self.alpha, gamma=self.gamma)
        self._bidprice.reset(config, demand, seed=0)
        self._n_parts = len(self._bidprice.alphas)
        self._action_of = {rate: i for i, rate in enumerate(self._rates)}
        self._table: list[list[int]] = []
        for j in range(len(self._products)):
            self._extend_rollout(j)

    def _extend_rollout(self, j: int) -> None:
        p = self._products[j]
        mu = self._bidprice.mu
        load = float(mu[p.first_slot:p.last_slot + 1].sum())
        row = []
        for alpha in self._bidprice.alphas:
            rate = self._bidprice.best_rate(p, float(alpha) * load)
            row.append(self._action_of[rate] if rate != REJECT else self._n_actions - 1)
        self._table.append(row)

    def _rollout_action(self, step: int, j: int) -> int:
        part = min(step * self._n_parts // self._n_steps, self._n_parts - 1)
        return self._table[j][part]
