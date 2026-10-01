## Why

As Sprints 1 a 5 entregaram o pipeline, a análise e o modelo. A Sprint 6 fecha o que o **enunciado** cobra na banca:
- **item 2:** a frase de fechamento com números do próprio pipeline e "um responsável concreto pela decisão, uma ação possível, um prazo e o custo de errar";
- **Requisito 6:** o decisor, o custo de falso positivo e de falso negativo, o limiar adotado e por quê, e as limitações;
- **Requisito 4:** um README que permita rodar tudo do zero.

A seção 8 do `architecture.md` define o pronto da Sprint 6: **"alguém de fora do grupo consegue rodar o pipeline seguindo só o README"**.

**Decisões do grupo (2026-09-27):**
- **Decisor:** a **diretoria de crédito de uma instituição financeira de atuação nacional**, que decide a cada trimestre em quais estados e modalidades expandir ou reduzir a oferta de financiamento. Substitui "cooperativa ou financeira regional", que não combinava com um estudo dos 27 estados. A seção 0 é mantida, porque o enunciado exige o decisor.
- **Checklist anti-vazamento completo com as perguntas do enunciado:** entidades em treino e teste, e imputadores.
- **Registrar que a API do Ipeadata não pagina** (Requisito 2 pede paginação).

**Proposta de limiar, a confirmar pelo grupo antes do apply:** recomendar **expandir nas 20 combinações com maior probabilidade** de ganhar força a cada trimestre, em vez de uma nota mínima fixa. No teste (fev/2025–jan/2026):

| Regra | Recomendações por mês | Acerto |
|---|---|---|
| nota ≥ 0,5 | ~107 | 67,7% |
| nota ≥ 0,7 | ~73 | 72,2% |
| nota ≥ 0,8 | ~48 | 76,2% |
| **20 maiores notas** | **20** | **82,5%** |
| nota ≥ 0,9 | ~15 | 84,8% |
| regra simples "volta ao normal" (20 maiores) | 20 | 75,0% |

Por quê:
- **O falso positivo** (expandir onde o crédito perde força) tem custo imediato: capital e equipe alocados, meta não batida. Vale ser seletivo.
- **Uma lista fixa e curta** combina com a capacidade de execução de uma diretoria.
- **É fácil de explicar.**

## What Changes

- **Nova etapa "decisão"** (`src/ml/decisao.py` + `run_pipeline.py`):
  - lê as previsões do ML e grava a **lista de recomendação** de set–nov/2026: as `TOP_RECOMENDACAO` (20) combinações com maior probabilidade de ganhar força, e as 20 com maior chance de perder força como alerta;
  - grava a **tabela de sensibilidade** calculada no teste: acerto e quantidade por limiar (0,5 a 0,9) e por tamanho de lista (10, 20 e 40), para o modelo e para a regra simples;
  - grava os **números da frase de fechamento**, para o texto nunca ter número digitado à mão.
- **`docs/architecture.md`:**
  - **seção 0:** o decisor novo, o escopo atualizado (o modelo já existe) e "onde os dados vivem" com a nota da publicação futura;
  - **seção 1:** a **frase de fechamento preenchida** com os números do pipeline;
  - **seção 10:** a ação, o custo de falso positivo e de falso negativo **para uma instituição de atuação nacional**, e o **limiar adotado e o porquê**, ligando a métrica à consequência;
  - **seção 6.3:** o checklist completo com as perguntas do enunciado. Os mesmos estados aparecem em treino e teste **de propósito**, porque a previsão é sobre o futuro das mesmas entidades (justificado na 6.2), e o split é temporal, com embargo. **Nenhum imputador**: as linhas sem histórico completo são excluídas, não preenchidas;
  - **seções 3 e 2.2:** a API do Ipeadata **não oferece paginação** (devolve a série inteira; `$top`/`$skip` são ignorados, conferido em 2026-09-27). Por isso o requisito de paginação é atendido na medida do que a fonte permite, com timeout, retry com backoff e carga incremental;
  - **seção 11:** as limitações do modelo (a Selic não antecipa o trimestre, as previsões extremas em combinações pequenas, uma avaliação só de 12 meses finais e os rótulos sobrepostos);
  - **seção 13:** as decisões 13 (decisor) e 14 (limiar).
- **`README.md` completo:**
  - o que o projeto responde, com a frase de fechamento;
  - **como rodar do zero** (Python 3.11, venv, `requirements.txt`, primeira carga de ~50 min e a repetição em segundos, testes e notebooks);
  - onde ficam os resultados;
  - a estrutura e as fontes, com as licenças;
  - a demonstração de idempotência;
  - as sprints atualizadas;
  - as limitações.
- **`CLAUDE.md`:** o trecho que diz "o projeto está na Sprint 1 e os módulos estão vazios" é atualizado.
- **Verificação do pronto:** um **clone limpo** numa pasta temporária, seguindo **só o README** (venv novo, instalação, `pytest`, pipeline com `--anos 2024`). O que faltar no README é corrigido.

Fora do escopo: a publicação na nuvem (Neon + Next.js), numa sprint futura.

## Capabilities

### New Capabilities
- `recomendacao-decisao`: lista de recomendação do trimestre, tabela de sensibilidade de limiares e números da frase de fechamento, gerados pelo pipeline a partir do modelo.

### Modified Capabilities

*(Nenhuma — o modelo e as camadas não mudam.)*

## Impact

- **Código:** `src/ml/decisao.py` (novo), uma etapa no `run_pipeline.py` e constantes no `config.py` (`TOP_RECOMENDACAO`, `LIMIARES_SENSIBILIDADE`, caminhos).
- **Testes:** `tests/test_decisao.py`.
- **Documentação:** `docs/architecture.md` (0, 1, 2.2, 3, 6.3, 10, 11, 13), `docs/data_dictionary.md` (saídas da decisão), `README.md` e `CLAUDE.md`.
- **Dados:** 3 arquivos pequenos em `data/final/`, fora do Git.
