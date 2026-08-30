from __future__ import annotations

from pathlib import Path

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


class LexicalPolicy:
    """Aplica somente regras lexicais de alta precisão e evidências de domínio."""

    def __init__(self, forbidden_path: Path, safe_path: Path, domain_terms_path: Path):
        self.forbidden = _read_patterns(forbidden_path)
        self.safe = frozenset(_read_patterns(safe_path))
        self.domain_terms = _read_patterns(domain_terms_path)

    def has_forbidden_control(self, lexical_text: str) -> bool:
        """Detecta padrões explícitos de extração ou substituição de instruções."""

        padded = f" {lexical_text} "
        return any(f" {pattern} " in padded for pattern in self.forbidden)

    def is_safe_conversation(self, lexical_text: str) -> bool:
        """Permite apenas mensagens inteiras que correspondam a uma conversa segura."""

        candidate = lexical_text.strip(" \t\n.!?,;:")
        return candidate in self.safe

    def has_domain_evidence(self, lexical_text: str) -> bool:
        """Indica se uma mensagem curta contém algum termo explícito do domínio."""

        padded = f" {lexical_text} "
        return any(f" {term} " in padded for term in self.domain_terms)
