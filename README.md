# Dynamické oceňovanie rezervácií nabíjania EV

Projekt k predmetu Moderné prístupy v optimalizácii (MPO), TUKE, Zadanie 1, Variant B. Navrhujeme bid-price politiku z lineárneho programu, ladenú cez CMA-ES, a porovnávame ju s metódou z článku Mrkos a kol., *Online Dynamic Pricing for Electric Vehicle Charging Stations with Reservations*.

## Príprava prostredia

Potrebný je Python 3.11. Príkazy sú pre PowerShell vo Windows.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Bez `py` launchera stačí ľubovoľný Python 3.11, napríklad `uv venv --python 3.11 .venv` a `uv pip install -r requirements.txt`.

## Spustenie

```powershell
pytest
ruff check .
```

Testy trvajú asi 1 minútu.

Flat rate:

```powershell
$env:PYTHONPATH = "src"
python -m mpo_ev.flat_baseline   # konfigurácie E1, asi 6 s
python -m mpo_ev.robustness      # E4, asi 25 s
```

Všetky experimenty jedným príkazom (z koreňa repozitára, `PYTHONPATH` netreba):

```powershell
python run_experiments.py --quick                   # kontrola celého reťazca, asi 30 s, do results/quick/
python run_experiments.py                           # grid search MCTS, E1, E2, E4 + tabuľky a grafy
python run_experiments.py --config config/e1.yaml   # jeden experiment podľa configu
python run_experiments.py e1 e2 --jobs 8            # vybrané experimenty, počet procesov
python run_experiments.py --tune e1                 # najprv ladenie θ cez CMA-ES (E3 Člena B), veľmi dlhé
python run_experiments.py --fresh e1                # prepočítať aj hotové úlohy
```

Experimenty: `mcts_grid` (úloha 3.8, `config/mcts_grid.yaml`), `e1` (dĺžka slotu), `e2` (hustota dopytu), `e4` (robustnosť). E3 (prínos ladenia) je `python -m mpo_ev.tuning` Člena B. Predvolený počet procesov je počet jadier − 1. Očakávaný čas na 12 jadrách (11 procesov): grid search asi 30 min, E1 asi 15 min, E2 asi 41 min, E4 asi 25 min (spolu asi 2 h); skutočné časy sú v `results/run_meta.json`. Výsledok nezávisí od počtu procesov. Hotové úlohy sa ukladajú do `results/.cache/`, prerušený beh preto po opätovnom spustení pokračuje.

Výstupy: `results/<exp>.csv` (riadok = metóda × inštancia), `results/<exp>_summary.csv` (štatistiky, pomery k Oracle, LP hranici a flat rate), `results/<exp>_bounds.csv` (LP hranica, hodnota VI), `results/<exp>_offline.csv` (offline čas prípravy), `results/run_meta.json` (verzie knižníc, git hash, seedy, parametre MCTS), `results/pilot_4s_vi.csv` (VI pre pilot), `results/tables.md` a `results/figures/*.png`. Tabuľky a grafy vytvorí znova z CSV `python -m mpo_ev.analysis` (s `PYTHONPATH=src`) alebo notebook `analysis.ipynb` (potrebuje navyše `pip install notebook`).

`bidprice_tuned` sa vyhodnotí, len ak existujú naladené parametre `results/params/<config>_cma_seed*.json` (úloha 4.4, `python -m mpo_ev.tuning` alebo `--tune`), inak ho runner vynechá s upozornením.

## Použitie

```python
from mpo_ev.demand import demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config, seed_range
from mpo_ev.policies.flat import FlatRatePolicy
from mpo_ev.simulator import run_episode

base = load_base()
config = make_config(n_slots=4, n_steps=96, expected_requests=18.98, base=base)
demand = demand_from_base(config, base)

policy = FlatRatePolicy()
policy.fit(generate_instances(config, seed_range(base, "train")), demand)
results = [run_episode(policy, i, demand) for i in generate_instances(config, seed_range(base, "test"))]
```

Inštancie sa neukladajú na disk, rovnaká konfigurácia a seed dajú vždy rovnakú inštanciu.

## Štruktúra

| Cesta | Obsah |
| --- | --- |
| `config/` | `base.yaml` (model, mriežka, seedy), `e1.yaml`, `e2.yaml`, `e4.yaml`, `mcts_grid.yaml` (experimenty), `mcts.yaml`, `tuning.yaml` |
| `src/mpo_ev/interfaces.py` | spoločné dátové triedy a protokoly |
| `src/mpo_ev/instances.py` | mriežka cien, diskretizácia, generátor inštancií |
| `src/mpo_ev/demand.py` | model dopytu pre politiky |
| `src/mpo_ev/simulator.py` | simulácia jednej epizódy |
| `src/mpo_ev/bounds.py` | LP horná hranica, vyžaduje `lp.py` |
| `src/mpo_ev/robustness.py` | experiment E4 |
| `src/mpo_ev/flat_baseline.py` | flat rate na konfiguráciách E1 |
| `src/mpo_ev/lp.py`, `tuning.py` | LP a duálne ceny, ladenie θ cez CMA-ES |
| `src/mpo_ev/experiments.py` | runner experimentov (register metód, paralelne, pokračovanie po páde); `run_experiments.py` ho spúšťa |
| `src/mpo_ev/analysis.py`, `analysis.ipynb` | štatistiky (Wilcoxon s Holmovou korekciou), tabuľky a grafy z `results/` |
| `src/mpo_ev/policies/` | flat, bid-price, Oracle, VI, MCTS, hybrid MCTS |
| `requirements.txt` | závislosti s presnými verziami |
| `tests/` | automatické testy |
| `results/` | výsledky experimentov |
| `report/` | podklady pre report |
| `team/` | doplnky k návodom pre členov tímu |

## Použitie AI a knižníc

Pri návrhu, kóde, testoch a podkladoch reportu sme použili nástroj Claude (Anthropic) \[doplniť rozsah za každého člena\]. Člen C: s pomocou Claude vznikli VI, MCTS, hybrid MCTS, runner experimentov, analýza, testy k nim a koncepty sekcií 7–9 a zoznamu nejasností. Výstupy sme kontrolovali a upravovali. Knižnice: NumPy, SciPy (LP a MILP cez HiGHS), cma, PyYAML, pandas, Matplotlib, pytest, ruff.
