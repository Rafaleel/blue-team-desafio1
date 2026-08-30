from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .assets import verify_prototype_assets
from .config import FilterConfig, load_config
from .embedder import ONNXEmbedder, verify_runtime_artifacts
from .lexical import LexicalPolicy
from .normalize import InputRejected, NormalizedText, normalize_input
from .reasons import Reason, Verdict
from .scorer import PrototypeScorer, UnitScore
from .segment import DeterministicSegmenter


@dataclass(frozen=True)
class Analysis:
    """Resultado reutilizável da análise, separado dos thresholds de decisão."""

    fixed_reason: Reason | None
    normalized: NormalizedText | None
    scores: tuple[UnitScore, ...]
    token_count: int
    has_domain_evidence: bool


class DomainGuardFilter:
    """Orquestra as camadas locais e produz uma decisão funcional estável."""

    def __init__(self, config_path: str | Path = "config/filter_config.yaml"):
        self.config: FilterConfig = load_config(config_path)
        verify_runtime_artifacts(self.config.root, self.config.path("model_manifest"))
        verify_prototype_assets(self.config.root, self.config.path("prototype_manifest"))
        limits = self.config.section("input_limits")
        self.embedder = ONNXEmbedder(
            self.config.path("runtime_model"),
            self.config.path("tokenizer"),
            self.config.section("runtime"),
            limits["max_model_tokens_per_unit"],
        )
        self.lexical = LexicalPolicy(
            self.config.path("forbidden_patterns"),
            self.config.path("safe_conversation_patterns"),
            self.config.path("domain_terms"),
        )
        self.segmenter = DeterministicSegmenter(
            self.config.root, self.config.values, self.embedder
        )
        positive = np.load(self.config.path("positive_embeddings"), allow_pickle=False)
        negative = np.load(self.config.path("negative_embeddings"), allow_pickle=False)
        self.scorer = PrototypeScorer(
            positive, negative, self.config.section("thresholds")["score_scale"]
        )

    def analyze(self, raw_text: object) -> Analysis:
        """Executa defesas baratas primeiro e calcula embeddings apenas se necessário."""

        try:
            normalized = normalize_input(raw_text, self.config.values)
        except InputRejected as rejection:
            return Analysis(rejection.reason, None, (), 0, False)
        if not normalized.model_text:
            return Analysis(Reason.EMPTY_INPUT, normalized, (), 0, False)
        if self.lexical.has_forbidden_control(normalized.lexical_text):
            return Analysis(Reason.FORBIDDEN_CONTROL_PATTERN, normalized, (), 0, False)
        if self.lexical.is_safe_conversation(normalized.lexical_text):
            return Analysis(Reason.SAFE_CONVERSATIONAL_INPUT, normalized, (), 0, False)
        try:
            units = self.segmenter.segment(normalized.model_text)
        except InputRejected as rejection:
            return Analysis(rejection.reason, normalized, (), 0, False)
        if not units:
            return Analysis(Reason.EMPTY_INPUT, normalized, (), 0, False)
        vectors = self.embedder.encode_quantized(units)
        return Analysis(
            None,
            normalized,
            self.scorer.score(vectors),
            self.embedder.token_count(normalized.model_text, add_special_tokens=False),
            self.lexical.has_domain_evidence(normalized.lexical_text),
        )

    def decision_from_analysis(
        self,
        analysis: Analysis,
        *,
        min_in_scope_score: int | None = None,
        min_contrastive_margin: int | None = None,
    ) -> tuple[Verdict, Reason]:
        """Aplica thresholds e a política de que todas as unidades devem passar."""

        # Rejeições estruturais e regras de alta precisão não dependem do scorer.
        if analysis.fixed_reason is not None:
            if analysis.fixed_reason is Reason.SAFE_CONVERSATIONAL_INPUT:
                return Verdict.ALLOW, analysis.fixed_reason
            return Verdict.DENY, analysis.fixed_reason

        configured = self.config.section("thresholds")
        in_threshold = configured["min_in_scope_score"] if min_in_scope_score is None else min_in_scope_score
        margin_threshold = (
            configured["min_contrastive_margin"]
            if min_contrastive_margin is None
            else min_contrastive_margin
        )
        if in_threshold is None or margin_threshold is None:
            raise RuntimeError("Filtro ainda não calibrado")

        passing = [
            score.in_score >= in_threshold and score.margin >= margin_threshold
            for score in analysis.scores
        ]
        if (
            all(passing)
            and analysis.token_count <= self.config.section("ambiguity")["max_tokens_without_context"]
            and not analysis.has_domain_evidence
        ):
            return Verdict.DENY, Reason.AMBIGUOUS_OR_MISSING_CONTEXT
        if all(passing):
            return Verdict.ALLOW, Reason.IN_SCOPE_VALIDATED
        # Uma combinação de unidades aprovadas e reprovadas caracteriza intenção mista.
        if any(passing):
            return Verdict.DENY, Reason.MIXED_SCOPE_DETECTED
        worst = min(analysis.scores, key=lambda score: (score.in_score, score.margin, score.position))
        if worst.in_score < in_threshold:
            return Verdict.DENY, Reason.OUT_OF_SCOPE_SEMANTIC_DISTANCE
        return Verdict.DENY, Reason.OUT_OF_SCOPE_CONTRASTIVE_MARGIN

    def evaluate(self, raw_text: object) -> dict[str, str]:
        """Retorna somente veredito, motivo e versão, sem ecoar o texto avaliado."""

        verdict, reason = self.decision_from_analysis(self.analyze(raw_text))
        return {
            "verdict": verdict.value,
            "reason": reason.value,
            "policy_version": self.config.policy_version,
        }
