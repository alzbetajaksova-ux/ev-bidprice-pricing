# Príprava na obhajobu – Člen C

<!-- Vytvorené s pomocou Claude, upravil: Martin Nový (Člen C) -->

Moduly Člena C: `policies/vi.py`, `policies/mcts.py`, `policies/hybrid_mcts.py`, `experiments.py` + `run_experiments.py`, `analysis.py`, `analysis.ipynb`, `config/e2.yaml`, `mcts.yaml`, `mcts_grid.yaml`, `tuning.yaml`, rozšírenie `e1.yaml` a `e4.yaml`, `requirements.txt`. Pôvodné testy z vetvy `clen-c` nahradil pri zjednotení do `main` súbor `tests/test_core.py` (VI: `test_vi_matches_reference_dp_and_lp_bound`, `test_vi_policy_in_simulator_reaches_value`; runner: `test_runner_rows_and_summary`; politiky: `test_policy_is_valid_and_deterministic`).

## Value Iteration

**Ako funguje naša VI?** Horizont je konečný, takže stačí jeden prechod spätnej indukcie od kroku K do 0. Pre každý krok t a kapacitu c počítame W_t(c), očakávané tržby od kroku t pred tým, než sa ukáže požiadavka. Pre produkt p je náklad príležitosti Δ = W_{t+1}(c) − W_{t+1}(c − 1_p) a najlepšia ponuka dá zisk max(0, max_a q(a)·(r(p,a) − Δ)). W_t(c) je W_{t+1}(c) plus tieto zisky vážené pravdepodobnosťami produktov.

**Prečo zvládneme 8 slotov a článok len 4?** Článok ukladá stav (c, t, p), my produkt vystredíme a ukladáme len W_t(c). Pamäť je K·(c₀ + 1)ⁿ, pri 8 slotoch 192 · 65 536 hodnôt (asi 100 MB), výpočet trvá asi 50 s. Pri 9 slotoch už 4⁹ = 262 144 stavov na krok, preto je limit 70 000.

**Ako vieš, že VI je správna?** (1) V₀ sa presne zhoduje s nezávislou DP Člena A (40,97 / 36,32 / 36,17). (2) Na malej inštancii ju porovnávame s priamou rekurziou nad (t, c, p) podľa článku, zhoda na 10⁻¹⁰. (3) Simulované tržby politiky VI na 4000 inštanciách sú v rámci 4 SE od V₀. (4) V₀ ≤ LP hranica. (5) W klesá v čase a rastie s kapacitou.

**Prečo nie je VI z článku (48,18 / 43,88 / 46,23) rovnaká?** Náš model podľa Tab. 1 (dĺžka 3 h) je viac kapacitne obmedzený, Tab. 2 sa s ním reprodukovať nedá (nejasnosť 8). Porovnávame preto pomery, napr. flat/VI.

## MCTS

**Opíš jednu iteráciu.** Výber: od koreňa sa v každom uzle zvolí akcia, najprv každá nevyskúšaná, potom podľa UCB1 Q + c·√(ln N / N_a). Prechod: so pravdepodobnosťou q(a) zákazník kúpi, potom sa vzorkuje ďalšia ponuka. Výber končí po d_max úrovniach, v koncovom stave alebo po nevyskúšanej akcii. Odhad: rollout náhodnými akciami do konca dňa. Spätné šírenie: každá úroveň dostane súčet odmien pod sebou a Q sa spriemeruje.

**Prečo strom obsahuje len rozhodovacie stavy?** Prázdny krok, nepredajný produkt alebo produkt bez kapacity nemá rozhodnutie, simulátor ho odmietne sám. Skok na ďalšiu ponuku (geometrický čas, rovnako ako rollout autorov) robí strom užitočnejším: d_max = 3 znamená 3 rozhodnutia dopredu.

**Ako vzorkuješ čas do ďalšej ponuky?** Príchod v kroku má pravdepodobnosť p₀ = Σ product_probs(0), takže čas do príchodu je geometrický: Δ = 1 + ⌊ln(1 − u) / ln(1 − p₀)⌋. Produkt sa vyberie úmerne pravdepodobnostiam a ak v danom kroku už nie je predajný, ponuka nevzniká. Na vetve `clen-c` to overoval test `test_offer_sampling_matches_demand`; v `main` ho po zjednotení testov už nemáme.

**Čo znamená znovupoužitie stromu?** Uzly sú v slovníku podľa (krok, kapacita, produkt). Keď príde ďalšia skutočná požiadavka, jej stav už môže byť v strome s nazbieranými štatistikami. Uzly z minulých krokov mažeme, až keď je ich viac ako 300 000.

**Ako ste zvolili parametre?** Grid search (úloha 3.8) na inštancii z článku (12 slotov, 96 krokov, λ = 24), ale na 30 tréningových inštanciách: n_iter od 10 po 10 000, d_max ∈ {1, 3, 8, 15}, c ∈ {0,5; …; 10}. Rozhoduje počet iterácií, d_max a c majú vplyv v rámci šumu, rovnako ako v článku (Obr. 6). Tržby sa ustália od ~1000 iterácií, 10 000 pridá ~0,4 za trojnásobný čas, preto 3000 iterácií; MCTS d_max = 8, c = 10, hybrid d_max = 3, c = 1.

**Čo by sa stalo pri väčšom c / menšom c?** Väčšie c viac skúša menej dobré sadzby, pri malom počte iterácií to môže pomôcť (rollout je šumný), pri veľkom počte zbytočne míňa iterácie. Pri c = 0 by sa po prvom vyskúšaní každej akcie vyberala len najlepšia podľa jedného zašumeného rolloutu.

**Prečo je náhodný rollout slabý?** Náhodná sadzba predá len asi v 47 % prípadov a často pod cenou, takže odhad hodnoty stavu je nízky a zašumený. MCTS potom potrebuje veľa iterácií, aby rozlíšil dobré a zlé akcie.

## Hybrid MCTS

**Čím sa líši od MCTS?** Iba rolloutom: namiesto náhodnej sadzby ponúkne bid-price politiku s μ z LP, vypočítanými raz pri reset. Sadzba závisí len od produktu a časti dňa, preto ju predpočítame do tabuľky a rollout je rovnako rýchly. Vo finálnych behoch rollout používa naladené α a γ od Člena B, prepočet LP v rolloute nie je.

**Je porovnanie MCTS a hybridu férové?** Áno: rovnaký počet iterácií, rovnaké inštancie, rovnaký seed politiky, rovnaký strom a UCB. Líši sa len rollout.

## Runner a metodológia

**Ako je zaručená reprodukovateľnosť?** Inštancia aj náhodnosť politiky sú dané seedom, výsledok nezávisí od počtu procesov ani od delenia na skupiny. Prepočet na vetve `main` dal bajt po bajte rovnaké výsledky. `results/run_meta.json` zaznamenáva verzie a parametre.

**Ako zabezpečuješ, že metóda nevidí test?** Flat rate, CMA-ES a grid search MCTS používajú len seedy 0–199. Testovacie seedy 1000–1099 slúžia len na finálne vyhodnotenie.

**Prečo pomer k Oracle a nie absolútne tržby?** Náš model sa od Tab. 2 líši (nejasnosť 8), absolútne čísla preto nie sú porovnateľné. Pomer k Oracle na tých istých inštanciách je porovnateľný aj s článkom.

**Prečo párový Wilcoxonov test?** Metódy bežia na rovnakých inštanciách, rozdiel na inštancii odstráni variabilitu dopytu. Rozdiely nemusia byť normálne rozdelené, Wilcoxon to nepredpokladá.

**Čo by zmenil väčší výpočtový rozpočet?** Podľa grid searchu takmer nič: 10 000 iterácií dalo v priemere o 0,4 viac ako 3000 (v rámci šumu) za trojnásobný čas. Bid-price má pevný čas daný počtom riešení LP.


**Prečo je E3 Člena B a nie váš grid search?** V pláne tímu je E3 prínos ladenia θ bid-price (úloha 5.4, Člen B). Grid search MCTS je úloha 3.8 a v runneri sa volá `mcts_grid`.

**Prečo Holmova korekcia?** Testujeme veľa dvojíc metód na viacerých konfiguráciách; bez korekcie by niektorý rozdiel vyšiel náhodou významný. Holm kontroluje pravdepodobnosť aspoň jedného falošného objavu a je menej konzervatívny ako Bonferroni.

**Ako runner pokračuje po páde?** Každá úloha (experiment, konfigurácia, metóda, skupina inštancií, parametre) má odtlačok; po dokončení sa uloží do results/.cache. Pri ďalšom behu sa hotové úlohy načítajú, zmena parametrov dá iný odtlačok, takže sa nepoužijú staré výsledky.

**Prečo je naladená bid-price lepšia ako MCTS, keď predvolená nie je?** Naladená verzia prepočítava LP po každom predaji a periodicky počas dňa, takže hodnoty slotov μ zodpovedajú skutočnej zostávajúcej kapacite. Predvolená má μ len z rána. Ladenie α a γ potom koriguje systematické chyby fluidného LP. Samostatný vplyv prepočtu a ladenia sme neoddelili.

**Nie je to nefér, že naladená bid-price mala tréning a MCTS nie?** Ladenie bežalo len na tréningových inštanciách (0–49) a jeho offline čas uvádzame. MCTS má svoje hyperparametre tiež vybrané na tréningových inštanciách (grid search). Testovacie inštancie nevidela žiadna metóda.

**Prečo hybrid s naladeným rolloutom nie je lepší?** Rollout má pevné μ z rána a nevie, ako sa kapacita počas dňa mení; strom MCTS s 3000 iteráciami to nedokáže vyvážiť. Naladená bid-price prepočítava LP priamo, preto je lepšia aj rýchlejšia.
