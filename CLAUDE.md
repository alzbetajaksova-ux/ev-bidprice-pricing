# Návod pre Claude – Člen A: model, prostredie, analýza a horná hranica

> **Ako použiť:** tento súbor je koreňový `CLAUDE.md` repozitára (lokálne `ev-bidprice-pricing`). Článok a návody sú mimo repozitára v `../docs/` (článok: `../docs/paper.pdf`).

## 0. Aktuálny stav (6. 11. 2026)

- [x] 1.1 Schválenie článku a rozsahu vyučujúcim – hotové.
- [x] Prostredie: Python 3.11.9, venv mimo OneDrive v `C:\Users\alzbe\.venvs\ev-bidprice-pricing` (numpy 2.4.6, scipy 1.17.1, cma 4.5.0, PyYAML 6.0.3, pandas 3.1.1, matplotlib 3.11.2, pytest 9.2.0, ruff 0.17.4). Predvolený Python v systéme je 3.15, na ňom sa stack nenainštaluje.
- [x] Článok overený voči časti 5a – pravidlá 2 a 6 opravené, pozri „Overenie voči článku“ v časti 5a.
- [x] Rozhodnutia v časti 5a potvrdené Členom A (6. 11.), vrátane dĺžky 3 h. Treba ich oznámiť B a C.
- [x] 1.4 `interfaces.py`, `mock.py`, `simulator.py` a testy napísané (24 testov prešlo, 0,3 ms na epizódu pri 24 slotoch), necommitnuté. Čaká na potvrdenie rozhrania od B a C.
- [x] 1.5 mriežka v `config/base.yaml` a 3.2 diskretizácia v `src/mpo_ev/instances.py` hotové, podklady v `report/sekcia3_podklady.md`.
- [x] 3.1 generátor v `src/mpo_ev/instances.py` hotový (63 testov prešlo); 200 + 100 inštancií na konfiguráciu sa dá kedykoľvek vytvoriť zo seedov.
- [x] `DemandModel` (`src/mpo_ev/demand.py`, trieda `EmpiricalDemandModel`) a 3.3 simulátor hotové, nezávislý test tržieb prešiel na skutočných inštanciách (86 testov). Validácia cez VI čaká na C. Simulátor cieľ ≤ 1 ms splnený.
- [x] 3.4 flat rate (`policies/flat.py`) hotový. Pomer flat/Oracle na 4 slotoch 0,600 (článok 0,583), Oracle a LP v tejto kontrole boli dočasné, nie dodávka.
- [x] `mock.py` odstránený, skutočný `EmpiricalDemandModel` a `generate_instance` ho úplne nahradili. B a C pracujú priamo s nimi.
- [x] `bounds.py` napísaný, netestovaný proti `lp.py`. Dohoda s B: `solve_dlp(capacity, Lambda, q, r, products) -> (value, mu)`, kde Lambda je slovník podľa produktu, q a r slovníky s kľúčom (produkt, sadzba).
- [x] Koncepty reportu: `report/sekcia2_opis_problemu.md`, `sekcia3_podklady.md` (2.1, 2.2), `sekcia11_obmedzenia.md`; `README.md`.
- [x] 5.5 E4 pripravené (`src/mpo_ev/robustness.py`, `config/e4.yaml`), výsledky pre flat na všetkých šiestich konfiguráciách E1 v `results/`, základné štatistiky flat rate v `results/e1_flat_summary.csv` (`flat_baseline.py`). Politiky B a C sa pripoja cez `evaluate_scenario`.
- [x] Podklady pre tím v `team/CLEN_B.md` a `team/CLEN_C.md`, príprava na obhajobu v `report/obhajoba_A.md`.
- [x] Kontrola pred commitom: čistá inštalácia, reprodukovateľnosť, `bounds.py` so skutočným LP (flat ≤ DP ≤ LP), 16 vložených chýb zachytených testami.
- [ ] **Čaká na B a C:** `lp.py` (4.6), VI (validácia M1), naladené politiky a runner (5.5). Commit až po dokončení začiatku sekcie Člena A.
- Nezávislý test simulátora (bez VI od C): kapacita 100, politika s pevnou sadzbou a; simulované tržby musia sedieť s Σ_p Λ_p · q(p,a) · r(p,a), kde Λ_p zahŕňa len predajné kroky (τ ≤ T_p).

## 1. Kto som a čo od teba chcem

Som **Člen A** v trojčlennom tíme na predmete Moderné prístupy v optimalizácii (MPO, TUKE), Zadanie 1, Variant B (návrh vlastného riešenia). Zodpovedám za **simulátor problému, formálnu analýzu, flat rate baseline, LP hornú hranicu a test robustnosti**. Od mojej práce závisia ostatní dvaja, preto je dôležitá rýchlosť v prvom týždni.

Ty si môj asistent: pomáhaš mi implementovať moje úlohy, vysvetľuješ kód (musím ho obhájiť) a píšeš podklady do reportu. Úlohy ostatných členov neimplementuj. Ak ich výstup potrebujem a ešte nie je hotový, navrhni mock podľa rozhraní v časti 5.

## 2. Zadanie v skratke

- Analyzovať optimalizačnú úlohu z článku: typ problému, rozhodovacie premenné, reprezentácia, obmedzenia, účelová funkcia, vyhodnocovanie.
- Variant B: navrhnúť vlastné riešenie a porovnať ho minimálne s hlavnou metódou článku tak, aby bolo jasné, kedy je lepšie alebo horšie.
- Férovosť: rovnaké inštancie, rovnaké vyhodnocovanie, rovnaký výpočtový rozpočet a kritériá ukončenia. Stochastické metódy opakovať s rôznymi `seed`, uviesť priemer, medián, smerodajnú odchýlku, min, max, konvergenciu a čas.
- Odovzdáva sa: kód s jedným príkazom na spustenie, `requirements.txt` s verziami, konfigurácie, `README`; report 6–10 strán A4 s 13 povinnými časťami; obhajoba, na ktorej každý vysvetlí celé riešenie.
- Hodnotenie 5 × 2 body: analýza, implementácia a reprodukovateľnosť, metodológia, interpretácia, obhajoba. Horší výsledok nestojí body, ak je postup správny.
- Použitie knižníc aj AI nástrojov treba uviesť a jasne oddeliť vlastnú prácu.

## 3. Problém z článku

Článok: Mrkos, Komenda, Fiedler, Vokřínek – *Online Dynamic Pricing for Electric Vehicle Charging Stations with Reservations*, IEEE Transactions on Intelligent Transportation Systems (preprint arXiv 2410.05538).

- Jedna nabíjacia lokalita s **3 nabíjačkami**, deň 00:00–24:00 rozdelený na *n* časových slotov.
- Produkt = súvislý blok slotov (rezervácia, parkovanie a nabíjanie s jednou cenou).
- Požiadavky prichádzajú Poissonovým procesom s intenzitou λ, diskretizovaným na *K* krokov (najviac 1 požiadavka na krok). Počet krokov sa volí tak, aby relatívna chyba ε₂/λ = 0,06, kde ε₂(k, λ) = λe^(−λ/k) + (λ − k)(1 − e^(−λ/k)).
- Predávajúci ponúkne cenu z konečnej mriežky A, ∞ znamená odmietnutie. Zákazník kúpi, ak jeho skrytý rozpočet > cena. Odmena = cena. Cieľ: maximalizovať očakávané tržby.
- MDP: stav (zostávajúca kapacita slotov c, krok t, aktuálne požadovaný produkt p).
- Parametre inštancií (Tab. 1): dĺžka rezervácie Exp(θ = 3 h), začiatok N(12 h, 3 h), rozpočet N(1; 0,5) za hodinu, 6–288 požiadaviek za 24 h, sloty 15 min–12 h, kroky 2 min–1,5 h, 100 inštancií na konfiguráciu.
- Metódy: **MCTS** (UCT, náhodný rollout, geometrické medzipríchody, znovupoužitie stromu); **flat rate** (jedna sadzba optimalizovaná na tréningových sekvenciách, FCFS); **VI** (optimum MDP, len 2–4 sloty); **Oracle** (binárny celočíselný program s plnou znalosťou budúcnosti, rozpočty zaokrúhlené nadol na mriežku).

**Výsledky článku (Tab. 2, priemer zo 100 inštancií, tržby v jednotkách článku)**

| Sloty | Dĺžka slotu | Kroky | Oracle | Flat | MCTS | VI | Čas MCTS \[s\] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 720 min | 48 |  |  |  | 48,18 |  |
| 3 | 480 min | 72 |  |  |  | 43,88 |  |
| 4 | 360 min | 96 | 67,45 | 39,33 | 44,01 | 46,23 | 1,467 |
| 8 | 180 min | 192 | 64,31 | 38,36 | 43,71 |  | 5,012 |
| 12 | 120 min | 288 | 62,66 | 40,14 | 43,15 |  | 10,905 |
| 24 | 60 min | 576 | 57,91 | 38,49 | 40,68 |  | 39,413 |
| 36 | 40 min | 864 | 55,58 | 38,27 | 39,99 |  | 93,557 |
| 72 | 20 min | 1728 | 51,67 | 36,64 | 38,51 |  | 450,417 |

**Nejasnosti článku (rozhodujeme a dokumentujeme sami)**

- Mriežka cien A nie je uvedená; dá sa odvodiť z Tab. 2 (pozri časť 5a, bod 6).
- Parametre MCTS sú uvedené dvakrát inak: č. 5.2.1 (d\_max = 3, c = 1, n\_iter = 800) vs. č. 6.3.1 (n\_iter = 10 000, d\_max = 10, c = 3).
- Diskretizácia: text uvádza 16–768 krokov, čo pri chybe 0,06 presne zodpovedá λ = 2 až 96, teda λ = počet slotov a λ · dĺžka slotu = 24 h („24 h nabíjania“). Tab. 2 však má pri 4 slotoch λ ≈ 19 a K = 24 × počet slotov, takže text a tabuľka opisujú iné nastavenie. Text navyše uvádza „240 slotov po 15 min“, 15 min je 96 slotov.
- Text uvádza fixný dopyt (24 h nabíjania), no priemerný počet požiadaviek v Tab. 2 rastie s počtom slotov (18,98 → 123,96).
- VI pri 3 slotoch (43,88) je nižšie ako pri 2 aj 4 slotoch.
- Vzťah času príchodu a slotov: text udáva len τ ≤ T_p, Obr. 3 ukazuje predaj slotu 12:00–15:59 o 12:30 (časť 5a, bod 2).
- Tab. 1 s dĺžkou 3 h nereprodukuje Tab. 2 (časť 5a, „Overenie voči článku“).
- Kód nie je zverejnený (pôvodná implementácia v Julii, POMDPs.jl).

## 4. Naše riešenie

**Bid-price politika z lineárneho programu, doladená cez CMA-ES**, plus hybrid MCTS a LP horná hranica.

1. Z očakávaného dopytu vyriešime choice-based LP. Duálne premenné kapacitných obmedzení μ\_j sú „hodnota“ slotu j.
2. Pri požiadavke na produkt p ponúkneme cenu, ktorá maximalizuje *pravdepodobnosť nákupu × (tržba − α · súčet μ\_j cez sloty p)*. Ak je maximum ≤ 0 alebo chýba kapacita, odmietneme.
3. LP sa prepočítava každých N krokov podľa zostávajúcej kapacity a času.
4. Parametre θ (škálovanie α pre časti dňa, korekcia dopytu γ, frekvencia N) ladí CMA-ES na tréningových sekvenciách.
5. Hybrid MCTS: náhodný rollout autorov nahradí bid-price politika.
6. Optimálna hodnota LP na začiatku dňa = horná hranica očakávaných tržieb online politiky, aj pre veľké inštancie, kde VI nefunguje.

```text
LP:  max  Σ_p Σ_a  r(p,a) · q(p,a) · x(p,a)
     s.t. Σ_a x(p,a) ≤ Λ_p                       pre každý produkt p
          Σ_{p ∋ j} Σ_a q(p,a) · x(p,a) ≤ c_j       pre každý slot j   (duál μ_j)
          x ≥ 0
Λ_p = očakávaný počet zostávajúcich požiadaviek na p, q(p,a) = P(nákup p za sadzbu a),
r(p,a) = sadzba a × dĺžka p v hodinách, c_j = zostávajúca kapacita slotu j.

Pravidlo: a* = argmax_a q(p,a) · ( r(p,a) − α · Σ_{j ∈ p} μ_j ),  inak odmietnutie (∞)
```

Výskumná otázka: dosiahne rýchla politika založená na hodnote slotov tržby MCTS alebo vyššie a ako ďaleko sú obe od hornej hranice? Na 2–4 slotoch nemôže nič prekonať VI, zlepšenie hľadáme pri 24+ slotoch.

## 5. Spoločné technické konvencie (rovnaké pre A, B aj C)

**Prostredie:** Python 3.11, `numpy`, `scipy` (LP aj MILP cez HiGHS), `cma`, `pyyaml`, `pandas`, `matplotlib`, `pytest`, `ruff`. Presné verzie v `requirements.txt`.

**Štruktúra repozitára a vlastníci**

```text
mpo-ev-pricing/
  config/                  base.yaml, e1.yaml ... e4.yaml       (C, hodnoty dodá každý)
  src/mpo_ev/
    interfaces.py          dátové triedy a protokoly             (A)
    instances.py           generátor inštancií + diskretizácia   (A)
    demand.py              EmpiricalDemandModel                  (A)
    simulator.py           run_episode                           (A)
    bounds.py              LP horná hranica                      (A)
    lp.py                  choice-based LP + duálne ceny         (B)
    tuning.py              ladenie theta cez CMA-ES              (B)
    policies/
      flat.py              flat rate                             (A)
      oracle.py            Oracle (MILP)                         (B)
      bidprice.py          bid-price politika                    (B)
      vi.py                Value Iteration                       (C)
      mcts.py              MCTS autorov                          (C)
      hybrid_mcts.py       MCTS s bid-price rolloutom            (C)
  run_experiments.py       jeden príkaz na experimenty           (C)
  analysis.ipynb           tabuľky a grafy                       (C)
  tests/                   pytest, každý pre svoje moduly
  results/                 CSV, params/, figures/
  requirements.txt         (C)
  README.md                (A)
```

**Rozhrania (finalizované 6. 11., platný zdroj je `src/mpo_ev/interfaces.py`; bez dohody tímu sa nemenia)**

```python
# Prehľad; plné definície sú v src/mpo_ev/interfaces.py
REJECT = math.inf
Product(first_slot, last_slot); .slots()
Config(n_slots, n_steps, capacity, expected_requests, price_grid, budget_mean=1.0,
       budget_std=0.5, duration_mean_h=3.0, start_mean_h=12.0, start_std_h=3.0)
    .slot_length_h, .duration_h(p), .last_sale_step(p), .is_sellable(p, step)
Request(step, product, budget_rate)   # budget_rate politika NEVIDÍ
Instance(config, requests, seed)
State(step, capacity, product)        # capacity len na čítanie; produkt predajný, s kapacitou

class DemandModel(Protocol):
    def product_probs(self, step) -> dict[Product, float]: ...      # len predajné produkty
    def expected_remaining(self, step) -> dict[Product, float]: ...  # Lambda_p od kroku step
    def acceptance_prob(self, product, rate) -> float: ...
    def revenue(self, product, rate) -> float: ...
    def duration_h(self, product) -> float: ...

class Policy(Protocol):
    name: str
    def reset(self, config, demand, seed) -> None: ...
    def price(self, state) -> float: ...   # sadzba z price_grid alebo REJECT

class TrainablePolicy(Policy, Protocol):
    def fit(self, train_instances, demand) -> None: ...

EpisodeResult(revenue, utilization_h, n_requests, n_accepted, runtime_s)

# simulator.py: run_episode(policy, instance, demand, seed=None) -> EpisodeResult
# demand = model pre politiku; seed predvolene instance.seed + 50 000
# instances.py: make_config, generate_instance(s), seed_range; demand.py: demand_from_base
```

**Dohodnuté pravidlá modelu** (A ich potvrdí do M0, zmeny hlási celému tímu)

- Cena = sadzba za hodinu × dĺžka rezervácie v hodinách. Mriežka A je mriežka sadzieb (kvantily rozpočtu, časť 5a, bod 6). Zákazník kúpi, ak jeho rozpočet za hodinu > sadzba. Záporný rozpočet = nikdy nekúpi.
- Flat rate v článku je tiež sadzba za čas, takže konvencia je s ním v súlade.
- Politika dostáva len `State`; rozpočty zákazníkov a budúce požiadavky inštancie nevidí. VI, MCTS a LP smie používať iba `DemandModel` (očakávania), nie konkrétnu inštanciu. Oracle a LP hranica sú výnimky a nie sú politiky.

**Seedy:** tréningové inštancie 0–199, testovacie 1000–1099, pilot 1000–1029, behy CMA-ES 0–9, náhodnosť MCTS = seed inštancie + 50 000. Vždy `np.random.default_rng(seed)`, nikdy globálny `np.random`.

**Formát výsledkov:** CSV so stĺpcami `experiment, config_id, method, instance_seed, run_seed, revenue, utilization_h, n_requests, n_accepted, runtime_s`.

**Spolupráca:** každá úloha vo vlastnej vetve, pull request reviewuje aspoň jeden ďalší člen, `pytest` musí prejsť. Súbory vytvorené s pomocou AI majú v hlavičke poznámku `# Vytvorené s pomocou Claude, upravil: <meno>` a README má sekciu o použití AI.

**Míľniky** (týždne relatívne od štartu, termín odovzdania \[doplniť\])

| Míľnik | Kedy | Podmienka |
| --- | --- | --- |
| M0 | koniec F0 (týždeň 1) | `interfaces.py` + mock simulátor, mriežka cien |
| M1 | týždeň 2 | simulátor overený cez VI, pilot vyhodnotený |
| M2 | týždeň 3 | kód zmrazený, θ naladené, menia sa už len configy |
| M3 | týždeň 4 | report v1 kompletný |
| Odovzdanie | \[doplniť\] | kontrolný zoznam odškrtnutý |

## 5a. Rozhodnutia o modeli (Člen A, 6. 11. 2026)

Rozhodnutia pre generátor, `DemandModel` a simulátor. Článok ich nedáva jednoznačne, preto patria aj do zoznamu nejasností (úloha 2.4) a do sekcie 3 reportu. Pred M0 ich treba oznámiť B a C.

| # | Téma | Rozhodnutie | Opora v článku |
| --- | --- | --- | --- |
| 1 | Časová os | Predaj aj nabíjanie na tej istej osi 00:00–24:00; K krokov pokrýva celý deň. | obdobie predaja (0, max T), Obr. 3 |
| 2 | Koniec predaja slotu | T\_p = koniec prvého slotu produktu: produkt sa dá kúpiť, kým jeho prvý slot neskončil. Inak automatické odmietnutie: požiadavka sa započíta, tržba 0. | podmienka τ ≤ T\_p (č. 3.1); Obr. 3: o 12:30 sa predáva produkt so slotom 12:00–15:59, ktorý ešte nie je sivý. Pôvodné „začiatok prvého slotu“ je v rozpore s Tab. 2 |
| 3 | Typ produktu vs. čas príchodu | Homogénny Poissonov proces; v každom kroku príde požiadavka na p s pravdepodobnosťou λ\_p/K (súčet λ/K), nezávisle od času. Dôsledok: časť neskorých požiadaviek je neprípustná (25–44 % pri 2–8 slotoch) – vlastnosť modelu autorov, uviesť v analýze. `product_probs(step)` vracia len produkty predajné v danom kroku, aby Λ\_p nezahŕňalo nepredajné požiadavky. | rovnica 3, č. 3.2.4, č. 4.2 |
| 4 | Prevod nabíjania na sloty | Prvý slot = ⌊začiatok / dĺžka slotu⌋, posledný = ⌈koniec / dĺžka slotu⌉ − 1; začiatok pred 0:00 → 0:00, nabíjanie po polnoci orezané na posledný slot. λ\_p = λ · P(produkt = p) z Monte Carla (10⁶ vzoriek, fixný seed). | Tab. 1 (rozdelenia); prevod neuvedený |
| 5 | Cena a rozpočet | Cena = sadzba × dĺžka produktu v h; celkový rozpočet = rozpočet za h × tá istá dĺžka → nákup práve vtedy, keď rozpočet za h > sadzba. Záporný rozpočet = nikdy nekúpi. | rozpočet „pre danú dĺžku relácie“ (č. 6.1); my používame dĺžku predávaného produktu. Článok je nekonzistentný b > a vs. b ≥ a, pri spojitom rozpočte bez vplyvu |
| 6 | Mriežka sadzieb | Kvantily rozpočtu F⁻¹(q) pre q = 0,05; 0,10; …; 0,95 (19 hodnôt, 0,178–1,822) + odmietnutie. Krok 0,05 je náš predpoklad, z článku vyplýva len, že mriežka obsahuje q = 0,35 a 0,40. Citlivosť overuje E4. | mriežka neuvedená; Tab. 2: tržby / vyťaženie flat rate = 0,8073 (= F⁻¹(0,35)) pri 4–8 slotoch a 0,8733 (= F⁻¹(0,40)) pri 12–72 slotoch |
| 7 | λ a počet krokov K | E1: K = 24 × počet slotov a λ = priemerný počet požiadaviek z Tab. 2 (porovnateľnosť s článkom). E2: K podľa ε₂/λ = 0,06 (K ≈ 8λ, λ od 24 do 240). | pozri zistenie nižšie |
| 8 | Dĺžka rezervácie | Exp s priemerom 3 h podľa Tab. 1 ako základ. Rozdiel voči Tab. 2 ide do nejasností a reportu; jedna konfigurácia s priemerom 0,8 h slúži ako kontrola citlivosti (`duration_mean_h`). | Tab. 1; pozri „Overenie voči článku“ |
| 9 | Čas kroku | Krok t (od 0) končí v čase (t + 1) · 24 / K a predajný je, ak tento čas ≤ T\_p. Pri rovnakej mriežke to zodpovedá τ = t v číslovaní článku od 1. | č. 3.2.4 |
| 10 | Volanie politiky | Pri požiadavke po T\_p alebo bez kapacity sa `price` nevolá, simulátor odmieta sám. `runtime_s` = `reset` + všetky `price`. | č. 3.1, krok 2 |

**Zistenie k bodu 7 (do zoznamu nejasností):** v Tab. 2 platí presne K = 24 × počet slotov (96/4, 192/8, …, 1728/72). Chyba ε₂/λ tam vychádza 0,035–0,093, nie 0,06, ako tvrdí text. Pre E2 text sedí: vzorec dáva K ≈ 8λ, čo zodpovedá uvedeným 192–1920 krokom.

| Sloty | K v Tab. 2 | λ (Ø požiadaviek, Tab. 2) | ε₂/λ pri K z Tab. 2 | K podľa ε₂/λ = 0,06 |
| --- | --- | --- | --- | --- |
| 2 | 48 | 9,00 | 0,088 | 72 |
| 3 | 72 | 13,94 | 0,091 | 112 |
| 4 | 96 | 18,98 | 0,093 | 152 |
| 8 | 192 | 36,67 | 0,090 | 294 |
| 12 | 288 | 49,95 | 0,082 | 400 |
| 24 | 576 | 76,28 | 0,063 | 610 |
| 36 | 864 | 92,86 | 0,052 | 743 |
| 72 | 1728 | 123,96 | 0,035 | 992 |

**Overenie voči článku (6. 11. 2026)**

- *Pravidlo 2:* so začiatkom prvého slotu vychádzal strop tržieb (každý zákazník zaplatí celý rozpočet, bez kapacity) 27,22 pri 2 slotoch a 60,28 pri 4 slotoch, teda pod VI 48,18 a Oracle 67,45. S koncom prvého slotu je strop 95,53 a 101,90, rozpor zmizol.
- *Pravidlo 5 potvrdené:* pri flat rate platí tržby = sadzba × vyťaženie na 4 miesta.
- *Príchody potvrdené:* pravdepodobnosť v kroku je λ/K (rovnica 3, č. 4.2), takže E\[počet\] = λ. Err₂ počíta príchody nad jeden za krok v Poissonovom procese, nie stratu v generátore.
- *Dĺžka rezervácie (rozhodnuté: bod 8, rozdiel zostáva nevysvetlený):* s Tab. 1 (priemer 3 h, λ z Tab. 2) je model výrazne viac kapacitne obmedzený než článok. Výsledky flat rate (150 epizód, optimalizovaná sadzba, λ a K z Tab. 2):

| Sloty | Článok: q, prijaté, vyťaženie \[h\], tržby | Náš model: q, prijaté, vyťaženie \[h\], tržby |
| --- | --- | --- |
| 4 | 0,35; 7,74; 48,72; 39,33 | 0,60; 3,5; 30,7; 34,6 |
| 12 | 0,40; 17,35; 45,96; 40,14 | 0,65; 6,3; 28,2; 33,6 |
| 24 | 0,40; 25,75; 44,07; 38,49 | 0,65; 8,3; 27,4; 32,6 |
| 72 | 0,40; 43,84; 41,96; 36,64 | 0,70; 10,1; 28,1; 35,4 |

- Pomery medzi metódami však sedia: na 100 testovacích inštanciách flat/Oracle 0,600 (4 sloty, článok 0,583), 0,615 (8; 0,596), 0,595 (12; 0,641), 0,588 (24; 0,665). Absolútne hodnoty a prínos dynamiky však nie: dočasná presná DP dala 40,97 / 36,32 / 36,17 pri 2 / 3 / 4 slotoch (VI v článku 48,18 / 43,88 / 46,23), LP 48,71 / 44,20 / 43,82, flat 39,67 / 34,10 / 33,97. Pokles pri 3 slotoch sa reprodukuje, nárast pri 4 slotoch nie. Flat/optimum je pri 4 slotoch 0,94, v článku 0,85, takže kritérium pilotu ≥ 93 % VI v našom modeli skoro nič nerozlišuje; B ho musí sprísniť.
- Simulátor proti presnej DP: politika z DP na 8000 inštanciách 40,66 ± 0,76 / 36,11 ± 0,55 / 36,08 ± 0,48 (4 SE), zhoda s hodnotou DP. Kontrolu VI od C to nenahrádza.
- Priemer dĺžky 0,8 h nepomohol: pri 24 slotoch prijaté 13,6 (článok 25,75), flat 24,88 (38,49), Oracle 41,01 (57,91), flat/Oracle 0,607 (0,665).
- Vypnutie expirácie to nevysvetľuje (rovnaké prijaté ≈ 12, q ≈ 0,8 pri 72 slotoch) a ani priemer 1/3 h alebo 1 h nesedí na prijaté aj vyťaženie súčasne (vyťaženie zostáva okolo 28–39 h).
- Nepriame indície z Tab. 2 (hypotézy): prijatá rezervácia pri flat rate trvá ≈ dĺžka slotu + 0,6 h (0,96 h pri 72 slotoch) a λ · (dĺžka slotu + 0,79 h) ≈ 135–139 pri 8–72 slotoch. Dopyt teda vyzerá konštantný v hodinách produktov (preto Ø požiadaviek rastie so slotmi), ale pri kratších reláciách než 3 h a inej hodnote než „24 h nabíjania“ z textu.

## 6. Moje úlohy (Člen A)

Poradie zodpovedá kritickej ceste. Každá úloha má výstup a kritérium hotovosti.

**F0 – do M0 (prvé dni)**

1. **1.1 Schválenie článku a rozsahu.** Napísať vyučujúcemu krátky e-mail: článok, Variant B, plánované experimenty E1–E4 a znížený rozsah (max. 24 slotov pre MCTS, menej inštancií pri pomalých nastaveniach). Hotové: písomný súhlas.
2. **1.4 Rozhrania + mock.** Finalizovať `interfaces.py` z časti 5 a `MockDemandModel` + jednoduchý `run_episode` pre 4 sloty, aby B a C mohli hneď začať. Hotové: B aj C potvrdia, že im rozhranie stačí.
3. **1.5 Mriežka cien.** Sadzby = kvantily rozpočtu N(1; 0,5)/h podľa časti 5a, bod 6, a zdôvodniť. Hotové: hodnoty v `config/base.yaml`, odsek zdôvodnenia pre report.

**F1 – do M1 (týždeň 1–2)**

4. **3.1 Generátor inštancií** (`instances.py`). Pre každý krok s pravdepodobnosťou λ/K príde požiadavka; začiatok \~ N(12, 3) h, dĺžka \~ Exp(3 h), prevod na sloty (prvý a posledný zasiahnutý slot, orezať na deň – pravidlo zdokumentovať), rozpočet \~ N(1; 0,5)/h. Čas príchodu a sloty rieši časť 5a, body 2–3; priemer dĺžky čítať z configu. Hotové: 200 tréningových a 100 testovacích inštancií na konfiguráciu, deterministické podľa seedu.
5. **3.2 Diskretizácia.** Funkcia, ktorá pre λ nájde najmenšie K s ε₂(K, λ)/λ ≤ 0,06. Porovnať s počtami krokov v Tab. 2 a nesedenia zapísať do zoznamu nejasností (úloha C 2.4). Hotové: unit test + tabuľka „naše K vs. článok“.
6. **DemandModel** (`demand.py`): `product_probs(step)`, `acceptance_prob`, `revenue`, `duration_h` konzistentné s generátorom. Hotové: test, že prázdne a neprázdne kroky v 10 000 vygenerovaných inštanciách sedia s pravdepodobnosťami.
7. **3.3 Simulátor** (`simulator.py`). `run_episode` prejde požiadavky inštancie, zavolá `policy.price(state)`, rozhodne nákup podľa `budget_rate`, aktualizuje kapacitu. Odmietne, ak chýba kapacita. Meria čas rozhodovania. Musí byť rýchly, lebo CMA-ES (B) volá tisíce epizód: cieľ ≤ 1 ms na epizódu pri 24 slotoch bez času politiky (zatiaľ 0,3 ms), inak vektorizovať alebo použiť Numbu. Hotové: testy (kapacita nikdy záporná, rovnaký seed = rovnaký výsledok).
8. **Prototyp pre pilot.** Hneď ako funguje 3.1–3.3, poslať B verziu pre 4 a 24 slotov, aj keď ešte nie je overená cez VI.
9. **2.1 a 2.2 Analýza.** Formálny zápis MDP (stav, akcie, prechodová pravdepodobnosť, odmena, horizont) a tabuľka klasifikácie dvoch úloh: (a) oceňovanie = maximalizačné, diskrétne, jednokriteriálne, stochastické, dynamické/online, s kapacitnými obmedzeniami; (b) ladenie θ = spojité, nízkodimenzionálne, zašumené, black-box, s hranicami parametrov.

**F2 – do M2 (týždeň 2–3)**

10. **3.4 Flat rate** (`policies/flat.py`). `fit(train_instances)` vyberie sadzbu z mriežky s najvyššími priemernými tržbami na tréningových inštanciách, potom FCFS. Hotové: na 4 slotoch rozumný pomer k Oracle ako v článku (39,33 / 67,45 ≈ 0,58), presné čísla nemusia sedieť.
11. **4.6 LP horná hranica** (`bounds.py`). Použije LP od B (`lp.py`) so začiatočnou kapacitou a Λ\_p pre celý deň. Hotové: hranica ≥ VI na 2–4 slotoch (kontrola správnosti) a tabuľka medzier každej metódy k hranici pre všetky konfigurácie.
12. **6.3 README.** Inštalácia, spustenie, očakávaný čas, štruktúra, použitie AI. Hotové: člen B alebo C ho prejde v čistom prostredí bez otázok.

**F3 – experimenty (týždeň 3–4)**

13. **5.5 E4 robustnosť.** Politiky (bid-price, MCTS, flat) dostanú nesprávny `DemandModel` (λ × 0,7 a × 1,3; priemer rozpočtu 0,8 a 1,2), simulátor beží so správnym. Plus citlivosť na mriežku cien (krok kvantilov 0,10 / 0,05 / 0,025). Hotové: tabuľka poklesu tržieb v % pre každú metódu.

## 7. Závislosti

| Potrebujem | Od koho | Kedy |
| --- | --- | --- |
| VI na 2–4 slotoch na kontrolu simulátora | C | M1 |
| `lp.py` (LP a duálne ceny) pre hornú hranicu | B | F1 |
| naladené politiky a runner pre E4 | B, C | M2 |

| Odovzdávam | Komu | Kedy |
| --- | --- | --- |
| `interfaces.py` + mock, mriežka cien | B, C | M0 |
| prototyp simulátora pre pilot | B | čo najskôr v F1 |
| generátor, simulátor, `DemandModel`, fixné inštancie | B, C | M1 |
| flat rate, LP hranica, výsledky E4 | C (do analýzy) | F2–F3 |

## 8. Moje sekcie reportu

- **2. Opis a význam problému:** kontext nabíjania EV, prečo rezervácie a dynamické oceňovanie, súvis s revenue managementom.
- **3. Formulácia optimalizačnej úlohy:** MDP, tabuľka klasifikácie, diskretizácia a jej chyba, naše rozhodnutia (mriežka cien, konvencia sadzby).
- **11. Obmedzenia:** syntetické dáta, arbitrárne rozpočty, diskretizácia, znížený rozsah experimentov, Python vs. Julia.
- Podklady pre B (rozdiely oproti článku) a C (porovnanie): tabuľka medzier k LP hranici, výsledky E4.

## 9. Pravidlá pre Claude a prvé prompty

- Odpovedaj po slovensky. Pred kódom stručne vysvetli prístup, po kóde pridaj `pytest` testy.
- Drž sa rozhraní z časti 5. Ak treba zmenu, navrhni ju ako správu pre tím, nemen ju potichu.
- Nevymýšľaj parametre článku. Čo článok neuvádza, označ `[doplniť]` alebo navrhni hodnotu so zdôvodnením.
- Každá náhodnosť má explicitný seed. Upozorni ma, ak niečo ohrozuje férovosť porovnania (napr. politika vidí budúcnosť).
- Uprednostni jednoduchý a čitateľný kód, ktorý viem vysvetliť. Po každej úlohe mi daj 3 otázky, ktoré môžu padňúť na obhajobe.

**Prvé prompty**

1. *„Prečítaj si CLAUDE.md a ../docs/paper.pdf (najmä č. 3, 4 a 6.1). Zhrň mi vlastnými slovami moje úlohy a stav z časti 0.“*
2. *„Finalizujme `interfaces.py` a mock simulátor pre 4 sloty (úloha 1.4). Najprv mi vysvetli, čo by si na návrhu rozhraní zmenil a prečo.“*
3. *„Napíš diskretizáciu (úloha 3.2) a porovnaj naše počty krokov s Tab. 2.“*
