# 7. Experimentálna metodológia

<!-- Vytvorené s pomocou Claude, upravil: Člen C. Čísla zodpovedajú behu v results/run_meta.json. -->

## Porovnávané metódy

| Metóda | Typ | Čo vidí | Zdroj |
| --- | --- | --- | --- |
| Oracle | referencia, nie politika | celú inštanciu vrátane rozpočtov | binárny program (rov. 11–12), Člen B |
| LP horná hranica | referencia | model dopytu | fluidný LP, Člen A a B |
| VI | optimum MDP | model dopytu | spätná indukcia, Člen C |
| Flat rate | politika článku | tréningové inštancie | jedna sadzba z mriežky, Člen A |
| MCTS | metóda článku | model dopytu | UCT, náhodný rollout, Člen C |
| Bid-price | naša metóda | model dopytu | duálne ceny LP, Člen B |
| Bid-price (CMA-ES) | naša metóda | model + tréningové inštancie 0–49 | θ ladené CMA-ES, prepočet LP počas dňa, Člen B |
| Hybrid MCTS | naša metóda | model dopytu | MCTS s bid-price rolloutom, Člen C |

## Férovosť porovnania

- **Rovnaké inštancie.** Všetky metódy sa hodnotia na tých istých testovacích inštanciách (seedy 1000–1099), ktoré sa generujú deterministicky zo seedu. Rozdiely medzi metódami preto meriame párovo, na tej istej inštancii, s rovnakými rozpočtami zákazníkov.
- **Rovnaké vyhodnotenie a mriežka.** Jediný simulátor (`run_episode`) rozhoduje o nákupe podľa skrytého rozpočtu, metódy vidia len stav (krok, kapacita, produkt) a ponúkajú ceny z rovnakej mriežky A. Pravdepodobnosti berú len z modelu dopytu, nie z konfigurácie inštancie.
- **Oddelenie tréningu a testu.** Flat rate, ladenie θ (CMA-ES) aj grid search MCTS používajú výhradne tréningové seedy 0–199. Testovacie inštancie sa na žiadne rozhodnutie o parametroch nepoužili.
- **Výpočtový rozpočet.** Pri ladení θ majú CMA-ES, náhodné hľadanie a mriežka rovnaký rozpočet: 60 vyhodnotení F(θ) na beh, 5 behov (seedy 0–4), F(θ) = priemerné tržby na 50 tréningových inštanciách (seedy 0–49), ukončenie po vyčerpaní rozpočtu. Mriežka pri 60 vyhodnoteniach stihne len 2⁴ = 16 bodov. Návod plánoval 10 behov × 100 vyhodnotení × 200 inštancií; to by pri 24 slotoch trvalo asi 76 CPU-hodín (jedno vyhodnotenie na 200 inštanciách asi 4,5 min), preto Člen B rozpočet znížil (`config/tuning.yaml`). Do E1, E2 a E4 ide θ z behu CMA-ES s najvyššou tréningovou hodnotou; θ pre E2 je z 24 slotov pri λ = 76,28, teda prenesené na iný dopyt. MCTS a hybrid majú rovnaký počet iterácií na rozhodnutie (3000), líšia sa len rolloutom (a d_max a c, ktoré sú pre každý zvolené zvlášť tým istým grid searchom). Rollout hybridu hrá bid-price s naladenými α a γ z ladenia θ, μ sa počítajú raz pri reset; parameter prepočtu LP sa v rolloute nepoužíva.
- **Kritériá ukončenia.** CMA-ES končí po vyčerpaní rozpočtu vyhodnotení, MCTS po pevnom počte iterácií, flat rate a VI sú deterministické.
- **Online a offline čas.** `runtime_s` je online čas politiky za jeden deň (reset + všetky rozhodnutia). Offline príprava (tréning flat rate na 200 inštanciách, výpočet tabuľky VI, ladenie θ, pri ktorom uvádzame čas jedného behu CMA-ES) sa meria zvlášť (`results/<exp>_offline.csv`) a uvádzame ju v tabuľke časov.

## Opakovania a seedy

| Náhodnosť | Seed (config/base.yaml) |
| --- | --- |
| tréningové inštancie | 0–199 |
| testovacie inštancie | 1000–1099 |
| pilot (podmnožina testu) | 1000–1029 |
| MCTS a hybrid (náhodnosť politiky) | seed inštancie + 50 000 |
| behy CMA-ES a náhodného hľadania | 0–4 (5 behov) |
| tréningové inštancie pre ladenie θ | 0–49 |
| odhad podielov produktov (Monte Carlo, 10⁶ vzoriek) | 20261106 |

Stochastické sú MCTS, hybrid a CMA-ES. MCTS beží na každej zo 100 inštancií s iným seedom, takže variabilita cez inštancie zahŕňa aj náhodnosť algoritmu. Pre každú metódu a konfiguráciu uvádzame priemer, štandardnú chybu, medián, smerodajnú odchýlku, minimum a maximum tržieb, ďalej pomer k Oracle, k LP hranici a k flat rate, počet prijatých požiadaviek, vyťaženie a čas.

**Štatistické testy.** Rozdiel dvoch metód testujeme párovým Wilcoxonovým testom na rovnakých inštanciách (rozdiely nemusia byť normálne rozdelené). Hlavná rodina testov sú porovnania s MCTS (bid-price vs. MCTS, naladená bid-price vs. MCTS, hybrid vs. MCTS) cez všetky konfigurácie experimentu; jej p-hodnoty korigujeme Holmovou metódou. Ostatné porovnania (s flat rate, VI vs. bid-price) tvoria druhú rodinu s vlastnou korekciou. Uvádzame aj nekorigované p, počet výhier a priemerný rozdiel ± SE.

## Experimenty

| Experiment | Otázka | Nastavenie | Konfigurácia |
| --- | --- | --- | --- |
| Grid search (3.8) | Ako nastaviť MCTS? | n_iter ∈ {10, 30, 100, 300, 1000, 3000, 10 000} × d_max ∈ {1, 3, 8, 15} × c ∈ {0,5; 1; 3; 6; 10}, MCTS aj hybrid, inštancia z č. 6.3.1 (12 slotov, 96 krokov, λ = 24), 30 tréningových inštancií | `config/mcts_grid.yaml` |
| E1 | Ako sa metódy správajú pri jemnejšom delení dňa? | 2–72 slotov, K a λ z Tab. 2 článku, 100 inštancií; VI do 8 slotov, MCTS a hybrid do 24 slotov | `config/e1.yaml` |
| E2 | Ako sa metódy správajú pri rastúcom dopyte? | 24 slotov, λ = 24–240 (10 úrovní), K z Err₂/λ = 0,06 (192–1920 krokov), 100 inštancií (MCTS a hybrid 30) | `config/e2.yaml` |
| E3 (Člen B) | Čo prinesie ladenie θ? | CMA-ES vs. náhodné hľadanie vs. mriežka, 5 behov × 60 vyhodnotení × 50 tréningových inštancií pre každú metódu | `config/tuning.yaml` |
| E4 (Člen A) | Ako citlivé sú metódy na chybný model dopytu? | politika verí λ × 0,7 / 1,3 alebo priemeru rozpočtu 0,8 / 1,2, mriežka s krokom 0,10 a 0,025; MCTS a hybrid 30 inštancií | `config/e4.yaml` |

**Voľba parametrov MCTS.** Článok uvádza dve rôzne nastavenia (č. 5.2.1: 800 iterácií, d_max = 3, c = 1; č. 6.3.1: 10 000, 10, 3). Grid search sme zopakovali na rovnakej inštancii ako autori, ale na tréningových seedoch a s 30 namiesto 100 sekvencií (10 000 iterácií trvá v Pythone asi 12 s na deň a grid má 280 kombinácií). Rovnako ako v článku rozhoduje počet iterácií, vplyv d_max a c je v rámci štandardnej chyby. Tržby sa ustália od asi 1000 iterácií: priemer cez všetky d_max a c je 25,7 pri 1000, 25,6 pri 3000 a 26,0 pri 10 000 iteráciách, pričom 10 000 iterácií je trikrát pomalších. Volíme preto 3000 iterácií a pri nich najlepšie d_max a c: MCTS d_max = 8, c = 10, hybrid d_max = 3, c = 1 (`config/mcts.yaml`). Rozpor v článku tak v našom modeli o výsledku nerozhoduje.

**Znížený rozsah.** VI beží do 8 slotov (pri 9 slotoch má 4⁹ stavov kapacity na krok). MCTS a hybrid obmedzujeme na 24 slotov podľa schváleného rozsahu: pri 36 a 72 slotoch by v Pythone trvali minúty na deň (článok v Julii 94 s a 450 s). Na 36 a 72 slotoch preto bežia len flat rate, bid-price, Oracle a LP hranica. V E2 a E4 hodnotíme MCTS a hybrid na prvých 30 testovacích inštanciách; pomer k Oracle a párové rozdiely sa počítajú na tých istých 30 inštanciách.

## Reprodukovateľnosť

Všetko spustí jeden príkaz `python run_experiments.py` (README), jednotlivý experiment `python run_experiments.py --config config/e1.yaml`. Metódy sa vyberajú podľa mena z registra, úlohy bežia paralelne a výsledok nezávisí od počtu procesov (test `test_chunked_parallel_equals_sequential`). Hotové úlohy sa ukladajú, takže prerušený beh pokračuje. Výsledky sa zapisujú do `results/` v dohodnutom formáte CSV (`experiment, config_id, method, instance_seed, run_seed, revenue, utilization_h, n_requests, n_accepted, runtime_s`), súhrny do `*_summary.csv`, tabuľky do `results/tables.md` a grafy do `results/figures/` (`analysis.py` alebo `analysis.ipynb`). Súbor `results/run_meta.json` zaznamenáva verzie knižníc, git hash, platformu, seedy a parametre MCTS.
