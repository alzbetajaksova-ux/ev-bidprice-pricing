"""Flat rate na konfiguráciách E1. Spustenie: python -m mpo_ev.flat_baseline"""
from __future__ import annotations

import pandas as pd
import yaml

from mpo_ev.demand import demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config, seed_range
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.robustness import ROOT, evaluate_policy, save_rows


def summary_table(rows: list[dict]) -> pd.DataFrame:
    """Súhrnné štatistiky tržieb a priemery ostatných metrík za konfiguráciu a metódu."""
    frame = pd.DataFrame(rows)
    return frame.groupby(["config_id", "method"], as_index=False, sort=False).agg(
        mean=("revenue", "mean"),
        median=("revenue", "median"),
        std=("revenue", "std"),
        min=("revenue", "min"),
        max=("revenue", "max"),
        n_accepted=("n_accepted", "mean"),
        utilization_h=("utilization_h", "mean"),
        n_requests=("n_requests", "mean"),
        runtime_s=("runtime_s", "mean"),
    )


def main() -> None:
    base = load_base()
    with open(ROOT / "config" / "e1.yaml", encoding="utf-8") as file:
        experiment = yaml.safe_load(file)
    rows = []
    for item in experiment["configurations"]:
        config = make_config(item["n_slots"], item["n_steps"], item["expected_requests"], base)
        demand = demand_from_base(config, base)
        policy = FlatRatePolicy()
        policy.fit(generate_instances(config, seed_range(base, "train")), demand)
        instances = generate_instances(config, seed_range(base, "test"))
        rows += evaluate_policy(policy, instances, demand, base, "e1", f"{item['n_slots']}s")
    save_rows(rows, ROOT / "results" / "e1_flat.csv")
    table = summary_table(rows)
    table.to_csv(ROOT / "results" / "e1_flat_summary.csv", index=False)
    print(table.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
