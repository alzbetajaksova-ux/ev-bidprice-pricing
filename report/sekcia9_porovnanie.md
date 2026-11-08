# 9. Porovnanie s výsledkami autorov

<!-- Vytvorené s pomocou Claude, upravil: Člen C. Čísla z results/e1_summary.csv (finálny beh). -->

Absolútne tržby s článkom porovnať nemožno: rozdelenia z Tab. 1 (dĺžka rezervácie s priemerom 3 h) dávajú výrazne viac kapacitne obmedzený model, než aký zodpovedá Tab. 2 (nejasnosť 8 v `report/nejasnosti_2_4.md`). Mriežku cien sme z Tab. 2 odvodili (flat sadzby článku sú presne F⁻¹(0,35) a F⁻¹(0,40)), preto ju ako hlavný dôvod rozdielov neuvádzame a jej vplyv overuje E4. Porovnávame **pomery k Oracle a k flat rate** na tých istých inštanciách a **poradie metód**.

**Tabuľka 9.1.** Pomer priemerných tržieb k Oracle, 100 testovacích inštancií. Článok: Tab. 2 (Oracle len pre 4 a viac slotov).

| Sloty | Dĺžka slotu | Flat, článok | Flat, my | MCTS, článok | MCTS, my | VI, článok | VI, my | Bid-price, my | Bid-price (CMA-ES), my |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 12 h | – | 0,626 | – | 0,610 | – | 0,633 | 0,609 | 0,609 |
| 3 | 8 h | – | 0,612 | – | 0,638 | – | 0,638 | 0,615 | 0,642 |
| 4 | 6 h | 0,583 | 0,600 | 0,653 | 0,631 | 0,685 | 0,653 | 0,625 | 0,653 |
| 8 | 3 h | 0,596 | 0,615 | 0,680 | 0,615 | – | 0,661 | 0,627 | 0,658 |
| 12 | 2 h | 0,641 | 0,595 | 0,689 | 0,625 | – | – | 0,641 | 0,664 |
| 24 | 1 h | 0,665 | 0,588 | 0,702 | 0,600 | – | – | 0,618 | 0,654 |
| 36 | 40 min | 0,689 | 0,587 | 0,720 | – | – | – | 0,617 | – |
| 72 | 20 min | 0,709 | 0,568 | 0,745 | – | – | – | 0,595 | – |

**Tabuľka 9.2.** Prínos dynamického oceňovania nad flat rate (relatívne zlepšenie priemeru; p a p_Holm sú z párového Wilcoxonovho testu).

| Sloty | MCTS vs. flat, článok | MCTS vs. flat, my | VI vs. flat, článok | VI vs. flat, my | Bid-price vs. flat, my | Bid-price (CMA-ES) vs. flat, my |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | +11,9 % | +5,1 % (p = 0,02; p_Holm = 0,27) | +17,5 % | +8,8 % | +4,2 % | +9,0 % |
| 8 | +13,9 % | +0,1 % | – | +7,5 % | +2,0 % | +7,1 % |
| 12 | +7,5 % | +5,1 % (p = 0,01; p_Holm = 0,19) | – | – | +7,8 % | +11,7 % |
| 24 | +5,7 % | +2,0 % | – | – | +5,1 % | +11,2 % |
| 36 | +4,5 % | – | – | – | +5,2 % | – |
| 72 | +5,1 % | – | – | – | +4,7 % | – |

## Čo sa reprodukovalo

- **Poradie Oracle > VI > MCTS ≥ flat.** VI je v našom modeli najlepšia politika všade, kde beží (2–8 slotov), MCTS je medzi VI a flat rate. Pri 4 slotoch je MCTS o 5,1 % nad flat rate (p = 0,02, po Holmovej korekcii 0,27), v článku o 11,9 %. Kritérium z návodu (MCTS ≤ VI a > flat na 4 slotoch) je splnené.
- **Pomer flat/Oracle okolo 0,6** pri 4 a 8 slotoch: máme 0,600 a 0,615, článok 0,583 a 0,596.
- **Pokles VI medzi 2 a 3 slotmi** (V₀ = 40,97 → 36,32), ktorý je v článku nečakaný (48,18 → 43,88). Nárast pri 4 slotoch (článok 46,23) sa nereprodukoval (36,17).
- **Grid search MCTS (Obr. 6 a 7 článku).** Rovnako ako autori zisťujeme, že rozhoduje počet iterácií, d_max aj c majú malý vplyv a čas rastie lineárne s počtom iterácií. Tržby na tejto inštancii sú porovnateľné (článok asi 18–23, my 19–27 podľa počtu iterácií).
- **Čas MCTS rastie s počtom slotov.** Pri 3000 iteráciách v Pythone máme 2,2 s pri 4 slotoch a 17,5 s pri 24 slotoch na deň, autori s 10 000 iteráciami v Julii 1,5 s a 39 s. Python je na iteráciu pomalší, ale pomer časov medzi metódami je porovnateľný.

## Čo sa nereprodukovalo

- **Rastúci pomer k Oracle pri kratších slotoch.** V článku sa pomer všetkých metód k Oracle s kratším slotom zlepšuje (flat 0,58 → 0,71, MCTS 0,65 → 0,75). U nás zostáva okolo 0,59–0,64 a pri 72 slotoch klesá (flat 0,568, bid-price 0,595). Pravdepodobná príčina je kapacitné obmedzenie nášho modelu: pri priemernej dĺžke 3 h je dopyt v špičke niekoľkonásobne vyšší ako tri nabíjačky a jemnejšie delenie dňa toho veľa nezmení. Oracle si naopak z jemnejších slotov vyberá presnejšie (59,97 pri 72 vs. 54,13 pri 4 slotoch). V článku sú relácie zjavne kratšie (Tab. 2: prijatá rezervácia pri flat rate trvá asi dĺžku slotu + 0,6 h), takže jemnejšie sloty uvoľnia viac kapacity pre všetky metódy.
- **Veľkosť prínosu dynamiky.** Prínos VI nad flat rate je pri 4 slotoch 8,8 % (článok 17,5 %), MCTS 5,1 % (11,9 %). Flat rate je v našom modeli bližšie k optimu, lebo pri silnom obmedzení kapacity je jedna vysoká sadzba takmer optimálna.
- **MCTS pri 8 slotoch nepredbehlo flat rate** (+0,1 %, p = 0,79), hoci v článku je o 13,9 % lepšie. Pri 12 slotoch je MCTS opäť nad flat rate (+5,1 %).

## Naše riešenie vs. metóda autorov

Pri rovnakých inštanciách, rovnakom vyhodnotení a rovnakej mriežke cien:

- **Naladená bid-price prekonáva MCTS autorov** pri 8, 12 a 24 slotoch o 6–9 % (p_Holm < 0,001) a pri vysokom dopyte (E2, λ ≥ 120) o 15–25 % (p_Holm ≤ 0,003). Pri 4 a 8 slotoch sa vyrovná optimálnej VI. Online potrebuje 1,25 s na deň pri 24 slotoch (MCTS 17,5 s) a offline ladenie trvá do 8 minút na jeden beh CMA-ES. Jej pomer k Oracle (0,65–0,66 pri 4–24 slotoch) je blízko hodnotám MCTS v článku (0,65–0,70), hoci náš model ponecháva dynamickému oceňovaniu menej priestoru.
- **Predvolená bid-price** (bez ladenia a bez prepočtu LP) dosahuje tržby MCTS (rozdiely −1,2 až +1,0, po korekcii nevýznamné) za asi 1/90 online času.
- **Hybrid MCTS** zlepší MCTS len pri dlhom horizonte (24 slotov: +4,5 %, p_Holm = 0,066) a je pomalší aj horší ako naladená bid-price.
- **Robustnosť (E4).** Naladená bid-price stráca pri chybnom modeli dopytu najviac 6,4 %, menej ako predvolená bid-price (do 16,6 %) aj MCTS (do 12,1 %).

Výskumná otázka „dosiahne rýchla politika založená na hodnote slotov tržby MCTS alebo vyššie“ má teda kladnú odpoveď: po naladení θ sú tržby vyššie, a to najmä pri jemnom delení dňa a vysokom dopyte, kde MCTS s náhodným rolloutom zlyháva. Ako ďaleko sú metódy od optima, vieme presne len do 8 slotov (VI); LP hranica je voľná (19–27 % nad VI). Na 36 a 72 slotoch, kde MCTS ani naladené θ v našom rozsahu nemáme, je predvolená bid-price o 5 % nad flat rate pri čase do 1,5 s na deň.

## Možné zdroje rozdielov

1. **Model dopytu (Tab. 1 vs. Tab. 2).** Hlavný a nevysvetlený rozdiel, ovplyvní absolútne čísla aj veľkosť prínosu dynamiky. Podrobne v sekcii 3 a v prílohe `report/nejasnosti_2_4.md`.
2. **Parametre MCTS.** Používame 3000 iterácií namiesto 10 000. Podľa nášho grid searchu pridá 10 000 iterácií v priemere asi 0,4 jednotky (v rámci šumu) za trojnásobný čas, takže tento rozdiel výsledky podstatne nemení.
3. **Štruktúra stromu.** Náš strom obsahuje len rozhodovacie stavy (nejasnosť 12), implementácia autorov v POMDPs.jl pravdepodobne aj prázdne kroky. Pri rovnakom d_max tak náš strom vidí ďalej.
4. **Mriežka cien.** Odvodili sme ju z Tab. 2 (krok kvantilov 0,05 je náš predpoklad). E4 ukazuje, že krok 0,10 alebo 0,025 mení tržby flat a bid-price najviac o 2,4 %.
5. **Python vs. Julia.** Ovplyvňuje len čas, nie tržby pri pevnom počte iterácií. Časy preto porovnávame relatívne medzi metódami.
6. **Počet inštancií a štatistika.** Pri 100 inštanciách je štandardná chyba priemeru 0,6–2,1 jednotky, porovnateľná s rozdielmi medzi MCTS a flat rate. Článok smerodajné chyby ani testy neuvádza, jeho rozdiely MCTS–flat (1,7 až 5,3 jednotky) sú pravdepodobne tiež zaťažené šumom.
7. **Implementácia Oracle.** Zhoduje sa s rov. 11–12, len vynechávame neprípustné požiadavky po T_p (Člen B). Bez toho by Oracle predával aj to, čo žiadna politika predať nemôže.
