"""Gera docs/REPORT.md exclusivamente a partir de artifacts/evaluation.json."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def percent(value: float) -> str:
    return f"{value * 100:.2f}%".replace(".", ",")


def main() -> int:
    evaluation = json.loads((ROOT / "artifacts" / "evaluation.json").read_text(encoding="utf-8"))
    metrics = evaluation["metrics"]
    error_lines = [
        f"- `{item['id']}`: esperado {item['expected']}, obtido {item['predicted']} ({item['reason']})."
        for item in evaluation["errors"]
    ] or ["- Nenhum erro observado no conjunto versionado."]
    category_lines = [
        f"| {category} | {values['correct']} | {values['total']} |"
        for category, values in evaluation["categories"].items()
    ]
    report = f"""# Relatório do Domain Guard Filter

Este arquivo é gerado por `make eval`. Valores numéricos não devem ser editados manualmente.

## O que foi construído

Um filtro local para o domínio de materiais de construção. Ele combina normalização Unicode, padrões de controle de alta precisão, segmentação com janelas sobrepostas e comparação semântica com múltiplos protótipos públicos. A decisão usa scores inteiros e retorna veredito, motivo e versão da política.

## Resultado no conjunto versionado

| Métrica | Valor |
|---|---:|
| Amostras | {metrics['total']} |
| Verdadeiros ALLOW | {metrics['tp']} |
| Verdadeiros DENY | {metrics['tn']} |
| Escapes | {metrics['fp']} |
| Bloqueios indevidos | {metrics['fn']} |
| Acurácia | {percent(metrics['accuracy'])} |
| Precisão de ALLOW | {percent(metrics['allow_precision'])} |
| Recall de ALLOW | {percent(metrics['allow_recall'])} |
| F1 de ALLOW | {percent(metrics['allow_f1'])} |
| Taxa de escape | {percent(metrics['escape_rate'])} |
| Taxa de bloqueio indevido | {percent(metrics['false_block_rate'])} |

## Resultado por categoria

| Categoria | Acertos | Total |
|---|---:|---:|
{chr(10).join(category_lines)}

## Erros observados

{chr(10).join(error_lines)}

## Onde parei e por quê

Os thresholds foram escolhidos somente com o conjunto de calibração. A primeira execução do conjunto separado revelou um defeito geral de segmentação: diferenças de pontuação terminal geravam unidades semanticamente duplicadas, e separadores genéricos produziam fragmentos sem contexto. A correção removeu a pontuação terminal antes da deduplicação e retirou separadores excessivos; por isso, este teste não é apresentado como totalmente cego. Os erros restantes foram mantidos, sem adicionar protótipos específicos para fazê-los desaparecer.

O conjunto é sintético e pequeno. A principal evidência de generalização será a avaliação externa com entradas novas e conhecimento completo do código. O filtro decide domínio, mas não substitui as demais proteções do assistente.
"""
    output = ROOT / "docs" / "REPORT.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
