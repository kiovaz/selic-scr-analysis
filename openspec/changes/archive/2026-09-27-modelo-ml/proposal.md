## Why

A Sprint 4 mostrou **associação** entre a Selic e o crédito (seção 5.4). O decisor precisa de outra coisa: saber, **para o próximo trimestre, em quais estados e modalidades expandir ou reduzir a oferta** (seção 10). A Sprint 5 constrói esse modelo. O `architecture.md` exige que a tabela 6.1 esteja preenchida **antes** de qualquer código de treino, e que o modelo supere um baseline com o checklist anti-vazamento (6.3) respondido por escrito.

**Decisões do grupo (2026-09-27, revisadas no mesmo dia com números da Gold real):**

| # | Decisão | Por quê |
|---|---|---|
| D1 | **Classificação:** "o crédito desta combinação UF × modalidade vai **ganhar força** no próximo trimestre?" Ganhar força = o saldo crescer mais no trimestre futuro do que cresceu nos últimos 3 meses. A classe positiva é **ganha força = expandir**; perde força = cuidado ao expandir | Liga o modelo à hipótese do trabalho (o ciclo do crédito, onde a Selic atua) e serve ao decisor. Compara o crédito com ele mesmo, então a inflação não distorce. Classes equilibradas: **~50%** positivos |
| D2 | **O trimestre com folga de publicação:** a variação do saldo de **t+2 a t+5** | O BCB publica com ~60 dias. Quando o dado do mês t sai, t+1 e t+2 já passaram; prever t→t+3 seria "prever" meses já decorridos. O rótulo mira o trimestre que o decisor ainda pode usar |
| D3 | **Coorte: as 174 combinações com os 120 meses completos** (99,995% do volume); as 42 com buracos ficam de fora | A série completa evita variáveis com buraco |

A primeira versão (D1 = "cresce mais que o Brasil?", horizonte t→t+3) foi trocada. Ao comparar cada estado com a média do país, o efeito da Selic, que é igual para todos, **se cancela**.

**O que os números já mostram** (medido na Gold, com D1–D3):
- **A Selic sozinha quase não antecipa** o próximo trimestre: AUC de ~0,51 (0,50 = moeda). Modalidade por modalidade, fica entre 0,49 e 0,54. Isso não contradiz a Sprint 4: andar junto não é o mesmo que avisar antes.
- **O próprio crédito antecipa mais:** "se perdeu força, vai ganhar força" (volta ao normal) acerta **64,7%**. É a régua a vencer.

Por isso o modelo é avaliado **com e sem as variáveis da Selic**, para responder de frente "a Selic ajuda a prever?", seja qual for a resposta.

## What Changes

- **`docs/architecture.md` primeiro:** a tabela 6.1 é preenchida com D1–D3 e as consequências. A seção 4.2 ganha a chave da `gold_ml_dataset`, e a seção 13 (Registro de decisões) ganha a decisão 11, incluindo a troca da primeira versão da pergunta.
- **`gold_ml_dataset`** (`src/ml/dataset.py` → `data/final/gold_ml_dataset.parquet`):
  - uma linha por `(uf, modalidade, origem)`;
  - features **só com dados até a origem t**: variações do saldo em 1, 3, 6 e 12 meses; **aceleração** dos últimos 3 meses (crescimento dos últimos 3 meses menos o dos 3 anteriores); variação relativa ao Brasil em 3 e 12 meses; participação no saldo nacional; Selic meta e decisões do Copom nos 3 e 6 meses anteriores; modalidade e UF;
  - rótulo `ganha_forca` (0/1) e a coluna `conjunto`.
- **Avaliação em duas camadas:**
  - **Janela móvel por ano** (blocos de origens 2020, 2021, 2022 e 2023). Cada bloco é previsto por um modelo treinado só com origens até 6 meses antes do bloco. Serve para **escolher o modelo** e medir se o resultado se repete em anos de juros altos e baixos.
  - **Teste final:** origens de **fev/2025 a jan/2026** (rótulos até jun/2026 = t0), avaliado **uma única vez**. O treino vai até ago/2024, com **embargo de 5 meses** (set/2024 a jan/2025), porque o rótulo olha até t+5.
- **Baselines primeiro:** a classe majoritária e a **volta ao normal** ("se perdeu força nos últimos 3 meses, ganha força"), que acerta 64,7%.
- **Modelos:** regressão logística (explicável) e `HistGradientBoostingClassifier`, num `Pipeline` do scikit-learn com `fit` **só no treino** de cada janela. Cada um em duas versões: **com e sem as variáveis da Selic**.
- **Métricas:**
  - **AUC** (principal) e precisão e recall da classe positiva;
  - **as melhores apostas:** a precisão nas **20 combinações de maior probabilidade em cada mês**;
  - a AUC **pesada pelo volume** (errar em SP imobiliário pesa mais que errar no AC);
  - tudo no total e por modalidade;
  - alerta se alguma métrica passar de 0,95.
- **Importância das variáveis** por permutação, para explicar o modelo.
- **Previsão de produção:** a origem t0 = jun/2026 dá, para cada combinação, a probabilidade de ganhar força de **set a nov/2026**.
- **`notebooks/03_modelo.ipynb`:**
  - a definição do problema em texto simples;
  - a comparação com os baselines, o efeito da Selic (com × sem) e a estabilidade por ano;
  - as melhores apostas e as previsões de set–nov/2026;
  - o **checklist 6.3 respondido item a item**;
  - uma nota sobre **por que os números parecem mais firmes do que são**: rótulos de meses seguidos se sobrepõem, e todos os estados sofrem os mesmos choques no mesmo mês. Por isso se mostra a variação entre os anos.
- **Etapa "ML"** no `scripts/run_pipeline.py`, e testes.

Fora do escopo:
- o **limiar de decisão** ligado ao custo do erro (Sprint 6, seção 10);
- a publicação na nuvem;
- regressão (o tamanho da variação).

## Capabilities

### New Capabilities
- `gold-ml-dataset`: construção da base de ML (coorte, rótulo "ganha força" com folga de publicação, features só do passado, conjuntos com embargo).
- `modelo-ml`: baselines, janela móvel por ano, teste final único, comparação com e sem a Selic, métricas de melhores apostas e pesadas por volume, previsão de produção e verificações anti-vazamento.

### Modified Capabilities

*(Nenhuma.)*

## Impact

- **Código novo:** `src/ml/dataset.py`, `src/ml/treino.py`, `notebooks/03_modelo.ipynb` e uma etapa no `run_pipeline.py`. O `config.py` ganha o horizonte, a folga, as datas, os blocos, `TOP_APOSTAS = 20`, a semente e os caminhos.
- **Dependências:** nenhuma nova. O modelo não é salvo em disco, porque treinar leva segundos.
- **Testes:** `tests/test_ml.py` e o acréscimo da chave da `gold_ml_dataset` em `tests/test_no_duplicates.py`.
- **Documentação:** `architecture.md` (6.1, 6.3 respondido, 4.2, 13) e `data_dictionary.md` (`gold_ml_dataset`).
- **Dados:** ~18 mil linhas na `gold_ml_dataset`, fora do Git.
