# 8. Dosiahnuté výsledky

<!-- Vytvorené s pomocou Claude, upravil: Člen C. Čísla z finálneho behu (results/run_meta.json,
results/*_summary.csv, results/tables.md), vrátane naladeného θ od Člena B (results/params/). -->

Všetky tržby sú v jednotkách článku (sadzba za hodinu × hodiny). SE je štandardná chyba priemeru, p je párový Wilcoxonov test na rovnakých inštanciách a p_Holm je p-hodnota po Holmovej korekcii (rodina porovnaní s MCTS, resp. rodina ostatných porovnaní, cez všetky konfigurácie experimentu). **Bid-price** je predvolená politika (α = 1, γ = 1, μ raz pri reset, bez prepočtu LP). **Bid-price (CMA-ES)** má θ naladené Členom B (E3, sekcia 5): α pre dopoludnie a popoludnie, korekciu dopytu γ, periodický prepočet LP a prepočet po každom predaji. **Hybrid MCTS** používa v rolloute bid-price s naladenými α a γ.

## Nastavenie MCTS (grid search, úloha 3.8)

**Obr. 8.1** (`results/figures/mcts_grid.png`). Priemerné tržby MCTS (hore) a hybridu (dole) na inštancii z č. 6.3.1 (12 slotov, 96 krokov, λ = 24, 30 tréningových inštancií) podľa počtu iterácií, d_max a c. Prerušované čiary sú flat rate (25,6) a predvolená bid-price (25,7) na tých istých inštanciách, Oracle dáva 42,7.

Tržby rastú s logaritmom počtu iterácií od 19,3 pri 10 iteráciách po asi 25,5 pri 1000 a potom sa ustália: priemer cez všetky d_max a c je pri MCTS 25,7 (1000 iterácií), 25,6 (3000) a 26,0 (10 000), pri hybride 25,0, 25,8 a 26,1. Rozdiely medzi d_max a c pri rovnakom počte iterácií sú menšie ako štandardná chyba (asi 1,4), d_max = 3, 8 a 15 dávajú pri menej ako 1000 iteráciách rovnaké výsledky, lebo strom s 20 akciami a náhodnými prechodmi do väčšej hĺbky takmer nerastie. Flat rate a bid-price MCTS dosiahne až pri asi 1000 iteráciách. Čas rastie lineárne s počtom iterácií (**Obr. 8.2**, `mcts_grid_runtime.png`): 1,1 s, 4,0 s a 12,2 s na deň pri 1000, 3000 a 10 000 iteráciách. Zvolili sme 3000 iterácií (MCTS d_max = 8, c = 10, hybrid d_max = 3, c = 1), zdôvodnenie je v sekcii 7. Grid search bežal ešte s predvolenou bid-price v rolloute hybridu.

## E1: dĺžka slotu

**Tabuľka 8.1.** Priemerné tržby na 100 testovacích inštanciách (± SE). VI beží do 8 slotov, MCTS a hybrid do 24 slotov, θ je naladené pre 2–24 slotov.

| Sloty | Oracle | LP hranica | VI | Flat | Bid-price | Bid-price (CMA-ES) | MCTS | Hybrid MCTS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 65,54 ± 2,14 | 48,71 | 41,52 ± 1,64 | 41,05 ± 1,57 | 39,89 ± 1,47 | 39,91 ± 1,60 | 39,98 ± 1,59 | 40,19 ± 1,70 |
| 3 | 54,14 ± 1,34 | 44,20 | 34,55 ± 1,26 | 33,12 ± 1,17 | 33,32 ± 1,36 | 34,76 ± 1,18 | 34,53 ± 1,22 | 34,16 ± 1,28 |
| 4 | 54,13 ± 1,24 | 43,82 | 35,33 ± 1,08 | 32,46 ± 1,08 | 33,83 ± 1,35 | 35,37 ± 1,12 | 34,13 ± 1,02 | 33,75 ± 1,10 |
| 8 | 55,72 ± 0,87 | 46,12 | 36,82 ± 0,86 | 34,24 ± 0,88 | 34,93 ± 0,87 | 36,68 ± 0,83 | 34,28 ± 0,80 | 34,52 ± 0,84 |
| 12 | 55,11 ± 0,78 | 47,67 | – | 32,77 ± 0,84 | 35,33 ± 0,87 | 36,61 ± 0,73 | 34,44 ± 0,73 | 34,67 ± 0,81 |
| 24 | 57,18 ± 0,78 | 50,97 | – | 33,63 ± 0,69 | 35,36 ± 0,81 | 37,40 ± 0,69 | 34,32 ± 0,60 | 35,87 ± 0,63 |
| 36 | 58,67 ± 0,67 | 52,95 | – | 34,43 ± 0,68 | 36,21 ± 0,81 | – | – | – |
| 72 | 59,97 ± 0,81 | 56,60 | – | 34,06 ± 0,72 | 35,65 ± 0,89 | – | – | – |

Mediány, smerodajné odchýlky, minimá, maximá a pomery k Oracle, LP hranici a flat rate sú v `results/e1_summary.csv` a `results/tables.md`.

**Tabuľka 8.2.** Čas na jeden deň: online (reset + všetky rozhodnutia) a offline príprava.

| Metóda | Online, 4 sloty | Online, 24 slotov | Online, 72 slotov | Offline príprava |
| --- | --- | --- | --- | --- |
| Flat rate | < 0,001 s | < 0,001 s | < 0,001 s | 0,6 s (4 sloty) až 2,8 s (72 slotov), tréning na 200 inštanciách |
| VI | 0,001 s | – | – | 0,04 s (4 sloty), 62 s (8 slotov), tabuľka W |
| Bid-price | 0,013 s | 0,20 s | 1,4 s | žiadna (LP pri reset je v online čase) |
| Bid-price (CMA-ES) | 0,06 s | 1,25 s | – | 30 s (4 sloty) až 469 s (24 slotov) na jeden beh CMA-ES, 5 behov |
| MCTS | 2,2 s | 17,5 s | – | žiadna |
| Hybrid MCTS | 2,1 s | 20,4 s | – | ladenie θ (zdieľané s bid-price) |
| Oracle (referencia) | 0,022 s | 0,018 s | 0,017 s | – |

**Obr. 8.3** (`results/figures/e1_ratio_runtime.png`). Vľavo pomer k Oracle podľa dĺžky slotu s LP hranicou (bodkovane) a hodnotami z Tab. 2 článku (prerušovane). Vpravo online čas politiky na deň (logaritmická os).

Interpretácia:

- **Naladená bid-price je najlepšia heuristika.** Pri 8, 12 a 24 slotoch prekonáva MCTS o 2,4; 2,2 a 3,1 jednotky (+7,0 %, +6,3 %, +9,0 %, p_Holm < 0,001), pri 4 slotoch o 1,2 jednotky (p = 0,02, po korekcii nevýznamné). Pri 4 a 8 slotoch sa vyrovná optimálnej VI v rámci šumu (35,37 vs. 35,33 a 36,68 vs. 36,82). Online potrebuje 1,25 s na deň pri 24 slotoch, MCTS 17,5 s. Ladenie oproti predvolenej bid-price pridáva 0–5,8 % (najviac pri 24 slotoch, +2,0 jednotky, p_Holm = 0,012), čo zodpovedá 1–6 % na tréningových inštanciách (sekcia 5). Väčšiu časť zlepšenia pravdepodobne prináša prepočet LP počas dňa, ktorý predvolená bid-price nemá; samostatne sme ho neoddelili.
- **VI je optimum.** Pri 2–8 slotoch je o 1,2–1,9 jednotky nad predvolenou bid-price (p_Holm = 0,011 pri 2 slotoch a 0,015 pri 8 slotoch). Hodnota V₀ (40,97 / 36,32 / 36,17 / 36,45) sedí so simulovanými tržbami politiky VI v rámci 2 SE, čo potvrdzuje simulátor aj VI. Žiadna politika nemôže VI prekonať v očakávaní; rozdiely priemerov na 100 inštanciách (napr. 34,76 vs. 34,55 pri 3 slotoch) sú šum.
- **LP hranica je platná, ale voľná.** Je o 19–27 % nad VI. Preto pri 12–72 slotoch, kde VI nebeží, medzera k LP hranici (23–40 %) neznamená, že metódy zaostávajú o toľko za optimom. Pomer LP/Oracle klesá z 0,94 pri 72 slotoch na 0,74 pri 2 slotoch.
- **Predvolená bid-price vs. MCTS.** Rozdiely sú −1,2 až +1,0 jednotky a po Holmovej korekcii žiadny nie je významný. Bez ladenia teda bid-price dosahuje tržby MCTS za asi 1/90 času.
- **Hybrid MCTS** je pri 24 slotoch o 1,6 jednotky nad MCTS (+4,5 %, p = 0,004, p_Holm = 0,066), pri 2–12 slotoch sú rozdiely do 0,4 jednotky. Lepší rollout teda MCTS pomáha len pri dlhom horizonte; naladená bid-price samotná je lepšia aj rýchlejšia ako hybrid.
- **Flat rate** je pri 2 slotoch najlepšia z jednoduchých heuristík (predvolená bid-price o 2,8 % horšia, p_Holm < 0,001), pri 12 a 24 slotoch najhoršia (predvolená bid-price o 7,8 % a 5,1 % lepšia, p_Holm = 0,002 a 0,035; pri 36 a 72 slotoch o 5,2 % a 4,7 %, po korekcii nevýznamné). Pri dvoch dlhých slotoch skoro nie je čo dynamicky oceňovať.
- **Variabilita.** Smerodajná odchýlka tržieb cez inštancie (6–17) je rádovo väčšia ako rozdiely medzi metódami (do 3), preto rozdiely posudzujeme párovo. Rozdelenie tržieb pri 4 a 24 slotoch ukazujú **Obr. 8.4 a 8.5** (`distribution_4s.png`, `distribution_24s.png`, obdoba Obr. 9 článku). MCTS ako stochastická metóda nemá väčší rozptyl ako deterministické politiky.

## E2: rastúci dopyt

**Obr. 8.6** (`results/figures/e2_demand.png`). Priemerné tržby (± 2 SE) pri 24 slotoch pre λ = 24 až 240, K = 192 až 1920 krokov, s LP hranicou. Flat, bid-price a Oracle 100 inštancií, MCTS a hybrid 30 inštancií. θ je naladené pri 24 slotoch a λ = 76,28 a prenesené na ostatné λ.

**Tabuľka 8.3.** Pomer k Oracle (vybrané λ; všetky úrovne v `results/e2_summary.csv`).

| λ | Flat | Bid-price | Bid-price (CMA-ES) | MCTS | Hybrid MCTS |
| --- | --- | --- | --- | --- | --- |
| 24 | 0,573 | 0,554 | 0,582 | 0,567 | 0,568 |
| 72 | 0,581 | 0,614 | 0,645 | 0,608 | 0,612 |
| 120 | 0,594 | 0,619 | 0,682 | 0,584 | 0,604 |
| 192 | 0,610 | 0,628 | 0,716 | 0,605 | 0,631 |
| 240 | 0,617 | 0,613 | 0,736 | 0,590 | 0,617 |

Tržby všetkých metód rastú s dopytom (flat 20,0 → 48,3, Oracle 35,0 → 78,3), rovnako ako v Obr. 10 článku. **Naladená bid-price s dopytom získava najviac**: jej pomer k Oracle rastie z 0,58 na 0,74 a od λ = 120 prekonáva MCTS o 5,8–10,7 jednotky (+15 až +25 %, p_Holm ≤ 0,003) a predvolenú bid-price o 10–20 % (p_Holm < 0,001). Rast medzery s dopytom zodpovedá článku, kde sa s dopytom zväčšuje rozdiel MCTS a flat rate. Parametre naladené pri λ = 76 sa teda dobre prenášajú aj na iný dopyt. Online čas naladenej bid-price je 0,6–1,7 s na deň, MCTS 2,8–74 s.

**MCTS pri vysokom dopyte zaostáva**: od λ = 144 je v priemere pod flat rate, lebo pri až 240 požiadavkach je náhodný rollout veľmi zašumený a 3000 iterácií nestačí. Hybrid je nad MCTS o 1,3–3,1 jednotky pri λ ≥ 120, po korekcii však nevýznamne (najnižšie p_Holm = 0,36). Predvolená bid-price je nad MCTS významne len pri λ = 120 (p_Holm = 0,019) a pri λ = 240 stratí výhodu nad flat rate (p = 0,81): pevné μ z rána pri veľkom dopyte zle odhadujú hodnotu kapacity večer, čo prepočet LP v naladenej verzii odstraňuje. Pri nízkom dopyte (λ = 24) je flat rate lepšia ako predvolená bid-price (p_Holm = 0,046), lebo kapacita takmer nie je obmedzením.

## E4: robustnosť

**Obr. 8.7** (`results/figures/e4_robustness.png`). Pokles priemerných tržieb v % oproti nominálnemu modelu (± 2 SE párových rozdielov). Politika verí chybnému modelu, simulácia beží so správnym. Flat a obe bid-price 100 inštancií, MCTS a hybrid 30. Naladená bid-price používa θ z nominálneho ladenia (nepreladzuje sa na chybný model).

**Tabuľka 8.4.** Pokles tržieb v % (± SE) pri 12 a 24 slotoch; všetky konfigurácie sú v `results/e4_summary.csv` a `results/tables.md`.

| Scenár | Flat 12 / 24 | Bid-price 12 / 24 | Bid-price (CMA-ES) 12 / 24 | MCTS 12 / 24 | Hybrid 12 / 24 |
| --- | --- | --- | --- | --- | --- |
| λ × 0,7 | −0,9 ± 1,0 / 1,3 ± 0,9 | 2,7 ± 1,6 / 2,4 ± 1,6 | 1,8 ± 0,9 / 2,5 ± 1,0 | 0,8 ± 2,1 / 0,4 ± 2,4 | 1,1 ± 2,8 / 2,6 ± 2,2 |
| λ × 1,3 | 3,7 ± 2,0 / 0,0 | 4,7 ± 1,5 / 6,2 ± 1,7 | 0,5 ± 1,0 / 1,8 ± 1,3 | 1,7 ± 3,1 / −1,7 ± 2,1 | 2,4 ± 2,7 / 6,2 ± 2,2 |
| rozpočet 0,8 | 0,1 ± 1,4 / 5,8 ± 1,3 | 4,2 ± 1,8 / 4,4 ± 1,9 | 6,4 ± 1,1 / 4,4 ± 1,2 | 6,8 ± 2,5 / 5,9 ± 2,2 | 10,4 ± 3,0 / 8,2 ± 2,1 |
| rozpočet 1,2 | −0,2 ± 1,4 / 5,2 ± 2,0 | 11,9 ± 2,5 / 13,1 ± 2,4 | 1,6 ± 1,8 / 4,3 ± 1,9 | 1,6 ± 2,8 / −4,6 ± 2,8 | 4,4 ± 3,7 / 4,4 ± 2,2 |
| mriežka 0,10 | −0,2 ± 1,4 / −1,8 ± 1,3 | −0,7 ± 1,2 / −0,1 ± 1,0 | 0,4 ± 0,9 / −0,1 ± 0,9 | 1,3 ± 2,5 / −3,8 ± 2,3 | 7,4 ± 3,1 / 6,6 ± 2,9 |
| mriežka 0,025 | 0,0 / −1,4 ± 0,8 | 0,2 ± 0,7 / 0,4 ± 0,7 | 0,3 ± 0,6 / 0,3 ± 0,5 | 0,9 ± 2,7 / −0,5 ± 2,2 | 2,7 ± 3,1 / 3,0 ± 3,1 |

Interpretácia:

- **Predvolená bid-price je citlivá na nadhodnotený rozpočet.** Ak politika verí priemeru 1,2 namiesto 1,0, nadhodnocuje pravdepodobnosť nákupu a ponúka privysoké sadzby. Pokles je 6,6–16,6 % pri 3–24 slotoch, vždy viac ako 2 SE. Chyba λ stojí 1–6 %, najviac nadhodnotený dopyt pri 24 slotoch (6,2 %): LP potom μ nadhodnotí a politika odmieta príliš veľa.
- **Naladená bid-price je výrazne robustnejšia.** Pri nadhodnotenom rozpočte stráca najviac 4,3 % (2–24 slotov), pri chybe λ najviac 5,1 %. Prepočet LP po predajoch zrejme koriguje chybu modelu podľa skutočne predanej kapacity. Najcitlivejšia je na podhodnotený rozpočet (3,2–6,4 %, ponúka príliš nízke sadzby).
- **Flat rate** zostáva robustná: chybný model často vedie k tej istej alebo susednej sadzbe, najväčší pokles je 7,7 % (2 sloty, rozpočet 0,8).
- **MCTS** stráca pri podhodnotenom rozpočte 5,9–12,1 % pri 3–24 slotoch (viac ako 2 SE okrem 3 slotov), pri 2 slotoch len 0,9 %. **Hybrid** stráca pri podhodnotenom rozpočte až 10,9 %. Pri ostatných scenároch je zmena MCTS a hybridu väčšinou v rámci šumu: pri 30 inštanciách a stochastickom strome je štandardná chyba 2–6 %, takže menšie poklesy nevieme rozlíšiť.
- **Mriežka cien.** Krok kvantilov 0,10 ani 0,025 nemení tržby flat ani oboch bid-price o viac ako 2,4 %. Náš predpoklad kroku 0,05 (nejasnosť 1) teda výsledky podstatne neovplyvňuje.

## Konvergencia ladenia θ (E3, Člen B)

**Obr. 8.8** (`results/figures/tuning_convergence.png`). Najlepšia tréningová hodnota F(θ) podľa počtu vyhodnotení pre CMA-ES a náhodné hľadanie (medián a rozpätie cez 5 behov) a mriežku (16 bodov). Rozbor je v sekcii 5.5 (Člen B): CMA-ES a náhodné hľadanie dosiahnu takmer rovnaké hodnoty, mriežka je pri 16 bodoch o 1,2–2,6 jednotky horšia.
