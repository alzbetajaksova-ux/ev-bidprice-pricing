# Príprava na obhajobu – Člen B (Adam Paľo)

<!-- Vytvorené s pomocou Claude, upravil: Adam Paľo. Čísla podľa reportu MPO_Zadanie1_report.docx (vetva main). -->

Moja časť: **lineárny program a hodnoty slotov** (`lp.py`), **bid-price politika** (`policies/bidprice.py`), **Oracle** (`policies/oracle.py`), **ladenie θ cez CMA-ES** (`tuning.py`, experiment E3), sekcia 5 reportu.

## Riešenie v troch vetách

1. Z očakávaného dopytu vyriešime lineárny program. Jeho duálne premenné μ_j sú „hodnota“ jedného voľného miesta v slote j.
2. Keď príde zákazník, ponúkneme sadzbu, pri ktorej je najväčší **očakávaný čistý zisk**: pravdepodobnosť nákupu × (tržba − hodnota slotov, ktoré zákazník obsadí). Ak je zisk záporný, odmietneme.
3. Štyri parametre tohto pravidla naladíme cez CMA-ES na tréningových dňoch.

## Hlavné výsledky (naspamäť)

| Čo | Číslo |
| --- | --- |
| Naladená bid-price vs. MCTS, 8–24 slotov | +6 až +9 % tržieb, p (Holm) < 0,001 |
| Naladená bid-price vs. VI (optimum), 4 a 8 slotov | 35,37 vs. 35,33 a 36,68 vs. 36,82, v rámci šumu |
| Rýchlosť | 24 slotov: 1,25 s vs. 17,5 s na deň (asi 14×) |
| Vysoký dopyt (E2), λ ≥ 120 | o 15–25 % nad MCTS |
| Ladenie na tréningu | +0,3 až +5,7 %; CMA-ES ≈ náhodné hľadanie > mriežka |
| Robustnosť (E4, 24 slotov) | naladená stratí najviac 4,4 %, predvolená až 13 % |
| 2 sloty | všetky metódy blízko seba, flat je mierne lepšia |

## Otázky k lineárnemu programu

**Čo je x(p,a)?** Očakávaný počet zákazníkov s produktom p, ktorým ponúkneme sadzbu a. Nie je celočíselné, LP pracuje s priemermi.

**Čo znamenajú dve skupiny obmedzení?** Prvá: nemôžeme ponúknuť viac, ako príde zákazníkov (Σ_a x(p,a) ≤ Λ_p). Druhá: očakávaný predaj nesmie prekročiť 3 nabíjačky v žiadnom slote.

**Čo je duálna premenná μ_j?** O koľko by stúpli očakávané tržby LP, keby sme mali v slote j o jedno miesto navyše. Teda koľko nás stojí, ak to miesto predáme teraz (náklad príležitosti). V noci je μ = 0, v popoludňajšej špičke vysoké.

**Prečo je hodnota LP horná hranica?** LP nahradí náhodný dopyt jeho priemerom. Podľa Jensenovej nerovnosti si žiadna politika, ktorá nepozná budúcnosť, v priemere nemôže zarobiť viac (Gallego a van Ryzin, 1997). Pre Oracle hranicou nie je, lebo Oracle budúcnosť pozná.

**Prečo je hranica taká voľná (o 19–27 % nad VI)?** Kapacita je len 3. Pri takej malej kapacite náhodné kolísanie dopytu veľmi škodí, no LP ho nevidí.

**Ako ste LP zrýchlili?** (1) Zo 19 sadzieb ponecháme len tie na hornom konkávnom obale krivky tržieb, ostatné sú horšie než zmes dvoch susedných. (2) Pomocná premenná s_p = očakávaný predaj produktu, takže kapacitné riadky sú kratšie. Pri 72 slotoch z 6,3 s na 0,8 s, optimum ani μ sa nezmenia.

**Čím riešite LP?** HiGHS cez `scipy.optimize.linprog` (metóda vnútorného bodu).

## Otázky k bid-price pravidlu

**Napíš pravidlo.** a* = argmax_a q(p,a) · (r(p,a) − α · Σ_{j∈p} μ_j), odmietnuť, ak je maximum ≤ 0.

**Prečo násobíme q?** Lebo tržbu dostaneme len vtedy, keď zákazník kúpi. Vysoká cena má vysoký zisk, ale malú šancu na nákup.

**Čo sa stane, keď sú sloty bezcenné?** Pravidlo zvolí sadzbu s najväčšou očakávanou tržbou q · r, čo je obyčajné krátkozraké oceňovanie.

**Prečo prepočítavať LP?** Ráno vypočítané μ nevedia, čo sa cez deň predalo. Prepočítavame po každom predaji a navyše R-krát za deň. Prepočet sa robí až pri ďalšej požiadavke, prázdne kroky nič nestoja.

**Vidí politika budúcnosť alebo rozpočty?** Nie. Vidí len stav (krok, kapacita, produkt) a model dopytu. To je podmienka férového porovnania s MCTS.

**Prečo funguje lepšie ako MCTS?** MCTS odhaduje budúcnosť rolloutom s náhodnými cenami, pri dlhom dni a vysokom dopyte je ten odhad veľmi zašumený. LP zhrnie budúcnosť priamo z modelu do hodnôt slotov.

## Otázky k ladeniu (CMA-ES, E3)

**Čo ladíte?** α_am, α_pm (násobok μ dopoludnia a popoludní), γ (násobok dopytu v LP) a R (počet prepočtov za deň).

**Aká je to optimalizačná úloha?** Maximalizácia priemerných tržieb na 50 pevných tréningových dňoch. Spojitá, 4 premenné, s hranicami, black-box (len simulácia, bez gradientu), nehladká (sadzby sú diskrétne).

**Prečo je funkcia deterministická, keď je simulácia náhodná?** Používame stále tých istých 50 dní (spoločné náhodné čísla). Rovnaké θ dá vždy rovnaké číslo.

**Prečo CMA-ES?** Je to štandard pre spojité black-box úlohy s malým počtom premenných: nepotrebuje gradient a zvláda nehladkú funkciu.

**Prečo nebolo CMA-ES lepšie ako náhodné hľadanie?** Okolie optima je ploché: rôzne θ dávajú skoro rovnaké tržby. CMA-ES sa učí tvar úzkeho údolia, tu žiadne nie je. Pri 4 premenných je náhodné hľadanie silná referencia (Bergstra a Bengio, 2012).

**Bolo porovnanie metód ladenia férové?** Áno: rovnaký rozpočet (5 behov × 60 vyhodnotení × 50 dní), rovnaké dni a rovnaké kritérium ukončenia. Mriežka stihla len 2⁴ = 16 bodov, preto je najhoršia.

**Prečo γ ≈ 1,5–2?** Hypotéza: LP nevidí kolísanie dopytu a vzácnu kapacitu v špičke podceňuje. Vyšší dopyt v LP zvýši μ a politika viac šetrí kapacitu. Samostatne sme to neoverili.

**Nie je to preučené?** Na 50 dňoch čiastočne áno: pri 200 dňoch kleslo zlepšenie zo 5,7 % na 2,2 %. Preto rozhodujú testovacie dni (seedy 1000–1099), ktoré sa pri ladení nepoužili. Na nich je naladená verzia jasne lepšia.

**Prečo menší rozpočet než plánovaný?** Jedno vyhodnotenie pri 24 slotoch na 200 dňoch trvá asi 4,5 min, plný plán by trval desiatky CPU-hodín. Je to uvedené v obmedzeniach.

## Otázky k Oracle

**Čo je Oracle?** Binárny celočíselný program, ktorý pozná celý deň vrátane rozpočtov. Vyberie zákazníkov, ktorí sa zmestia do kapacity, a každému účtuje najvyššiu sadzbu z mriežky menšiu ako jeho rozpočet. Riešime ho cez `scipy.optimize.milp` (HiGHS), do 10 ms na deň.

**Prečo to nie je politika?** Lebo pozná budúcnosť. Je to nedosiahnuteľný strop, slúži na pomery (metóda / Oracle).

**Čím sa líši od článku?** Vynecháva požiadavky, ktoré prišli po konci predaja ich produktu. Tie nemôže predať žiadna politika, takže by strop zbytočne nafukovali.

## Otázky na celé riešenie (každý musí vedieť)

- **Stav MDP:** zostávajúca kapacita slotov, krok, požadovaný produkt. **Akcia:** sadzba z 19 kvantilov rozpočtu alebo odmietnutie. **Odmena:** sadzba × dĺžka, ak rozpočet > sadzba.
- **Prečo nestačí VI:** počet stavov rastie ako 4ⁿ (kapacita 0–3 v n slotoch). Pri 24 slotoch je to rádovo 10¹⁹ stavov.
- **Flat rate:** jedna sadzba vybraná na tréningových dňoch, predaj v poradí príchodu.
- **Prečo nesedia absolútne čísla s článkom:** text a tabuľky článku opisujú rôzne nastavenia dopytu. Porovnávame preto pomery a poradie metód na rovnakých dňoch.
- **Férovosť:** rovnaké testovacie dni, jeden simulátor, rovnaká mriežka, tréning oddelený od testu, párový Wilcoxonov test s Holmovou korekciou.
- **Kedy je naše riešenie horšie:** pri 2 slotoch (flat je mierne lepšia) a predvolená verzia pri chybne odhadnutom rozpočte zákazníkov (E4).
- **Použitie AI:** kód a texty vznikli s pomocou Claude, každý súbor má poznámku v hlavičke, README má sekciu o AI. Kód sme prešli, otestovali a vieme ho vysvetliť.
