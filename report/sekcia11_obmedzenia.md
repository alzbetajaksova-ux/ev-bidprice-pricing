# 11. Obmedzenia

Čísla v hranatých zátvorkách doplníme po experimentoch.

- **Syntetické dáta.** Inštancie generujeme z rozdelení v Tab. 1 článku. Reálny dataset nie je dostupný a autori uvádzajú, že ani oni nemali údaje o rozpočtoch, ich parametre zvolili arbitrárne. Závery preto platia pre tento model, nie priamo pre reálnu stanicu.
- **Zjednodušený dopyt.** Začiatok a dĺžka nabíjania sú nezávislé, intenzita príchodov je konštantná a rozpočet nezávisí od času. V praxi tieto predpoklady neplatia. Experiment E4 skúma len chybný odhad λ a priemeru rozpočtu.
- **Nejednoznačnosť článku.** Mriežku cien, koniec predaja slotu T_p a prevod nabíjania na sloty článok neuvádza, doplnili sme ich sami. Sadzby z mriežky sme odvodili z Tab. 2, krok 0,05 je však náš predpoklad. T_p vychádza z Obr. 3, nie z explicitnej definície.
- **Nezhoda s absolútnymi číslami.** Pri parametroch z Tab. 1 náš model nereprodukuje Tab. 2: optimálna flat sadzba je vyššia (kvantil 0,45 až 0,65 oproti 0,35 až 0,40) a prijatých požiadaviek je menej. Rozpor sme nevedeli jednoznačne vysvetliť, text a tabuľka článku navyše opisujú rozdielne nastavenie dopytu. Kratšia priemerná dĺžka 0,8 h, odhadnutá z Tab. 2, rozpor neodstránila: počet prijatých požiadaviek sa priblížil, tržby sa však vzdialili. Porovnávame preto pomery medzi metódami, nie absolútne tržby.
- **Diskretizácia.** V každom kroku príde najviac jedna požiadavka. V E1 preberáme počty krokov z Tab. 2, kde relatívna chyba kolíše od 0,035 do 0,093, a nie je teda konštantná.
- **Znížený rozsah.** Pre výpočtovú náročnosť porovnávame metódy najviac do 24 slotov \[doplniť počet inštancií\]. Výsledky pre 36 a 72 slotov z článku teda neoverujeme.
- **Python a Julia.** Autori použili Juliu, my Python. Absolútne časy behu preto nie sú porovnateľné s Tab. 2, porovnávame len časy v rámci našej implementácie.
- **Výpočtový rozpočet.** Výsledky MCTS závisia od zvoleného počtu iterácií, článok uvádza dve rôzne nastavenia \[doplniť zvolené\].
