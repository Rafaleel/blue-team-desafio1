# Relatório do Domain Guard Filter

Este arquivo é gerado por `make eval`. Valores numéricos não devem ser editados manualmente.

## O que foi construído

Um filtro local para o domínio de materiais de construção. Ele combina normalização Unicode, padrões de controle de alta precisão, segmentação com janelas sobrepostas e comparação semântica com múltiplos protótipos públicos. A decisão usa scores inteiros e retorna veredito, motivo e versão da política.

## Resultado no conjunto versionado

| Métrica | Valor |
|---|---:|
| Amostras | 64 |
| Verdadeiros ALLOW | 29 |
| Verdadeiros DENY | 31 |
| Escapes | 1 |
| Bloqueios indevidos | 3 |
| Acurácia | 93,75% |
| Precisão de ALLOW | 96,67% |
| Recall de ALLOW | 90,62% |
| F1 de ALLOW | 93,55% |
| Taxa de escape | 3,12% |
| Taxa de bloqueio indevido | 9,38% |

## Resultado por categoria

| Categoria | Acertos | Total |
|---|---:|---:|
| alvenaria | 4 | 4 |
| ambiguo | 2 | 2 |
| atendimento | 0 | 1 |
| conhecimento_geral | 3 | 3 |
| controle_assistente | 3 | 3 |
| conversa_segura | 2 | 2 |
| direito | 3 | 4 |
| eletrica | 4 | 4 |
| entretenimento | 2 | 2 |
| ferramentas | 2 | 3 |
| fronteira_direito | 1 | 1 |
| fronteira_medica | 1 | 1 |
| fronteira_norma | 1 | 1 |
| fronteira_seguranca | 0 | 1 |
| hidraulica | 4 | 4 |
| impermeabilizacao | 2 | 2 |
| medicina | 4 | 4 |
| misto | 5 | 5 |
| misto_multiparagrafo | 2 | 2 |
| pintura | 4 | 4 |
| pisos_revestimentos | 4 | 4 |
| programacao | 4 | 4 |
| seguranca_obra | 2 | 2 |
| unicode_adversarial | 1 | 1 |

## Erros observados

- `test-023`: esperado ALLOW, obtido DENY (OUT_OF_SCOPE_CONTRASTIVE_MARGIN).
- `test-029`: esperado ALLOW, obtido DENY (OUT_OF_SCOPE_CONTRASTIVE_MARGIN).
- `test-031`: esperado ALLOW, obtido DENY (OUT_OF_SCOPE_SEMANTIC_DISTANCE).
- `test-038`: esperado DENY, obtido ALLOW (IN_SCOPE_VALIDATED).

## Onde parei e por quê

Os thresholds foram escolhidos somente com o conjunto de calibração. A primeira execução do conjunto separado revelou um defeito geral de segmentação: diferenças de pontuação terminal geravam unidades semanticamente duplicadas, e separadores genéricos produziam fragmentos sem contexto. A correção removeu a pontuação terminal antes da deduplicação e retirou separadores excessivos; por isso, este teste não é apresentado como totalmente cego. Os erros restantes foram mantidos, sem adicionar protótipos específicos para fazê-los desaparecer.

O conjunto é sintético e pequeno. A principal evidência de generalização será a avaliação externa com entradas novas e conhecimento completo do código. O filtro decide domínio, mas não substitui as demais proteções do assistente.
