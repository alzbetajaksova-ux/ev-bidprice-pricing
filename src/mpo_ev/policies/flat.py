"""Flat rate: jedna sadzba pre všetky požiadavky, alokácia v poradí príchodu (č. 6.2.1)."""
from __future__ import annotations

from collections.abc import Sequence

from mpo_ev.interfaces import Config, DemandModel, Instance, State
from mpo_ev.simulator import run_episode


class FlatRatePolicy:
    name = "flat"

    def __init__(self, rate: float | None = None) -> None:
        self.rate = rate
        self.train_revenue: dict[float, float] = {}  # priemerné tržby každej sadzby z fit

    def fit(self, train_instances: Sequence[Instance], demand: DemandModel) -> None:
        """Vyberie sadzbu z mriežky s najvyššími priemernými tržbami na tréningových dátach."""
        grid = train_instances[0].config.price_grid
        for rate in grid:
            revenues = [
                run_episode(FlatRatePolicy(rate), instance, demand).revenue
                for instance in train_instances
            ]
            self.train_revenue[rate] = sum(revenues) / len(revenues)
        self.rate = max(self.train_revenue, key=self.train_revenue.get)

    def reset(self, config: Config, demand: DemandModel, seed: int) -> None:
        if self.rate is None:
            raise ValueError("flat rate treba najprv natrénovať cez fit alebo zadať sadzbu")

    def price(self, state: State) -> float:
        return self.rate
