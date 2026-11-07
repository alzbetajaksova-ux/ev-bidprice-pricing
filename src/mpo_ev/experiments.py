# Vytvorené s pomocou Claude, upravil: Člen C
"""Runner experimentov (úloha 5.1). Spúšťa sa cez run_experiments.py v koreni.

Experimenty Člena C: E1 (dĺžka slotu, 5.2), E2 (hustota dopytu, 5.3) a grid search MCTS
(3.8); E4 (robustnosť, 5.5 Člena A) runner rozširuje o bid-price a MCTS. E3 (prínos
ladenia, 5.4) patrí Členovi B a beží cez tuning.py (`run_experiments.py --tune`).

Každá kombinácia (experiment, konfigurácia, metóda, scenár) sa rozdelí na úlohy po
skupinách inštancií a úlohy bežia paralelne v procesoch. Výsledok nezávisí od počtu
procesov: inštancia aj náhodnosť politiky sú dané seedom (seed inštancie + 50 000).
Hotové úlohy sa ukladajú do results/.cache, takže beh po páde pokračuje (--fresh ich zahodí).

Férovosť:
- všetky metódy dostanú rovnaké testovacie inštancie a ten istý `DemandModel`,
- tréning (flat rate) a ladenie (θ bid-price, grid search MCTS) používajú len tréningové
  seedy 0–199, testovacie seedy 1000–1099 sa na rozhodovanie nepoužijú,
- Oracle a LP hranica nie sú politiky, slúžia ako referencie,
- offline príprava (tréning flat rate, tabuľka VI, ladenie θ) sa meria zvlášť od online
  času rozhodovania (`runtime_s`), do súboru <experiment>_offline.csv.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import yaml

from mpo_ev.bounds import gap_to_bound, lp_upper_bound
from mpo_ev.demand import demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config, required_steps, seed_range
from mpo_ev.interfaces import Config, DemandModel, Policy
from mpo_ev.policies.bidprice import BidPricePolicy
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.policies.hybrid_mcts import HybridMCTSPolicy
from mpo_ev.policies.mcts import MCTSPolicy
from mpo_ev.policies.oracle import evaluate_oracle
from mpo_ev.policies.vi import ValueIteration, VIPolicy
from mpo_ev.robustness import (
    ROOT,
    Scenario,
    believed_config,
    evaluate_policy,
    save_rows,
    true_config,
)

CONFIG_DIR = ROOT / "config"
RESULTS = ROOT / "results"
SLOW = {"mcts", "hybrid_mcts"}  # metódy, ktoré sa delia na menšie skupiny inštancií
USES_THETA = {"bidprice_tuned", "hybrid_mcts"}  # metódy, ktoré čítajú naladené θ Člena B
CHUNK = 5


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as file:
        return yaml.safe_load(file)


def config_id(config: Config) -> str:
    return f"{config.n_slots}s"


# --- register politík -----------------------------------------------------------------

def tuned_result(cid: str, params_dir: Path = RESULTS / "params") -> dict | None:
    """Beh CMA-ES s najvyššou tréningovou hodnotou (úloha 4.4 Člena B), ak existuje."""
    best = None
    for path in sorted(params_dir.glob(f"{cid}_cma_seed*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if best is None or data["best_value"] > best["best_value"]:
            best = data
    return best


def tuned_theta(cid: str, params_dir: Path = RESULTS / "params") -> dict[str, float] | None:
    best = tuned_result(cid, params_dir)
    return None if best is None else best["best_theta"]


def _flat(config: Config, demand: DemandModel, base: dict, params: dict) -> Policy:
    policy = FlatRatePolicy()
    policy.fit(generate_instances(config, seed_range(base, "train")), demand)
    return policy


def _vi(config: Config, demand: DemandModel, base: dict, params: dict) -> Policy:
    policy = VIPolicy()
    policy.reset(config, demand, 0)  # tabuľka W offline; reset v epizóde ju znovu použije
    return policy


def _bidprice_tuned(config: Config, demand: DemandModel, base: dict, params: dict) -> Policy:
    from mpo_ev.tuning import make_policy

    return make_policy(params["theta"], config.n_steps)


def _hybrid(config: Config, demand: DemandModel, base: dict, params: dict) -> Policy:
    theta = params.get("theta")
    extra = {}
    if theta is not None:  # rollout s naladeným α a γ, μ stále len raz pri reset
        extra = {"alpha": [theta["alpha_am"], theta["alpha_pm"]], "gamma": theta["gamma"]}
    return HybridMCTSPolicy(**params["hybrid_mcts"], **extra)


# Register metód podľa mena: meno -> továreň (config, demand, base, params) -> politika.
REGISTRY: dict[str, Callable[[Config, DemandModel, dict, dict], Policy]] = {
    "flat": _flat,
    "vi": _vi,
    "bidprice": lambda config, demand, base, params: BidPricePolicy(),
    "bidprice_tuned": _bidprice_tuned,
    "mcts": lambda config, demand, base, params: MCTSPolicy(**params["mcts"]),
    "hybrid_mcts": _hybrid,
}


def build_policy(method: str, config: Config, demand: DemandModel, base: dict,
                 params: dict) -> Policy:
    """Vytvorí politiku z registra. `config` je to, čomu politika verí (v E4 chybný model)."""
    if method not in REGISTRY:
        raise ValueError(f"neznáma metóda {method}")
    return REGISTRY[method](config, demand, base, params)


# --- úlohy ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Task:
    experiment: str
    config: Config
    method: str                 # oracle alebo meno z REGISTRY
    seeds: tuple[int, ...]      # seedy inštancií
    label: str                  # config_id v CSV
    params: dict = field(default_factory=dict)
    scenario: Scenario | None = None
    name: str | None = None     # prepíše stĺpec method (grid search: parametre v názve)

    def key(self) -> str:
        """Odtlačok úlohy pre pokračovanie po páde; zmena parametrov dá iný odtlačok."""
        return hashlib.sha1(repr(self).encode("utf-8")).hexdigest()[:16]


@dataclass
class TaskResult:
    rows: list[dict]
    offline_s: float = 0.0  # príprava politiky pred dňom (tréning, tabuľka VI)


_DEMAND_CACHE: dict[Config, DemandModel] = {}


def _demand(config: Config, base: dict) -> DemandModel:
    # Rovnaký objekt pre rovnaký config: VIPolicy potom W nepočíta znova.
    if config not in _DEMAND_CACHE:
        _DEMAND_CACHE[config] = demand_from_base(config, base)
    return _DEMAND_CACHE[config]


def run_task(task: Task, base: dict) -> TaskResult:
    scenario = task.scenario or Scenario("nominal")
    truth = true_config(task.config, scenario)
    instances = [generate_instances(truth, range(s, s + 1))[0] for s in task.seeds]
    if task.method == "oracle":
        return TaskResult(evaluate_oracle(instances, base, task.experiment, task.label))
    believed = believed_config(truth, scenario)
    demand = _demand(believed, base)
    start = perf_counter()
    policy = build_policy(task.method, believed, demand, base, task.params)
    offline_s = perf_counter() - start
    rows = evaluate_policy(policy, instances, demand, base, task.experiment, task.label)
    if task.name is not None:
        for row in rows:
            row["method"] = task.name
    return TaskResult(rows, offline_s)


def split(method: str, seeds: Sequence[int]) -> list[tuple[int, ...]]:
    if method not in SLOW:
        return [tuple(seeds)]
    return [tuple(seeds[i:i + CHUNK]) for i in range(0, len(seeds), CHUNK)]


class TaskCache:
    """Hotové úlohy na disku: results/.cache/<experiment>/<odtlačok>.json."""

    def __init__(self, root: Path | None) -> None:
        self.root = root

    def _path(self, task: Task) -> Path:
        assert self.root is not None
        return self.root / task.experiment / f"{task.key()}.json"

    def get(self, task: Task) -> TaskResult | None:
        if self.root is None or not self._path(task).exists():
            return None
        data = json.loads(self._path(task).read_text(encoding="utf-8"))
        return TaskResult(data["rows"], data["offline_s"])

    def put(self, task: Task, result: TaskResult) -> None:
        if self.root is None:
            return
        path = self._path(task)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(result)), encoding="utf-8")
        tmp.replace(path)  # atomicky, aby pád počas zápisu nenechal poškodený súbor


def run_tasks(tasks: list[Task], base: dict, jobs: int,
              cache: TaskCache | None = None) -> list[TaskResult]:
    """Spustí úlohy (paralelne pri jobs > 1), hotové z cache preskočí; poradie ako `tasks`."""
    cache = cache or TaskCache(None)
    results: dict[int, TaskResult] = {}
    for i, task in enumerate(tasks):
        cached = cache.get(task)
        if cached is not None:
            results[i] = cached
    todo = [i for i in range(len(tasks)) if i not in results]
    if len(todo) < len(tasks):
        print(f"  {len(tasks) - len(todo)} úloh z cache, zostáva {len(todo)}")
    start = perf_counter()
    if jobs <= 1:
        for done, i in enumerate(todo, 1):
            results[i] = run_task(tasks[i], base)
            cache.put(tasks[i], results[i])
            _progress(done, len(todo), tasks[i], start)
    elif todo:
        with ProcessPoolExecutor(jobs) as pool:
            futures = {pool.submit(run_task, tasks[i], base): i for i in todo}
            for done, future in enumerate(as_completed(futures), 1):
                i = futures[future]
                results[i] = future.result()
                cache.put(tasks[i], results[i])
                _progress(done, len(todo), tasks[i], start)
    return [results[i] for i in range(len(tasks))]


def _rows(results: Sequence[TaskResult]) -> list[dict]:
    return [row for result in results for row in result.rows]


def offline_table(tasks: Sequence[Task], results: Sequence[TaskResult]) -> pd.DataFrame:
    """Offline čas prípravy za (konfigurácia, metóda); ladenie θ doplní tuned_result."""
    rows = {}
    for task, result in zip(tasks, results, strict=True):
        key = (task.label, task.name or task.method)
        rows[key] = max(rows.get(key, 0.0), result.offline_s)
    frame = pd.DataFrame([{"config_id": c, "method": m, "offline_s": s}
                          for (c, m), s in rows.items()])
    for i, row in frame.iterrows():
        if row["method"] == "bidprice_tuned":  # čas CMA-ES behu z results/params (Člen B)
            tuned = tuned_result(row["config_id"].split("_")[0])
            if tuned is not None:
                frame.loc[i, "offline_s"] = tuned.get("time_s", math.nan)
    return frame


def _progress(done: int, total: int, task: Task, start: float) -> None:
    print(f"  [{done}/{total}] {task.experiment} {task.label} {task.name or task.method}"
          f" ({len(task.seeds)} inšt.)  {perf_counter() - start:.0f} s", flush=True)


# --- zostavenie experimentov ----------------------------------------------------------

@dataclass
class Settings:
    """Rozsah behu; `quick` zmenší všetko na rýchly test celého reťazca."""

    jobs: int = 1
    quick: bool = False
    out_dir: Path = RESULTS
    resume: bool = True  # použiť hotové úlohy z out_dir/.cache

    def test_seeds(self, base: dict, limit: int | None = None) -> list[int]:
        seeds = list(seed_range(base, "test"))
        if self.quick:
            return seeds[:4]
        return seeds if limit is None else seeds[:limit]

    def mcts_params(self) -> dict:
        params = load_yaml("mcts.yaml")
        if self.quick:
            params = {k: {**v, "n_iter": 30} for k, v in params.items()}
        return params

    def cache(self) -> TaskCache:
        return TaskCache(self.out_dir / ".cache" if self.resume else None)


def policy_tasks(
    experiment: str, config: Config, methods: Sequence[str], spec: dict, base: dict,
    settings: Settings, label: str, theta_from: str | None = None,
) -> list[Task]:
    """Úlohy pre Oracle a politiky na jednej konfigurácii E1/E2."""
    seeds = settings.test_seeds(base)
    mcts_seeds = settings.test_seeds(base, spec.get("mcts_test_instances"))
    params = settings.mcts_params()
    theta = tuned_theta(theta_from or label)
    tasks = [Task(experiment, config, "oracle", tuple(seeds), label)]
    for method in methods:
        if method == "vi" and config.n_slots > spec.get("vi_max_slots", 4):
            continue
        if method in SLOW and config.n_slots > spec.get("mcts_max_slots", 10**9):
            continue
        if method == "bidprice_tuned" and theta is None:
            print(f"  {label}: chýba results/params/{theta_from or label}_cma_seed*.json "
                  "(úloha 4.4 Člena B, alebo --tune), bidprice_tuned sa vynechá")
            continue
        method_seeds = mcts_seeds if method in SLOW else seeds
        for chunk in split(method, method_seeds):
            tasks.append(Task(experiment, config, method, chunk, label,
                              with_theta(params, method, theta)))
    return tasks


def with_theta(params: dict, method: str, theta: dict | None) -> dict:
    """Pridá θ len metódam, ktoré ho používajú. Ostatným sa tak nezmení odtlačok úlohy
    a po doplnení θ (Člen B) sa z cache nepočítajú znova."""
    if theta is None or method not in USES_THETA:
        return params
    return {**params, "theta": theta}


def bounds_table(configs: Sequence[tuple[str, Config]], base: dict, vi_max_slots: int) -> pd.DataFrame:
    """LP horná hranica (Člen A) a hodnota VI V₀ pre každú konfiguráciu."""
    rows = []
    for label, config in configs:
        demand = _demand(config, base)
        row = {"config_id": label, "n_slots": config.n_slots, "n_steps": config.n_steps,
               "expected_requests": config.expected_requests,
               "lp_bound": lp_upper_bound(config, demand), "vi_value": math.nan}
        if config.n_slots <= vi_max_slots:
            row["vi_value"] = ValueIteration(config, demand).value
        rows.append(row)
    return pd.DataFrame(rows)


def _paired_mean(frame: pd.DataFrame, method: str, name: str) -> pd.DataFrame:
    ref = (frame[frame["method"] == method]
           .set_index(["config_id", "instance_seed"])["revenue"].rename(name))
    return frame.join(ref, on=["config_id", "instance_seed"])


def summarize(rows: list[dict], bounds: pd.DataFrame | None = None) -> pd.DataFrame:
    """Štatistiky tržieb; pomer k Oracle a k flat rate na tých istých inštanciách; LP medzera."""
    frame = _paired_mean(pd.DataFrame(rows), "oracle", "oracle")
    frame = _paired_mean(frame, "flat", "flat_ref")
    table = frame.groupby(["config_id", "method"], as_index=False, sort=False).agg(
        n=("revenue", "size"),
        mean=("revenue", "mean"),
        se=("revenue", "sem"),
        median=("revenue", "median"),
        std=("revenue", "std"),
        min=("revenue", "min"),
        max=("revenue", "max"),
        oracle_mean=("oracle", "mean"),
        flat_mean=("flat_ref", "mean"),
        n_accepted=("n_accepted", "mean"),
        utilization_h=("utilization_h", "mean"),
        n_requests=("n_requests", "mean"),
        runtime_s=("runtime_s", "mean"),
    )
    table["ratio_oracle"] = table["mean"] / table["oracle_mean"]
    table["ratio_flat"] = table["mean"] / table["flat_mean"]
    if bounds is not None:
        table = table.merge(bounds[["config_id", "lp_bound", "vi_value"]], on="config_id",
                            how="left")
        table["ratio_lp"] = table["mean"] / table["lp_bound"]
        table["gap_lp_pct"] = [gap_to_bound(m, b) for m, b in zip(table["mean"],
                                                                     table["lp_bound"])]
        table["ratio_vi"] = table["mean"] / table["vi_value"]
    return table


def _write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _execute(name: str, tasks: list[Task], base: dict, settings: Settings) -> list[dict]:
    print(f"{name}: {len(tasks)} úloh")
    results = run_tasks(tasks, base, settings.jobs, settings.cache())
    rows = _rows(results)
    save_rows(rows, settings.out_dir / f"{name}.csv")
    _write(offline_table(tasks, results), settings.out_dir / f"{name}_offline.csv")
    return rows


def run_policy_experiment(
    name: str, configs: list[tuple[str, Config]], spec: dict, base: dict, settings: Settings,
    theta_from: Callable[[str], str] = lambda label: label,
) -> pd.DataFrame:
    tasks = []
    for label, config in configs:
        tasks += policy_tasks(name, config, spec["methods"], spec, base, settings, label,
                              theta_from(label))
    rows = _execute(name, tasks, base, settings)
    bounds = bounds_table(configs, base, spec.get("vi_max_slots", 0))
    _write(bounds, settings.out_dir / f"{name}_bounds.csv")
    table = summarize(rows, bounds)
    _write(table, settings.out_dir / f"{name}_summary.csv")
    return table


def e1(base: dict, settings: Settings, spec: dict | None = None) -> pd.DataFrame:
    spec = spec or load_yaml("e1.yaml")
    items = spec["configurations"][:3] if settings.quick else spec["configurations"]
    configs = []
    for item in items:
        config = make_config(item["n_slots"], item["n_steps"], item["expected_requests"], base)
        configs.append((config_id(config), config))
    return run_policy_experiment("e1", configs, spec, base, settings)


def e2(base: dict, settings: Settings, spec: dict | None = None) -> pd.DataFrame:
    spec = spec or load_yaml("e2.yaml")
    lambdas = spec["expected_requests"][:2] if settings.quick else spec["expected_requests"]
    n_slots = spec["n_slots"]
    configs = []
    for lam in lambdas:
        config = make_config(n_slots, required_steps(lam), float(lam), base)
        configs.append((f"{n_slots}s_l{lam}", config))
    # θ sa ladí len pri 24 slotoch z E1; pri inom lambda ide o prenos parametrov.
    return run_policy_experiment("e2", configs, spec, base, settings,
                                 theta_from=lambda label: f"{n_slots}s")


def mcts_grid(base: dict, settings: Settings, spec: dict | None = None) -> pd.DataFrame:
    """Úloha 3.8: grid search MCTS a hybridu na inštancii z č. 6.3.1, tréningové seedy."""
    spec = spec or load_yaml("mcts_grid.yaml")
    item = spec["configuration"]
    config = make_config(item["n_slots"], item["n_steps"], item["expected_requests"], base)
    label = f"{config.n_slots}s_grid"
    seeds = list(seed_range(base, "train"))[: 3 if settings.quick else spec["train_instances"]]
    grid = [(m, i, d, c) for m in spec["methods"] for i in spec["n_iter"]
            for d in spec["depth"] for c in spec["c"]]
    if settings.quick:
        grid = [(m, 10, d, 1.0) for m in spec["methods"] for d in spec["depth"][:2]]
    tasks = [Task("mcts_grid", config, "oracle", tuple(seeds), label)]
    tasks += [Task("mcts_grid", config, m, tuple(seeds), label)
              for m in spec.get("reference_methods", [])]
    for method, n_iter, depth, c in grid:
        params = {method: {"n_iter": n_iter, "depth": depth, "c": c}}
        name = f"{method}|{n_iter}|{depth}|{c}"
        for chunk in split(method, seeds):
            tasks.append(Task("mcts_grid", config, method, chunk, label, params, name=name))
    rows = _execute("mcts_grid", tasks, base, settings)
    table = summarize(rows)
    parts = table["method"].str.split("|", expand=True)
    table["algorithm"] = parts[0]  # pri Oracle a referenciách je to názov metódy
    if parts.shape[1] == 4:
        table["n_iter"] = pd.to_numeric(parts[1])
        table["depth"] = pd.to_numeric(parts[2])
        table["c"] = pd.to_numeric(parts[3])
    _write(table, settings.out_dir / "mcts_grid_summary.csv")
    return table


def e4(base: dict, settings: Settings, spec: dict | None = None) -> pd.DataFrame:
    """Robustnosť (úloha 5.5 Člena A, robustness.py) rozšírená o bid-price a MCTS."""
    from mpo_ev.robustness import drop_table

    spec = spec or load_yaml("e4.yaml")
    items = spec["configurations"][:2] if settings.quick else spec["configurations"]
    scenarios = [Scenario(**s) for s in spec["scenarios"]]
    methods = spec.get("methods", ["flat", "bidprice", "mcts", "hybrid_mcts"])
    params = settings.mcts_params()
    tasks = []
    for item in items:
        config = make_config(item["n_slots"], item["n_steps"], item["expected_requests"], base)
        cid = config_id(config)
        theta = tuned_theta(cid)
        for scenario in scenarios:
            label = f"{cid}_{scenario.name}"
            for method in methods:
                if method == "bidprice_tuned" and theta is None:
                    continue
                if method in SLOW and config.n_slots > spec.get("mcts_max_slots", 10**9):
                    continue
                limit = spec.get("mcts_test_instances") if method in SLOW else None
                for chunk in split(method, settings.test_seeds(base, limit)):
                    tasks.append(Task("e4", config, method, chunk, label,
                                      with_theta(params, method, theta), scenario))
    rows = _execute("e4", tasks, base, settings)
    table = drop_table(rows)
    _write(table, settings.out_dir / "e4_summary.csv")
    return table


# Názov experimentu = názov configu v config/ bez prípony (run_experiments.py --config).
EXPERIMENTS = {"mcts_grid": mcts_grid, "e1": e1, "e2": e2, "e4": e4}


def git_revision() -> str:
    """Hash commitu a príznak necommitnutých zmien, alebo 'unknown' mimo gitu."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return commit + ("-dirty" if dirty else "")


def write_meta(settings: Settings, names: Sequence[str], durations: dict[str, float]) -> None:
    import cma
    import matplotlib
    import scipy

    path = settings.out_dir / "run_meta.json"
    meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    meta.update({
        "date": datetime.now().isoformat(timespec="seconds"),
        "git": git_revision(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "versions": {"numpy": np.__version__, "scipy": scipy.__version__,
                     "pandas": pd.__version__, "cma": cma.__version__,
                     "matplotlib": matplotlib.__version__, "pyyaml": yaml.__version__},
        "settings": {k: str(v) for k, v in asdict(settings).items()},
        "mcts": load_yaml("mcts.yaml"),
        "seeds": load_base()["seeds"],
    })
    # trvanie po experimentoch sa zlučuje, aby samostatné behy neprepísali ostatné
    meta["durations_s"] = {**meta.get("durations_s", {}), **durations}
    meta["experiments"] = sorted(meta["durations_s"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def run(names: Sequence[str], settings: Settings, specs: dict[str, dict] | None = None) -> None:
    base = load_base()
    specs = specs or {}
    durations = {}
    for name in names:
        start = perf_counter()
        table = EXPERIMENTS[name](base, settings, specs.get(name))
        durations[name] = round(perf_counter() - start, 1)
        with pd.option_context("display.width", 200, "display.max_columns", 30):
            print(table.round(3).to_string(index=False))
        print(f"{name} hotové za {durations[name]:.0f} s\n")
    write_meta(settings, names, durations)
    from mpo_ev.analysis import analyze

    print(f"tabuľky a grafy: {analyze(settings.out_dir)}")
