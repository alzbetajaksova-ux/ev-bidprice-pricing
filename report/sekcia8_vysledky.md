# 8. Dosiahnuté výsledky

<!-- Vytvorené s pomocou Claude, upravil: Člen C. Čísla z finálneho behu (results/run_meta.json,
results/*_summary.csv, results/tables.md). Bid-price s naladeným θ (CMA-ES) doplní Člen B po behu
tuning.py; runner ho potom zaradí automaticky. -->

Všetky tržby sú v jednotkách článku (sadzba za hodinu × hodiny). SE je štandardná chyba priemeru, p je párový Wilcoxonov test na rovnakých inštanciách a p_Holm je p-hodnota po Holmovej korekcii (rodina porovnaní s MCTS, resp. rodina ostatných porovnaní, cez všetky konfigurácie experimentu). Bid-price je predvolená politika (α = 1, γ = 1, bez prepočtu LP); verzia s θ naladeným cez CMA-ES sa doplní po dokončení úlohy 4.4.

## Nastavenie MCTS (grid search, úloha 3.8)

**Obr. 8.1** (`results/figures/mcts_grid.png`). Priemerné tržby MCTS (hore) a hybridu (dole) na inštancii z č. 6.3.1 (12 slotov, 96 krokov, λ = 24, 30 tréningových inštancií) podľa počtu iterácií, d_max a c. Prerušované čiary sú flat rate (25,6) a bid-price (25,7) na tých istých inštanciách, Oracle dáva 42,7.

Tržby rastú s logaritmom počtu iterácií od 19,3 pri 10 iteráciách po asi 25,5 pri 1000 a potom sa ustália: priemer cez všetky d_max a c je pri MCTS 25,7 (1000 iterácií), 25,6 (3000) a 26,0 (10 000), pri hybride 25,0, 25,8 a 26,1. Rozdiely medzi d_max a c pri rovnakom počte iterácií sú menšie ako štandardná chyba (asi 1,4), d_max = 3, 8 a 15 dávajú pri menej ako 1000 iteráciách rovnaké výsledky, lebo strom s 20 akciami a náhodnými prechodmi do väčšej hĺbky takmer nerastie. Flat rate a bid-price MCTS dosiahne až pri asi 1000 iteráciách. Čas rastie lineárne s počtom iterácií (**Obr. 8.2**, `mcts_grid_runtime.png`): 1,1 s, 4,0 s a 12,2 s na deň pri 1000, 3000 a 10 000 iteráciách. Zvolili sme 3000 iterácií (MCTS d_max = 8, c = 10, hybrid d_max = 3, c = 1), zdôvodnenie je v sekcii 7.

## E1: dĺžka slotu

**Tabuľka 8.1.** Priemerné tržby na 100 testovacích inštanciách (± SE). VI beží do 8 slotov, MCTS a hybrid do 24 slotov.

| Sloty | Oracle | LP hranica | VI | Flat | Bid-price | MCTS | Hybrid MCTS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 65,54 ± 2,14 | 48,71 | 41,52 ± 1,64 | 41,05 ± 1,57 | 39,89 ± 1,47 | 39,98 ± 1,59 | 39,21 ± 1,74 |
| 3 | 54,14 ± 1,34 | 44,20 | 34,55 ± 1,26 | 33,12 ± 1,17 | 33,32 ± 1,36 | 34,53 ± 1,22 | 32,35 ± 1,33 |
| 4 | 54,13 ± 1,24 | 43,82 | 35,33 ± 1,08 | 32,46 ± 1,08 | 33,83 ± 1,35 | 34,13 ± 1,02 | 34,74 ± 1,13 |
| 8 | 55,72 ± 0,87 | 46,12 | 36,82 ± 0,86 | 34,24 ± 0,88 | 34,93 ± 0,87 | 34,28 ± 0,80 | 33,88 ± 0,81 |
| 12 | 55,11 ± 0,78 | 47,67 | – | 32,77 ± 0,84 | 35,33 ± 0,87 | 34,44 ± 0,73 | 33,90 ± 0,80 |
| 24 | 57,18 ± 0,78 | 50,97 | – | 33,63 ± 0,69 | 35,36 ± 0,81 | 34,32 ± 0,60 | 35,28 ± 0,65 |
| 36 | 58,67 ± 0,67 | 52,95 | – | 34,43 ± 0,68 | 36,21 ± 0,81 | – | – |
| 72 | 59,97 ± 0,81 | 56,60 | – | 34,06 ± 0,72 | 35,65 ± 0,89 | – | – |

Mediány, smerodajné odchýlky, minimá, maximá a pomery k Oracle, LP hranici a flat rate sú v `results/e1_summary.csv` a `results/tables.md`.

**Tabuľka 8.2.** Čas na jeden deň: online (reset + všetky rozhodnutia) a offline príprava.

| Metóda | Online, 4 sloty | Online, 24 slotov | Online, 72 slotov | Offline príprava |
| --- | --- | --- | --- | --- |
| Flat rate | < 0,001 s | < 0,001 s | < 0,001 s | 0,6 s (4 sloty) až 2,8 s (72 slotov), tréning na 200 inštanciách |
| VI | 0,001 s | – | – | 0,04 s (4 sloty), 62 s (8 slotov), tabuľka W |
| Bid-price | 0,013 s | 0,20 s | 1,4 s | žiadna (LP pri reset je v online čase) |
| MCTS | 2,2 s | 17,5 s | – | žiadna |
| Hybrid MCTS | 2,4 s | 18,6 s | – | žiadna |
| Oracle (referencia) | 0,022 s | 0,018 s | 0,017 s | – |

**Obr. 8.3** (`results/figures/e1_ratio_runtime.png`). Vľavo pomer k Oracle podľa dĺžky slotu s LP hranicou (bodkovane) a hodnotami z Tab. 2 článku (prerušovane). Vpravo online čas politiky na deň (logaritmická os).

Interpretácia:

- **VI je najlepšia politika všade, kde beží.** Pri 2–8 slotoch je o 1,2–1,9 jednotky nad bid-price (p_Holm = 0,008 pri 2 slotoch a 0,011 pri 8 slotoch). Hodnota V₀ (40,97 / 36,32 / 36,17 / 36,45) sedí so simulovanými tržbami politiky VI v rámci 2 SE, čo potvrdzuje simulátor aj VI.
- **LP hranica je platná, ale voľná.** Je o 19–27 % nad VI. Preto pri 12–72 slotoch, kde VI nebeží, medzera k LP hranici (26–40 %) neznamená, že metódy zaostávajú o toľko za optimom. Pomer LP/Oracle klesá z 0,94 pri 72 slotoch na 0,74 pri 2 slotoch.
- **Bid-price vs. MCTS.** Pri 2, 4 a 8 slotoch sú rozdiely v rámci šumu (p ≥ 0,31), pri 3 slotoch je MCTS lepšie o 1,2 jednotky (p = 0,04, p_Holm = 0,37). Pri 12 a 24 slotoch je bid-price lepšia o 0,9 a 1,0 jednotky (+2,6 % a +3,1 %, p = 0,036 a 0,023), po Holmovej korekcii však rozdiel nie je štatisticky významný (p_Holm = 0,36 a 0,25). Bid-price pritom potrebuje asi 1/90 času MCTS (0,20 s vs. 17,5 s na deň pri 24 slotoch). Záver: bid-price dosahuje tržby MCTS za zlomok času, preukázateľne lepšia nie je.
- **Hybrid MCTS** nie je konzistentne lepší ako MCTS: pri 4 a 24 slotoch o 0,6–1,0 jednotky lepší, pri 3 slotoch o 2,2 horší (p = 0,017), žiadny rozdiel po korekcii nie je významný. Rollout s pevnými μ z rána nevie, že kapacita sa počas dňa minula, a pri malom počte slotov je to väčšia chyba než šum náhodného rolloutu.
- **Flat rate** je pri 2 slotoch najlepšia heuristika (bid-price o 2,8 % horšia, p_Holm < 0,001), pri 12 slotoch a viac je najhoršia: bid-price je o 7,8 % (12 slotov, p_Holm = 0,001), 5,1 % (24 slotov, p_Holm = 0,026), 5,2 % a 4,7 % (36 a 72 slotov, p = 0,03 a 0,04, po korekcii nevýznamné) lepšia. Pri dvoch dlhých slotoch skoro nie je čo dynamicky oceňovať.
- **Variabilita.** Smerodajná odchýlka tržieb cez inštancie (6–17) je rádovo väčšia ako rozdiely medzi metódami (do 3), preto rozdiely posudzujeme párovo. Rozdelenie tržieb pri 4 a 24 slotoch ukazujú **Obr. 8.4 a 8.5** (`distribution_4s.png`, `distribution_24s.png`, obdoba Obr. 9 článku). MCTS ako stochastická metóda nemá väčší rozptyl ako deterministické politiky.

## E2: rastúci dopyt

**Obr. 8.6** (`results/figures/e2_demand.png`). Priemerné tržby (± 2 SE) pri 24 slotoch pre λ = 24 až 240, K = 192 až 1920 krokov, s LP hranicou. Flat, bid-price a Oracle 100 inštancií, MCTS a hybrid 30 inštancií.

**Tabuľka 8.3.** Pomer k Oracle (vybrané λ; všetky úrovne v `results/e2_summary.csv`).

| λ | Flat | Bid-price | MCTS | Hybrid MCTS |
| --- | --- | --- | --- | --- |
| 24 | 0,573 | 0,554 | 0,567 | 0,584 |
| 72 | 0,581 | 0,614 | 0,608 | 0,615 |
| 120 | 0,594 | 0,619 | 0,584 | 0,626 |
| 192 | 0,610 | 0,628 | 0,605 | 0,644 |
| 240 | 0,617 | 0,613 | 0,590 | 0,613 |

Tržby všetkých metód rastú s dopytom (flat 20,0 → 48,3, Oracle 35,0 → 78,3), rovnako ako v Obr. 10 článku. Pri nízkom dopyte (λ = 24) je flat rate lepšia ako bid-price (p_Holm = 0,04), lebo kapacita takmer nie je obmedzením. Od λ = 48 je bid-price nad flat rate o 3–8,5 %, po korekcii je to významné len pri λ = 216 (+8,5 %, p_Holm = 0,008). **MCTS pri vysokom dopyte zaostáva**: od λ = 144 je v priemere pod flat rate. Hybrid ho prekonáva o 2,8–4,0 jednotky pri λ = 120, 192 a 216 (p = 0,02; 0,006; < 0,001), po korekcii je významné λ = 216 (p_Holm = 0,003). Bid-price je nad MCTS o 5,1 jednotky pri λ = 120 (p_Holm = 0,015). Pri dlhom horizonte (až 240 požiadaviek) je náhodný rollout veľmi zašumený a 3000 iterácií nestačí; to je najvýraznejší prínos hybridu. Pri λ = 240 bid-price bez prepočtu LP stratí výhodu nad flat rate (p = 0,81): pevné μ z rána pri veľkom dopyte zle odhadujú hodnotu kapacity večer. Online čas MCTS rastie s dopytom z 2,8 s na 74 s na deň, bid-price zostáva okolo 0,2 s.

## E4: robustnosť

**Obr. 8.7** (`results/figures/e4_robustness.png`). Pokles priemerných tržieb v % oproti nominálnemu modelu (± 2 SE párových rozdielov). Politika verí chybnému modelu, simulácia beží so správnym. Flat a bid-price 100 inštancií, MCTS a hybrid 30.

**Tabuľka 8.4.** Pokles tržieb v % (± SE) pri 12 a 24 slotoch; všetky konfigurácie sú v `results/e4_summary.csv` a `results/tables.md`.

| Scenár | Flat 12 / 24 | Bid-price 12 / 24 | MCTS 12 / 24 | Hybrid 12 / 24 |
| --- | --- | --- | --- | --- |
| λ × 0,7 | −0,9 ± 1,0 / 1,3 ± 0,9 | 2,7 ± 1,6 / 2,4 ± 1,6 | 0,8 ± 2,1 / 0,4 ± 2,4 | 5,4 ± 2,8 / −1,9 ± 2,9 |
| λ × 1,3 | 3,7 ± 2,0 / 0,0 | 4,7 ± 1,5 / 6,2 ± 1,7 | 1,7 ± 3,1 / −1,7 ± 2,1 | 3,9 ± 2,7 / −1,8 ± 3,3 |
| rozpočet 0,8 | 0,1 ± 1,4 / 5,8 ± 1,3 | 4,2 ± 1,8 / 4,4 ± 1,9 | 6,8 ± 2,5 / 5,9 ± 2,2 | 6,2 ± 2,5 / 3,5 ± 2,5 |
| rozpočet 1,2 | −0,2 ± 1,4 / 5,2 ± 2,0 | 11,9 ± 2,5 / 13,1 ± 2,4 | 1,6 ± 2,8 / −4,6 ± 2,8 | 2,8 ± 3,2 / 3,3 ± 3,8 |
| mriežka 0,10 | −0,2 ± 1,4 / −1,8 ± 1,3 | −0,7 ± 1,2 / −0,1 ± 1,0 | 1,3 ± 2,5 / −3,8 ± 2,3 | 6,0 ± 3,4 / 5,8 ± 2,3 |
| mriežka 0,025 | 0,0 / −1,4 ± 0,8 | 0,2 ± 0,7 / 0,4 ± 0,7 | 0,9 ± 2,7 / −0,5 ± 2,2 | 3,0 ± 2,6 / −0,5 ± 2,6 |

Interpretácia:

- **Bid-price je citlivá na nadhodnotený rozpočet.** Ak politika verí priemeru 1,2 namiesto 1,0, nadhodnocuje pravdepodobnosť nákupu a ponúka privysoké sadzby. Pokles je 6,6–16,6 % pri 3–24 slotoch, vždy viac ako 2 SE. Podhodnotený rozpočet (0,8) stojí 3,8–9,2 %. Chyba λ stojí 1–6 %, najviac nadhodnotený dopyt pri 24 slotoch (6,2 %): LP potom μ nadhodnotí a politika odmieta príliš veľa.
- **Flat rate je najrobustnejšia.** Sadzbu vyberá podľa tréningových tržieb z modelu, ktorému verí, ale chybný model často vedie k tej istej alebo susednej sadzbe. Najväčší pokles je 7,7 % (2 sloty, rozpočet 0,8).
- **MCTS** stráca pri podhodnotenom rozpočte 5,9–12,1 % pri 3–24 slotoch (viac ako 2 SE okrem 3 slotov), pri 2 slotoch len 0,9 %. Pri ostatných scenároch je zmena väčšinou v rámci šumu: pri 30 inštanciách a stochastickom strome je štandardná chyba 2–4,4 %, takže menšie poklesy nevieme rozlíšiť.
- **Mriežka cien.** Krok kvantilov 0,10 ani 0,025 nemení tržby flat ani bid-price o viac ako 2,4 %. Náš predpoklad kroku 0,05 (nejasnosť 1) teda výsledky podstatne neovplyvňuje.
- **Dôsledok pre porovnanie.** Bid-price je pri správnom modeli rovnako dobrá ako MCTS a asi 90× rýchlejšia, no pri chybe v rozpočte zákazníkov stráca viac. Pri nasadení by sa oplatilo odhadovať rozdelenie rozpočtu z dát priebežne, alebo ladiť α a γ cez CMA-ES na dátach, nie na modeli.

## Konvergencia ladenia θ (E3, Člen B)

\[doplní Člen B: `results/figures/tuning_convergence.png` vznikne automaticky z `results/tuning_*.csv` po behu `python -m mpo_ev.tuning`\]
