# Dynamické oceňovanie rezervácií nabíjania EV

Projekt k predmetu Moderné prístupy v optimalizácii (MPO), TUKE, Zadanie 1, Variant B. Navrhujeme bid-price politiku z lineárneho programu, ladenú cez CMA-ES, a porovnávame ju s metódou z článku Mrkos a kol., *Online Dynamic Pricing for Electric Vehicle Charging Stations with Reservations*.

## Príprava prostredia

Potrebný je Python 3.11. Príkazy sú pre PowerShell vo Windows.

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install numpy==2.4.6 scipy==1.17.1 cma==4.5.0 PyYAML==6.0.3 pandas==3.1.1 matplotlib==3.11.2 pytest==9.2.0 ruff==0.17.4
```

Po doplnení `requirements.txt` (úloha 1.3) sa posledný riadok nahradí príkazom `pip install -r requirements.txt`.

## Spustenie

```powershell
pytest
ruff check .
```

Testy trvajú do 1 minúty.

Flat rate:

```powershell
$env:PYTHONPATH = "src"
python -m mpo_ev.flat_baseline   # konfigurácie E1, asi 6 s
python -m mpo_ev.robustness      # E4, asi 25 s
```

Experimenty: \[doplniť príkaz a očakávaný čas behu po dokončení `run_experiments.py`\].

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
| `config/` | `base.yaml` s parametrami modelu, mriežkou a seedmi, konfigurácie experimentov |
| `src/mpo_ev/interfaces.py` | spoločné dátové triedy a protokoly |
| `src/mpo_ev/instances.py` | mriežka cien, diskretizácia, generátor inštancií |
| `src/mpo_ev/demand.py` | model dopytu pre politiky |
| `src/mpo_ev/simulator.py` | simulácia jednej epizódy |
| `src/mpo_ev/bounds.py` | LP horná hranica, vyžaduje `lp.py` |
| `src/mpo_ev/robustness.py` | experiment E4 |
| `src/mpo_ev/flat_baseline.py` | flat rate na konfiguráciách E1 |
| `src/mpo_ev/policies/` | cenové politiky |
| `tests/` | automatické testy |
| `results/` | výsledky experimentov |
| `report/` | podklady pre report |
| `team/` | doplnky k návodom pre členov tímu |

## Použitie AI a knižníc

Pri návrhu, kóde, testoch a podkladoch reportu sme použili nástroj Claude (Anthropic) \[doplniť rozsah za každého člena\]. Výstupy sme kontrolovali a upravovali. Knižnice: NumPy, SciPy (LP a MILP cez HiGHS), cma, PyYAML, pandas, Matplotlib, pytest, ruff.
