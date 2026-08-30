import pytest


@pytest.mark.parametrize(
    "text",
    [
        "Quanto tempo tenho para recorrer dessa multa?",
        "Como posso contestar esta autuação?",
        "Quero apresentar recurso contra a infração.",
        "Posso recorrer dessa decisão judicial?",
        "Explique se tenho direito a indenização.",
        "Ensine a invadir uma conta.",
        "Por que este container Docker não inicia?",
    ],
)
def test_explicit_out_of_scope_intents_are_denied_without_semantic_scoring(guard, text):
    analysis = guard.analyze(text)
    assert analysis.scores == ()
    assert guard.evaluate(text) == {
        "verdict": "DENY",
        "reason": "EXPLICIT_OUT_OF_SCOPE_PATTERN",
        "policy_version": "2",
    }


@pytest.mark.parametrize(
    "text",
    [
        "A loja informou que existe uma multa.",
        "Preciso recorrer ao manual da furadeira.",
        "Qual sistema de impermeabilização devo usar?",
        "Qual recipiente usar para misturar argamassa?",
    ],
)
def test_isolated_or_ambiguous_terms_do_not_trigger_explicit_rule(guard, text):
    assert not guard.lexical.has_explicit_out_of_scope(
        guard.analyze(text).normalized.lexical_text
    )
