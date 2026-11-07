# Vytvorené s pomocou Claude, upravil: Člen B
"""Oracle: najlepšia alokácia s plnou znalosťou budúcnosti (úloha 3.5, č. 6.2.3 článku).

Oracle pozná všetky požiadavky dňa aj skryté rozpočty. Vyberie podmnožinu požiadaviek,
ktorá zmestí do kapacity a má najvyššie tržby, ak by každému zákazníkovi ponúkol
najvyššiu sadzbu z mriežky, ktorú ešte prijme. Binárny program (rov. 11–12 článku):

    max  Σ_i x_i · ⌊b_i⌋_A · d_i
    s.t. Σ_{i : j ∈ p_i} x_i ≤ c_j     pre každý slot j
         x_i ∈ {0, 1}

⌊b⌋_A je najvyššia sadzba z mriežky ostro pod rozpočtom za hodinu (simulátor predá len
pri rozpočte > sadzba), d_i je dĺžka produktu v hodinách. Požiadavky po T_p sa nedajú
predať ani Oracle (`config.is_sellable`).

Oracle nie je `Policy`: nepozná len stav, ale celú inštanciu. Slúži ako nedosiahnuteľná
horná hranica tržieb na konkrétnej inštancii, nie ako metóda na porovnanie férovosti.
Každá politika má na každej inštancii tržby ≤ Oracle, lebo jej predaje tvoria prípustné
riešenie a za každý predaj dostane najviac ⌊b_i⌋_A · d_i.
"""
from __future__ import annotations

import bisect
from collections.abc import Sequence
from time import perf_counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from mpo_ev.interfaces import EpisodeResult, Instance, Request

METHOD = "oracle"


def floor_rate(budget_rate: float, grid: Sequence[float]) -> float | None:
    """Najvyššia sadzba z mriežky ostro pod rozpočtom, alebo None, ak žiadna nie je."""
    i = bisect.bisect_left(grid, budget_rate) - 1
    return float(grid[i]) if i >= 0 else None


def oracle_allocation(instance: Instance) -> list[tuple[Request, float]]:
    """Prijaté požiadavky a ich sadzby v optimálnej alokácii Oracle."""
    config = instance.config
    grid = sorted(config.price_grid)

    candidates: list[tuple[Request, float]] = []
    for request in instance.requests:
        if not config.is_sellable(request.product, request.step):
            continue
        rate = floor_rate(request.budget_rate, grid)
        if rate is not None:
            candidates.append((request, rate))
    if not candidates:
        return []

    revenue = np.array([rate * config.duration_h(req.product) for req, rate in candidates])
    rows = [j for req, _ in candidates for j in req.product.slots()]
    cols = [i for i, (req, _) in enumerate(candidates) for _ in req.product.slots()]
    a = coo_matrix((np.ones(len(rows)), (rows, cols)),
                   shape=(config.n_slots, len(candidates))).tocsr()

    res = milp(
        -revenue,
        constraints=LinearConstraint(a, -np.inf, np.full(config.n_slots, config.capacity)),
        integrality=np.ones(len(candidates)),
        bounds=Bounds(0, 1),
    )
    if res.status != 0:
        raise RuntimeError(f"Oracle: MILP sa nepodarilo vyriešiť: {res.message}")
    chosen = np.round(res.x).astype(bool)
    return [cand for cand, take in zip(candidates, chosen, strict=True) if take]


def oracle_episode(instance: Instance) -> EpisodeResult:
    """Výsledok Oracle v rovnakom tvare ako `run_episode`; runtime_s je čas MILP."""
    start = perf_counter()
    accepted = oracle_allocation(instance)
    runtime_s = perf_counter() - start
    config = instance.config
    durations = [config.duration_h(req.product) for req, _ in accepted]
    return EpisodeResult(
        revenue=sum(rate * d for (_, rate), d in zip(accepted, durations, strict=True)),
        utilization_h=sum(durations),
        n_requests=len(instance.requests),
        n_accepted=len(accepted),
        runtime_s=runtime_s,
    )


def evaluate_oracle(
    instances: Sequence[Instance], base: dict, experiment: str, config_id: str
) -> list[dict]:
    """Riadky v dohodnutom formáte CSV, rovnako ako `robustness.evaluate_policy`."""
    rows = []
    for instance in instances:
        result = oracle_episode(instance)
        rows.append(
            {
                "experiment": experiment,
                "config_id": config_id,
                "method": METHOD,
                "instance_seed": instance.seed,
                "run_seed": instance.seed + base["seeds"]["mcts_offset"],
                "revenue": result.revenue,
                "utilization_h": result.utilization_h,
                "n_requests": result.n_requests,
                "n_accepted": result.n_accepted,
                "runtime_s": result.runtime_s,
            }
        )
    return rows
