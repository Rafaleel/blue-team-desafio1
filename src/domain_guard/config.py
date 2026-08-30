from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FilterConfig:
    """Configuração validada, com caminhos resolvidos pela raiz do projeto."""

    root: Path
    source: Path
    values: dict[str, Any]

    def section(self, name: str) -> dict[str, Any]:
        return self.values[name]

    def path(self, key: str) -> Path:
        return self.root / self.values["paths"][key]

    @property
    def policy_version(self) -> str:
        return self.values["policy_version"]


def load_config(path: str | Path = "config/filter_config.yaml") -> FilterConfig:
    """Carrega a política e falha se a configuração estiver incompleta ou incoerente."""

    source = Path(path).resolve()
    if not source.is_file():
        raise ConfigurationError("Arquivo de configuração ausente")
    root = source.parent.parent
    schema_path = source.parent / "filter_config.schema.json"
    if not schema_path.is_file():
        raise ConfigurationError("Schema de configuração ausente")

    values = yaml.safe_load(source.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(values), key=lambda e: list(e.path))
    if errors:
        locations = [".".join(map(str, error.path)) or "<root>" for error in errors]
        raise ConfigurationError("Configuração inválida em: " + ", ".join(locations))

    segmentation = values["segmentation"]
    limits = values["input_limits"]
    # O tokenizer adiciona dois tokens especiais; a janela precisa deixar esse espaço.
    if segmentation["window_tokens"] > limits["max_model_tokens_per_unit"] - 2:
        raise ConfigurationError("window_tokens não deixa espaço para tokens especiais")
    if segmentation["window_stride_tokens"] > segmentation["window_tokens"]:
        raise ConfigurationError("window_stride_tokens não pode exceder window_tokens")

    required_files = (
        Path(values["segmentation"]["conjunctions_file"]),
        Path(values["paths"]["forbidden_patterns"]),
        Path(values["paths"]["out_of_scope_rules"]),
        Path(values["paths"]["safe_conversation_patterns"]),
        Path(values["paths"]["domain_terms"]),
    )
    for relative in required_files:
        if not (root / relative).is_file():
            raise ConfigurationError(f"Arquivo obrigatório ausente: {relative}")
    return FilterConfig(root=root, source=source, values=values)
