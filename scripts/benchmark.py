"""Mede startup e decisão sem misturar I/O de arquivos."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_guard.classifier import DomainGuardFilter
from domain_guard.assets import sha256


def percentile(values: list[float], value: int) -> float:
    return float(np.percentile(np.asarray(values), value, method="nearest"))


def workload(unit_count: int) -> str:
    return "\n".join(
        f"Preciso comprar argamassa para a parede identificada como setor {index}."
        for index in range(unit_count)
    )


def measure(guard: DomainGuardFilter, text: str, repetitions: int) -> dict[str, float | int]:
    guard.evaluate(text)
    values = []
    for _ in range(repetitions):
        started = time.perf_counter_ns()
        guard.evaluate(text)
        values.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "repetitions": repetitions,
        "p50_ms": round(percentile(values, 50), 3),
        "p95_ms": round(percentile(values, 95), 3),
        "p99_ms": round(percentile(values, 99), 3),
        "max_ms": round(max(values), 3),
    }


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce-budget", action="store_true")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    started = time.perf_counter_ns()
    guard = DomainGuardFilter(ROOT / "config" / "filter_config.yaml")
    startup_ms = (time.perf_counter_ns() - started) / 1_000_000
    normal_repetitions = 20 if args.quick else 200
    maximum_repetitions = 10 if args.quick else 50
    result = {
        "policy_version": guard.config.policy_version,
        "config_sha256": sha256(ROOT / "config" / "filter_config.yaml"),
        "thresholds": guard.config.section("thresholds"),
        "environment": {
            "cpu": cpu_model(),
            "logical_cpus": os.cpu_count(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "startup_ms": round(startup_ms, 3),
        "workloads": {
            "short_1_unit": measure(guard, workload(1), normal_repetitions),
            "normal_16_units": measure(guard, workload(16), normal_repetitions),
            "maximum_64_units": measure(guard, workload(64), maximum_repetitions),
        },
        "budget": {"normal_p95_ms": 150, "maximum_p99_ms": 400},
    }
    result["budget_passed"] = (
        result["workloads"]["normal_16_units"]["p95_ms"] <= 150
        and result["workloads"]["maximum_64_units"]["p99_ms"] <= 400
    )
    output = ROOT / "artifacts" / "benchmark-local.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.enforce_budget and not result["budget_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
