from __future__ import annotations

import re
from pathlib import Path

from .embedder import ONNXEmbedder
from .reasons import Reason
from .normalize import InputRejected


def _load_conjunctions(path: Path) -> tuple[str, ...]:
    """Carrega conectores que podem introduzir uma intenção independente."""

    values = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not values:
        raise RuntimeError("Lista de conjunções vazia")
    return values


class DeterministicSegmenter:
    """Produz unidades sobrepostas sem truncar nem descartar conteúdo curto."""

    def __init__(self, root: Path, config: dict, embedder: ONNXEmbedder):
        self.config = config
        self.embedder = embedder
        conjunctions = _load_conjunctions(root / config["segmentation"]["conjunctions_file"])
        alternatives = "|".join(re.escape(item) for item in sorted(conjunctions, key=len, reverse=True))
        self.clause_split = re.compile(rf"\s*(?:,|:)?\s+\b(?:{alternatives})\b\s+", re.IGNORECASE)
        separators = config["segmentation"]["strong_separators"]
        characters = "".join(item for item in separators if item != "LF")
        escaped = re.escape(characters)
        self.sentence_split = re.compile(rf"[\n{escaped}]+")

    def _windows(self, text: str) -> list[str]:
        """Cobre uma unidade longa com janelas de tokens sobrepostas."""

        token_ids = self.embedder.token_ids(text)
        size = self.config["segmentation"]["window_tokens"]
        stride = self.config["segmentation"]["window_stride_tokens"]
        windows = []
        for start in range(0, len(token_ids), stride):
            piece = token_ids[start : start + size]
            if not piece:
                break
            decoded = self.embedder.decode_ids(piece)
            if decoded:
                windows.append(decoded)
            if start + size >= len(token_ids):
                break
        return windows

    def segment(self, text: str) -> list[str]:
        """Preserva contexto global e também expõe sentenças e cláusulas locais."""

        paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
        candidates: list[str] = []
        for paragraph in paragraphs:
            # O parágrafo preserva contexto; as partes menores revelam pedidos escondidos.
            candidates.append(paragraph)
            sentences = [part.strip() for part in self.sentence_split.split(paragraph) if part.strip()]
            candidates.extend(sentences)
            for sentence in sentences:
                clauses = [part.strip(" ,:;") for part in self.clause_split.split(sentence)]
                candidates.extend(part for part in clauses if part)

        units: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate = candidate.strip(" \t\n.!?;")
            if not candidate:
                continue
            # Unidades longas são cobertas por janelas; nunca são truncadas silenciosamente.
            pieces = (
                [candidate]
                if self.embedder.token_count(candidate) <= self.config["input_limits"]["max_model_tokens_per_unit"]
                else self._windows(candidate)
            )
            for piece in pieces:
                piece = piece.strip(" \t\n.!?;")
                if piece and piece not in seen:
                    seen.add(piece)
                    units.append(piece)
                    if len(units) > self.config["input_limits"]["max_semantic_units"]:
                        raise InputRejected(Reason.INPUT_LIMIT_EXCEEDED)
        return units
