"""Seleciona thresholds usando somente data/calibration.jsonl."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_guard.classifier import Analysis, DomainGuardFilter
from domain_guard.dataset import load_labeled_jsonl


def metrics(expected: list[str], predicted: list[str]) -> dict[str, int | float]:
    tp = sum(t == "ALLOW" and p == "ALLOW" for t, p in zip(expected, predicted))
    tn = sum(t == "DENY" and p == "DENY" for t, p in zip(expected, predicted))
    fp = sum(t == "DENY" and p == "ALLOW" for t, p in zip(expected, predicted))
    fn = sum(t == "ALLOW" and p == "DENY" for t, p in zip(expected, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/filter_config.yaml")
    parser.add_argument("--dataset", default="data/calibration.jsonl")
    parser.add_argument("--output", default="artifacts/calibration.json")
    args = parser.parse_args()

    guard = DomainGuardFilter(ROOT / args.config)
    samples = load_labeled_jsonl(ROOT / args.dataset)
    analyses: list[Analysis] = [guard.analyze(sample.text) for sample in samples]
    expected = [sample.expected for sample in samples]
    calibration = guard.config.section("calibration")
    step = calibration["threshold_grid_step"]
    allow_total = sum(value == "ALLOW" for value in expected)
    max_false_blocks = int(allow_total * calibration["max_false_block_rate"])

    best = None
    for in_threshold in range(2000, 9001, step):
        for margin_threshold in range(-4000, 5001, step):
            predicted = [
                guard.decision_from_analysis(
                    analysis,
                    min_in_scope_score=in_threshold,
                    min_contrastive_margin=margin_threshold,
                )[0].value
                for analysis in analyses
            ]
            current = metrics(expected, predicted)
            if current["fn"] > max_false_blocks:
                continue
            key = (
                current["fp"],
                -current["f1"],
                -in_threshold,
                -margin_threshold,
            )
            if best is None or key < best[0]:
                best = (key, in_threshold, margin_threshold, current)
    if best is None:
        raise RuntimeError("Nenhum threshold respeita o teto de bloqueio indevido")

    _, in_threshold, margin_threshold, result_metrics = best
    output = {
        "dataset": args.dataset,
        "sample_count": len(samples),
        "max_false_block_rate": calibration["max_false_block_rate"],
        "thresholds": {
            "min_in_scope_score": in_threshold,
            "min_contrastive_margin": margin_threshold,
        },
        "metrics": result_metrics,
        "samples": [asdict(sample) | {"analysis_units": len(analysis.scores)} for sample, analysis in zip(samples, analyses)],
    }
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"thresholds": output["thresholds"], "metrics": result_metrics}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
