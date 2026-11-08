# Zoznam nejasností článku (úloha 2.4)

<!-- Vytvorené s pomocou Claude, upravil: Člen C -->

Podklad pre sekcie 3, 6 a 10 reportu. Prvá časť preberá rozhodnutia Člena A o modeli (sekcia 3 a príloha na konci tohto súboru), druhá dopĺňa nejasnosti k metódam VI a MCTS, ktoré implementoval Člen C.

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
| 16 | Vzorkovanie produktu po príchode, keď sloty postupne končia | príchod s p₀ = Σ product_probs(0), produkt úmerne pravdepodobnostiam kroku 0, nepredajný produkt = bez ponuky | rovnica 3 článku | presne rovnaké rozdelenie ako generátor inštancií |
| 17 | Stav VI obsahuje produkt, pamäť k·c₀ⁿ·n(n+1)/2 | ukladáme len W_t(c) pred odhalením produktu, pamäť K·(c₀ + 1)ⁿ | ekvivalentná Bellmanova rovnica | VI zvládne aj 8 slotov (V₀ = 36,45); článok uvádza VI len do 4 slotov |
| 18 | Stav kapacity vo VI článku má c₀ⁿ hodnôt, správne je (c₀ + 1)ⁿ | (c₀ + 1)ⁿ, kapacita 0 až c₀ | počet hodnôt c_j ∈ {0, …, c₀} | iba opis v článku, výsledky neovplyvní |
| 19 | Čas behu MCTS v Tab. 2 (Julia) nie je porovnateľný s Pythonom | porovnávame tržby pri pevnom počte iterácií a čas uvádzame zvlášť | – | časové údaje porovnávať len relatívne medzi našimi metódami |

## Príloha: overenie modelu voči Tab. 2 (Člen A, 6. 11. 2026)

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
