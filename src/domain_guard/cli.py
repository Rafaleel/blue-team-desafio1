from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .classifier import DomainGuardFilter


def stable_json(value: dict) -> str:
    """Serializa a saída funcional sem campos ou espaços variáveis."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def classify_single(args: argparse.Namespace) -> int:
    """Classifica integralmente uma entrada de argumento ou stdin."""

    text = sys.stdin.read() if args.stdin else args.text
    result = DomainGuardFilter(args.config).evaluate(text)
    sys.stdout.write(stable_json(result) + "\n")
    return 0


def classify_file(args: argparse.Namespace) -> int:
    """Processa JSONL incrementalmente, preservando ordem e omitindo o texto."""

    guard = DomainGuardFilter(args.config)
    input_path = Path(args.input)
    output_path = Path(args.output)
    with input_path.open("r", encoding="utf-8") as source, output_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as destination:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                result = guard.evaluate(item.get("text"))
                output = {"id": item.get("id"), **result}
                destination.write(stable_json(output) + "\n")
            except (json.JSONDecodeError, AttributeError, TypeError):
                raise RuntimeError(f"JSONL inválido na linha {line_number}") from None
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Define a interface de entrada única e de arquivo em lote."""

    parser = argparse.ArgumentParser(description="Filtro local de domínio")
    parser.add_argument("--config", default="config/filter_config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    single = subparsers.add_parser("classify", help="classifica uma entrada")
    source = single.add_mutually_exclusive_group(required=True)
    source.add_argument("--stdin", action="store_true")
    source.add_argument("--text")
    single.set_defaults(handler=classify_single)

    batch = subparsers.add_parser("classify-file", help="classifica arquivo JSONL")
    batch.add_argument("--input", required=True)
    batch.add_argument("--output", required=True)
    batch.set_defaults(handler=classify_file)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except Exception as error:
        sys.stderr.write(f"domain_guard_error:{type(error).__name__}\n")
        return 2
