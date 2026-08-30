from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    """Calcula SHA-256 em blocos para não carregar artefatos inteiros na memória."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_prototype_assets(root: Path, manifest_path: Path) -> None:
    """Falha se textos ou embeddings de protótipos divergirem do manifesto."""

    if not manifest_path.is_file():
        raise RuntimeError("Manifesto de protótipos ausente; execute make setup")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.is_file() or sha256(path) != entry["sha256"]:
            raise RuntimeError(f"Protótipo ausente ou desatualizado: {entry['path']}")
