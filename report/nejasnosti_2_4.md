# Zoznam nejasností článku (úloha 2.4)

<!-- Vytvorené s pomocou Claude, upravil: Člen C -->

Podklad pre sekcie 3, 6 a 10 reportu. Prvá časť preberá rozhodnutia Člena A o modeli (`CLAUDE.md`, časť 5a, a `team/CLEN_C.md`), druhá dopĺňa nejasnosti k metódam VI a MCTS, ktoré implementoval Člen C.

## Model a inštancie

| # | Nejasnosť | Naša voľba | Opora | Možný dôsledok |
| --- | --- | --- | --- | --- |
| 1 | Mriežka cien A nie je uvedená | 19 kvantilov rozpočtu, q = 0,05 až 0,95 (0,178–1,822) + odmietnutie | podiel tržby/vyťaženie flat rate v Tab. 2 je presne F⁻¹(0,35) a F⁻¹(0,40) | jemnejšia mriežka zvyšuje tržby dynamických metód, overuje E4 (grid_0.10, grid_0.025) |
| 2 | Koniec predaja T_p nie je definovaný | koniec prvého slotu produktu | Obr. 3: o 12:30 sa predáva slot 12:00–15:59 | so „začiatkom slotu“ by bol strop tržieb pod VI a Oracle článku |
| 3 | Prevod nabíjania na sloty neuvedený | prvý a posledný zasiahnutý slot, orezanie na deň | vlastná voľba | dlhšie produkty než samotné nabíjanie |
| 4 | Tab. 2: K = 24 × počet slotov, chyba Err₂/λ = 0,035–0,093, text tvrdí 0,06 | E1 podľa Tab. 2, E2 podľa chyby 0,06 | výpočet, `report/sekcia3_podklady.md` | E1 je porovnateľné s Tab. 2, nie s textom |
| 5 | Text: 16–768 krokov | zodpovedá λ = 2 až 96 (λ = počet slotov), Tab. 2 má iné λ | výpočet | text a tabuľka opisujú iné nastavenie |
| 6 | „240 slotov po 15 min“ | preklep, 15 min je 96 slotov | výpočet | žiadny |
| 7 | „24 h nabíjania“ vs. rastúci Ø počet požiadaviek v Tab. 2 | λ podľa Tab. 2 | λ × dĺžka slotu = 24 h platí pre text, nie pre tabuľku | – |
| 8 | Tab. 1 (dĺžka Exp, priemer 3 h) nereprodukuje Tab. 2 | ponechávame Tab. 1, porovnávame pomery k Oracle | simulácia, priemer 0,8 h nepomohol | absolútne tržby sa líšia, náš model je viac kapacitne obmedzený |
| 9 | VI pri 3 slotoch nižšie ako pri 2 aj 4 slotoch | pokles 2 → 3 sa reprodukuje, nárast pri 4 nie | naša VI: 40,97 / 36,32 / 36,17 | – |
| 10 | b > a vs. b ≥ a | b > a | pri spojitom rozpočte bez vplyvu | žiadny |

## Metódy VI a MCTS (Člen C)

| # | Nejasnosť | Naša voľba | Opora | Možný dôsledok |
| --- | --- | --- | --- | --- |
| 11 | Parametre MCTS uvedené dvakrát inak: č. 5.2.1 (d_max = 3, c = 1, 800 iterácií) a č. 6.3.1 (10 000, 10, 3) | vlastný grid search (úloha 3.8) na inštancii z č. 6.3.1 a tréningových seedoch: tržby sa ustália od ~1000 iterácií, 10 000 pridá ~0,4 za trojnásobný čas; pre E1, E2, E4 3000 iterácií, MCTS d_max = 8, c = 10, hybrid d_max = 3, c = 1 | Obr. 6: rozhoduje počet iterácií, d_max a c málo | rozdiel medzi nastaveniami článku je v našom modeli v rámci šumu |
| 12 | Či prázdne kroky (bez požiadavky) tvoria úrovne stromu MCTS | strom obsahuje len rozhodovacie stavy; prechod T(s, a) skočí na ďalšiu predajnú požiadavku s voľnou kapacitou | Algoritmus 2 tak robí rollout (geometrický čas do príchodu); v POMDPs.jl by prázdne kroky tvorili úrovne s jedinou akciou | pri d_max = 3 vidí náš strom 3 rozhodnutia dopredu, nie 3 kroky času; MCTS je skôr silnejšie |
| 13 | Znamienko v UCB (riadok 18 Algoritmu 1) je v texte „q − c·√…“ | štandardné UCB1 s „+“ | č. 5.1: „exploration term“, odkaz na UCT [25] | s „−“ by išlo o pesimistický výber, rozpor s textom |
| 14 | Náhodná akcia v rolloute: patrí odmietnutie do A? | áno, 19 sadzieb + odmietnutie, rovnomerne | č. 3.1: odmietnutie je cena ∞ ∈ A | náhodný rollout predá asi pri 47 % ponúk |
| 15 | Znovupoužitie stromu (č. 5.2.1) bez detailov | uzly v slovníku podľa stavu (krok, kapacita, produkt); štatistiky ostávajú celú epizódu, staré kroky sa mažú pri 300 000 uzloch | POMDPs.jl `reuse_tree` | koreň ďalšej požiadavky môže mať už nazbierané štatistiky |
| 16 | Vzorkovanie produktu po príchode, keď sloty postupne končia | príchod s p₀ = Σ product_probs(0), produkt úmerne pravdepodobnostiam kroku 0, nepredajný produkt = bez ponuky | `team/CLEN_C.md`, 3.7; rovnica 3 | presne rovnaké rozdelenie ako generátor inštancií |
| 17 | Stav VI obsahuje produkt, pamäť k·c₀ⁿ·n(n+1)/2 | ukladáme len W_t(c) pred odhalením produktu, pamäť K·(c₀ + 1)ⁿ | ekvivalentná Bellmanova rovnica | VI zvládne aj 8 slotov (V₀ = 36,45); článok uvádza VI len do 4 slotov |
| 18 | Stav kapacity vo VI článku má c₀ⁿ hodnôt, správne je (c₀ + 1)ⁿ | (c₀ + 1)ⁿ, kapacita 0 až c₀ | počet hodnôt c_j ∈ {0, …, c₀} | iba opis v článku, výsledky neovplyvní |
| 19 | Čas behu MCTS v Tab. 2 (Julia) nie je porovnateľný s Pythonom | porovnávame tržby pri pevnom počte iterácií a čas uvádzame zvlášť | – | časové údaje porovnávať len relatívne medzi našimi metódami |
