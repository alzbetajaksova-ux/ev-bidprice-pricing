# Doplnok k návodu – Člen B

Platí spolu s tvojím PDF návodom a v rozporoch má prednosť. Vlož ho do svojho Clauda spolu s návodom. Zdroj rozhraní je `src/mpo_ev/interfaces.py`, definície v časti 5 návodu sú už neaktuálne. Článok a návody sú mimo repozitára.

## Stav (6. 11. 2026)

Člen A má hotový generátor, model dopytu, simulátor, flat rate a kód pre E4. **Mock neexistuje, pracuj rovno so skutočnými modulmi.** Prototyp pre pilot je teda hotový. Prostredie: Python 3.11, inštalácia podľa `README.md`.

```python
from mpo_ev.demand import demand_from_base
from mpo_ev.instances import generate_instances, load_base, make_config, seed_range
from mpo_ev.simulator import run_episode

base = load_base()
config = make_config(4, 96, 18.98, base)
demand = demand_from_base(config, base)
train = generate_instances(config, seed_range(base, "train"))
```

## Zmeny pravidiel modelu

| Téma | Platí |
| --- | --- |
| Koniec predaja | do konca prvého slotu produktu, `config.is_sellable(p, step)` (Obr. 3 článku) |
| Mriežka cien | 19 kvantilov rozpočtu, q = 0,05 až 0,95; 0,178 až 1,822 (Tab. 2: flat sadzby sú presne q = 0,35 a 0,40) |
| Dĺžka rezervácie | Exp s priemerom 3 h |
| Príchod | v každom kroku s pravdepodobnosťou λ/K |

Tab. 1 nereprodukuje absolútne čísla Tab. 2. Porovnávame pomery, nie absolútne tržby.

## Zmeny oproti tvojim úlohám

**4.1 Vstupy LP.** Použi `demand.expected_remaining(step)`, nesčítavaj cez kroky. Vracia len produkty, ktoré sa ešte dajú kúpiť, takže `Λ_p(t) = γ · expected_remaining(t)[p]`. Test „Σ Λ_p(0) = počet požiadaviek“ neplatí, neskoré požiadavky sa do Λ nerátajú. Porovnaj Σ Λ_p(0) s priemerným počtom predajných požiadaviek.

**4.2 Vstup `solve_dlp`.** Hotový `bounds.py` volá `solve_dlp(capacity, Lambda, q, r, products) -> (value, mu)`:

- `capacity`: pole dĺžky n_slots,
- `Lambda`: `dict[Product, float]`,
- `q`, `r`: slovníky s kľúčom `(Product, sadzba)`,
- `products`: zoznam produktov.

Ak chceš iný tvar, dohodni to s Členom A. Kontrolné hodnoty LP so seedom modelu z `base.yaml`:

| Sloty | 2 | 3 | 4 | 8 | 12 | 24 |
| --- | --- | --- | --- | --- | --- | --- |
| Hodnota LP | 48,71 | 44,20 | 43,82 | 46,12 | 47,67 | 50,97 |

**4.3 Bid-price.** Simulátor volá `price` len pri predajnom produkte s voľnou kapacitou, kontrolu kapacity netreba opakovať. Čas `reset` sa počíta do `runtime_s`.

**3.5 Oracle.** Musí vynechať požiadavky, ktoré sa nedajú predať: `config.is_sellable(r.product, r.step)`. V návode to chýba. Kapacita je `config.capacity`. Dočasná kontrola s týmto pravidlom dala pri 2 / 3 / 4 / 8 / 12 / 24 slotoch Oracle 65,54 / 54,14 / 54,13 / 55,72 / 55,11 / 57,18 a flat/Oracle pri 4 slotoch 0,600 (článok 0,583).

**1.6 Pilot, kritériá treba zmeniť.** Dočasná presná dynamická úloha ukazuje, že flat rate dosahuje v našom modeli pri 4 slotoch 94 % optima, v článku 85 %. Kritérium „≥ ~93 % VI“ by teda splnil aj sám flat rate. Návrh: merať, akú časť medzery flat–VI bid-price zatvorí. Prínos optima nad flat je pri 4 slotoch 6,5 % (článok 17,5 %), takže aj hranicu +5,7 % pri 24 slotoch treba prehodnotiť. Kritériá dohodni s tímom pred spustením pilotu.

**1.6 Pilot, seedy.** Inštancie 1000–1029 sú podmnožinou testovacích. Rozhodovanie na nich je slabé porušenie oddelenia tréningu a testu. Návrh: pilot na samostatných seedoch 2000–2029 a zmena v `config/base.yaml`, dohodnúť v tíme.

**4.4 CMA-ES.** Fitness rátaj cez `run_episode` na tréningových inštanciách. Simulátor bez politiky trvá pri 24 slotoch asi 0,3 ms na epizódu, brzdou bude LP.

## Pravidlá férovosti pre politiky

- Pravdepodobnosti ber len z `demand`. Z `config` používaj len sloty, kroky, kapacitu a mriežku. V E4 nesie `config` skutočné λ a rozpočet, ich čítanie by bolo nahliadnutie do pravdy.
- Sadzba mimo `config.price_grid` vyvolá chybu, vracaj hodnoty z mriežky alebo `REJECT`.
- Veľmi zriedkavé produkty môžu v modeli chýbať (pri 72 slotoch ich je 2182 z 2628), hoci v inštancii sa objaviť môžu. Politika nesmie spadnúť, ak produkt nenájde v slovníku.
- `state.capacity` je len na čítanie a mení sa počas epizódy. Ak si stav odkladáš, sprav kópiu.

## Na čo nadväzujú ostatní

- **Člen A:** po dodaní `lp.py` spustí `bounds.py` a tabuľku medzier. E4 pripojí tvoju politiku cez `robustness.evaluate_scenario` a `PolicyFactory`.
- **Člen C:** potrebuje `BidPricePolicy` s μ počítanými raz pri `reset` pre hybrid.

## Podklady pre sekciu 6 reportu

Rozdiely oproti článku sú v `report/sekcia3_podklady.md`, nejasnosti v `team/CLEN_C.md`. Obmedzenia v sekcii 11 píše Člen A.
