# Príprava na obhajobu: časť Člena A

## Model a článok

**Ako sa z Tab. 2 dá odvodiť mriežka cien?** Pri flat rate sú tržby sadzba × vyťaženie, takže ich podiel je sadzba: 0,8073 a 0,8733. To sú presne kvantily 0,35 a 0,40 rozpočtu N(1; 0,5). Krok 0,05 z toho nevyplýva, je to náš predpoklad.

**Prečo je T_p koniec prvého slotu?** Článok T_p nedefinuje. Obr. 3 ukazuje, že o 12:30 sa predáva slot 12:00–15:59. Keby bol T_p začiatok slotu, pri 2 slotoch by sa slot 0:00–12:00 prakticky nedal predať a strop tržieb (27,22) by bol pod VI z článku (48,18).

**Prečo neskoré požiadavky necháme v inštancii?** Podľa rovnice 3 článku príde požiadavka bez ohľadu na čas, takže patrí do počtu požiadaviek. Odmietne ju simulátor bez ponuky ceny. Model dopytu ju pre politiky do Λ_p nezapočíta, lebo sa nedá predať.

**Čo meria Err₂ a prečo je očakávaný počet požiadaviek stále λ?** Err₂ je očakávaný počet príchodov nad jeden za krok, ktoré by Poissonov proces vytvoril. Diskrétny proces má v každom kroku pravdepodobnosť λ/K, takže E[počet] = K · λ/K = λ. Chyba je v rozložení príchodov, nie v ich priemere.

**Prečo v E1 preberáme K z Tab. 2?** Kvôli porovnateľnosti s výsledkami článku. V E2 používame chybu 0,06, lebo tam text a vzorec sedia.

**Prečo nesedia absolútne čísla s článkom?** Pri parametroch z Tab. 1 model vychádza inak než Tab. 2 a článok nedáva dosť údajov, aby sa príčina určila. Skúšali sme iné T_p aj kratšiu dĺžku, nezhoda zostala. Preto porovnávame pomery a rozpor uvádzame v obmedzeniach.

## MDP a klasifikácia

**Prečo počet stavov rastie exponenciálne so slotmi, ale lineárne s krokmi?** Vektor kapacít má (c₀ + 1)ⁿ kombinácií, lebo každý slot má vlastnú kapacitu. Krok je len jedno číslo, pridáva lineárny faktor K.

**Aký je rozdiel medzi úlohou oceňovania a ladenia θ?** Oceňovanie je online, diskrétne a stochastické rozhodnutie pri každej požiadavke. Ladenie θ je offline, spojitá, zašumená black-box úloha s hranicami.

## Simulátor a generátor

**Prečo stačí inštanciu definovať seedom?** Rovnaký config a seed dajú rovnakú inštanciu. Všetky metódy tak dostanú tie isté požiadavky aj rozpočty, čo je podmienka férového porovnania.

**Prečo `demand` v `run_episode` nepoužíva simulátor?** Pravda je v inštancii, `demand` je len to, čomu verí politika. Preto môže E4 dať politike nesprávny model bez zmeny simulácie.

**Prečo sa politika nevolá bez kapacity a po T_p?** Podľa protokolu v č. 3.1 článku tu predávajúci odmieta ešte pred ponukou ceny. Politiky tak nemusia tieto prípady riešiť.

**Prečo sa do `runtime_s` počíta aj `reset`?** Začiatočné LP je výpočet potrebný pre každú epizódu. Bez neho by bid-price vyzerala rýchlejšia, než je.

**Ako je simulátor overený?** Tržby bez väzby kapacity sa zhodujú so vzorcom Σ_p Λ_p · q(p,a) · r(p,a). Politika z presnej DP dala v simulátore hodnotu zhodnú s DP. Testy navyše zachytili všetkých 16 chýb, ktoré sme do kópie kódu vložili zámerne. Konečnú kontrolu dá VI od C.

**Prečo nezávislý test tržieb platí len bez väzby kapacity?** Vzorec predpokladá, že každý zákazník s dostatočným rozpočtom dostane produkt. Pri obmedzenej kapacite závisí predaj od poradia príchodov.

## Metódy a hranica

**Prečo sa flat rate učí len na tréningových inštanciách?** Výber sadzby je tiež optimalizácia. Pri výbere na testovacích dátach by bol výsledok optimisticky skreslený.

**Prečo je LP horná hranica online politík, ale nie Oracle?** Očakávané predaje každej online politiky spĺňajú obmedzenia LP, takže jej tržby sú najviac hodnota LP. Oracle pozná budúcnosť aj rozpočty, predá každému presne za jeho maximum, preto môže LP prekonať. Pri 4 slotoch dočasne vyšlo Oracle 54,13 a LP 43,82.

**Prečo má flat rate v našom modeli 94 % optima pri 4 slotoch?** Príčinu presne nepoznáme, v článku je to 85 %. Súvisí to s tým, že náš model sa od Tab. 2 líši, napríklad vyššou optimálnou sadzbou. Dôsledok je praktický: kritérium pilotu „≥ 93 % VI“ v našom modeli nič nerozlišuje, preto ho treba zmeniť.

**Čo ukázalo E4 pre flat rate?** Chyba λ ho takmer nezasiahne, lebo sadzba sa zvyčajne nezmení. Chybný priemer rozpočtu je horší, pokles je až 7,7 %, keďže flat zvolí zlú sadzbu. Zlepšenia sú v rámci šumu, žiadne nepresahuje dve štandardné chyby.

**Prečo v E4 skresľujeme model politiky, a nie simulátor?** Skúmame chybný odhad dopytu. Skutočný svet zostáva rovnaký, mení sa len to, čomu politika verí, a pokles tržieb meria cenu tejto chyby.
