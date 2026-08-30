from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .reasons import Reason


_C0_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")
_WORD = re.compile(r"\w+", re.UNICODE)


class InputRejected(ValueError):
    """Recusa esperada de entrada, acompanhada de um motivo público e estável."""

    def __init__(self, reason: Reason):
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class NormalizedText:
    """Representações separadas para o modelo semântico e para regras lexicais."""

    model_text: str
    lexical_text: str


def _letter_script(character: str) -> str | None:
    if not character.isalpha():
        return None
    name = unicodedata.name(character, "")
    for script in ("LATIN", "CYRILLIC", "GREEK"):
        if script in name:
            return script
    return None


def _contains_mixed_script_word(text: str) -> bool:
    for word in _WORD.findall(text):
        scripts = {script for char in word if (script := _letter_script(char))}
        if len(scripts) > 1:
            return True
    return False


def lexical_canonical(text: str) -> str:
    """Canonicaliza texto para comparar padrões apesar de acentos e formatação invisível."""

    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks_or_format = "".join(
        char
        for char in decomposed
        if unicodedata.category(char) not in {"Mn", "Cf"}
    )
    without_punctuation = re.sub(r"[^\w\s]+", " ", without_marks_or_format, flags=re.UNICODE)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def normalize_input(raw_text: object, config: dict) -> NormalizedText:
    """Valida limites e Unicode sem remover as fronteiras de parágrafo."""

    if not isinstance(raw_text, str):
        raise InputRejected(Reason.INVALID_INPUT_TYPE)
    if len(raw_text) > config["input_limits"]["max_raw_chars"]:
        raise InputRejected(Reason.INPUT_LIMIT_EXCEEDED)
    try:
        raw_text.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise InputRejected(Reason.INVALID_OR_SUSPICIOUS_UNICODE) from error

    # Quebras de linha são preservadas porque o segmentador as usa como fronteira forte.
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)
    if len(text) > config["input_limits"]["max_normalized_chars"]:
        raise InputRejected(Reason.INPUT_LIMIT_EXCEEDED)
    text = _C0_CONTROLS.sub("", text)
    text = "\n".join(_HORIZONTAL_SPACE.sub(" ", line).strip() for line in text.split("\n"))
    text = text.strip()

    if config["unicode_policy"]["reject_mixed_scripts"] and _contains_mixed_script_word(text):
        raise InputRejected(Reason.INVALID_OR_SUSPICIOUS_UNICODE)
    return NormalizedText(model_text=text, lexical_text=lexical_canonical(text))
