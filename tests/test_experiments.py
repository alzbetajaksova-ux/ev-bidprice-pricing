# Vytvorené s pomocou Claude, upravil: Člen C
import json

import pandas as pd
import pytest

from mpo_ev.analysis import holm, paired_comparison
from mpo_ev.experiments import (
    CHUNK,
    REGISTRY,
    Task,
    TaskCache,
    bounds_table,
    build_policy,
    run_task,
    run_tasks,
    split,
    summarize,
    tuned_theta,
)
from mpo_ev.instances import load_base, make_config
from mpo_ev.robustness import COLUMNS, Scenario

BASE = load_base()
SMALL_BASE = {
    **BASE,
    "demand": {"mc_samples": 20_000, "mc_seed": 1},
    "seeds": {**BASE["seeds"], "train": [0, 9], "test": [1000, 1009]},
}
MCTS = {"mcts": {"n_iter": 20, "depth": 2, "c": 1.0},
        "hybrid_mcts": {"n_iter": 20, "depth": 2, "c": 1.0}}


@pytest.fixture(scope="module")
def config():
    return make_config(3, 72, 13.94, BASE)


def test_split_chunks_only_slow_methods():
    seeds = list(range(12))
    assert split("flat", seeds) == [tuple(seeds)]
    chunks = split("mcts", seeds)
    assert [s for c in chunks for s in c] == seeds
    assert max(len(c) for c in chunks) == CHUNK


@pytest.mark.parametrize("method", ["flat", "vi", "bidprice", "mcts", "hybrid_mcts", "oracle"])
def test_run_task_rows_have_agreed_columns(config, method):
    task = Task("e1", config, method, (1000, 1001), "3s", MCTS)
    rows = run_task(task, SMALL_BASE).rows
    assert len(rows) == 2
    assert all(list(row) == COLUMNS for row in rows)
    assert {row["method"] for row in rows} == {method}
    assert [row["run_seed"] for row in rows] == [51000, 51001]


def test_chunked_parallel_equals_sequential(config):
    # Výsledok nesmie závisieť od delenia na skupiny ani od počtu procesov.
    seeds = tuple(range(1000, 1004))
    whole = run_task(Task("e1", config, "mcts", seeds, "3s", MCTS), SMALL_BASE).rows
    tasks = [Task("e1", config, "mcts", c, "3s", MCTS) for c in split("mcts", seeds)]
    def strip(rows):  # čas behu sa medzi behmi líši
        return [{k: v for k, v in row.items() if k != "runtime_s"} for row in rows]

    parallel = [row for r in run_tasks(tasks, SMALL_BASE, jobs=2) for row in r.rows]
    assert strip(parallel) == strip(whole)


def test_scenario_changes_only_policy_belief(config):
    nominal = run_task(Task("e4", config, "oracle", (1000,), "x"), SMALL_BASE).rows
    wrong = run_task(Task("e4", config, "oracle", (1000,), "x",
                          scenario=Scenario("lambda_0.7", lambda_factor=0.7)), SMALL_BASE).rows
    assert nominal[0]["revenue"] == wrong[0]["revenue"]  # rovnaké skutočné inštancie


def test_summarize_pairs_oracle_on_same_instances():
    def row(method, seed, revenue):
        return {"config_id": "4s", "method": method, "instance_seed": seed, "revenue": revenue,
                "n_accepted": 1, "utilization_h": 1.0, "n_requests": 2, "runtime_s": 0.0}

    rows = [row("oracle", 1, 10.0), row("oracle", 2, 30.0), row("flat", 1, 4.0),
            row("flat", 2, 40.0), row("mcts", 1, 5.0)]  # MCTS len na prvej inštancii
    bounds = pd.DataFrame([{"config_id": "4s", "lp_bound": 20.0, "vi_value": 8.0}])
    table = summarize(rows, bounds).set_index("method")
    assert table.loc["mcts", "ratio_oracle"] == pytest.approx(0.5)
    assert table.loc["oracle", "ratio_oracle"] == pytest.approx(1.0)
    assert table.loc["mcts", "gap_lp_pct"] == pytest.approx(75.0)
    assert table.loc["mcts", "ratio_vi"] == pytest.approx(5 / 8)
    assert table.loc["mcts", "ratio_flat"] == pytest.approx(5 / 4)  # len párová inštancia
    assert table.loc["mcts", "ratio_lp"] == pytest.approx(5 / 20)


def test_tuned_theta_picks_best_run(tmp_path):
    for seed, value in [(0, 30.0), (1, 35.0), (2, 31.0)]:
        data = {"best_value": value, "best_theta": {"alpha_am": seed}}
        (tmp_path / f"4s_cma_seed{seed}.json").write_text(json.dumps(data))
    (tmp_path / "4s_random_seed0.json").write_text(json.dumps(
        {"best_value": 99.0, "best_theta": {"alpha_am": 9}}))
    assert tuned_theta("4s", tmp_path) == {"alpha_am": 1}
    assert tuned_theta("8s", tmp_path) is None


def test_build_policy_unknown_method(config):
    with pytest.raises(ValueError):
        build_policy("nope", config, None, SMALL_BASE, {})


def test_bounds_table_vi_only_for_small(config):
    big = make_config(8, 192, 36.67, BASE)
    table = bounds_table([("3s", config), ("8s", big)], SMALL_BASE, vi_max_slots=4)
    small, large = table.iloc[0], table.iloc[1]
    assert small["vi_value"] <= small["lp_bound"]
    assert pd.isna(large["vi_value"])


def test_registry_covers_methods():
    assert set(REGISTRY) == {"flat", "vi", "bidprice", "bidprice_tuned", "mcts", "hybrid_mcts"}


def test_vi_table_is_offline(config):
    # Tabuľka VI sa počíta pred dňom; online čas epizódy je potom malý.
    result = run_task(Task("e1", config, "vi", (1000, 1001), "3s"), SMALL_BASE)
    assert result.offline_s > 0
    assert max(row["runtime_s"] for row in result.rows) < result.offline_s


def test_cache_skips_finished_tasks(config, tmp_path, monkeypatch):
    task = Task("e1", config, "bidprice", (1000,), "3s")
    cache = TaskCache(tmp_path)
    first = run_tasks([task], SMALL_BASE, jobs=1, cache=cache)
    assert cache.get(task) is not None

    def boom(*args, **kwargs):
        raise AssertionError("hotová úloha sa nemá počítať znova")

    monkeypatch.setattr("mpo_ev.experiments.run_task", boom)
    again = run_tasks([task], SMALL_BASE, jobs=1, cache=cache)
    assert again[0].rows == first[0].rows
    changed = Task("e1", config, "bidprice", (1001,), "3s")
    assert changed.key() != task.key()


def test_holm_correction():
    p = pd.Series([0.01, 0.04, 0.03, float("nan")])
    adjusted = holm(p)
    assert adjusted.iloc[0] == pytest.approx(0.03)   # 3 · 0,01
    assert adjusted.iloc[2] == pytest.approx(0.06)   # 2 · 0,03
    assert adjusted.iloc[1] == pytest.approx(0.06)   # max(1 · 0,04; 0,06), monotónne
    assert pd.isna(adjusted.iloc[3])


def test_paired_comparison_families():
    rows = pd.DataFrame([
        {"config_id": "4s", "method": m, "instance_seed": s, "revenue": v}
        for s in range(10)
        for m, v in [("mcts", 10.0 + s), ("bidprice", 11.0 + s * 1.1), ("flat", 9.0 + s)]
    ])
    table = paired_comparison(rows, [("bidprice", "mcts"), ("bidprice", "flat")])
    assert list(table["family"]) == ["vs. MCTS", "ostatné"]
    assert (table["p_holm"] >= table["p_wilcoxon"]).all()
    assert (table["wins_A"] == 10).all()


def test_theta_only_for_methods_that_use_it():
    from mpo_ev.experiments import with_theta

    params = {"mcts": {"n_iter": 5}}
    theta = {"alpha_am": 1.0, "alpha_pm": 1.0, "gamma": 1.0, "resolves_per_day": 0.0}
    assert with_theta(params, "mcts", theta) is params      # odtlačok MCTS sa nezmení
    assert with_theta(params, "flat", theta) is params
    assert with_theta(params, "hybrid_mcts", theta)["theta"] == theta
    assert with_theta(params, "bidprice_tuned", theta)["theta"] == theta
    assert with_theta(params, "hybrid_mcts", None) is params
