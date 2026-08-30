from __future__ import annotations

from pathlib import Path

import yaml

from .normalize import lexical_canonical


def _read_patterns(path: Path) -> tuple[str, ...]:
    """Lê padrões públicos usando a mesma canonicalização aplicada às entradas."""

    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.append(lexical_canonical(stripped))
    if not patterns:
        raise RuntimeError("Arquivo de padrões vazio")
    return tuple(patterns)


def _read_out_of_scope_rules(path: Path) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """Carrega grupos de termos; cada regra exige um termo de cada grupo."""

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"schema_version", "rules"}:
        raise RuntimeError("Schema inválido nas regras explícitas de fora de escopo")
    if document["schema_version"] != 1 or not isinstance(document["rules"], list):
        raise RuntimeError("Versão ou lista inválida nas regras explícitas de fora de escopo")

    identifiers = set()
    rules = []
    for rule in document["rules"]:
        if not isinstance(rule, dict) or set(rule) != {"id", "all"}:
            raise RuntimeError("Regra explícita de fora de escopo inválida")
        identifier = rule["id"]
        groups = rule["all"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise RuntimeError("ID inválido ou duplicado nas regras de fora de escopo")
        if not isinstance(groups, list) or not groups:
            raise RuntimeError(f"Regra sem grupos: {identifier}")
        identifiers.add(identifier)

        normalized_groups = []
        for group in groups:
            if not isinstance(group, list) or not group or not all(
                isinstance(term, str) and term.strip() for term in group
            ):
                raise RuntimeError(f"Grupo inválido na regra: {identifier}")
            normalized_groups.append(tuple(lexical_canonical(term) for term in group))
        rules.append(tuple(normalized_groups))
    if not rules:
        raise RuntimeError("Arquivo de regras explícitas de fora de escopo vazio")
    return tuple(rules)


def _contains_phrase(padded_text: str, phrase: str) -> bool:
    return f" {phrase} " in padded_text


class LexicalPolicy:
    """Aplica somente regras lexicais de alta precisão e evidências de domínio."""

    def __init__(
        self,
        forbidden_path: Path,
        out_of_scope_path: Path,
        safe_path: Path,
        domain_terms_path: Path,
    ):
        self.forbidden = _read_patterns(forbidden_path)
        self.out_of_scope = _read_out_of_scope_rules(out_of_scope_path)
        self.safe = frozenset(_read_patterns(safe_path))
        self.domain_terms = _read_patterns(domain_terms_path)

    def has_forbidden_control(self, lexical_text: str) -> bool:
        """Detecta padrões explícitos de extração ou substituição de instruções."""

        padded = f" {lexical_text} "
        return any(_contains_phrase(padded, pattern) for pattern in self.forbidden)

    def has_explicit_out_of_scope(self, lexical_text: str) -> bool:
        """Rejeita apenas combinações públicas de termos inequivocamente externos."""

        padded = f" {lexical_text} "
        return any(
            all(any(_contains_phrase(padded, term) for term in group) for group in rule)
            for rule in self.out_of_scope
        )

    def is_safe_conversation(self, lexical_text: str) -> bool:
        """Permite apenas mensagens inteiras que correspondam a uma conversa segura."""

        candidate = lexical_text.strip(" \t\n.!?,;:")
        return candidate in self.safe

    def has_domain_evidence(self, lexical_text: str) -> bool:
        """Indica se uma mensagem curta contém algum termo explícito do domínio."""

        padded = f" {lexical_text} "
        return any(_contains_phrase(padded, term) for term in self.domain_terms)
