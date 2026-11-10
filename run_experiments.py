# Vytvorené s pomocou Claude, upravil: Martin Nový (Člen C)
"""Jeden príkaz na všetky experimenty (úloha 5.1).

    python run_experiments.py                          # grid MCTS, E1, E2, E4 + tabuľky a grafy
    python run_experiments.py --config config/e1.yaml  # jeden experiment podľa configu
    python run_experiments.py e1 e2 --jobs 8           # vybrané experimenty, 8 procesov
    python run_experiments.py --quick                  # rýchly test reťazca, do results/quick/
    python run_experiments.py --tune e1                # najprv ladenie θ cez CMA-ES (Člen B, E3)
    python run_experiments.py --fresh e1               # ignorovať hotové úlohy v results/.cache

Experimenty: mcts_grid (3.8), e1 (5.2), e2 (5.3), e4 (5.5). Parametre sú v config/
(base.yaml, mcts_grid.yaml, e1.yaml, e2.yaml, e4.yaml, mcts.yaml, tuning.yaml).
Prerušený beh pokračuje od posledných hotových úloh.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    # Výpis s diakritikou aj pri presmerovaní do súboru vo Windows (cp1252).
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    from mpo_ev.experiments import EXPERIMENTS, RESULTS, Settings, load_yaml, run

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiments", nargs="*", metavar="{" + ",".join(EXPERIMENTS) + "}",
                        help="predvolene všetky")
    parser.add_argument("--config", type=Path, action="append", default=[],
                        help="YAML experimentu; názov súboru určuje experiment (opakovateľné)")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--quick", action="store_true",
                        help="malý rozsah na kontrolu, výsledky do results/quick/")
    parser.add_argument("--fresh", action="store_true",
                        help="nepoužiť hotové úlohy z results/.cache")
    parser.add_argument("--tune", action="store_true",
                        help="pred experimentmi naladiť θ bid-price cez CMA-ES (dlhé)")
    args = parser.parse_args()

    names = list(args.experiments)
    specs = {}
    for path in args.config:
        name = path.stem
        if name not in EXPERIMENTS:
            parser.error(f"{path}: neznámy experiment {name} (možnosti: {', '.join(EXPERIMENTS)})")
        with open(path, encoding="utf-8") as file:
            specs[name] = yaml.safe_load(file)
        names.append(name)
    unknown = set(names) - set(EXPERIMENTS)
    if unknown:
        parser.error(f"neznámy experiment: {', '.join(sorted(unknown))}")
    names = list(dict.fromkeys(names)) or list(EXPERIMENTS)

    out_dir = RESULTS / "quick" if args.quick else RESULTS
    if args.tune:
        from mpo_ev.tuning import main as tune

        spec = load_yaml("tuning.yaml")
        for slots in spec["slots"]:
            tune(["--slots", str(slots), "--runs", str(spec["runs"]),
                  "--budget", str(spec["budget"]), "--n-train", str(spec["n_train"]),
                  "--jobs", str(args.jobs)])
    settings = Settings(jobs=args.jobs, quick=args.quick, out_dir=out_dir,
                        resume=not args.fresh)
    run(names, settings, specs)


if __name__ == "__main__":
    main()
