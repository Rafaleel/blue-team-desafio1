from pathlib import Path

from domain_guard.dataset import load_labeled_jsonl, load_prototype_texts, validate_no_leakage


ROOT = Path(__file__).resolve().parents[1]


def test_no_exact_or_near_duplicate_leakage():
    calibration = load_labeled_jsonl(ROOT / "data" / "calibration.jsonl")
    test = load_labeled_jsonl(ROOT / "data" / "test.jsonl")
    validate_no_leakage(
        {
            "positive": load_prototype_texts(ROOT / "data" / "prototypes_positive.jsonl"),
            "negative": load_prototype_texts(ROOT / "data" / "prototypes_negative.jsonl"),
            "calibration": [sample.text for sample in calibration],
            "test": [sample.text for sample in test],
        }
    )


def test_all_known_adversarial_regressions_are_denied(guard):
    rows = load_labeled_jsonl(ROOT / "data" / "adversarial_regression.jsonl")
    failures = [sample.id for sample in rows if guard.evaluate(sample.text)["verdict"] != "DENY"]
    assert failures == []
