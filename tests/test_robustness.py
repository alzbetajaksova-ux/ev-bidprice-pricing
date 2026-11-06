from dataclasses import replace

import pytest

from mpo_ev.instances import generate_instance, load_base, make_config
from mpo_ev.robustness import (
    COLUMNS,
    Scenario,
    believed_config,
    drop_table,
    evaluate_scenario,
    flat_factory,
    true_config,
)

BASE = load_base()
SMALL_BASE = {
    **BASE,
    "demand": {"mc_samples": 20_000, "mc_seed": 1},
    "seeds": {**BASE["seeds"], "train": [0, 19], "test": [1000, 1019]},
}


@pytest.fixture
def config():
    return make_config(4, 96, 18.98, BASE)


def test_wrong_lambda_changes_only_belief(config):
    scenario = Scenario("lambda_0.7", lambda_factor=0.7)
    assert true_config(config, scenario) == config
    believed = believed_config(config, scenario)
    assert believed.expected_requests == pytest.approx(0.7 * 18.98)
    assert believed.budget_mean == config.budget_mean


def test_wrong_budget_keeps_price_grid(config):
    believed = believed_config(config, Scenario("budget_0.8", budget_mean=0.8))
    assert believed.budget_mean == 0.8
    assert believed.price_grid == config.price_grid


@pytest.mark.parametrize("step,size", [(0.1, 9), (0.025, 39)])
def test_grid_scenario_changes_truth(config, step, size):
    assert len(true_config(config, Scenario("grid", grid_step=step)).price_grid) == size


def test_grid_scenario_keeps_same_customers(config):
    # Spoločné náhodné čísla: mriežka nesmie zmeniť požiadavky ani rozpočty.
    other = true_config(config, Scenario("grid", grid_step=0.1))
    assert generate_instance(config, 7).requests == generate_instance(other, 7).requests


def test_evaluate_scenario_writes_agreed_columns(config):
    scenario = Scenario("nominal")
    rows = evaluate_scenario(flat_factory(SMALL_BASE), config, scenario, SMALL_BASE, "4s")
    assert len(rows) == 20
    assert list(rows[0]) == COLUMNS
    assert rows[0]["config_id"] == "4s_nominal"
    assert (rows[0]["instance_seed"], rows[0]["run_seed"]) == (1000, 51_000)


def test_wrong_model_does_not_change_real_customers(config):
    # E4: nesprávny je len model politiky, inštancie zostávajú skutočné.
    def requests(scenario):
        rows = evaluate_scenario(flat_factory(SMALL_BASE), config, scenario, SMALL_BASE, "4s")
        return [r["n_requests"] for r in rows]

    assert requests(Scenario("lambda_0.7", lambda_factor=0.7)) == requests(Scenario("nominal"))


def test_flat_learns_from_believed_data(config):
    # Flat sa učí na tom, čomu verí: keď verí vyššiemu rozpočtu, zvolí vyššiu sadzbu.
    high = evaluate_scenario(
        flat_factory(SMALL_BASE), config, Scenario("budget_1.2", budget_mean=1.2), SMALL_BASE, "4s"
    )
    low = evaluate_scenario(
        flat_factory(SMALL_BASE), config, Scenario("budget_0.8", budget_mean=0.8), SMALL_BASE, "4s"
    )
    assert sum(r["n_accepted"] for r in high) < sum(r["n_accepted"] for r in low)


def test_drop_table_is_relative_to_nominal():
    def row(config_id, seed, revenue):
        return {"config_id": config_id, "method": "flat", "instance_seed": seed, "revenue": revenue}

    rows = [
        row("4s_nominal", 1, 100.0), row("4s_nominal", 2, 100.0),
        row("4s_lambda_0.7", 1, 80.0), row("4s_lambda_0.7", 2, 100.0),
        row("4s_grid_0.10", 1, 110.0), row("4s_grid_0.10", 2, 110.0),
    ]
    table = drop_table(rows).set_index("scenario")
    assert table.loc["nominal", "drop_pct"] == 0.0
    assert table.loc["lambda_0.7", "drop_pct"] == pytest.approx(10.0)
    assert table.loc["lambda_0.7", "se_pct"] == pytest.approx(10.0)  # párové rozdiely 20 a 0
    assert table.loc["grid_0.10", "drop_pct"] == pytest.approx(-10.0)
    assert table.loc["grid_0.10", "se_pct"] == 0.0


def test_scenarios_do_not_change_capacity(config):
    believed = believed_config(replace(config, capacity=2), Scenario("x", lambda_factor=1.3))
    assert believed.capacity == 2
