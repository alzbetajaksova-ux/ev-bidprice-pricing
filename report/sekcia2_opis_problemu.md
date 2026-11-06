# 2. Opis a význam problému

Elektromobily sa nabíjajú oveľa dlhšie, než trvá tankovanie, a elektrinu nemožno na stanici skladovať tak ľahko ako palivo. Kapacita nabíjacej stanice je preto obmedzená počtom nabíjačiek a časom a nepredaný čas sa nedá nahradiť neskôr. Pre vodiča na dlhej ceste je navyše dôležité vopred vedieť, že bude mať kde nabíjať a za akú cenu. Mrkos a kol. preto skúmajú rezerváciu, ktorá spája nabíjanie, čas na stanici a parkovacie miesto do jedného produktu s cenou pevne stanovenou v okamihu rezervácie.

Problém rieši prevádzkovateľ jednej lokality s tromi nabíjačkami. Vodiči počas dňa postupne žiadajú o súvislé časové bloky a prevádzkovateľ musí každému hneď ponúknuť cenu bez toho, aby poznal jeho rozpočet alebo budúce požiadavky. Príliš nízka cena môže zabrať čas niekomu, kto by zaplatil viac. Príliš vysoká cena môže nechať nabíjačku nevyužitú. Cieľom je maximalizovať očakávané tržby.

Problém má štruktúru sieťového revenue managementu, známeho z predaja leteniek a hotelových izieb: pevná, časom sa znehodnocujúca kapacita, viac druhov zdrojov (časové sloty) a produkty, ktoré spotrebúvajú ich kombinácie (rezervácia cez niekoľko slotov). Dôležitosť problému vidíme v troch bodoch:

- online rozhodnutie musí byť rýchle, no presné riešenie Markovovho rozhodovacieho procesu je možné len pre 2 až 4 sloty,
- metóda autorov (Monte Carlo Tree Search) je pri jemnom delení dňa výpočtovo náročná a jej odstup od optima tam nie je známy,
- štandardné metódy revenue managementu článok neporovnáva, hoci sa na úlohu priamo hodia.

Na tieto medzery nadväzuje naše riešenie.

Zdroje: Mrkos, Komenda, Fiedler, Vokřínek, *Online Dynamic Pricing for Electric Vehicle Charging Stations with Reservations*, IEEE Transactions on Intelligent Transportation Systems (preprint arXiv 2410.05538); Talluri, van Ryzin, *The Theory and Practice of Revenue Management* \[overiť kapitoly pred citáciou\].
