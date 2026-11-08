# Vytvorené s pomocou Claude, upravil: Člen C
"""Tabuľky a grafy z výsledkov E1–E4 (časť „analysis“ v návode, sekcie 8 a 9 reportu).

Spustenie: python -m mpo_ev.analysis (s PYTHONPATH=src); run_experiments.py ju volá
na konci automaticky. Vstup: results/*.csv, výstup: results/figures/*.png a
results/tables.md. Chýbajúce experimenty sa preskočia.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from mpo_ev.paths import RESULTS

# Pevné priradenie farby metóde (farba patrí metóde, nie poradiu), plus značka.
STYLE = {
    "flat": ("#2a78d6", "o", "flat rate"),
    "bidprice": ("#eb6834", "s", "bid-price"),
    "bidprice_tuned": ("#1baf7a", "D", "bid-price (CMA-ES)"),
    "mcts": ("#eda100", "^", "MCTS (autori)"),
    "hybrid_mcts": ("#e87ba4", "v", "hybrid MCTS"),
    "vi": ("#008300", "P", "VI (optimum MDP)"),
    "oracle": ("#555555", "*", "Oracle"),
}
ORDER = list(STYLE)
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"

# Tab. 2 článku: (Oracle, flat, MCTS, VI) podľa počtu slotov
PAPER = {
    2: (None, None, None, 48.18), 3: (None, None, None, 43.88),
    4: (67.45, 39.33, 44.01, 46.23), 8: (64.31, 38.36, 43.71, None),
    12: (62.66, 40.14, 43.15, None), 24: (57.91, 38.49, 40.68, None),
    36: (55.58, 38.27, 39.99, None), 72: (51.67, 36.64, 38.51, None),
}
PAPER_RUNTIME = {4: 1.467, 8: 5.012, 12: 10.905, 24: 39.413}


def _style_axes(ax) -> None:
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)


def _slots(config_id: str) -> int:
    return int(config_id.split("s")[0])


def _methods(frame: pd.DataFrame) -> list[str]:
    present = set(frame["method"])
    return [m for m in ORDER if m in present]


def _cols(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Len stĺpce, ktoré v súhrne existujú (staršie výsledky nemusia mať všetky)."""
    return frame[[c for c in cols if c in frame.columns]]


def _md(frame: pd.DataFrame, digits: int = 3) -> str:
    """Markdown tabuľka bez závislosti na balíku tabulate."""
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in frame.iterrows():
        cells = []
        for value in row:
            if isinstance(value, float):
                cells.append("" if np.isnan(value) else f"{value:.{digits}f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# --- párové porovnania ----------------------------------------------------------------

def holm(pvalues: pd.Series) -> pd.Series:
    """Holmova korekcia p-hodnôt pre rodinu testov (NaN sa ignorujú)."""
    valid = pvalues.dropna().sort_values()
    m = len(valid)
    adjusted = pd.Series(np.nan, index=pvalues.index)
    running = 0.0
    for rank, (idx, p) in enumerate(valid.items()):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[idx] = running
    return adjusted


def paired_comparison(rows: pd.DataFrame, pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """Rozdiel tržieb A − B na rovnakých inštanciách: priemer, SE, výhry a Wilcoxonovo p.

    Holmova korekcia (`p_holm`) sa robí zvlášť pre hlavnú rodinu testov (porovnania s MCTS,
    úloha 5.6) a pre ostatné porovnania, vždy cez všetky konfigurácie experimentu.
    """
    out = []
    for cid, group in rows.groupby("config_id", sort=False):
        wide = group.pivot_table(index="instance_seed", columns="method", values="revenue")
        for a, b in pairs:
            if a not in wide or b not in wide:
                continue
            both = wide[[a, b]].dropna()
            diff = both[a] - both[b]
            nonzero = diff[diff != 0]
            p = wilcoxon(nonzero).pvalue if len(nonzero) >= 5 else np.nan
            out.append({
                "config_id": cid, "A": a, "B": b, "n": len(diff),
                "mean_diff": diff.mean(), "se": diff.sem(),
                "rel_pct": 100 * diff.mean() / both[b].mean(),
                "wins_A": int((diff > 0).sum()), "wins_B": int((diff < 0).sum()),
                "p_wilcoxon": p,
                "family": "vs. MCTS" if b == "mcts" else "ostatné",
            })
    table = pd.DataFrame(out)
    if table.empty:
        return table
    table["p_holm"] = np.nan
    for idx in table.groupby("family").groups.values():
        table.loc[idx, "p_holm"] = holm(table.loc[idx, "p_wilcoxon"])
    return table


PAIRS = [("bidprice", "mcts"), ("bidprice_tuned", "mcts"), ("hybrid_mcts", "mcts"),
         ("bidprice", "flat"), ("mcts", "flat"), ("bidprice_tuned", "bidprice"),
         ("vi", "bidprice")]


# --- E1 -------------------------------------------------------------------------------

def e1_tables(summary: pd.DataFrame) -> tuple[str, str]:
    table = summary.copy()
    table["slots"] = table["config_id"].map(_slots)
    main = _cols(table, ["config_id", "method", "n", "mean", "se", "median", "std", "min",
                         "max", "ratio_oracle", "ratio_lp", "ratio_flat", "gap_lp_pct",
                         "runtime_s"])
    rows = []
    for slots, group in table.groupby("slots"):
        by = group.set_index("method")
        oracle, flat, mcts, vi = PAPER.get(slots, (None,) * 4)
        row = {"slots": slots}
        for name, ours, paper in [("flat", "flat", flat), ("mcts", "mcts", mcts),
                                  ("vi", "vi", vi)]:
            row[f"{name}/oracle článok"] = (paper / oracle) if paper and oracle else np.nan
            row[f"{name}/oracle my"] = by["ratio_oracle"].get(ours, np.nan)
        row["bidprice/oracle my"] = by["ratio_oracle"].get("bidprice", np.nan)
        row["flat/VI článok"] = (flat / vi) if flat and vi else np.nan
        if "vi" in by.index:
            row["flat/VI my"] = by.loc["flat", "mean"] / by.loc["vi", "mean"]
        rows.append(row)
    return _md(main), _md(pd.DataFrame(rows))


def time_table(summary: pd.DataFrame, offline: pd.DataFrame | None) -> pd.DataFrame:
    """Priemerný online čas politiky na epizódu [s] a offline čas prípravy [s] za konfiguráciu.

    Online = reset + všetky rozhodnutia jedného dňa (runtime_s zo simulátora). Offline =
    tréning flat rate na 200 tréningových inštanciách, výpočet tabuľky VI, ladenie θ.
    """
    table = summary[summary["method"] != "oracle"][["config_id", "method", "runtime_s"]]
    if offline is not None:
        table = table.merge(offline, on=["config_id", "method"], how="left")
    table = table.rename(columns={"runtime_s": "online_s_per_day"})
    order = {m: i for i, m in enumerate(ORDER)}
    table["_o"] = table["method"].map(order)
    table["_s"] = table["config_id"].map(_slots)
    return table.sort_values(["_s", "_o"]).drop(columns=["_o", "_s"])


def plot_e1(summary: pd.DataFrame, out: Path) -> None:
    table = summary.copy()
    table["slot_h"] = 24 / table["config_id"].map(_slots)
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    ax = axes[0]
    for method in _methods(table):
        if method == "oracle":
            continue
        color, marker, label = STYLE[method]
        g = table[table["method"] == method].sort_values("slot_h")
        ax.plot(g["slot_h"], g["ratio_oracle"], color=color, marker=marker, linewidth=2,
                markersize=7, label=label)
    lp = table.groupby("slot_h")[["lp_bound", "oracle_mean"]].first().sort_index()
    ax.plot(lp.index, lp["lp_bound"] / lp["oracle_mean"], color=MUTED, linestyle=":",
            marker="x", linewidth=1.5, label="LP horná hranica")
    for idx, method in [(1, "flat"), (2, "mcts")]:
        xs = [24 / s for s, v in PAPER.items() if v[0] and v[idx]]
        ys = [v[idx] / v[0] for v in PAPER.values() if v[0] and v[idx]]
        color, marker, label = STYLE[method]
        ax.plot(xs, ys, color=color, marker=marker, linestyle="--", linewidth=1.5,
                markerfacecolor="none", markersize=7, label=f"{label}, článok")
    ax.set_xscale("log")
    ax.set_xticks([1 / 3, 2 / 3, 1, 2, 3, 6, 12])
    ax.set_xticklabels(["⅓", "⅔", "1", "2", "3", "6", "12"])
    ax.minorticks_off()
    ax.set_xlabel("dĺžka slotu [h]")
    ax.set_ylabel("tržby / Oracle (rovnaké inštancie)")
    ax.set_title("E1: normalizované tržby", color=INK, loc="left")
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.17))

    ax = axes[1]
    for method in _methods(table):
        if method in ("oracle", "flat"):
            continue
        color, marker, label = STYLE[method]
        g = table[table["method"] == method].sort_values("slot_h")
        ax.plot(g["slot_h"], g["runtime_s"], color=color, marker=marker, linewidth=2,
                markersize=7, label=label)
    ax.plot([24 / s for s in PAPER_RUNTIME], list(PAPER_RUNTIME.values()),
            color=STYLE["mcts"][0], marker="^", linestyle="--", markerfacecolor="none",
            label="MCTS, článok (Julia, 10 000 iter.)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks([1 / 3, 2 / 3, 1, 2, 3, 6, 12])
    ax.set_xticklabels(["⅓", "⅔", "1", "2", "3", "6", "12"])
    ax.minorticks_off()
    ax.set_xlabel("dĺžka slotu [h]")
    ax.set_ylabel("online čas politiky na epizódu [s]")
    ax.set_title("E1: výpočtový čas", color=INK, loc="left")
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.17))
    fig.tight_layout()
    fig.savefig(out / "e1_ratio_runtime.png", dpi=150)
    plt.close(fig)


def plot_distribution(rows: pd.DataFrame, config_id: str, out: Path) -> None:
    """Rozdelenie tržieb na inštanciách (ekvivalent Obr. 9 článku)."""
    group = rows[rows["config_id"] == config_id]
    methods = _methods(group)
    if not methods:
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    data = [group[group["method"] == m]["revenue"].to_numpy() for m in methods]
    parts = ax.violinplot(data, showmedians=True, widths=0.8)
    for body, m in zip(parts["bodies"], methods, strict=True):
        body.set_facecolor(STYLE[m][0])
        body.set_edgecolor(STYLE[m][0])
        body.set_alpha(0.55)
    for key in ("cmedians", "cmins", "cmaxes", "cbars"):
        parts[key].set_color(MUTED)
        parts[key].set_linewidth(1)
    ax.set_xticks(range(1, len(methods) + 1))
    ax.set_xticklabels([STYLE[m][2] for m in methods], rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("tržby na inštancii")
    ax.set_title(f"Rozdelenie tržieb, {config_id}", color=INK, loc="left")
    _style_axes(ax)
    fig.tight_layout()
    fig.savefig(out / f"distribution_{config_id}.png", dpi=150)
    plt.close(fig)


# --- E2 -------------------------------------------------------------------------------

def plot_e2(summary: pd.DataFrame, bounds: pd.DataFrame | None, out: Path) -> None:
    table = summary.copy()
    table["lam"] = table["config_id"].str.split("_l").str[1].astype(float)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for method in _methods(table):
        color, marker, label = STYLE[method]
        g = table[table["method"] == method].sort_values("lam")
        ax.errorbar(g["lam"], g["mean"], yerr=2 * g["se"], color=color, marker=marker,
                    linewidth=2, markersize=7, capsize=2, label=label)
    if bounds is not None:
        b = bounds.sort_values("expected_requests")
        ax.plot(b["expected_requests"], b["lp_bound"], color=MUTED, linestyle=":",
                linewidth=1.5, label="LP horná hranica")
    ax.set_xlabel("očakávaný počet požiadaviek λ")
    ax.set_ylabel("priemerné tržby (± 2 SE)")
    ax.set_title("E2: rastúci dopyt, 24 slotov", color=INK, loc="left")
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "e2_demand.png", dpi=150)
    plt.close(fig)


# --- grid search MCTS (úloha 3.8) -------------------------------------------------------------------------------

def plot_grid(grid: pd.DataFrame, out: Path) -> None:
    refs = grid[grid["n_iter"].isna() & (grid["method"] != "oracle")]
    grid = grid[grid["n_iter"].notna()].copy()
    algorithms = list(dict.fromkeys(grid["algorithm"]))
    depths = sorted(grid["depth"].unique())
    cs = sorted(grid["c"].unique())
    # c je usporiadaná veličina: sivá škála od svetlej po tmavú, aby sa nebila s farbami
    # referenčných metód (flat modrá, bid-price oranžová)
    ramp = ["#b9b8b0", "#94938b", "#6f6e67", "#4b4a45", "#2b2a27", "#111110"]
    shades = {c: ramp[min(i * (len(ramp) - 1) // max(1, len(cs) - 1), len(ramp) - 1)]
              for i, c in enumerate(cs)}
    fig, axes = plt.subplots(len(algorithms), len(depths), sharey=True, sharex=True,
                             figsize=(3.4 * len(depths), 3.0 * len(algorithms)), squeeze=False)
    for r, alg in enumerate(algorithms):
        for k, depth in enumerate(depths):
            ax = axes[r][k]
            for c in cs:
                g = grid[(grid["algorithm"] == alg) & (grid["depth"] == depth)
                         & (grid["c"] == c)].sort_values("n_iter")
                ax.errorbar(g["n_iter"], g["mean"], yerr=g["se"], color=shades[c], marker="o",
                            markersize=4, linewidth=1.6, capsize=1.5, label=f"c = {c:g}")
            for _, ref in refs.iterrows():
                color, _, label = STYLE[ref["method"]]
                ax.axhline(ref["mean"], color=color, linestyle="--", linewidth=1.2, label=label)
            ax.set_xscale("log")
            ax.set_title(f"{STYLE[alg][2]}, d_max = {depth:g}", color=INK, fontsize=9,
                         loc="left")
            _style_axes(ax)
            if r == len(algorithms) - 1:
                ax.set_xlabel("iterácie na rozhodnutie")
            if k == 0:
                ax.set_ylabel("priemerné tržby")
    axes[0][-1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "mcts_grid.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    for alg in algorithms:
        color, marker, label = STYLE[alg]
        for depth, style in zip(depths, ["-", "--", ":"], strict=False):
            g = (grid[(grid["algorithm"] == alg) & (grid["depth"] == depth)]
                 .groupby("n_iter", as_index=False)["runtime_s"].mean())
            ax.plot(g["n_iter"], g["runtime_s"], color=color, marker=marker, linestyle=style,
                    linewidth=1.8, label=f"{label}, d_max = {depth:g}")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("iterácie na rozhodnutie")
    ax.set_ylabel("čas na epizódu [s]")
    ax.set_title("Grid search: výpočtový čas MCTS", color=INK, loc="left")
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "mcts_grid_runtime.png", dpi=150)
    plt.close(fig)


def grid_table(grid: pd.DataFrame) -> str:
    g = grid[grid["n_iter"].notna()]
    best = g.loc[g.groupby(["algorithm", "n_iter"])["mean"].idxmax()]
    cols = ["algorithm", "n_iter", "depth", "c", "mean", "se", "ratio_oracle", "runtime_s"]
    refs = grid[grid["n_iter"].isna()][["algorithm", "mean", "se", "ratio_oracle", "runtime_s"]]
    return _md(best[cols]) + "\n\nReferencie na tých istých inštanciách:\n\n" + _md(refs)


# --- E4 -------------------------------------------------------------------------------

def plot_e4(summary: pd.DataFrame, out: Path) -> None:
    table = summary[summary["scenario"] != "nominal"]
    scenarios = list(dict.fromkeys(table["scenario"]))
    configs = sorted(table["configuration"].unique(), key=_slots)
    methods = _methods(table)
    fig, axes = plt.subplots(1, len(configs), sharey=True, sharex=True,
                             figsize=(2.6 * len(configs), 4.6), squeeze=False)
    width = 0.8 / max(1, len(methods))
    for ax, cid in zip(axes[0], configs, strict=True):
        for i, m in enumerate(methods):
            g = table[(table["configuration"] == cid) & (table["method"] == m)]
            g = g.set_index("scenario").reindex(scenarios)
            x = np.arange(len(scenarios)) + (i - (len(methods) - 1) / 2) * width
            ax.barh(x, g["drop_pct"], height=width * 0.9, xerr=2 * g["se_pct"],
                    color=STYLE[m][0], label=STYLE[m][2], error_kw={"ecolor": MUTED,
                                                                     "lw": 0.8})
        ax.axvline(0, color=MUTED, linewidth=0.8)
        ax.set_yticks(np.arange(len(scenarios)))
        ax.set_yticklabels(scenarios, fontsize=8)
        ax.set_title(cid, color=INK, loc="left")
        ax.set_xlabel("pokles tržieb [%]")
        _style_axes(ax)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, ncol=len(methods),
               loc="upper center")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out / "e4_robustness.png", dpi=150)
    plt.close(fig)


# --- tuning (Člen B) ------------------------------------------------------------------

def plot_tuning(results: Path, out: Path) -> None:
    files = sorted(results.glob("tuning_*.csv"))
    if not files:
        return
    frame = pd.concat([pd.read_csv(f) for f in files])
    configs = sorted(frame["config_id"].unique(), key=_slots)
    colors = {"cma": "#2a78d6", "random": "#eb6834", "grid": "#1baf7a"}
    fig, axes = plt.subplots(1, len(configs), figsize=(3.3 * len(configs), 3.4), squeeze=False)
    for ax, cid in zip(axes[0], configs, strict=True):
        for method, group in frame[frame["config_id"] == cid].groupby("method"):
            curves = group.pivot_table(index="eval", columns="run_seed", values="best")
            median = curves.median(axis=1)
            ax.plot(median.index, median, color=colors.get(method, MUTED), linewidth=2,
                    label=method)
            if curves.shape[1] > 1:
                ax.fill_between(curves.index, curves.min(axis=1), curves.max(axis=1),
                                color=colors.get(method, MUTED), alpha=0.15, linewidth=0)
        ax.set_title(cid, color=INK, loc="left")
        ax.set_xlabel("vyhodnotenia F(θ)")
        _style_axes(ax)
    axes[0][0].set_ylabel("najlepšie tréningové tržby")
    axes[0][0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "tuning_convergence.png", dpi=150)
    plt.close(fig)


# --- hlavná funkcia -------------------------------------------------------------------

def _read(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def analyze(results: Path = RESULTS) -> Path:
    out = results / "figures"
    out.mkdir(parents=True, exist_ok=True)
    sections = ["# Tabuľky z experimentov\n",
                ("Generované `python -m mpo_ev.analysis`. Tržby v jednotkách článku, "
                 "SE = štandardná chyba priemeru, p = Wilcoxonov párový test.\n")]

    summary, rows = _read(results / "e1_summary.csv"), _read(results / "e1.csv")
    if summary is not None and rows is not None:
        main, paper = e1_tables(summary)
        sections += ["## E1: dĺžka slotu\n", main, "\n### Porovnanie pomerov s článkom\n",
                     paper, "\n### Párové porovnania (rovnaké inštancie)\n",
                     _md(paired_comparison(rows, PAIRS))]
        sections += ["\n### Časy: online (rozhodovanie za deň) a offline (príprava)\n",
                     _md(time_table(summary, _read(results / "e1_offline.csv")), digits=4)]
        plot_e1(summary, out)
        for cid in ("4s", "24s"):
            plot_distribution(rows, cid, out)

    summary, rows = _read(results / "e2_summary.csv"), _read(results / "e2.csv")
    if summary is not None and rows is not None:
        sections += ["\n## E2: rastúci dopyt\n",
                     _md(_cols(summary, ["config_id", "method", "n", "mean", "se", "median", "std",
                                         "min", "max", "ratio_oracle", "ratio_lp",
                                         "ratio_flat", "gap_lp_pct", "runtime_s"])),
                     "\n### Párové porovnania\n", _md(paired_comparison(rows, PAIRS))]
        plot_e2(summary, _read(results / "e2_bounds.csv"), out)

    grid = _read(results / "mcts_grid_summary.csv")
    if grid is not None and "n_iter" in grid:
        sections += ["\n## Grid search MCTS, úloha 3.8 (najlepšie d_max a c pre každé n_iter)\n",
                     grid_table(grid)]
        plot_grid(grid, out)

    summary = _read(results / "e4_summary.csv")
    if summary is not None:
        sections += ["\n## E4: robustnosť (pokles tržieb v % oproti nominálu)\n",
                     _md(summary.pivot_table(index=["configuration", "scenario"],
                                             columns="method", values="drop_pct")
                         .reset_index(), digits=2)]
        plot_e4(summary, out)

    plot_tuning(results, out)
    path = results / "tables.md"
    path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Tabuľky a grafy z results/")
    parser.add_argument("--results", type=Path, default=RESULTS)
    args = parser.parse_args()
    print(f"zapísané: {analyze(args.results)}")


if __name__ == "__main__":
    main()
