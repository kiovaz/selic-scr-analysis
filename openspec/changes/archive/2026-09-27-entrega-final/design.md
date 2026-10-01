## Context

O motivo e as decisões estão em `proposal.md`; o requisito novo está na spec `recomendacao-decisao`.

Estado atual:
- **ML pronto (Sprint 5):**
  - `data/final/ml_previsoes_teste.parquet`, com `uf, modalidade, origem, ganha_forca, prob_ganha_forca, prob_sem_selic`;
  - `data/final/ml_previsao_producao.parquet`, com 174 linhas para set–nov/2026;
  - `ml_resultados.json`.
- **Gold** com `volume_rs` por combinação e mês, e a **análise** da Sprint 4 em `analise_brasil_modalidade.parquet`.
- **Documentação em aberto:**
  - seção 10: o limiar "PENDENTE", o decisor antigo e a frase "a preencher";
  - README: as sprints desmarcadas e a seção "Como rodar" parando na Sprint 1;
  - `CLAUDE.md`: diz "Sprint 1, pacotes vazios".
- **Ambiente:** o CI roda Python 3.11. Esta máquina **não tem** Python 3.11 (o `.venv` é 3.14), o que importa para o teste do clone limpo (decisão 5).

## Goals / Non-Goals

**Goals:**
- Cumprir os itens 2, 6, 8 e 9 do enunciado com números do pipeline.
- Um README que um colega de fora siga sem ajuda.

**Non-Goals:**
- Mudar o modelo ou a análise.
- Calcular o ganho em reais.
- A publicação na nuvem.
- Os commits dos outros integrantes e o ensaio da defesa, que são do grupo.

## Decisions

### 1. A recomendação como etapa do pipeline, não como texto

`src/ml/decisao.py` com `montar_recomendacao()`, `tabela_sensibilidade()`, `numeros_da_frase()` e `executar_decisao()`. As saídas vão para `data/final/`:
- `recomendacao_trimestre.parquet`;
- `sensibilidade_limiar.parquet`;
- `frase_fechamento.json`.

Os textos da seção 1 e da seção 10 e o README citam os números desse JSON, que também são impressos no pipeline. *Por quê:* o enunciado pede a frase "com números do próprio pipeline". Se o pipeline rodar de novo e os números mudarem, a divergência aparece na hora.

### 2. Limiar: lista das 20 maiores notas

A regra de decisão é **"a cada trimestre, expandir nas 20 combinações com maior probabilidade de ganhar força"**, com `TOP_RECOMENDACAO = 20` no `config.py`. Em vez de uma nota mínima fixa, vale uma lista de tamanho fixo, porque:
- a capacidade de execução de uma diretoria é um número de frentes, não uma probabilidade;
- as notas do gradient boosting não são probabilidades calibradas, então comparar "0,8" entre trimestres engana, e o ranking não depende disso;
- a tabela de sensibilidade mostra o equilíbrio para quem quiser outro tamanho de lista.

**Custo do erro** para uma instituição de atuação nacional, que vai para a seção 10:
- **Falso positivo** (expandir onde o crédito perde força): orçamento de captação e marketing, equipe comercial realocada, meta regional não batida e pressão para afrouxar a concessão. É imediato.
- **Falso negativo** (não expandir onde ganha força): participação de mercado cedida a concorrentes e custo de reentrada depois. É de oportunidade.
- O falso positivo pesa mais no curto prazo, então a regra favorece a **precisão**: uma lista curta com acerto alto, em vez de cobrir todas as oportunidades. O recall baixo é assumido e fica escrito.

### 3. Frase de fechamento

O modelo é este, com os números vindos do JSON:

> "Cruzando o **SCR.data (Banco Central)** e a **Selic meta do Copom (Ipeadata)**, identificamos que **o crédito imobiliário anda junto com a Selic de 4 meses antes (ρ = +0,42), mas a Selic não antecipa o trimestre seguinte; o que antecipa é o próprio ritmo recente do crédito em cada estado**. Recomendamos que **a diretoria de crédito de uma instituição financeira de atuação nacional** faça **a expansão da oferta de financiamento nas 20 combinações estado × modalidade com maior probabilidade de ganhar força** nos próximos **3 meses (set–nov/2026)**, priorizando **as de maior saldo dentro da lista**. Se agir, o ganho esperado é **acertar ~16,5 de 20 expansões por trimestre (82,5%), contra ~15 da regra simples e ~10 ao acaso**; se errarmos, o custo é **~3,5 expansões por trimestre em mercados que estão perdendo força — capital e equipe alocados sem retorno no trimestre**."

"Priorizando as de maior saldo" usa o `volume_rs` da lista: dentro das 20, a execução começa pelos mercados maiores.

### 4. Checklist 6.3 com as perguntas do enunciado

São acrescentados dois itens, com resposta e evidência:
- **"O split respeita tempo e grupo? Nenhuma entidade aparece em treino e teste ao mesmo tempo?"** Resposta: o split é **temporal**. As mesmas 174 combinações aparecem em treino e teste **de propósito**, porque o objetivo é prever o futuro dessas mesmas entidades (seção 6.2). Nenhuma observação do teste (origem e trimestre futuro) cruza com o treino, garantido pelo embargo de 5 meses. Split por grupo não se aplica.
- **"Imputadores ajustados só no treino?"** Resposta: **não há imputação**. Linhas sem 12 meses de histórico são excluídas, e as 42 combinações com buracos ficam fora da coorte.

### 5. Verificação do clone limpo

Numa pasta temporária: `git clone` do branch, `python -m venv`, `pip install -r requirements.txt`, `pytest` e `python scripts/run_pipeline.py --anos 2024`. É **só um ano**, para não baixar ~2 GB. Os passos seguem **exatamente** o README; o que precisar de ajuda que o README não dá vira correção nele.

**Limitação registrada:** esta máquina não tem Python 3.11, então o teste usa o Python disponível (3.14). O CI confirma o 3.11 a cada PR. O README passa a pedir **Python 3.11** explicitamente, e um integrante do grupo, a "pessoa de fora" da seção 8, refaz o roteiro na máquina dele antes da entrega.

## Risks / Trade-offs

- [O grupo preferir outro limiar] → a regra é um parâmetro (`TOP_RECOMENDACAO`), e a tabela de sensibilidade já mostra as alternativas. A troca é só de número e texto.
- [Python 3.11 não testado localmente] → mitigado pelo CI em 3.11 e pela verificação de um integrante.
- [A frase de fechamento simplificar demais] → as ressalvas (associação não é causa, previsões extremas em mercados pequenos, avaliação em 12 meses) ficam na seção 11 e no README, logo após a frase.

## Migration Plan

1. Documentação primeiro (seções 0, 10, 6.3, 2.2/3, 11 e 13), depois o código da decisão e os testes.
2. Rodar a etapa de decisão sobre as previsões reais e preencher a frase e a seção 10 com o JSON.
3. README e `CLAUDE.md`.
4. Clone limpo.
5. PR.
