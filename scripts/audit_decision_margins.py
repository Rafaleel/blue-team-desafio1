"""Audita a resistência de entradas DENY a variações numéricas do encoder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_guard.classifier import DomainGuardFilter
from domain_guard.dataset import load_labeled_jsonl


DATASETS = (
    ROOT / "data" / "calibration.jsonl",
    ROOT / "data" / "test.jsonl",
    ROOT / "data" / "adversarial_regression.jsonl",
)


def semantic_headroom(guard: DomainGuardFilter, analysis, verdict: str) -> int | None:
    """Retorna quanto os scores precisam variar para inverter a decisão semântica."""

    if analysis.fixed_reason is not None:
        return None
    thresholds = guard.config.section("thresholds")
    unit_margins = [
        min(
            score.in_score - thresholds["min_in_scope_score"],
            score.margin - thresholds["min_contrastive_margin"],
        )
        for score in analysis.scores
    ]
    if verdict == "ALLOW":
        return min(unit_margins)
    if all(value >= 0 for value in unit_margins):
        # O bloqueio veio da regra de ambiguidade, não de uma fronteira semântica.
        return None
    return -min(unit_margins)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "margin-audit.json",
    )
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()

    guard = DomainGuardFilter(ROOT / "config" / "filter_config.yaml")
    minimum = guard.config.section("stability")["min_deny_headroom"]
    rows = []
    failures = []

    for dataset in DATASETS:
        for sample in load_labeled_jsonl(dataset):
            analysis = guard.analyze(sample.text)
            verdict, reason = guard.decision_from_analysis(analysis)
            headroom = semantic_headroom(guard, analysis, verdict.value)
            row = {
                "dataset": dataset.name,
                "id": sample.id,
                "expected": sample.expected,
                "verdict": verdict.value,
                "reason": reason.value,
                "deny_headroom": headroom if sample.expected == "DENY" else None,
            }
            rows.append(row)
            if sample.expected == "DENY" and verdict.value != "DENY":
                failures.append(f"{dataset.name}:{sample.id}:ALLOW")
            elif (
                sample.expected == "DENY"
                and headroom is not None
                and headroom < minimum
            ):
                failures.append(f"{dataset.name}:{sample.id}:headroom={headroom}")

    output = {
        "schema_version": 1,
        "policy_version": guard.config.policy_version,
        "min_deny_headroom": minimum,
        "failures": failures,
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    if failures:
        print("Auditoria de margem falhou: " + ", ".join(failures))
        return 1 if args.enforce else 0
    print(f"Margem DENY confirmada: mínimo de {minimum} pontos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
