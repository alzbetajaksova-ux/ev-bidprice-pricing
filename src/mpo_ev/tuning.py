# Vytvorené s pomocou Claude, upravil: Člen B
"""Ladenie parametrov θ bid-price politiky cez CMA-ES (úloha 4.4).

Úloha ladenia: max_θ  F(θ) = priemerné tržby BidPricePolicy(θ) na pevnej množine
tréningových inštancií. Je spojitá, nízkodimenzionálna, s hranicami a black-box
(F sa dá len simulovať). Vďaka pevným inštanciám a deterministickej politike je F
deterministická (common random numbers): rovnaké θ dá vždy rovnakú hodnotu, takže
rozdiel dvoch θ nie je zašumený výberom inštancií. Zostáva však nehladká, lebo sadzby
sú diskrétne a malá zmena θ zmení cenu až po prekročení hranice medzi sadzbami.

Parametre θ (ladí sa v normalizovanom priestore [0, 1]^4, CMA-ES s hranicami):
- alpha_am, alpha_pm: škálovanie hodnôt slotov μ v prvej a druhej polovici dňa,
- gamma: korekcia očakávaného dopytu v LP,
- resolves_per_day: koľkokrát za deň sa LP prepočíta aj bez predaja; transformácia
  na celé číslo resolve_every = round(K / R), pre R < 0,5 sa periodicky neprepočítava.
Prepočet po predaji (resolve_on_sale) je vždy zapnutý.

Hranice: alpha ∈ [0,1; 1,5], gamma ∈ [0,7; 2,5], resolves_per_day ∈ [0; 96]. Prvé
skúšobné ladenie s užšími hranicami (gamma ≤ 1,6, R ≤ 48) skončilo na ich okraji.

Referencie s rovnakým rozpočtom vyhodnotení:
- náhodné hľadanie (rovnomerne v [0, 1]^4) s presne rovnakým počtom vyhodnotení,
- grid search; pravidelná mriežka má k^4 bodov, takže využije najviac rozpočet
  (pri 100 je to 81 bodov, pri 60 len 16).

Spustenie (príklad): python -m mpo_ev.tuning --slots 4 --runs 10 --budget 100 --jobs 4
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter

import cma
import numpy as np
import yaml

from mpo_ev.demand import demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config, seed_range
from mpo_ev.interfaces import Config, DemandModel, Instance
from mpo_ev.policies.bidprice import BidPricePolicy
from mpo_ev.robustness import ROOT
from mpo_ev.simulator import run_episode

NAMES = ("alpha_am", "alpha_pm", "gamma", "resolves_per_day")
LOWER = np.array([0.1, 0.1, 0.7, 0.0])
UPPER = np.array([1.5, 1.5, 2.5, 96.0])
DEFAULT = {"alpha_am": 1.0, "alpha_pm": 1.0, "gamma": 1.0, "resolves_per_day": 0.0}


# --- priestor parametrov ----------------------------------------------------------------

def to_theta(x: Sequence[float]) -> dict[str, float]:
    """Normalizovaný bod x ∈ [0, 1]^4 → θ v pôvodných jednotkách."""
    x = np.clip(np.asarray(x, dtype=float), 0.0, 1.0)
    values = LOWER + x * (UPPER - LOWER)
    return dict(zip(NAMES, (float(v) for v in values), strict=True))


def to_unit(theta: dict[str, float]) -> np.ndarray:
    values = np.array([theta[name] for name in NAMES], dtype=float)
    return (values - LOWER) / (UPPER - LOWER)


def resolve_every(theta: dict[str, float], n_steps: int) -> int | None:
    per_day = theta["resolves_per_day"]
    return None if per_day < 0.5 else max(1, round(n_steps / per_day))


def make_policy(theta: dict[str, float], n_steps: int) -> BidPricePolicy:
    return BidPricePolicy(
        alpha=[theta["alpha_am"], theta["alpha_pm"]],
        gamma=theta["gamma"],
        resolve_every=resolve_every(theta, n_steps),
        resolve_on_sale=True,
        name="bidprice_tuned",
    )


def fitness(theta: dict[str, float], instances: Sequence[Instance], demand: DemandModel) -> float:
    """Priemerné tržby politiky s parametrami θ na daných inštanciách."""
    policy = make_policy(theta, instances[0].config.n_steps)
    return float(np.mean([run_episode(policy, i, demand).revenue for i in instances]))


# --- vyhodnocovanie (voliteľne paralelne) -----------------------------------------------

_WORKER: dict = {}


def _init_worker(config: Config, seeds: Sequence[int], base: dict) -> None:
    _WORKER["instances"] = generate_instances(config, seeds)
    _WORKER["demand"] = demand_from_base(config, base)


def _worker_fitness(theta: dict[str, float]) -> float:
    return fitness(theta, _WORKER["instances"], _WORKER["demand"])


class Evaluator:
    """Počíta F(θ) pre dávku bodov; s jobs > 1 v samostatných procesoch.

    Výsledok nezávisí od počtu procesov, lebo F je deterministická.
    """

    def __init__(self, config: Config, seeds: Sequence[int], base: dict, jobs: int = 1) -> None:
        self.jobs = jobs
        if jobs > 1:
            self._pool = ProcessPoolExecutor(jobs, initializer=_init_worker,
                                             initargs=(config, list(seeds), base))
        else:
            _init_worker(config, list(seeds), base)

    def __call__(self, thetas: Sequence[dict[str, float]]) -> list[float]:
        if self.jobs > 1:
            return list(self._pool.map(_worker_fitness, thetas))
        return [_worker_fitness(t) for t in thetas]

    def close(self) -> None:
        if self.jobs > 1:
            self._pool.shutdown()


# --- optimalizátory ---------------------------------------------------------------------

@dataclass
class TuningResult:
    method: str
    run_seed: int
    best_theta: dict[str, float]
    best_value: float
    n_evals: int
    time_s: float
    history: list[dict] = field(default_factory=list)  # eval, value, best


def _record(history: list[dict], values: Sequence[float]) -> None:
    best = history[-1]["best"] if history else -math.inf
    for value in values:
        best = max(best, value)
        history.append({"eval": len(history) + 1, "value": value, "best": best})


def tune_cma(
    evaluate: Callable[[Sequence[dict[str, float]]], list[float]],
    budget: int,
    seed: int,
    sigma0: float = 0.25,
    popsize: int | None = None,
    x0: dict[str, float] | None = None,
) -> TuningResult:
    """CMA-ES s pevným rozpočtom vyhodnotení, štart v predvolených parametroch."""
    start = perf_counter()
    options = {"bounds": [0.0, 1.0], "seed": seed + 1, "verbose": -9}  # seed 0 = náhodný v cma
    if popsize is not None:
        options["popsize"] = popsize
    es = cma.CMAEvolutionStrategy(to_unit(x0 or DEFAULT), sigma0, options)
    history: list[dict] = []
    best_theta, best_value = dict(x0 or DEFAULT), -math.inf
    while len(history) < budget:
        xs = es.ask()
        xs = xs[: budget - len(history)]
        thetas = [to_theta(x) for x in xs]
        values = evaluate(thetas)
        _record(history, values)
        i = int(np.argmax(values))
        if values[i] > best_value:
            best_value, best_theta = values[i], thetas[i]
        if len(xs) < es.popsize:
            break  # neúplná generácia: rozpočet minutý, tell by nemal zmysel
        es.tell(xs, [-v for v in values])
    return TuningResult("cma", seed, best_theta, best_value, len(history),
                        perf_counter() - start, history)


def grid_points(budget: int) -> list[dict[str, float]]:
    """Rovnomerná mriežka s najviac `budget` bodmi (rovnaký počet úrovní v každom smere)."""
    levels = max(1, math.floor(budget ** (1 / len(NAMES)) + 1e-9))
    axis = [0.5] if levels == 1 else list(np.linspace(0.0, 1.0, levels))
    return [to_theta(x) for x in itertools.product(axis, repeat=len(NAMES))]


def tune_grid(
    evaluate: Callable[[Sequence[dict[str, float]]], list[float]], budget: int
) -> TuningResult:
    start = perf_counter()
    thetas = grid_points(budget)
    values = evaluate(thetas)
    history: list[dict] = []
    _record(history, values)
    i = int(np.argmax(values))
    return TuningResult("grid", 0, thetas[i], values[i], len(history),
                        perf_counter() - start, history)


def tune_random(
    evaluate: Callable[[Sequence[dict[str, float]]], list[float]], budget: int, seed: int
) -> TuningResult:
    """Náhodné hľadanie: `budget` bodov rovnomerne v [0, 1]^4, plus predvolené θ."""
    start = perf_counter()
    rng = np.random.default_rng(seed)
    thetas = [dict(DEFAULT)] + [to_theta(x) for x in rng.random((budget - 1, len(NAMES)))]
    values = evaluate(thetas)
    history: list[dict] = []
    _record(history, values)
    i = int(np.argmax(values))
    return TuningResult("random", seed, thetas[i], values[i], len(history),
                        perf_counter() - start, history)


# --- ukladanie a spustenie --------------------------------------------------------------

def save_result(result: TuningResult, config_id: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{config_id}_{result.method}_seed{result.run_seed}.json"
    data = {k: v for k, v in asdict(result).items() if k != "history"}
    data["config_id"] = config_id
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_theta(path: Path) -> dict[str, float]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["best_theta"]


def save_history(results: Sequence[TuningResult], config_id: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["config_id", "method", "run_seed", "eval", "value", "best"])
        for r in results:
            for h in r.history:
                writer.writerow([config_id, r.method, r.run_seed, h["eval"], h["value"], h["best"]])


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ladenie θ bid-price politiky cez CMA-ES")
    parser.add_argument("--slots", type=int, required=True, help="počet slotov z config/e1.yaml")
    parser.add_argument("--runs", type=int, default=10, help="počet behov CMA-ES (seedy 0..runs-1)")
    parser.add_argument("--budget", type=int, default=100, help="vyhodnotenia F na jeden beh")
    parser.add_argument("--n-train", type=int, default=200, help="počet tréningových inštancií")
    parser.add_argument("--jobs", type=int, default=1, help="počet procesov")
    parser.add_argument("--no-baselines", action="store_true",
                        help="vynechať náhodné hľadanie a grid search")
    args = parser.parse_args(argv)

    base = load_base()
    with open(ROOT / "config" / "e1.yaml", encoding="utf-8") as file:
        items = yaml.safe_load(file)["configurations"]
    item = next(c for c in items if c["n_slots"] == args.slots)
    config = make_config(item["n_slots"], item["n_steps"], item["expected_requests"], base)
    seeds = list(seed_range(base, "train"))[: args.n_train]
    config_id = f"{args.slots}s"
    cma_seeds = list(seed_range(base, "cma_runs"))[: args.runs]

    evaluate = Evaluator(config, seeds, base, args.jobs)
    try:
        default_value = evaluate([DEFAULT])[0]
        print(f"{config_id}: {len(seeds)} tréningových inštancií, predvolené θ → {default_value:.3f}")
        results = []
        for seed in cma_seeds:
            result = tune_cma(evaluate, args.budget, seed)
            results.append(result)
            save_result(result, config_id, ROOT / "results" / "params")
            print(f"  cma seed {seed}: {result.best_value:.3f}  θ = "
                  + ", ".join(f"{k}={v:.3g}" for k, v in result.best_theta.items())
                  + f"  ({result.time_s:.0f} s)", flush=True)
        if not args.no_baselines:
            for seed in cma_seeds:
                rnd = tune_random(evaluate, args.budget, seed)
                results.append(rnd)
                save_result(rnd, config_id, ROOT / "results" / "params")
                print(f"  random seed {seed}: {rnd.best_value:.3f}", flush=True)
            grid = tune_grid(evaluate, args.budget)
            results.append(grid)
            save_result(grid, config_id, ROOT / "results" / "params")
            print(f"  grid ({grid.n_evals} bodov): {grid.best_value:.3f}")
        save_history(results, config_id, ROOT / "results" / f"tuning_{config_id}.csv")
    finally:
        evaluate.close()


if __name__ == "__main__":
    main()
