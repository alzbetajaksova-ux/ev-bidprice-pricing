"""Mriežka sadzieb, diskretizácia Poissonovho procesu a konfigurácie inštancií."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import yaml
from scipy.stats import norm

from mpo_ev.interfaces import HORIZON_H, Config, Instance, Product, Request

BASE_CONFIG = Path(__file__).resolve().parents[2] / "config" / "base.yaml"


def load_base(path: Path = BASE_CONFIG) -> dict:
    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file)


def quantile_price_grid(
    start: float, stop: float, step: float, budget_mean: float, budget_std: float
) -> tuple[float, ...]:
    """Sadzby ako kvantily rozpočtu pre úrovne start, start + step, ..., stop."""
    n = round((stop - start) / step) + 1
    levels = [start + i * step for i in range(n)]
    return tuple(float(norm.ppf(q, budget_mean, budget_std)) for q in levels)


def err2(k: int, lam: float) -> float:
    """Očakávaný počet príchodov nad jeden za krok, ktoré k-kroková diskretizácia ignoruje.

    Rovnica 5 článku. Rovnaká hodnota je lam - k * (1 - exp(-lam / k)).
    """
    return lam * math.exp(-lam / k) + (lam - k) * (1 - math.exp(-lam / k))


def required_steps(lam: float, target: float = 0.06) -> int:
    """Najmenšie k >= lam s err2(k, lam) / lam <= target. Chyba s rastúcim k klesá."""
    low = max(1, math.ceil(lam))
    if err2(low, lam) / lam <= target:
        return low
    high = low * 2
    while err2(high, lam) / lam > target:
        high *= 2
    while high - low > 1:
        middle = (low + high) // 2
        if err2(middle, lam) / lam <= target:
            high = middle
        else:
            low = middle
    return high


def make_config(n_slots: int, n_steps: int, expected_requests: float, base: dict) -> Config:
    """Spojí parametre experimentu so spoločnými hodnotami z base.yaml."""
    model = base["model"]
    grid = base["price_grid"]
    price_grid = quantile_price_grid(
        grid["quantile_start"],
        grid["quantile_stop"],
        grid["quantile_step"],
        model["budget_mean"],
        model["budget_std"],
    )
    return Config(n_slots, n_steps, price_grid=price_grid, expected_requests=expected_requests,
                  **model)


def seed_range(base: dict, name: str) -> range:
    """Seedy z base.yaml, napr. "train" alebo "test"; horná hranica je vrátane."""
    first, last = base["seeds"][name]
    return range(first, last + 1)


def sessions_to_slots(
    start_h: np.ndarray, duration_h: np.ndarray, n_slots: int
) -> tuple[np.ndarray, np.ndarray]:
    """Prevedie nabíjania na prvý a posledný zasiahnutý slot (pravidlo 4 v CLAUDE.md).

    Začiatok pred 0:00 sa posunie na 0:00, nabíjanie po polnoci sa oreže na posledný slot.
    """
    slot_h = HORIZON_H / n_slots
    end_h = np.clip(start_h + duration_h, 0.0, HORIZON_H)
    first = np.minimum(np.floor(np.clip(start_h, 0.0, HORIZON_H) / slot_h), n_slots - 1)
    last = np.ceil(end_h / slot_h) - 1
    return first.astype(np.int64), np.maximum(first, last).astype(np.int64)


def generate_instance(config: Config, seed: int) -> Instance:
    """Vygeneruje jeden deň požiadaviek; rovnaký config a seed dajú rovnakú inštanciu."""
    rng = np.random.default_rng(seed)
    arrivals = rng.random(config.n_steps) < config.expected_requests / config.n_steps
    steps = np.flatnonzero(arrivals)
    start_h = rng.normal(config.start_mean_h, config.start_std_h, size=len(steps))
    duration_h = rng.exponential(config.duration_mean_h, size=len(steps))
    budgets = rng.normal(config.budget_mean, config.budget_std, size=len(steps))
    first, last = sessions_to_slots(start_h, duration_h, config.n_slots)
    requests = tuple(
        Request(step, Product(f, l), budget)
        for step, f, l, budget in zip(
            steps.tolist(), first.tolist(), last.tolist(), budgets.tolist()
        )
    )
    return Instance(config, requests, seed)


def generate_instances(config: Config, seeds: range) -> list[Instance]:
    return [generate_instance(config, seed) for seed in seeds]
