from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .normalize import lexical_canonical


@dataclass(frozen=True)
class LabeledSample:
    """Amostra pública usada em calibração, teste ou regressão."""

    id: str
    text: str
    expected: str
    category: str
    source: str


def load_labeled_jsonl(path: Path) -> list[LabeledSample]:
    """Carrega um dataset rotulado exigindo schema e IDs válidos."""

    rows = []
    seen_ids = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        raw = json.loads(line)
        expected_keys = {"id", "text", "expected", "category", "source"}
        if set(raw) != expected_keys:
            raise RuntimeError(f"Schema inválido em {path.name}:{line_number}")
        if raw["id"] in seen_ids:
            raise RuntimeError(f"ID duplicado em {path.name}:{line_number}")
        if raw["expected"] not in {"ALLOW", "DENY"} or not isinstance(raw["text"], str):
            raise RuntimeError(f"Rótulo ou texto inválido em {path.name}:{line_number}")
        seen_ids.add(raw["id"])
        rows.append(LabeledSample(**raw))
    if not rows:
        raise RuntimeError(f"Dataset vazio: {path}")
    return rows


def load_prototype_texts(path: Path) -> list[str]:
    """Carrega apenas os textos que definem os protótipos semânticos."""

    return [
        json.loads(line)["text"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_no_leakage(groups: dict[str, list[str]], approximate_threshold: float = 0.97) -> None:
    """Rejeita duplicatas exatas ou quase idênticas entre grupos de avaliação."""

    canonical = {
        group: [(lexical_canonical(text), index) for index, text in enumerate(texts)]
        for group, texts in groups.items()
    }
    names = list(canonical)
    for left_index, left_name in enumerate(names):
        left_rows = canonical[left_name]
        if len({text for text, _ in left_rows}) != len(left_rows):
            raise RuntimeError(f"Duplicata interna em {left_name}")
        for right_name in names[left_index + 1 :]:
            for left_text, left_position in left_rows:
                for right_text, right_position in canonical[right_name]:
                    if left_text == right_text:
                        raise RuntimeError(
                            f"Vazamento exato entre {left_name}:{left_position} e {right_name}:{right_position}"
                        )
                    if SequenceMatcher(None, left_text, right_text, autojunk=False).ratio() >= approximate_threshold:
                        raise RuntimeError(
                            f"Vazamento aproximado entre {left_name}:{left_position} e {right_name}:{right_position}"
                        )
