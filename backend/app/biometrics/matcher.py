"""Comparação 1:N de embeddings (BIOMETRICS.md §3). Função pura."""

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MatchResult:
    employee_id: int | None
    score: float  # melhor similaridade de cosseno encontrada
    runner_up: float  # melhor similaridade de outro funcionário


def normalize(vector: np.ndarray) -> np.ndarray:
    v = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(v))
    if norm == 0.0:
        raise ValueError("Embedding nulo.")
    return v / norm


def best_match(
    probe: np.ndarray,
    candidates: Iterable[tuple[int, np.ndarray]],
    *,
    threshold: float,
    margin: float,
) -> MatchResult:
    """Aceita só se o melhor for >= limiar E estiver `margin` acima do melhor de outra pessoa.

    A margem evita identificar a pessoa errada quando dois funcionários têm rostos parecidos.
    """
    p = normalize(probe)
    by_employee: dict[int, float] = {}
    for employee_id, template in candidates:
        score = float(np.dot(p, normalize(template)))
        by_employee[employee_id] = max(score, by_employee.get(employee_id, -1.0))
    if not by_employee:
        return MatchResult(None, -1.0, -1.0)
    ranked = sorted(by_employee.items(), key=lambda kv: kv[1], reverse=True)
    best_id, best = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else -1.0
    accepted = best >= threshold and best - runner_up >= margin
    return MatchResult(best_id if accepted else None, best, runner_up)
