# Vytvorené s pomocou Claude, upravil: Člen B
"""Deterministický LP pre oceňovanie a duálne ceny slotov (úlohy 4.1 a 4.2).

Fluidná (deterministická) relaxácia viacproduktového dynamického oceňovania,
pozri Gallego a van Ryzin (1997) a Talluri a van Ryzin (2004), kap. 3 a 5:

    max  Σ_p Σ_a  r(p,a) · q(p,a) · x(p,a)
    s.t. Σ_a x(p,a)                    ≤ Λ_p     pre každý produkt p
         Σ_{p ∋ j} Σ_a q(p,a) · x(p,a) ≤ c_j     pre každý slot j   (duál μ_j)
         x ≥ 0

x(p,a) je očakávaný počet ponúk produktu p so sadzbou a. Každý zákazník chce jeden
konkrétny produkt, takže LP rozdeľuje očakávané požiadavky na p medzi sadzby
(prípadne niektoré odmietne). Rozdelenie medzi dve sadzby zodpovedá konkávnemu obalu
krivky tržieb produktu.

Hodnota LP je horná hranica očakávaných tržieb každej neanticipatívnej politiky
(Jensenova nerovnosť), nie hranica pre Oracle, ktorý pozná budúcnosť.
"""
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from mpo_ev.interfaces import DemandModel, Product

Key = tuple[Product, float]


def solve_dlp(
    capacity: Sequence[float] | np.ndarray,
    Lambda: Mapping[Product, float],
    q: Mapping[Key, float],
    r: Mapping[Key, float],
    products: Iterable[Product],
) -> tuple[float, np.ndarray]:
    """Vyrieši LP a vráti (optimálna hodnota, μ) s μ dĺžky n_slots.

    `q` a `r` majú kľúč (produkt, sadzba); sadzby produktu sa berú zo všetkých kľúčov
    s daným produktom. Produkty bez Λ alebo s Λ ≤ 0 sa preskočia. Duálne ceny μ_j ≥ 0
    nie sú pri degenerácii jednoznačné; vraciame tie, ktoré dá HiGHS.
    """
    capacity = np.asarray(capacity, dtype=float)
    n_slots = len(capacity)

    rates_of: dict[Hashable, list[float]] = {}
    for p, a in q:
        rates_of.setdefault(p, []).append(a)

    obj: list[float] = []         # r · q na premennú
    row_idx: list[int] = []       # riadky matice A_ub
    col_idx: list[int] = []
    vals: list[float] = []
    bounds_rhs: list[float] = []  # Λ_p pre riadky produktov
    n_prod_rows = 0

    for p in products:
        volume = float(Lambda.get(p, 0.0))
        if volume <= 0.0:
            continue
        if p.last_slot >= n_slots:
            raise ValueError(f"produkt {p} presahuje {n_slots} slotov")
        prod_row = n_prod_rows
        n_prod_rows += 1
        bounds_rhs.append(volume)
        for a in rates_of.get(p, []):
            qa = float(q[(p, a)])
            ra = float(r[(p, a)])
            if qa <= 0.0 or ra <= 0.0:
                continue  # takáto ponuka nič neprinesie ani nespotrebuje
            col = len(obj)
            obj.append(ra * qa)
            row_idx.append(prod_row)
            col_idx.append(col)
            vals.append(1.0)
            for j in p.slots():
                row_idx.append(-1 - j)  # riadky slotov dočasne záporné, preindexujú sa nižšie
                col_idx.append(col)
                vals.append(qa)

    if not obj:
        return 0.0, np.zeros(n_slots)

    rows = np.asarray(row_idx)
    rows = np.where(rows >= 0, rows, n_prod_rows + (-rows - 1))
    a_ub = coo_matrix(
        (vals, (rows, col_idx)), shape=(n_prod_rows + n_slots, len(obj))
    ).tocsr()
    b_ub = np.concatenate([np.asarray(bounds_rhs), capacity])

    res = linprog(-np.asarray(obj), A_ub=a_ub, b_ub=b_ub, bounds=(0, None), method="highs")
    if res.status != 0:
        raise RuntimeError(f"LP sa nepodarilo vyriešiť: {res.message}")

    # HiGHS minimalizuje −tržby; marginály ≤ 0 sú citlivosť na pravú stranu.
    mu = np.maximum(-np.asarray(res.ineqlin.marginals[n_prod_rows:]), 0.0)
    return float(-res.fun), mu


def lp_inputs(
    demand: DemandModel,
    price_grid: Sequence[float],
    step: int = 0,
    gamma: float = 1.0,
) -> tuple[dict[Product, float], dict[Key, float], dict[Key, float], list[Product]]:
    """Vstupy LP od kroku `step` (úloha 4.1): Λ_p = γ · expected_remaining(step)[p].

    Pravdepodobnosti a tržby sa berú len z `demand`, nie z `config` (férovosť v E4).
    """
    volumes = {p: gamma * v for p, v in demand.expected_remaining(step).items()}
    products = list(volumes)
    q: dict[Key, float] = {}
    r: dict[Key, float] = {}
    for p in products:
        for a in price_grid:
            q[(p, a)] = demand.acceptance_prob(p, a)
            r[(p, a)] = demand.revenue(p, a)
    return volumes, q, r, products
