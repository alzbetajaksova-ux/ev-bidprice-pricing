# 5. Návrh vlastného riešenia

<!-- Vytvorené s pomocou Claude, upravil: Člen B. Zahŕňa aj úlohu 2.3 (formulácia nášho riešenia).
MDP a mriežka cien sú v sekcii 3 (Člen A), metóda autorov v sekcii 4 (Člen C). Čísla ladenia
z results/tuning_*.csv a results/params/ (50 tréningových inštancií); výsledky na testovacích
inštanciách sú v sekcii 8. -->

MCTS autorov pri každej požiadavke znova prehľadáva strom budúcich scenárov, preto jeho čas rastie s počtom slotov (sekcia 4). Navrhujeme opačný prístup, ktorý sa bežne používa v revenue managemente leteckých spoločností a hotelov (Talluri a van Ryzin, 1998; 2004): raz vypočítať **hodnotu každého slotu** z jednoduchého lineárneho programu a pri požiadavke iba porovnať možnú tržbu s hodnotou slotov, ktoré by predaj spotreboval. Rozhodnutie je potom otázkou milisekúnd. Riešenie má tri časti:

1. deterministický LP, z ktorého získame hodnoty slotov,
2. bid-price pravidlo, ktoré z nich určí ponúkanú sadzbu,
3. ladenie niekoľkých parametrov pravidla cez CMA-ES na tréningových inštanciách.

Z toho istého LP vychádzajú aj dve doplnkové časti: hybrid MCTS (Člen C) a horná hranica tržieb (Člen A).

## 5.1 Deterministický LP a hodnoty slotov

Náhodné príchody nahradíme ich očakávaním (fluidná aproximácia, Gallego a van Ryzin, 1997). Nech Λ_p je očakávaný počet zostávajúcich požiadaviek na produkt p, q(p,a) = P(b > a) je pravdepodobnosť nákupu pri sadzbe a a r(p,a) = a · d(p) je tržba pri nákupe. Premenná x(p,a) ≥ 0 hovorí, koľkým z očakávaných zákazníkov na p ponúkneme sadzbu a:

```text
max  Σ_p Σ_a  r(p,a) · q(p,a) · x(p,a)
s.t. Σ_a x(p,a)                    ≤ Λ_p     pre každý produkt p      (dopyt)
     Σ_{p ∋ j} Σ_a q(p,a) · x(p,a) ≤ c_j     pre každý slot j         (kapacita, duál μ_j)
     x ≥ 0
```

**Vstupy (úloha 4.1)** berie LP výhradne z modelu dopytu, nie z konkrétnej inštancie: Λ_p od aktuálneho kroku (`expected_remaining`), q a r pre všetky sadzby mriežky. Nepredajné požiadavky po T_p sa do Λ_p nezapočítajú (sekcia 3).

**Hodnoty slotov.** Duálna premenná μ_j kapacitného obmedzenia slotu j udáva, o koľko by vzrástla optimálna hodnota LP pri jednom voľnom mieste navyše v slote j. Je to teda odhad toho, koľko budúcich tržieb stratíme, ak miesto v slote j predáme teraz (náklad príležitosti). Sloty v popoludňajšej špičke majú vysoké μ_j, sloty v noci nulové.

**Implementácia (úloha 4.2).** LP riešime solverom HiGHS (`scipy.optimize.linprog`, metóda vnútorného bodu). Pri 24 slotoch má model 281 produktov s nenulovým dopytom. Dve úpravy ho zmenšia bez zmeny optima aj duálnych cien:

- Pre každý produkt ponecháme len sadzby na hornom konkávnom obale bodov (q, r·q) po sadzbu s najvyššou očakávanou tržbou. Ostatné sadzby nahradí zmes dvoch susedných, ktorá prinesie viac a spotrebuje menej kapacity. Pri 24 slotoch to zníži počet premenných z 5 339 na 3 653.
- Očakávaný predaj produktu sa zavedie ako pomocná premenná s_p, takže kapacitné riadky obsahujú len s_p. Matica má asi desaťkrát menej nenulových prvkov.

Riešenie trvá asi 0,04 s pri 24 slotoch a 0,8 s pri 72 slotoch (pôvodne 0,13 s a 6,3 s). Správnosť overujú testy (`tests/test_lp.py`): ručne vyrátané prípady, silná dualita, μ_j porovnané s konečnými diferenciami hodnoty LP a kontrolné hodnoty člena A.

## 5.2 Bid-price pravidlo

Pri požiadavke na produkt p v kroku t (s voľnou kapacitou a pred T_p) politika ponúkne sadzbu

```text
a* = argmax_{a ∈ A}  q(p,a) · ( r(p,a) − α(t) · Σ_{j ∈ p} μ_j )
```

a ak je toto maximum ≤ 0, požiadavku odmietne (∞). Výraz v zátvorke je čistý zisk z predaja: tržba mínus hodnota slotov, ktoré predaj spotrebuje. Vynásobením pravdepodobnosťou nákupu dostaneme očakávaný čistý zisk z ponuky. Pravidlo tak vyvažuje dve chyby: privysoká sadzba znamená, že zákazník nekúpi, prinízka znamená, že lacno predáme slot, ktorý by sme neskôr predali drahšie.

Správanie pravidla je intuitívne:
- Keď sú sloty produktu bezcenné (Σ μ_j = 0, napríklad v noci), pravidlo zvolí sadzbu maximalizujúcu očakávanú tržbu q · r.
- S rastúcou hodnotou slotov sa ponúkaná sadzba zvyšuje.
- Pri veľmi drahých slotoch sa požiadavka odmietne, aby sa kapacita ušetrila pre dlhšie alebo lepšie platiace rezervácie.

Parameter α(t) ≥ 0 škáluje hodnoty slotov: α = 0 je krátkozraké pravidlo, ktoré kapacitu vôbec necení, α = 1 berie μ z LP doslova. Pravidlo potrebuje len stav (krok, kapacita, produkt) a model dopytu, budúce požiadavky ani rozpočty zákazníkov nevidí.

## 5.3 Prepočítavanie LP

Hodnoty μ z rána neodrážajú, čo sa počas dňa predalo. Politika preto vie LP prepočítať z aktuálnej kapacity a zo zostávajúceho dopytu od nasledujúceho kroku (aktuálna požiadavka je už známa). Používame dve pravidlá:

- **Po predaji.** Ak sa od posledného riešenia zmenila kapacita, LP sa prepočíta. Tým sa μ prispôsobí zostávajúcej kapacite.
- **Periodicky.** LP sa prepočíta každých N krokov, aj keď sa nič nepredalo. Zachytí sa tak, že s ubiehajúcim dňom ubúda zostávajúci dopyt.

Prepočet sa vykoná až pri najbližšej požiadavke, kroky bez požiadavky nič nestoja. Naladená politika rieši pri 4 slotoch asi 6 a pri 24 slotoch asi 11 LP za deň, s celkovým časom 0,02 s a 0,32 s na deň.

## 5.4 Parametre a formulácia ladenia (úloha 2.3)

Ladíme vektor θ so štyrmi parametrami:

| Parameter | Význam | Hranice |
| --- | --- | --- |
| α_am, α_pm | škálovanie μ v prvej a druhej polovici dňa | [0,1; 1,5] |
| γ | korekcia očakávaného dopytu v LP (Λ_p → γ · Λ_p) | [0,7; 2,5] |
| R | počet periodických prepočtov LP za deň, N = round(K / R); R < 0,5 znamená bez periodického prepočtu | [0; 96] |

Rozdelenie α na dve časti dňa umožňuje, aby politika ráno, keď je ešte veľa voľnej kapacity, cenila sloty inak ako večer. Parameter γ koriguje systematickú chybu fluidného LP: ten pozná len priemerný dopyt, nie jeho kolísanie. Prvé skúšobné ladenie s užšími hranicami (γ ≤ 1,6, R ≤ 48) skončilo na ich okraji, preto sme hranice rozšírili.

**Formulácia ladenia.** Pre pevnú množinu tréningových inštancií I_train riešime

```text
max_θ  F(θ) = (1 / |I_train|) · Σ_{i ∈ I_train} tržby( BidPrice(θ), i )     s.t.  θ_min ≤ θ ≤ θ_max
```

Je to spojitá, štvorrozmerná úloha s hranicami. F sa dá iba simulovať (black-box, bez gradientu) a je nehladká, lebo sadzby sú diskrétne: malá zmena θ zmení ponúkanú cenu až po prekročení hranice medzi dvoma sadzbami. Vďaka pevným inštanciám a deterministickej politike je F deterministická (spoločné náhodné čísla): rovnaké θ dá vždy rovnakú hodnotu a rozdiel dvoch θ nie je zašumený výberom inštancií. Klasifikácia úlohy je v tabuľke v sekcii 3.

**Prečo CMA-ES.** CMA-ES (Hansen, 2016) je evolučná stratégia pre spojité black-box úlohy, ktorá si z úspešných kandidátov učí tvar a mierku prehľadávacieho rozdelenia. Nepotrebuje gradient, toleruje nehladkú funkciu a pri štyroch parametroch stačí niekoľko desiatok vyhodnotení. Používame knižnicu `cma`: ladí sa v priestore normalizovanom na [0, 1]⁴ s hranicami, štart je v predvolenom θ (α = 1, γ = 1, bez periodického prepočtu), počiatočná smerodajná odchýlka σ₀ = 0,25, ukončenie po vyčerpaní rozpočtu vyhodnotení.

**Referencie s rovnakým rozpočtom.** Aby bolo vidieť, čo prináša samotné CMA-ES, porovnávame ho s dvoma jednoduchšími metódami s rovnakým počtom vyhodnotení F:

- **Náhodné hľadanie:** rovnomerné body v [0, 1]⁴ (prvý bod je predvolené θ). Pri malom počte parametrov je to silná referencia (Bergstra a Bengio, 2012).
- **Grid search:** pravidelná mriežka s k⁴ bodmi, ktorá sa zmestí do rozpočtu.

**Rozpočet.** Kvôli výpočtovému času sme plánovaný rozpočet (10 behov × 100 vyhodnotení × 200 inštancií) znížili na **5 behov (seedy 0–4) × 60 vyhodnotení × 50 tréningových inštancií (seedy 0–49)**, rovnako pre všetky tri metódy. Grid search pri 60 vyhodnoteniach stihne len 2⁴ = 16 bodov. Ladenie jednej konfigurácie trvá od 3 min (2 sloty) po 85 min (24 sloty) na dvoch jadrách. Testovacie inštancie sa pri ladení nepoužili. Do vyhodnotenia na teste ide z piatich behov CMA-ES ten s najvyšším F(θ).

## 5.5 Výsledky ladenia na tréningových inštanciách

**Tabuľka 5.1.** F(θ) na 50 tréningových inštanciách: predvolené θ a priemer najlepších nájdených hodnôt cez 5 behov.

| Sloty | Predvolené θ | CMA-ES | Náhodné hľadanie | Grid (16 bodov) | Zlepšenie CMA-ES |
| --- | --- | --- | --- | --- | --- |
| 2 | 41,23 | 41,36 | 41,27 | 39,90 | +0,3 % |
| 3 | 32,52 | 33,72 | 33,34 | 32,40 | +3,7 % |
| 4 | 35,37 | 37,38 | 37,35 | 34,80 | +5,7 % |
| 8 | 33,28 | 34,61 | 34,59 | 33,03 | +4,0 % |
| 12 | 36,09 | 36,41 | 36,52 | 35,23 | +0,9 % |
| 24 | 36,40 | 37,33 | 37,26 | 35,61 | +2,6 % |

**Tabuľka 5.2.** θ z najlepšieho behu CMA-ES, ktoré sa použije na teste.

| Sloty | α_am | α_pm | γ | R (prepočty za deň) | F(θ) |
| --- | --- | --- | --- | --- | --- |
| 2 | 1,29 | 0,50 | 0,95 | 2,9 | 41,63 |
| 3 | 0,82 | 0,82 | 0,96 | 1,1 | 34,18 |
| 4 | 0,87 | 0,49 | 1,65 | 10,0 | 37,54 |
| 8 | 0,84 | 0,65 | 1,67 | 71,9 | 34,75 |
| 12 | 0,68 | 1,02 | 1,95 | 9,6 | 36,55 |
| 24 | 0,84 | 1,10 | 1,52 | 4,5 | 37,66 |

Zistenia:

- **Ladenie pomáha najviac pri 3–8 slotoch** (+3,7 až +5,7 %). Pri 2 slotoch nie je takmer čo zlepšovať: s dvoma dlhými slotmi je aj flat rate blízko optimu (sekcia 8).
- **CMA-ES a náhodné hľadanie sú rovnako dobré**, rozdiely 0,02–0,4 jednotky, pri 12 slotoch je náhodné hľadanie dokonca mierne lepšie. Grid search je pri rovnakom rozpočte najhorší, lebo 16 bodov mriežky pokryje priestor príliš hrubo.
- **Okolie optima je ploché.** Rôzne behy nachádzajú dosť odlišné θ (napríklad R od 0 do 72 prepočtov za deň) s takmer rovnakou hodnotou F. Pri 50 inštanciách sú rozdiely medzi najlepšími θ menšie ako štandardná chyba priemeru. Pre CMA-ES to znamená, že nemá čo sledovať: učenie tvaru rozdelenia pomáha pri úzkych údoliach, nie pri plochom a nehladkom povrchu. To vysvetľuje, prečo nie je lepšie ako náhodné hľadanie.
- **Stabilné sú len niektoré parametre.** α_am vychádza vo všetkých konfiguráciách 0,7–1,3, teda blízko α = 1 (μ z LP sú približne správne). Pri 4 a viac slotoch je γ = 1,5–2: politika funguje lepšie, keď LP počíta s vyšším dopytom, než je priemer, a teda cení sloty vyššie. Vysvetľujeme to tým, že fluidný LP nevidí náhodné kolísanie dopytu a hodnotu vzácnej kapacity v špičke podceňuje. Toto vysvetlenie je naša hypotéza, samostatne sme ho neoverovali.
- **Kontrola na väčšej vzorke.** Pri 4 slotoch sme ladenie zopakovali s 200 tréningovými inštanciami (2 behy): predvolené θ 35,97, CMA-ES 36,75, náhodné hľadanie 36,79, flat rate 34,44. Zlepšenie sa zmenší z 5,7 % na 2,2 %. Hodnoty na 50 inštanciách sú teda čiastočne preučené a výber najlepšieho z piatich behov ich ďalej nadhodnocuje. Skutočný prínos ladenia preto posudzujeme až na testovacích inštanciách (sekcia 8).

Konvergenciu najlepšej hodnoty podľa počtu vyhodnotení ukazuje Obr. 8.x (`results/figures/tuning_convergence.png`). Pri 4 slotoch a 200 inštanciách je CMA-ES blízko konečnej hodnoty už po 10 vyhodnoteniach (99–100 %), náhodné hľadanie sa k nej dostane po 20–40 vyhodnoteniach.

## 5.6 Hybrid MCTS a horná hranica

**Hybrid MCTS (Člen C).** MCTS autorov odhaduje hodnotu listu náhodným rolloutom, pri dlhom horizonte veľmi zašumeným. V hybride rollout hrá bid-price politika s μ vypočítanými na začiatku dňa, ostatné časti MCTS (výber, expanzia, spätné šírenie, 3000 iterácií) zostávajú ako v sekcii 4. Rollout je tak rýchly (bez riešenia LP) a hrá rozumné ceny namiesto náhodných.

**LP horná hranica (Člen A).** Optimálna hodnota toho istého LP so začiatočnou kapacitou a dopytom celého dňa je horná hranica očakávaných tržieb každej politiky, ktorá nepozná budúcnosť (Gallego a van Ryzin, 1997). Na rozdiel od VI ju vieme spočítať pre ľubovoľný počet slotov, takže dáva referenciu aj pri 12–72 slotoch. Pre Oracle hranicou nie je, lebo Oracle budúcnosť pozná.

## 5.7 Implementácia a zložitosť

| Časť | Súbor | Testy | Online čas na deň |
| --- | --- | --- | --- |
| LP a vstupy | `src/mpo_ev/lp.py` | `tests/test_lp.py` | 0,04 s na jedno riešenie (24 slotov) |
| Bid-price politika | `src/mpo_ev/policies/bidprice.py` | `tests/test_bidprice.py` | 0,2 s (bez prepočtu), 0,3 s (naladená), 24 slotov |
| Ladenie θ | `src/mpo_ev/tuning.py` | `tests/test_tuning.py` | offline, 3–85 min na konfiguráciu |
| Oracle (referencia) | `src/mpo_ev/policies/oracle.py` | `tests/test_oracle.py` | 0,02 s na inštanciu |

Výpočtová náročnosť politiky je daná počtom riešení LP, nie dĺžkou horizontu: jedno rozhodnutie bez prepočtu je výber z 19 sadzieb. Ladenie spustí `python -m mpo_ev.tuning --slots 24 --runs 5 --budget 60 --n-train 50 --jobs 2`, výstupy sú v `results/params/` a `results/tuning_<s>s.csv`. Pri rovnakom seede je ladenie reprodukovateľné. Výsledok nezávisí od počtu procesov (test `test_evaluator_fitness_deterministic_and_parallel_equal`).

**Obmedzenia návrhu** (podrobnejšie v sekcii 11):
- LP pracuje s priemerným dopytom, preto μ pri kapacite 3 hodnotu slotov iba aproximuje. Ladenie γ a α to len čiastočne koriguje.
- Politika plne verí modelu dopytu, a preto je citlivá na chybne odhadnutý rozpočet zákazníkov (E4, sekcia 8).

## Literatúra k sekcii

- Gallego, G., van Ryzin, G. (1997). A multiproduct dynamic pricing problem and its applications to network yield management. *Operations Research*, 45(1), 24–41.
- Talluri, K., van Ryzin, G. (1998). An analysis of bid-price controls for network revenue management. *Management Science*, 44(11), 1577–1593.
- Talluri, K., van Ryzin, G. (2004). *The Theory and Practice of Revenue Management*. Springer.
- Hansen, N. (2016). The CMA Evolution Strategy: A Tutorial. arXiv:1604.00772.
- Bergstra, J., Bengio, Y. (2012). Random search for hyper-parameter optimization. *Journal of Machine Learning Research*, 13, 281–305.
