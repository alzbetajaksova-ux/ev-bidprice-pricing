"""Vyhodnotenie politík: riadky CSV, scenáre chybného modelu (E4) a pokles tržieb."""
from __future__ import annotations

import csv
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from mpo_ev.instances import quantile_price_grid
from mpo_ev.interfaces import Config, DemandModel, EpisodeResult, Instance, Policy
from mpo_ev.simulator import run_episode

COLUMNS = [
    "experiment", "config_id", "method", "instance_seed", "run_seed",
    "revenue", "utilization_h", "n_requests", "n_accepted", "runtime_s",
]


def result_row(
    experiment: str, config_id: str, method: str, instance_seed: int, run_seed: int,
    result: EpisodeResult,
) -> dict:
    """Jeden riadok výsledkov v dohodnutom formáte CSV."""
    return {
        "experiment": experiment,
        "config_id": config_id,
        "method": method,
        "instance_seed": instance_seed,
        "run_seed": run_seed,
        "revenue": result.revenue,
        "utilization_h": result.utilization_h,
        "n_requests": result.n_requests,
        "n_accepted": result.n_accepted,
        "runtime_s": result.runtime_s,
    }


def evaluate_policy(
    policy: Policy,
    instances: Sequence[Instance],
    demand: DemandModel,
    base: dict,
    experiment: str,
    config_id: str,
) -> list[dict]:
    """Odsimuluje politiku na inštanciách; náhodnosť politiky = seed inštancie + offset."""
    rows = []
    for instance in instances:
        run_seed = instance.seed + base["seeds"]["mcts_offset"]
        result = run_episode(policy, instance, demand, seed=run_seed)
        rows.append(result_row(experiment, config_id, policy.name, instance.seed, run_seed,
                               result))
    return rows


def save_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


# --- E4: politika verí chybnému modelu, simulácia beží so správnym ----------------------

@dataclass(frozen=True)
class Scenario:
    name: str
    lambda_factor: float = 1.0
    budget_mean: float | None = None  # priemer rozpočtu, s ktorým počíta politika
    grid_step: float | None = None    # krok kvantilov, mení mriežku aj v simulácii


def true_config(config: Config, scenario: Scenario) -> Config:
    """Skutočnosť v scenári; od nominálnej sa líši len mriežkou."""
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
