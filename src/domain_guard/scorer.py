from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def scaled_cosine(left: np.ndarray, right: np.ndarray, scale: int) -> int:
    """Calcula cosseno escalado com aritmética inteira e arredondamento simétrico."""

    left64 = left.astype(np.int64, copy=False)
    right64 = right.astype(np.int64, copy=False)
    dot = int(left64 @ right64)
    denominator = math.isqrt(int(left64 @ left64) * int(right64 @ right64))
    if denominator == 0:
        return 0
    numerator = dot * scale
    if numerator >= 0:
        return (numerator + denominator // 2) // denominator
    return -((-numerator + denominator // 2) // denominator)


@dataclass(frozen=True)
class UnitScore:
    """Melhores scores positivo e negativo de uma unidade semântica."""

    position: int
    in_score: int
    out_score: int
    margin: int


class PrototypeScorer:
    """Compara cada unidade com múltiplos protótipos positivos e negativos."""

    def __init__(self, positive: np.ndarray, negative: np.ndarray, score_scale: int):
        if positive.dtype != np.int16 or negative.dtype != np.int16:
            raise RuntimeError("Embeddings de protótipos precisam ser int16")
        if positive.ndim != 2 or negative.ndim != 2 or positive.shape[1] != negative.shape[1]:
            raise RuntimeError("Dimensões inválidas nos protótipos")
        self.positive = positive
        self.negative = negative
        self.score_scale = score_scale

    def score(self, queries: np.ndarray) -> tuple[UnitScore, ...]:
        """Retorna proximidade positiva, negativa e margem para cada consulta."""

        results = []
        for position, query in enumerate(queries):
            in_score = max(scaled_cosine(query, prototype, self.score_scale) for prototype in self.positive)
            out_score = max(scaled_cosine(query, prototype, self.score_scale) for prototype in self.negative)
            results.append(UnitScore(position, in_score, out_score, in_score - out_score))
        return tuple(results)
