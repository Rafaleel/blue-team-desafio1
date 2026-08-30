"""Gera os embeddings int16 dos protótipos públicos."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_guard.assets import sha256
from domain_guard.config import load_config
from domain_guard.embedder import ONNXEmbedder, verify_runtime_artifacts


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    seen_ids = set()
    seen_texts = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) != {"id", "category", "text"}:
            raise RuntimeError(f"Schema inválido em {path.name}:{line_number}")
        normalized = " ".join(row["text"].casefold().split())
        if row["id"] in seen_ids or normalized in seen_texts:
            raise RuntimeError(f"Duplicata em {path.name}:{line_number}")
        seen_ids.add(row["id"])
        seen_texts.add(normalized)
        rows.append(row)
    if not rows:
        raise RuntimeError(f"Arquivo sem protótipos: {path}")
    return rows


def save_npy(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with temporary.open("wb") as stream:
        np.save(stream, values, allow_pickle=False)
    os.replace(temporary, path)


def main() -> int:
    config = load_config(ROOT / "config" / "filter_config.yaml")
    verify_runtime_artifacts(config.root, config.path("model_manifest"))
    embedder = ONNXEmbedder(
        config.path("runtime_model"),
        config.path("tokenizer"),
        config.section("runtime"),
        config.section("input_limits")["max_model_tokens_per_unit"],
    )
    files = []
    for polarity in ("positive", "negative"):
        source = config.path(f"{polarity}_prototypes")
        destination = config.path(f"{polarity}_embeddings")
        rows = read_jsonl(source)
        values = embedder.encode_quantized([row["text"] for row in rows])
        save_npy(destination, values)
        files.extend(
            [
                {"path": str(source.relative_to(ROOT)), "sha256": sha256(source)},
                {"path": str(destination.relative_to(ROOT)), "sha256": sha256(destination)},
            ]
        )
    manifest = {
        "schema_version": 1,
        "embedding_quantization_scale": config.section("runtime")["embedding_quantization_scale"],
        "files": files,
    }
    config.path("prototype_manifest").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Embeddings de protótipos gerados e verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
