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

Implementácia rieši ekvivalentný tvar s pomocnou premennou s_p = Σ_a q(p,a)·x(p,a)
(očakávaný predaj produktu p). Kapacitné riadky potom obsahujú len s_p, takže pri
72 slotoch má matica asi 10× menej nenulových prvkov. Hodnota a μ sa nemenia.
"""
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

from mpo_ev.interfaces import DemandModel, Product

Key = tuple[Product, float]
# Interior-point s crossoverom: pri 72 slotoch ~0,7 s namiesto ~2,9 s pre duálny simplex,
# s rovnakou hodnotou aj μ (overené na E1 konfiguráciách).
_METHOD = "highs-ipm"


def efficient_rates(points: Sequence[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """Sadzby, ktoré LP môže potrebovať: horný konkávny obal bodov (q, r·q) s počiatkom.

    `points` sú trojice (sadzba, q, r). Ponechá sa len časť obalu od počiatku po bod
    s najvyššou očakávanou tržbou r·q. Ostatné sadzby sú dominované: buď spotrebujú
    viac kapacity za menšiu tržbu, alebo ich nahradí zmes dvoch susedných sadzieb
    (a nepredaných ponúk). Ich vynechanie nemení hodnotu LP ani množinu duálnych riešení.
    """
    pts = sorted((q, r * q, a, r) for a, q, r in points if q > 0.0 and r > 0.0)
    if not pts:
        return []
    best = max(range(len(pts)), key=lambda i: (pts[i][1], -pts[i][0]))
    hull: list[tuple[float, float, float, float]] = [(0.0, 0.0, 0.0, 0.0)]
    for pt in pts[: best + 1]:
        while len(hull) >= 2:
            (x1, y1, *_), (x2, y2, *_) = hull[-2], hull[-1]
            # odstráň stred, ak neleží ostro nad spojnicou susedov (nie je konkávny)
            if (x2 - x1) * (pt[1] - y1) - (y2 - y1) * (pt[0] - x1) >= 0:
                hull.pop()
            else:
                break
        if hull[-1][0] == pt[0]:  # rovnaké q: ponechaj vyššiu tržbu
            if pt[1] > hull[-1][1]:
                hull[-1] = pt
            continue
        hull.append(pt)
    return [(a, q, r) for q, _, a, r in hull[1:]]


def solve_dlp(
    capacity: Sequence[float] | np.ndarray,
    Lambda: Mapping[Product, float],
    q: Mapping[Key, float],
    r: Mapping[Key, float],
    products: Iterable[Product],
    prune: bool = True,
) -> tuple[float, np.ndarray]:
    """Vyrieši LP a vráti (optimálna hodnota, μ) s μ dĺžky n_slots.

    `q` a `r` majú kľúč (produkt, sadzba); sadzby produktu sa berú zo všetkých kľúčov
    s daným produktom. Produkty bez Λ alebo s Λ ≤ 0 sa preskočia. Duálne ceny μ_j ≥ 0
    nie sú pri degenerácii jednoznačné; vraciame tie, ktoré dá HiGHS. `prune` vynechá
    dominované sadzby (`efficient_rates`); hodnotu LP to nemení, len zrýchli riešenie.
    """
    capacity = np.asarray(capacity, dtype=float)
    n_slots = len(capacity)

    rates_of: dict[Hashable, list[float]] = {}
    for p, a in q:
        rates_of.setdefault(p, []).append(a)

    # Premenné: x(p,a) pre každú efektívnu sadzbu a s_p = očakávaný predaj produktu p.
    # Sloty vidia len s_p, takže matica je riedka aj pri dlhých produktoch.
    obj: list[float] = []      # r · q pre x; s_p má v účelovej funkcii 0
    x_prod: list[int] = []     # index produktu pre každé x
    x_q: list[float] = []      # q pre každé x
    volumes: list[float] = []
    prod_slots: list[range] = []

    for p in products:
        volume = float(Lambda.get(p, 0.0))
        if volume <= 0.0:
            continue
        if p.last_slot >= n_slots:
            raise ValueError(f"produkt {p} presahuje {n_slots} slotov")
        candidates = [(a, float(q[(p, a)]), float(r[(p, a)])) for a in rates_of.get(p, [])]
        if prune:
            candidates = efficient_rates(candidates)
        candidates = [(a, qa, ra) for a, qa, ra in candidates if qa > 0.0 and ra > 0.0]
        if not candidates:
            continue  # žiadna ponuka nič neprinesie
        k = len(volumes)
        volumes.append(volume)
        prod_slots.append(p.slots())
        for _a, qa, ra in candidates:
            obj.append(ra * qa)
            x_prod.append(k)
            x_q.append(qa)

    if not obj:
        return 0.0, np.zeros(n_slots)

    n_x, n_p = len(obj), len(volumes)
    x_cols = np.arange(n_x)
    s_cols = n_x + np.arange(n_p)

    # A_ub: [Σ_a x(p,a) ≤ Λ_p] pre produkty, potom [Σ_{p ∋ j} s_p ≤ c_j] pre sloty
    cap_rows = np.fromiter((n_p + j for slots in prod_slots for j in slots), dtype=np.int64)
    cap_cols = np.repeat(s_cols, [len(slots) for slots in prod_slots])
    a_ub = coo_matrix(
        (
            np.ones(n_x + len(cap_rows)),
            (np.concatenate([x_prod, cap_rows]), np.concatenate([x_cols, cap_cols])),
        ),
        shape=(n_p + n_slots, n_x + n_p),
    ).tocsr()
    b_ub = np.concatenate([volumes, capacity])

    # A_eq: Σ_a q(p,a) · x(p,a) − s_p = 0
    a_eq = coo_matrix(
        (
            np.concatenate([x_q, -np.ones(n_p)]),
            (np.concatenate([x_prod, np.arange(n_p)]), np.concatenate([x_cols, s_cols])),
        ),
        shape=(n_p, n_x + n_p),
    ).tocsr()

    c = -np.concatenate([obj, np.zeros(n_p)])
    res = linprog(c, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=np.zeros(n_p),
                  bounds=(0, None), method=_METHOD)
    if res.status != 0:
        raise RuntimeError(f"LP sa nepodarilo vyriešiť: {res.message}")

    # HiGHS minimalizuje −tržby; marginály ≤ 0 sú citlivosť na pravú stranu.
    mu = np.maximum(-np.asarray(res.ineqlin.marginals[n_p:]), 0.0)
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
