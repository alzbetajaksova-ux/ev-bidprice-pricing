# 4. Opis metódy autorov článku

<!-- Vytvorené s pomocou Claude, upravil: Člen C. Formálny MDP je v sekcii 3 (Člen A),
tu sa naň len odkazuje, aby sa sekcie neopakovali. -->

Mrkos a kol. formulujú online oceňovanie rezervácií ako Markovov rozhodovací proces s konečným horizontom (sekcia 3) a riešia ho Monte Carlo prehľadávaním stromu (MCTS). Ako referencie používajú tri metódy: flat rate (dolná referencia), Value Iteration (optimum MDP na malých inštanciách) a Oracle (nedosiahnuteľná horná referencia s plnou znalosťou budúcnosti).

## Model dopytu

Požiadavky prichádzajú homogénnym Poissonovým procesom s intenzitou λ za deň. Autori ho diskretizujú na K krokov, v každom príde najviac jedna požiadavka s pravdepodobnosťou λ/K a jej produkt sa vyberie úmerne intenzitám λ_p (č. 4, rov. 3). Počet krokov volia tak, aby relatívna chyba Err₂(K, λ)/λ, teda podiel príchodov nad jeden za krok, bol 0,06. Rozpočet zákazníka za hodinu je N(1; 0,5²), zákazník kúpi, ak ponúknutá cena neprevyšuje rozpočet. Začiatok rezervácie je N(12 h; 3 h), dĺžka Exp s priemerom 3 h (Tab. 1).

## MCTS (č. 5, Algoritmy 1 a 2)

Pri každej požiadavke autori spustia MCTS z aktuálneho stavu (kapacita, krok, produkt) a ponúknu akciu s najvyššou odhadnutou hodnotou v koreni. Akcie sú ceny z konečnej mriežky A a odmietnutie (cena ∞).

1. **Výber a expanzia.** Od koreňa sa v každom uzle zvolí akcia. Kým má uzol nevyskúšané akcie, vyberie sa nevyskúšaná, inak akcia s najvyšším UCB1, Q(s,a) + c·√(ln N(s) / N(s,a)). Nasledujúci stav sa vzorkuje z modelu (nákup podľa rozdelenia rozpočtu, ďalšia požiadavka podľa modelu dopytu). Výber končí po d_max úrovniach, v koncovom stave alebo po prvej nevyskúšanej akcii, takže strom rastie do šírky.
2. **Odhad hodnoty (rollout).** Z posledného stavu sa až do konca dňa hrajú rovnomerne náhodné akcie. Čas do ďalšej požiadavky sa vzorkuje z geometrického rozdelenia, prázdne kroky sa tak preskočia naraz.
3. **Spätné šírenie.** Každá úroveň dostane súčet odmien pod sebou vrátane rolloutu a Q(s,a) sa aktualizuje ako priebežný priemer.
4. **Znovupoužitie stromu.** Implementácia v POMDPs.jl (Julia) ponecháva strom medzi skutočnými krokmi epizódy.

Parametre sú tri: počet iterácií n_iter, hĺbka d_max a konštanta c. Článok uvádza dve nastavenia: v č. 5.2.1 n_iter = 800, d_max = 3, c = 1, v č. 6.3.1 po grid searchi na inštancii s 12 slotmi, 96 krokmi a λ = 24 n_iter = 10 000, d_max = 10, c = 3. Podľa autorov rozhoduje najmä počet iterácií, d_max a c majú malý vplyv (Obr. 6). Výpočtový čas rastie s n_iter aj d_max (Obr. 7), pri 24 slotoch je to 39 s na deň (Tab. 2).

## Referenčné metódy

- **Flat rate (č. 6.2.1).** Jedna sadzba za hodinu pre všetky požiadavky, vybraná z mriežky A tak, aby maximalizovala priemerné tržby na tréningových sekvenciách. Rezervácie sa prideľujú v poradí príchodu, kým je kapacita.
- **Value Iteration (č. 6.2.2).** Optimálna politika MDP spätnou indukciou cez všetky stavy (c, t, p). Pamäť rastie ako K · c₀ⁿ · n(n+1)/2 (správne (c₀ + 1)ⁿ, nejasnosť 18), preto ju autori používajú len do 4 slotov.
- **Oracle (č. 6.2.3).** Binárny celočíselný program nad celou sekvenciou s rozpočtami: vyberie podmnožinu požiadaviek, ktorá sa zmestí do kapacity, a každej účtuje najvyššiu cenu z mriežky neprevyšujúcu rozpočet (rov. 11–12). Nie je to politika, ale horná hranica tržieb na danej inštancii.

## Vyhodnotenie v článku

Každá metóda ocení rovnaké sekvencie požiadaviek a tržby sa priemerujú cez 100 inštancií (Tab. 2). Experimenty menia dĺžku slotu od 12 h do 20 min (č. 6.3.2, Obr. 8 a 9) a očakávaný dopyt pri 24 slotoch (č. 6.3.3, Obr. 10). Výsledok autorov: MCTS je bližšie k VI ako flat rate a nad flat rate je o 4,5–14 %, s rastúcim počtom slotov sa však zvyšuje jeho výpočtový čas (450 s na deň pri 72 slotoch). Článok neuvádza smerodajné odchýlky ani štatistické testy a kód nie je zverejnený.

## Ako sme metódy autorov implementovali (prehľad pre sekciu 5 a 6)

| Metóda | Súbor | Vernosť článku | Odchýlka |
| --- | --- | --- | --- |
| MCTS | `policies/mcts.py` | Algoritmy 1 a 2, UCB1, rozšírenie do šírky, geometrický rollout, znovupoužitie stromu | strom obsahuje len rozhodovacie stavy (nejasnosť 12); n_iter podľa grid searchu v Pythone (3.8) |
| VI | `policies/vi.py` | presné optimum MDP | stav bez produktu, W_t(c), preto beží až do 8 slotov (nejasnosť 17) |
| Flat rate | `policies/flat.py` (Člen A) | č. 6.2.1 | žiadna |
| Oracle | `policies/oracle.py` (Člen B) | rov. 11–12 | vynecháva požiadavky po T_p, ktoré nemôže predať žiadna politika |
