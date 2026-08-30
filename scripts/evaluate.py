"""Executa a avaliação final e gera artefatos estáveis."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_guard.assets import sha256
from domain_guard.classifier import DomainGuardFilter
from domain_guard.dataset import load_labeled_jsonl, load_prototype_texts, validate_no_leakage


def compute_metrics(expected: list[str], predicted: list[str]) -> dict:
    tp = sum(t == "ALLOW" and p == "ALLOW" for t, p in zip(expected, predicted))
    tn = sum(t == "DENY" and p == "DENY" for t, p in zip(expected, predicted))
    fp = sum(t == "DENY" and p == "ALLOW" for t, p in zip(expected, predicted))
    fn = sum(t == "ALLOW" and p == "DENY" for t, p in zip(expected, predicted))
    total = len(expected)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    deny_total = tn + fp
    allow_total = tp + fn
    return {
        "total": total,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": (tp + tn) / total if total else 0.0,
        "allow_precision": precision,
        "allow_recall": recall,
        "allow_f1": f1,
        "escape_rate": fp / deny_total if deny_total else 0.0,
        "false_block_rate": fn / allow_total if allow_total else 0.0,
    }


def main() -> int:
    calibration = load_labeled_jsonl(ROOT / "data" / "calibration.jsonl")
    test = load_labeled_jsonl(ROOT / "data" / "test.jsonl")
    validate_no_leakage(
        {
            "prototypes_positive": load_prototype_texts(ROOT / "data" / "prototypes_positive.jsonl"),
            "prototypes_negative": load_prototype_texts(ROOT / "data" / "prototypes_negative.jsonl"),
            "calibration": [sample.text for sample in calibration],
            "test": [sample.text for sample in test],
        }
    )

    guard = DomainGuardFilter(ROOT / "config" / "filter_config.yaml")
    expected = []
    predicted = []
    reasons: dict[str, int] = defaultdict(int)
    categories: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
    errors = []
    predictions = []

    prediction_path = ROOT / "artifacts" / "predictions.jsonl"
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    with prediction_path.open("w", encoding="utf-8", newline="\n") as prediction_file:
        for sample in test:
            result = guard.evaluate(sample.text)
            expected.append(sample.expected)
            predicted.append(result["verdict"])
            reasons[result["reason"]] += 1
            categories[sample.category]["total"] += 1
            if result["verdict"] == sample.expected:
                categories[sample.category]["correct"] += 1
            else:
                errors.append(
                    {
                        "id": sample.id,
                        "expected": sample.expected,
                        "predicted": result["verdict"],
                        "reason": result["reason"],
                    }
                )
            prediction = {"id": sample.id, "expected": sample.expected, **result}
            predictions.append(prediction)
            prediction_file.write(
                json.dumps(
                    prediction, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ) + "\n"
            )

    result = {
        "schema_version": 1,
        "policy_version": guard.config.policy_version,
        "thresholds": guard.config.section("thresholds"),
        "hashes": {
            "config": sha256(ROOT / "config" / "filter_config.yaml"),
            "out_of_scope_rules": sha256(ROOT / "config" / "out_of_scope_rules.yaml"),
            "calibration": sha256(ROOT / "data" / "calibration.jsonl"),
            "test": sha256(ROOT / "data" / "test.jsonl"),
            "positive_prototypes": sha256(ROOT / "data" / "prototypes_positive.jsonl"),
            "negative_prototypes": sha256(ROOT / "data" / "prototypes_negative.jsonl"),
        },
        "metrics": compute_metrics(expected, predicted),
        "categories": {key: categories[key] for key in sorted(categories)},
        "reasons": dict(sorted(reasons.items())),
        "errors": errors,
        "predictions": predictions,
        "methodology_note": "O conjunto de teste revelou uma correção estrutural de segmentação antes desta execução final; por isso, o teste não é apresentado como totalmente cego.",
    }
    output_path = ROOT / "artifacts" / "evaluation.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
