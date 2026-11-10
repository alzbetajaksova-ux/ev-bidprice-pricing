# Vytvorené s pomocou Claude, upravil: Alžbeta Jakšová (Člen A)
"""Spoločné dátové triedy a protokoly. Bez dohody tímu sa nemenia."""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

REJECT = math.inf  # cena nekonečno = odmietnutie
HORIZON_H = 24.0   # dĺžka dňa v hodinách


@dataclass(frozen=True)
class Product:
    first_slot: int  # index prvého slotu
    last_slot: int   # index posledného slotu (vrátane)

    def __post_init__(self) -> None:
        if not 0 <= self.first_slot <= self.last_slot:
            raise ValueError(f"neplatný produkt: {self}")

    def slots(self) -> range:
        return range(self.first_slot, self.last_slot + 1)


@dataclass(frozen=True)
class Config:
    n_slots: int                   # počet slotov dňa
    n_steps: int                   # počet krokov diskretizácie K
    capacity: int                  # počet nabíjačiek (3)
    expected_requests: float       # lambda za celý horizont
    price_grid: tuple[float, ...]  # sadzby za hodinu, bez REJECT
    budget_mean: float = 1.0       # rozpočet za hodinu
    budget_std: float = 0.5
    duration_mean_h: float = 3.0
    start_mean_h: float = 12.0
    start_std_h: float = 3.0

    def __post_init__(self) -> None:
        if self.expected_requests > self.n_steps:
            raise ValueError("lambda / K musí byť pravdepodobnosť (K >= lambda)")

    @property
    def slot_length_h(self) -> float:
        return HORIZON_H / self.n_slots

    def duration_h(self, product: Product) -> float:
        return (product.last_slot - product.first_slot + 1) * self.slot_length_h

    def last_sale_step(self, product: Product) -> int:
        """Posledný krok (od 0), ktorý celý leží pred T_p = koniec prvého slotu.

        Celočíselne, aby hranicu nezmenilo zaokrúhlenie. Krok t končí v čase
        (t + 1) * 24 / K, čo zodpovedá t + 1 v číslovaní článku od 1.
        """
        return (product.first_slot + 1) * self.n_steps // self.n_slots - 1

    def is_sellable(self, product: Product, step: int) -> bool:
        return step <= self.last_sale_step(product)


@dataclass(frozen=True)
class Request:
    step: int            # krok príchodu
    product: Product
    budget_rate: float   # skrytý rozpočet za hodinu; politika ho NEVIDÍ


@dataclass(frozen=True)
class Instance:
    config: Config
    requests: tuple[Request, ...]  # zoradené podľa step, najviac 1 na krok
    seed: int

    def __post_init__(self) -> None:
        steps = [r.step for r in self.requests]
        if any(a >= b for a, b in itertools.pairwise(steps)):
            raise ValueError("kroky požiadaviek musia ostro rásť")


@dataclass(frozen=True)
class State:
    step: int
    capacity: np.ndarray  # zostávajúca kapacita na slot, tvar (n_slots,), len na čítanie
    product: Product      # práve požadovaný produkt, vždy predajný a s voľnou kapacitou


class DemandModel(Protocol):
    # Generatívny model dopytu pre LP, VI a MCTS (implementuje A).
    def product_probs(self, step: int) -> dict[Product, float]:
        """P(požiadavka na p v kroku); len produkty predajné v danom kroku. Nemeniť."""
        ...

    def expected_remaining(self, step: int) -> dict[Product, float]:
        """Lambda_p: súčet product_probs(s)[p] cez s = step ... K-1."""
        ...

    def acceptance_prob(self, product: Product, rate: float) -> float: ...
    def revenue(self, product: Product, rate: float) -> float: ...  # sadzba x dĺžka v h
    def duration_h(self, product: Product) -> float: ...


class Policy(Protocol):
    # Pravdepodobnosti brať len z demand. Z config používať len sloty, kroky, kapacitu
    # a mriežku: v E4 config nesie skutočné lambda a rozpočet, demand nesprávne.
    name: str

    def reset(self, config: Config, demand: DemandModel, seed: int) -> None: ...
    def price(self, state: State) -> float: ...  # sadzba z price_grid alebo REJECT


@dataclass
class EpisodeResult:
    revenue: float
    utilization_h: float
    n_requests: int
    n_accepted: int
    runtime_s: float  # čas politiky: reset + všetky volania price
