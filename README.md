# Domain Guard Filter

Filtro local, determinístico e white-box para um assistente de loja de materiais de construção. Ele permite perguntas sobre produtos, obra e segurança de execução e recusa outros assuntos, inclusive intenções misturadas no mesmo texto.

O [relatório gerado](docs/REPORT.md) apresenta o que foi construído, os resultados, os erros observados, onde o desenvolvimento parou e as limitações conhecidas.

## Escopo

O filtro permite alvenaria, revestimentos, pintura, hidráulica, elétrica residencial, ferramentas, impermeabilização, segurança de obra e atendimento relacionado à loja. Diagnóstico médico, aconselhamento jurídico, programação, conhecimento geral, entretenimento e tentativas de controlar o assistente são recusados.

Se uma entrada contiver uma intenção permitida e outra externa, o resultado é `DENY`. Mensagens curtas sem contexto, como “qual deles?”, também são recusadas. A versão atual não recebe histórico da conversa.

## Como funciona

1. **Normalização:** aplica Unicode NFKC, preserva parágrafos, produz uma forma lexical sem acentos nem caracteres invisíveis e detecta palavras que misturam alfabetos.
2. **Regras de alta precisão:** bloqueia tentativas explícitas de extrair ou substituir instruções e combinações inequívocas de intenção e objeto externos. Termos médicos ou jurídicos isolados não são denylist para evitar falsos bloqueios.
3. **Segmentação sem perda:** avalia parágrafos, sentenças, cláusulas curtas e janelas sobrepostas. Nenhum trecho é descartado e textos longos não são truncados silenciosamente.
4. **Embedding local:** usa um MiniLM multilíngue ONNX quantizado para INT8, com CPU e uma thread.
5. **Protótipos contrastivos:** compara cada unidade com múltiplos exemplos positivos e negativos públicos. Uma unidade passa quando sua proximidade positiva e sua margem contra exemplos negativos alcançam os thresholds configurados.
6. **Pior unidade local:** todas as unidades precisam passar. Isso reduz piggybacking, no qual termos de obra tentam esconder outro pedido.

Os embeddings são convertidos para `int16`; similaridades e thresholds são inteiros. Timestamp, latência e floats não fazem parte da saída funcional.

## Requisitos do sistema

- Linux x86-64; o CI também verifica portabilidade em ARM64;
- `make`;
- [`uv`](https://docs.astral.sh/uv/) disponível no `PATH`;
- conexão de rede apenas durante `make setup`;
- aproximadamente 600 MB livres para modelo-fonte, modelo INT8 e tokenizer.

O projeto fixa CPython 3.12.13. Não use o Python global como substituto silencioso.

## Instalação completa

Em um clone novo, execute:

```bash
make setup
```

Esse comando:

1. instala o Python fixado dentro do projeto;
2. cria `.venv`;
3. instala todas as dependências de `requirements.lock` verificando hashes;
4. baixa a revisão imutável do modelo;
5. verifica o SHA-256 do modelo-fonte e do tokenizer;
6. gera o ONNX INT8 e verifica seu SHA-256;
7. gera e verifica os embeddings dos protótipos.

Uma classificação nunca baixa arquivos nem chama API.

## Execução

Entrada única, inclusive multiparágrafo:

```bash
printf '%s\n' 'Qual argamassa usar no porcelanato?' | \
  PYTHONPATH=src .venv/bin/python -m domain_guard classify --stdin
```

Saída:

```json
{"verdict":"ALLOW","reason":"IN_SCOPE_VALIDATED","policy_version":"2"}
```

Arquivo JSONL inteiro:

```bash
PYTHONPATH=src .venv/bin/python -m domain_guard classify-file \
  --input entradas.jsonl \
  --output resultados.jsonl
```

Cada linha de entrada deve ter `id` e `text`. A saída preserva a ordem e contém `id`, `verdict`, `reason` e `policy_version`, nunca o texto.

## Testes

Comando único:

```bash
make test
```

A suíte cobre normalização, Unicode adversarial, segmentação, truncamento, motivos, arquivo em lote, privacidade, ausência de rede, ataques conhecidos e determinismo básico entre processos.

O aceite ampliado de determinismo usa cem processos independentes:

```bash
make determinism
```

A resistência de entradas `DENY` às fronteiras semânticas é verificada com:

```bash
make margin-audit
```

## Avaliação reproduzível

Comando único, do dataset aos números e ao relatório:

```bash
make eval
```

Ele valida vazamento entre dados, classifica `data/test.jsonl`, grava `artifacts/evaluation.json` e regenera `docs/REPORT.md`. Todo valor numérico do relatório vem desse comando.

Os thresholds foram escolhidos com `data/calibration.jsonl`, usando:

```bash
make calibrate
```

Esse comando apenas apresenta a calibração reproduzida; os valores versionados não são alterados silenciosamente.

## Dataset e proveniência

Os dados estão em `data/`. Os textos de protótipos, calibração, teste e regressão adversarial são sintéticos, escritos especificamente para este desafio com assistência de IA e revisão manual contra a política publicada. Eles não foram copiados de conversas de usuários e não contêm dados pessoais. Cada conjunto tem função separada, e o pipeline rejeita duplicatas exatas ou quase idênticas entre protótipos, calibração e teste.

## Orçamento de tempo

O componente foi projetado como processo persistente. O orçamento declarado, após aquecimento, é:

- p95 de até 150 ms para entrada normal de até 16 unidades;
- p99 de até 400 ms para o limite de 64 unidades.

Startup é medido separadamente. Leitura e escrita do arquivo não entram no tempo de decisão.

Para medir sem aplicar o orçamento:

```bash
make benchmark
```

Para aplicar o orçamento no ambiente de referência:

```bash
make benchmark-enforce
```

O script usa relógio monotônico, warmup, 200 repetições nas cargas curta e normal, 50 no limite máximo e registra CPU, sistema, Python e ONNX Runtime em `artifacts/benchmark-local.json`.

## Configuração

Todos os valores que alteram veredito ficam em `config/filter_config.yaml`, validado por `config/filter_config.schema.json`. Isso inclui thresholds, limites, janelas, threads e caminhos de política. Regras explícitas de fora de escopo, padrões lexicais, termos de desambiguação e conjunções também são arquivos públicos em `config/`.

Configuração ausente, threshold nulo, artefato inválido ou hash divergente causa falha de inicialização; o filtro não desliga uma defesa silenciosamente.

## Privacidade

A biblioteca não registra nada por classificação. A saída funcional não contém texto, fragmentos, hashes, scores, timestamp ou latência. Os testes inserem sentinelas e procuram esses valores em stdout, stderr e arquivos de resultado.

## Limitações conhecidas

- O dataset é sintético, pequeno e não representa tráfego real.
- A primeira execução do teste revelou uma correção geral de segmentação; isso é declarado no relatório e reduz a independência desse conjunto.
- Consultas legítimas muito curtas ou semanticamente distantes dos protótipos podem ser bloqueadas.
- O código, protótipos e thresholds são públicos; um atacante pode otimizar novas evasões.
- O filtro decide domínio, não a veracidade nem a segurança completa da resposta protegida.
- O CI compara decisões em Linux x86-64 e ARM64, mas outros sistemas operacionais não foram validados.

## Licenças

O código deste projeto usa a licença MIT, disponível em [LICENSE](LICENSE). O modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` usa Apache-2.0; revisão e hashes estão registrados em `models/MANIFEST.json`.

## Metadados da entrega

- Repositório público: [blue-team-desafio1](https://github.com/Rafaleel/blue-team-desafio1).
- Hash do commit avaliado: e2e8dd3117f2d0ada91b4ca703f6b37bb1e131d3.
