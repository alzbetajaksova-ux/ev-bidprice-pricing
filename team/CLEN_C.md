# Doplnok k návodu – Člen C

Platí spolu s tvojím PDF návodom a v rozporoch má prednosť. Vlož ho do svojho Clauda spolu s návodom. Zdroj rozhraní je `src/mpo_ev/interfaces.py`, definície v časti 5 návodu sú už neaktuálne. Článok a návody sú mimo repozitára.

## Stav (6. 11. 2026)

Člen A má hotový generátor, model dopytu, simulátor, flat rate a kód pre E4. **Mock neexistuje, pracuj rovno so skutočnými modulmi.** Prostredie: Python 3.11, inštalácia podľa `README.md`.

```python
from mpo_ev.demand import demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config, seed_range
from mpo_ev.simulator import run_episode

base = load_base()
config = make_config(4, 96, 18.98, base)
demand = demand_from_base(config, base)
test = generate_instances(config, seed_range(base, "test"))
```

## Zmeny pravidiel modelu

| Téma | Platí |
| --- | --- |
| Koniec predaja | do konca prvého slotu produktu, `config.is_sellable(p, step)` (Obr. 3 článku) |
| Mriežka cien | 19 kvantilov rozpočtu, q = 0,05 až 0,95; 0,178 až 1,822 |
| Dĺžka rezervácie | Exp s priemerom 3 h |
| Príchod | v každom kroku s pravdepodobnosťou λ/K |

## Zmeny oproti tvojim úlohám

**1.3 Repozitár.** Člen A už vytvoril `src/mpo_ev/`, `tests/`, `pyproject.toml` a `.gitignore`. Štruktúra navyše obsahuje `robustness.py`, `flat_baseline.py` a `team/`. `config/base.yaml`, `e1.yaml`, `e4.yaml` existujú. Chýba `requirements.txt`, verzie sú v `README.md`:

```text
numpy==2.4.6
scipy==1.17.1
cma==4.5.0
PyYAML==6.0.3
pandas==3.1.1
matplotlib==3.11.2
pytest==9.2.0
ruff==0.17.4
```

**3.6 VI.** Vzorec z návodu platí, `P_t(p) = demand.product_probs(t)` a `P_t(žiadna) = 1 − súčet`. Nepredajné produkty v slovníku nie sú, takže sa ráta s nimi ako s prázdnym krokom. Politika dostane len predajný produkt s voľnou kapacitou. Kontrolné hodnoty:

| Sloty | 2 | 3 | 4 |
| --- | --- | --- | --- |
| Presná DP, V₀ | 40,97 | 36,32 | 36,17 |
| Táto politika v simulátore (8000 inštancií, ± 4 SE) | 40,66 ± 0,76 | 36,11 ± 0,55 | 36,08 ± 0,48 |
| Flat rate (4000 inštancií) | 39,75 | 34,09 | 34,16 |
| LP hranica | 48,71 | 44,20 | 43,82 |

Ide o dočasnú kontrolu Člena A, VI je stále tvoja úloha a validácia pre M1. Ak dáš iné čísla, ozvi sa Členovi A a hľadajte rozdiel spolu. VI z článku (48,18 / 43,88 / 46,23) nie je priamo porovnateľné.

**3.7 MCTS, čas do ďalšej požiadavky.** Pravdepodobnosť predajnej požiadavky klesá v čase, lebo sloty končia. Geometrické rozdelenie preto použi na všetky príchody a nepredajné vyraď:

1. `p0 = sum(demand.product_probs(0).values())` je pravdepodobnosť príchodu v kroku. Ber ju z `demand`, nie z `config`, inak E4 nebude merať chybu modelu.
2. Ďalší príchod v kroku s vzorkuj geometricky s `p0`.
3. S pravdepodobnosťou `sum(product_probs(s).values()) / p0` je predajný, produkt vyber úmerne `product_probs(s)`. Inak v tomto kroku ponuka nevzniká.

**3.7 MCTS, stav.** `State` sa nedá použiť ako kľúč slovníka, obsahuje numpy pole. Pre kľúč uzla použi napríklad `state.capacity.tobytes()`. `state.capacity` je len na čítanie a mení sa počas epizódy, pri odkladaní sprav kópiu.

**3.8 Grid search.** Inštancia z č. 6.3.1 je `make_config(12, 96, 24.0, base)`.

**5.1 Runner.** Na vyhodnotenie použi `robustness.evaluate_policy`, zapisuje dohodnuté stĺpce CSV. `robustness.save_rows` ich uloží a `flat_baseline.summary_table` dá základné štatistiky. Politiky s tréningom majú `fit(train_instances, demand)` (protokol `TrainablePolicy`), volaj ho len s tréningovými inštanciami. LP hranicu dáva `bounds.lp_upper_bound(config, demand)`, medzeru `bounds.gap_to_bound`, Oracle nie je `Policy`. Konfigurácie E1 sú v `config/e1.yaml`.

**5.3 E2.** λ od 24 do 240, K cez `instances.required_steps(lam)`. Vzorec presne dáva 192 až 1920 krokov z textu článku.

**Report, sekcia 9.** Dôvod „mriežka cien sa líši“ z návodu už neplatí, mriežku sme odvodili z Tab. 2. Absolútne čísla sa líšia, lebo Tab. 1 nereprodukuje Tab. 2, preto porovnávaj pomery.

## Pravidlá férovosti pre politiky

- Pravdepodobnosti ber len z `demand`. Z `config` používaj len sloty, kroky, kapacitu a mriežku. V E4 nesie `config` skutočné λ a rozpočet.
- Sadzba mimo `config.price_grid` vyvolá chybu, vracaj hodnoty z mriežky alebo `REJECT`.
- Veľmi zriedkavé produkty môžu v modeli chýbať (pri 72 slotoch 2182 z 2628), hoci v inštancii sa objaviť môžu. MCTS nesmie spadnúť.
- Pri reálnom behu `run_episode` nastavuje seed politiky na seed inštancie + 50 000 podľa `evaluate_policy`.

## Podklady pre zoznam nejasností (2.4)

| Nejasnosť | Naša voľba | Opora |
| --- | --- | --- |
| Mriežka cien neuvedená | kvantily rozpočtu po 0,05 | podiel tržby/vyťaženie flat v Tab. 2 |
| T_p nedefinované | koniec prvého slotu | Obr. 3, slot 12:00–15:59 o 12:30 |
| Prevod nabíjania na sloty neuvedený | prvý a posledný zasiahnutý slot, orezanie na deň | vlastná voľba |
| Tab. 2: K = 24 × sloty, chyba 0,035–0,093, text 0,06 | E1 podľa Tab. 2, E2 podľa chyby 0,06 | výpočet, `report/sekcia3_podklady.md` |
| Text: 16–768 krokov | zodpovedá presne λ = 2 až 96, teda λ = počet slotov; Tab. 2 má iné λ | výpočet |
| „240 slotov po 15 min“ | preklep, 15 min je 96 slotov | výpočet |
| „24 h nabíjania“ vs. rastúce Ø požiadaviek | λ podľa Tab. 2 | λ × dĺžka slotu = 24 h platí pre text, nie pre tabuľku |
| Tab. 1 nereprodukuje Tab. 2 | ponechávame Tab. 1, porovnávame pomery | simulácia, priemer 0,8 h nepomohol |
| VI pri 3 slotoch nižšie než pri 2 aj 4 | pokles 2 → 3 sa reprodukuje, nárast pri 4 nie | dočasná DP |
| b > a vs. b ≥ a | b > a | pri spojitom rozpočte bez vplyvu |

## Výsledky Člena A pre analýzu

- `results/e1_flat.csv`, `results/e1_flat_summary.csv`: flat rate na konfiguráciách E1.
- `results/e4_flat.csv`, `results/e4_flat_summary.csv`: E4 pre flat rate. `drop_pct` je pokles tržieb oproti nominálu, `se_pct` jeho štandardná chyba z párových rozdielov.

Flat rate na E4: chyba λ ho takmer nezasiahne, chybný priemer rozpočtu dá pokles až 7,7 %. Žiadne zlepšenie nepresahuje dve štandardné chyby. Výsledky treba po M2 vygenerovať znova z finálnej verzie kódu a doplniť o bid-price a MCTS.
