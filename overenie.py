"""Overenie stability výsledkov (Príloha B reportu).

1. MCTS s ďalšími seedmi (seed dňa + 50 000 + 100 000·k) pri 4, 8 a 24 slotoch.
2. Bid-price s θ zo všetkých 5 behov CMA-ES na 100 testovacích dňoch.
3. MCTS s 200 a 400 iteráciami pri 24 slotoch (porovnateľný online čas ako bid-price).

Spustenie z koreňa repozitára: python overenie/overenie.py  (asi 15 min na 2 jadrách)
Výstup: overenie/vysledky.csv (riadok = beh × testovací deň).
Vytvorené s pomocou Claude.
"""
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mpo_ev.demand import demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config, seed_range
from mpo_ev.policies.mcts import MCTSPolicy
from mpo_ev.simulator import run_episode
from mpo_ev.tuning import make_policy

E1 = {4: (96, 18.98), 8: (192, 36.67), 12: (288, 49.95), 24: (576, 76.28)}
PAR = ROOT / "results" / "params"
OUT = Path(__file__).resolve().parent


def job(args):
    kind, slots, label, extra, n_days, run_seed_k = args
    base = load_base()
    k, lam = E1[slots]
    cfg = make_config(slots, k, lam, base)
    dem = demand_from_base(cfg, base)
    insts = generate_instances(cfg, seed_range(base, "test"))[:n_days]
    rows = []
    for inst in insts:
        if kind == "mcts":
            pol = MCTSPolicy(n_iter=extra, depth=8, c=10.0)
            seed = inst.seed + 50_000 + 100_000 * run_seed_k
        else:
            pol = make_policy(extra, k)
            seed = None
        r = run_episode(pol, inst, dem, seed=seed)
        rows.append({"kind": kind, "slots": slots, "label": label, "instance_seed": inst.seed,
                         "revenue": r.revenue, "runtime_s": r.runtime_s})
    return rows


def main():
    jobs = []
    for s in (4, 8, 12, 24):  # všetkých 5 θ z CMA-ES na 100 testovacích dňoch
        for p in sorted(PAR.glob(f"{s}s_cma_seed*.json")):
            d = json.loads(p.read_text())
            jobs.append(("tuned", s, f"cma_run{d['run_seed']}", d["best_theta"], 100, 0))
    jobs.append(("mcts", 24, "mcts_200it", 200, 100, 0))  # ~ rovnaký online čas ako tuned
    jobs.append(("mcts", 24, "mcts_400it", 400, 100, 0))
    jobs.append(("mcts", 4, "seed0", 3000, 100, 0))
    for k in (1, 2, 3, 4):
        jobs.append(("mcts", 4, f"seed{k}", 3000, 100, k))
    for k in (1, 2):
        jobs.append(("mcts", 8, f"seed{k}", 3000, 100, k))
        jobs.append(("mcts", 24, f"seed{k}", 3000, 30, k))
    t = time.time()
    frames = []
    with ProcessPoolExecutor() as ex:
        for rows in ex.map(job, jobs):
            df = pd.DataFrame(rows)
            frames.append(df)
            print(rows[0]["kind"], rows[0]["slots"], rows[0]["label"],
                  round(df.revenue.mean(), 3), round(df.runtime_s.mean(), 3),
                  round(time.time() - t), flush=True)
    pd.concat(frames).to_csv(OUT / "vysledky.csv", index=False)


if __name__ == "__main__":
    main()
