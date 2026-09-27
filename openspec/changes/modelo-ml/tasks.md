## 1. Definição antes do código (regra da seção 8)

- [x] 1.1 Preencher a tabela 6.1 do `docs/architecture.md` com D1–D3 (2026-09-27, revisadas no mesmo dia) e as consequências: tipo (classificação), label (`ganha_forca`, positivo = expandir), regra de rotulagem (a fórmula do design, com a folga de 2 meses e o motivo), coorte (174 combinações, 42 excluídas), janela de observação (até 12 meses antes da origem), janela de predição (t+2 a t+5), baseline (classe majoritária e volta ao normal, 64,7%) e métrica (AUC principal, melhores apostas, AUC pesada pelo volume; classe positiva). Registrar também a primeira versão da pergunta (relativa ao Brasil) e por que foi trocada. Trocar o status "definição adiada" por "definido". Na seção 4.2, a chave `(uf, modalidade, origem)` da `gold_ml_dataset`; na seção 13, a decisão 11. Verificar: nenhuma célula "a definir" sobra na 6.1.
- [x] 1.2 Acrescentar a `src/config.py`: `HORIZONTE_MESES = 3`, `FOLGA_PUBLICACAO_MESES = 2`, `MESES_HISTORICO_ML = 12`, `FIM_TREINO_FINAL = (2024, 8)`, `INICIO_TESTE = (2025, 2)`, `BLOCOS_JANELA_MOVEL = [2020, 2021, 2022, 2023]`, `TOP_APOSTAS = 20`, `SEMENTE = 42` e os caminhos `ARQUIVO_ML_DATASET`, `ARQUIVO_ML_RESULTADOS`, `ARQUIVO_ML_PREVISOES_TESTE` e `ARQUIVO_ML_PREVISAO_PRODUCAO` (em `DIR_GOLD`), com comentários; isolar os caminhos em `tests/conftest.py`. Verificar: `pytest tests/test_config.py`.

## 2. gold_ml_dataset

- [x] 2.1 Criar `src/ml/dataset.py` com a coorte (combinações com todos os meses; excluídas listadas), a série nacional por modalidade e o rótulo `ganha_forca` (futuro t+2→t+5 contra passado t−3→t). Verificar: teste com UFs sintéticas (uma com buraco) confere a coorte; os cenários "2% → 4% = 1" e "6% → 2% = 0" da spec.
- [x] 2.2 Calcular as features da tabela do design só com `shift` para trás, marcando quais são "variáveis da Selic"; descartar as origens sem 12 meses de histórico. Verificar: **teste anti-vazamento** (alterar volume e Selic de meses posteriores a uma origem e conferir features idênticas); a primeira origem é o 13º mês.
- [x] 2.3 Marcar `conjunto` (desenvolvimento / embargo / teste / produção), descartar origens sem rótulo completo que não são produção e gravar `gold_ml_dataset.parquet` de forma atômica. Verificar: o último mês de rótulo do desenvolvimento é anterior à primeira origem de teste; a produção é só t0, sem rótulo; e a chave é única.

## 3. Treino e avaliação

- [x] 3.1 Criar `src/ml/treino.py` com os baselines (classe majoritária; volta ao normal = `aceleracao_3m < 0`, pontuação `−aceleracao_3m`) e as métricas (AUC, precisão/recall/F1/acurácia, melhores apostas por mês com `TOP_APOSTAS`, AUC pesada pelo volume, por modalidade, alerta > 0,95). Verificar: testes com linhas sintéticas conferem a volta ao normal e as melhores apostas (13 acertos em 20 = 0,65).
- [x] 3.2 Montar `montar_pipeline(modelo, com_selic)` (StandardScaler + OneHotEncoder + modelo; sem Selic = mesmas features sem as 3 da Selic) e a janela móvel pelos blocos (treino ≤ jul do ano anterior; avaliação no ano), com a escolha pela maior AUC média das versões com Selic e o desempate pela logística. Verificar: um teste confere que a média do scaler é a do treino do bloco; outro, que trocar os rótulos do `teste` não muda a escolha; e numa base sintética com sinal plantado o modelo supera a classe majoritária.
- [x] 3.3 Teste final único (o escolhido com e sem Selic, e os baselines, treinados em `desenvolvimento`), importância por permutação agrupada por variável (mais os coeficientes, se for logística) e a diferença de AUC "com − sem Selic" no teste e em cada bloco. Verificar: uma base sintética "perfeita" dispara o alerta; o resultado contém a diferença com/sem Selic por bloco.
- [x] 3.4 Treinar de novo com todas as linhas rotuladas, prever a produção (174 probabilidades para set–nov/2026) e gravar `ml_resultados.json`, `ml_previsoes_teste.parquet` e `ml_previsao_producao.parquet` com `SEMENTE` fixa. Verificar: duas execuções sobre a mesma base sintética produzem saídas idênticas.

## 4. Pipeline, notebook e documentação

- [x] 4.1 Acrescentar a etapa "Sprint 5: ML" ao `scripts/run_pipeline.py` (modelo escolhido; AUC do modelo, dos baselines e sem Selic no teste; se superou a volta ao normal; melhores apostas; alerta, se houver). Verificar: o resumo aparece na execução real.
  - **Resultado:** pipeline completo em 499 s (ML ~2 min); o resumo aparece com os mesmos números da 5.1.
- [x] 4.2 Acrescentar a `tests/test_no_duplicates.py` a chave da `gold_ml_dataset`. Verificar: `pytest -v` verde, sem rede e sem tocar em `data/`.
- [x] 4.3 Criar `notebooks/03_modelo.ipynb`: a definição do problema em texto simples (o que é "ganhar força", por que a folga, por que não "cresce mais que o Brasil"); o modelo × baselines no teste; a estabilidade por bloco anual; **com × sem Selic**; as melhores apostas e o resultado pesado pelo volume; os resultados por modalidade; a importância das variáveis; as previsões de set–nov/2026 (10 maiores e 10 menores); a nota "por que os números parecem mais firmes do que são"; e o **checklist 6.3 respondido item a item** com a evidência (teste ou trecho de código). Executar com as saídas gravadas. Verificar: `jupyter nbconvert --execute` sem erro.
  - **Resultado:** notebook executado com `jupyter nbconvert --execute` sem erro, saídas gravadas, checklist 6.3 com evidências.
- [x] 4.4 Copiar para a seção 6.3 do `architecture.md` o checklist respondido e registrar na seção 6 o resultado principal (o modelo supera a volta ao normal? a Selic agrega?). Atualizar o `data_dictionary.md` com a `gold_ml_dataset` e as saídas do ML. Verificar: nenhum item do checklist sem resposta.
  - **Resultado:** checklist 6.3 respondido no `architecture.md` (5/5, sem item em aberto) e nova seção 6.5 com o resultado; `data_dictionary.md` com a `gold_ml_dataset` e as saídas do ML.

## 5. Execução real

- [x] 5.1 Rodar a etapa de ML sobre a Gold real e anotar nesta task: linhas por conjunto; a AUC de cada candidato (com e sem Selic) em cada bloco; o modelo escolhido; no teste, o modelo × baselines × sem Selic (AUC, melhores apostas, AUC pesada, por modalidade); as 5 variáveis mais importantes; a conclusão sobre a Selic; e o resumo das previsões set–nov/2026. Se o modelo **não** superar a volta ao normal, registrar sem esconder.
  - **Resultado (2026-09-27, Gold real):** 122 s. Conjuntos: desenvolvimento 14.964, embargo 870, teste 2.088, produção 174; 42 combinações fora da coorte.
  - **Janela móvel (AUC por ano 2020/2021/2022/2023):** logística 0,626/0,748/0,788/0,726 (média 0,722); **gradient boosting 0,757/0,757/0,732/0,763 (média 0,752) → escolhido**; volta ao normal 0,669/0,661/0,714/0,685.
  - **Teste final:** modelo AUC **0,778** (pesada pelo volume 0,792; melhores apostas **82,5%**; precisão 0,677; recall 0,827; acurácia 0,715) × volta ao normal 0,688 (melhores apostas 75,0%) × classe majoritária 0,500 → **supera a volta ao normal**. Por modalidade o modelo vence em todas; ganho maior em geral (+0,146) e importação (+0,129), menor em infraestrutura (+0,004) e interveniência (+0,016).
  - **Selic:** sem as variáveis da Selic a AUC foi 0,796 (melhores apostas 86,7%). Efeito "com − sem" por ano: +0,007, +0,035, −0,067, −0,034; no teste −0,017 → **a Selic não ajuda a prever o próximo trimestre**.
  - **Variáveis mais importantes (queda de AUC):** var_3m 0,170; var_6m 0,019; aceleracao_3m 0,016; var_12m 0,009; selic_var_3m 0,007.
  - **Produção (set–nov/2026):** probabilidade média 0,527, 95 de 174 combinações acima de 0,5; os extremos são combinações pequenas (ex.: AP exportação 0,95; PR títulos 0,01). Nenhum alerta > 0,95.
- [x] 5.2 Rodar de novo e confirmar métricas e previsões idênticas. Anotar.
  - **Resultado:** segunda execução com `ml_resultados.json` (exceto `gerado_em`), `ml_previsoes_teste.parquet` e `ml_previsao_producao.parquet` **idênticos**.
- [ ] 5.3 `pytest -v`, CI verde no PR para o `develop` e commits atômicos em pt-BR **sem linha de atribuição**.
