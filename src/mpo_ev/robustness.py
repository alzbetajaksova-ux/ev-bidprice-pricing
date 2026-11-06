"""Experiment E4: citlivosť politík na nesprávny model dopytu a na mriežku cien.

Spustenie pre flat rate: python -m mpo_ev.robustness
Politiky B a C sa pripoja cez `evaluate_scenario` vlastným `PolicyFactory`.
"""
from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd
import yaml

from mpo_ev.demand import demand_from_base
from mpo_ev.instances import (
    generate_instances,
    load_base,
    make_config,
    quantile_price_grid,
    seed_range,
)
from mpo_ev.interfaces import Config, DemandModel, Instance, Policy
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.simulator import run_episode

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = [
    "experiment", "config_id", "method", "instance_seed", "run_seed",
    "revenue", "utilization_h", "n_requests", "n_accepted", "runtime_s",
]

# Dostane nesprávny config a model, vráti politiku pripravenú na simuláciu.
PolicyFactory = Callable[[Config, DemandModel], Policy]


@dataclass(frozen=True)
class Scenario:
    name: str
    lambda_factor: float = 1.0
    budget_mean: float | None = None  # priemer rozpočtu, s ktorým počíta politika
    grid_step: float | None = None    # krok kvantilov, mení mriežku aj v simulácii


def true_config(config: Config, scenario: Scenario) -> Config:
    """Skutočnosť v scenári; odlišuje sa od nominálnej len mriežkou."""
    if scenario.grid_step is None:
        return config
    step = scenario.grid_step
    grid = quantile_price_grid(step, 1 - step, step, config.budget_mean, config.budget_std)
    return replace(config, price_grid=grid)


def believed_config(config: Config, scenario: Scenario) -> Config:
    """Čo si o dopyte myslí politika. Mriežka zostáva, lebo ponúka ceny v simulácii."""
    budget_mean = config.budget_mean if scenario.budget_mean is None else scenario.budget_mean
    return replace(
        config,
        expected_requests=config.expected_requests * scenario.lambda_factor,
        budget_mean=budget_mean,
    )


def evaluate_policy(
    policy: Policy,
    instances: Sequence[Instance],
    demand: DemandModel,
    base: dict,
    experiment: str,
    config_id: str,
) -> list[dict]:
    """Vyhodnotí politiku na inštanciách a vráti riadky v dohodnutom formáte CSV."""
    rows = []
    for instance in instances:
        run_seed = instance.seed + base["seeds"]["mcts_offset"]
        result = run_episode(policy, instance, demand, seed=run_seed)
        rows.append(
            {
                "experiment": experiment,
                "config_id": config_id,
                "method": policy.name,
                "instance_seed": instance.seed,
                "run_seed": run_seed,
                "revenue": result.revenue,
                "utilization_h": result.utilization_h,
                "n_requests": result.n_requests,
                "n_accepted": result.n_accepted,
                "runtime_s": result.runtime_s,
            }
        )
    return rows


def evaluate_scenario(
    factory: PolicyFactory, config: Config, scenario: Scenario, base: dict, config_id: str
) -> list[dict]:
    truth = true_config(config, scenario)
    believed = believed_config(truth, scenario)
    demand = demand_from_base(believed, base)
    instances = generate_instances(truth, seed_range(base, "test"))
    policy = factory(believed, demand)
    return evaluate_policy(policy, instances, demand, base, "e4", f"{config_id}_{scenario.name}")


def flat_factory(base: dict) -> PolicyFactory:
    """Flat rate sa učí na tréningových dátach z toho, čomu verí: nesprávny config."""

    def build(believed: Config, demand: DemandModel) -> FlatRatePolicy:
        policy = FlatRatePolicy()
        policy.fit(generate_instances(believed, seed_range(base, "train")), demand)
        return policy

    return build


def drop_table(rows: list[dict]) -> pd.DataFrame:
    """Pokles priemerných tržieb v % oproti scenáru nominal; záporný pokles je zlepšenie.

    Scenáre majú rovnaké inštancie, takže `se_pct` je štandardná chyba párových rozdielov.
    """
    frame = pd.DataFrame(rows)
    split = frame["config_id"].str.split("_", n=1, expand=True)
    frame["configuration"], frame["scenario"] = split[0], split[1]
    keys = ["configuration", "method", "instance_seed"]
    nominal = frame[frame["scenario"] == "nominal"].set_index(keys)["revenue"].rename("nominal")
    paired = frame.join(nominal, on=keys)
    paired["loss"] = paired["nominal"] - paired["revenue"]
    table = paired.groupby(["configuration", "method", "scenario"], as_index=False).agg(
        revenue=("revenue", "mean"),
        nominal=("nominal", "mean"),
        loss=("loss", "mean"),
        loss_se=("loss", "sem"),
    )
    table["drop_pct"] = 100 * table["loss"] / table["nominal"]
    table["se_pct"] = 100 * table["loss_se"] / table["nominal"]
    return table[["configuration", "method", "scenario", "revenue", "drop_pct", "se_pct"]]


def save_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    base = load_base()
    with open(ROOT / "config" / "e4.yaml", encoding="utf-8") as file:
        experiment = yaml.safe_load(file)
    rows = []
    for item in experiment["configurations"]:
        config = make_config(item["n_slots"], item["n_steps"], item["expected_requests"], base)
        for settings in experiment["scenarios"]:
            scenario = Scenario(**settings)
            rows += evaluate_scenario(
                flat_factory(base), config, scenario, base, f"{item['n_slots']}s"
            )
    save_rows(rows, ROOT / "results" / "e4_flat.csv")
    table = drop_table(rows)
    table.to_csv(ROOT / "results" / "e4_flat_summary.csv", index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
