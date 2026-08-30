from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from domain_guard.classifier import DomainGuardFilter


ROOT = Path(__file__).resolve().parents[1]


def cli_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return environment


def run_single(text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "domain_guard", "classify", "--stdin"],
        cwd=ROOT,
        env=cli_environment(),
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_output_is_byte_deterministic_across_processes():
    outputs = [run_single("Qual broca devo usar no concreto?") for _ in range(5)]
    assert all(item.returncode == 0 for item in outputs)
    assert all(item.stderr == "" for item in outputs)
    assert len({item.stdout.encode("utf-8") for item in outputs}) == 1


def test_cli_does_not_log_or_echo_input():
    sentinel = "SENTINELA-PRIVADA-918273"
    result = run_single(f"Conte uma história sobre {sentinel}")
    assert result.returncode == 0
    assert sentinel not in result.stdout
    assert sentinel not in result.stderr
    assert json.loads(result.stdout)["verdict"] == "DENY"


def test_batch_is_incremental_stable_and_does_not_copy_text(tmp_path):
    source = tmp_path / "input.jsonl"
    output = tmp_path / "output.jsonl"
    sentinel = "NAO-COPIAR-ESTE-TEXTO-1122"
    source.write_text(
        json.dumps({"id": "a", "text": "Qual tinta usar na parede?"}, ensure_ascii=False)
        + "\n"
        + json.dumps({"id": "b", "text": f"Conte uma piada {sentinel}"}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "domain_guard",
            "classify-file",
            "--input",
            str(source),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env=cli_environment(),
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0
    assert process.stdout == process.stderr == ""
    content = output.read_text(encoding="utf-8")
    assert sentinel not in content
    rows = [json.loads(line) for line in content.splitlines()]
    assert [row["id"] for row in rows] == ["a", "b"]
    assert [row["verdict"] for row in rows] == ["ALLOW", "DENY"]


def test_runtime_does_not_require_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("acesso de rede durante classificação")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    guard = DomainGuardFilter()
    assert guard.evaluate("Qual cimento usar?")["verdict"] == "ALLOW"
