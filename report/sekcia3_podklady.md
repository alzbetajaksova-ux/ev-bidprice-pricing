# 3. Formulácia optimalizačnej úlohy

## Markovov rozhodovací proces

Deň rozdelíme na n slotov dĺžky L = 24/n hodín. Zdroje sú sloty, každý s kapacitou c₀ = 3. Produkt p je súvislý blok slotov, P je množina všetkých n(n+1)/2 produktov a d(p) je dĺžka produktu v hodinách. Predaj prebieha v K krokoch.

- **Stav:** s = (c, t, p), kde c ∈ {0, …, c₀}ⁿ je zostávajúca kapacita slotov, t ∈ {0, …, K−1} je krok a p ∈ P ∪ {∅} je práve požadovaný produkt (∅ = žiadna požiadavka).
- **Akcie:** sadzba a ∈ A alebo odmietnutie a = ∞. Prípustná je iba ∞, ak p = ∅, ak krok skončil po T_p alebo ak c_j = 0 pre niektorý slot j ∈ p. T_p je koniec prvého slotu produktu.
- **Odmena:** R = a · d(p), ak zákazník kúpi, inak 0. Zákazník s rozpočtom b za hodinu kúpi práve vtedy, keď b > a, teda s pravdepodobnosťou q(a) = P(b > a), kde b ~ N(1; 0,5²).
- **Prechod:** kapacita sa zníži o jednotku na slotoch produktu s pravdepodobnosťou q(a), inak sa nemení. Nezávisle od toho príde v kroku t + 1 požiadavka na p′ s pravdepodobnosťou λ_p′/K, ak je p′ v tomto kroku ešte predajný, inak krok zostane bez ponuky.
- **Horizont a cieľ:** konečný horizont K krokov bez diskontovania. Hľadáme politiku π, ktorá maximalizuje očakávané tržby E[Σ_t R_t]. Počiatočný stav má c = (c₀, …, c₀).

Optimálna hodnota spĺňa pre p ≠ ∅ a prípustnú a

V_t(c, p) = max_a { q(a) · [a · d(p) + W_(t+1)(c − 1_p)] + (1 − q(a)) · W_(t+1)(c) },

kde W_(t+1)(c) je očakávanie V_(t+1)(c, p′) cez požiadavku v ďalšom kroku a W_K ≡ 0. Možnosť odmietnutia dáva hodnotu W_(t+1)(c).

Počet stavov je K · (c₀ + 1)ⁿ · (n(n+1)/2 + 1). Pri 4 slotoch, K = 96 a c₀ = 3 je to asi 270 tisíc stavov, pri 24 slotoch a K = 576 už približne 5 · 10¹⁹. Preto je presná Value Iteration použiteľná len pre malé n a pri väčších inštanciách potrebujeme heuristiku.

## Klasifikácia úloh

Riešime dve rôzne úlohy. Oceňovanie sa rieši online pri každej požiadavke, ladenie parametrov θ našej politiky prebieha offline.

| Vlastnosť | Oceňovanie (MDP) | Ladenie θ (CMA-ES) |
| --- | --- | --- |
| Typ | maximalizácia | maximalizácia |
| Rozhodovacie premenné | sadzba pre každú požiadavku | α, γ, N z vektora θ |
| Priestor | diskrétny (A ∪ {∞}) | spojitý, nízkorozmerný; N sa zaokrúhľuje |
| Reprezentácia | politika π(c, t, p) | reálny vektor s hranicami |
| Účelová funkcia | očakávané tržby | priemerné tržby na tréningových inštanciách |
| Počet kritérií | jedno | jedno |
| Neurčitosť | stochastická (príchody, rozpočty) | zašumená fitness, konečná vzorka inštancií |
| Dynamika | dynamická, online, konečný horizont | statická, offline |
| Obmedzenia | kapacita slotov, koniec predaja T_p | hranice parametrov |
| Znalosť modelu | model dopytu známy, rozpočet skrytý | black-box, bez gradientu |
| Vyhodnotenie | simulácia na testovacích inštanciách | simulácia so spoločnými náhodnými číslami |

## Doplnenia oproti článku

- Cena je sadzba za hodinu × dĺžka produktu. Pri flat rate to Tab. 2 potvrdzuje: tržby sa rovnajú sadzbe × vyťaženie.
- T_p je koniec prvého slotu produktu. Článok T_p nedefinuje, no Obr. 3 ukazuje predaj slotu 12:00–15:59 o 12:30. Požiadavka po T_p sa započíta a odmietne sa bez ponuky.
- Prvý slot je ⌊začiatok/L⌋, posledný ⌈koniec/L⌉ − 1. Začiatok pred polnocou sa posunie na 0:00 a koniec po polnoci sa oreže na posledný slot. Podiely produktov λ_p/λ odhadujeme Monte Carlom s 10⁶ vzorkami a pevným seedom.

## Mriežka cien

Článok množinu cien A neuvádza. Dá sa však odvodiť z Tab. 2: pri flat rate sa všetky tržby rovnajú jednej sadzbe vynásobenej vyťažením, takže ich podiel odhaľuje použitú sadzbu. Tento podiel je 0,8073 pri 4 a 8 slotoch a 0,8733 pri 12 až 72 slotoch, čo na štyri desatinné miesta zodpovedá 35 % a 40 % kvantilu rozpočtu N(1; 0,5). Mriežku preto definujeme ako kvantily rozpočtu F⁻¹(q) pre q = 0,05; 0,10; …; 0,95, teda 19 sadzieb od 0,178 do 1,822 za hodinu, doplnených o odmietnutie. Krok 0,05 je náš predpoklad, z článku vyplýva len prítomnosť úrovní 0,35 a 0,40. Kvantilová mriežka má navyše praktický význam: susedné sadzby sa líšia o rovnakých päť percentuálnych bodov pravdepodobnosti nákupu. Vplyv tohto predpokladu overuje experiment E4.

## Diskretizácia dopytu

Poissonov proces s intenzitou λ nahrádzame K krokmi, v každom s pravdepodobnosťou λ/K príde najviac jedna požiadavka. Očakávaný počet požiadaviek tak zostáva presne λ. Chybu meria Err₂(K, λ) = λe^(−λ/K) + (λ − K)(1 − e^(−λ/K)), teda očakávaný počet príchodov nad jeden za krok, ktoré by Poissonov proces vygeneroval a diskrétny model ignoruje. Text článku udáva konštantnú relatívnu chybu Err₂/λ = 0,06, Tab. 2 však používa K = 24 × počet slotov, takže chyba tam kolíše od 0,035 do 0,093.

| Sloty | λ | K v Tab. 2 | Err₂/λ pri K z Tab. 2 | K pri Err₂/λ = 0,06 |
| --- | --- | --- | --- | --- |
| 2 | 9,00 | 48 | 0,088 | 72 |
| 3 | 13,94 | 72 | 0,091 | 112 |
| 4 | 18,98 | 96 | 0,093 | 152 |
| 8 | 36,67 | 192 | 0,090 | 294 |
| 12 | 49,95 | 288 | 0,082 | 400 |
| 24 | 76,28 | 576 | 0,063 | 610 |
| 36 | 92,86 | 864 | 0,052 | 743 |
| 72 | 123,96 | 1728 | 0,035 | 992 |

V experimente E1 preto kvôli porovnateľnosti s článkom preberáme K z Tab. 2. V experimente E2 volíme K podľa chyby 0,06, čo pre λ od 24 do 240 presne reprodukuje rozsah 192 až 1920 krokov uvedený v texte. Rovnako rozsah 16 až 768 krokov z experimentu s dĺžkou slotu presne zodpovedá λ = 2 až 96, teda λ rovnému počtu slotov. To vysvetľuje údaj o 24 hodinách nabíjania (λ × dĺžka slotu = 24 h), no nezhoduje sa to s priemernými počtami požiadaviek v Tab. 2, ktoré sú pri 4 slotoch asi 19.
