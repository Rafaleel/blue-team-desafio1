"""Verifica configuração, hashes de modelo e protótipos sem acessar a rede."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_guard.assets import verify_prototype_assets
from domain_guard.config import load_config
from domain_guard.embedder import verify_runtime_artifacts


def main() -> int:
    config = load_config(ROOT / "config" / "filter_config.yaml")
    verify_runtime_artifacts(ROOT, config.path("model_manifest"))
    verify_prototype_assets(ROOT, config.path("prototype_manifest"))
    thresholds = config.section("thresholds")
    if thresholds["min_in_scope_score"] is None or thresholds["min_contrastive_margin"] is None:
        raise RuntimeError("Thresholds ainda não calibrados")
    print("Configuração e artefatos verificados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
