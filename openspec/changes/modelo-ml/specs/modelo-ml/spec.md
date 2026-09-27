## Purpose

Treina e avalia o modelo que prevê se o crédito de cada combinação UF × modalidade vai ganhar força no próximo trimestre utilizável, comparando-o com baselines, medindo se as variáveis da Selic agregam, sem vazamento de informação, e gera a previsão de produção (seções 6 e 10 de `docs/architecture.md`).

## ADDED Requirements

### Requirement: Baseline primeiro

Antes do modelo, a avaliação SHALL calcular, com as mesmas métricas do modelo:
- **classe majoritária do treino**: prevê sempre a classe mais frequente do treino;
- **volta ao normal**: prevê 1 (ganha força) quando a `aceleracao_3m` é menor que 0 (o crédito perdeu força nos últimos 3 meses), usando `−aceleracao_3m` como pontuação para a AUC.

#### Scenario: Volta ao normal

- **WHEN** uma linha tem `aceleracao_3m` = −1,5 p.p. (perdeu força)
- **THEN** o baseline de volta ao normal prevê 1 para ela

### Requirement: Treino sem vazamento

O pré-processamento (padronização das variáveis numéricas e one-hot de `uf` e `modalidade`) e o modelo SHALL estar num único `Pipeline` do scikit-learn, ajustado (`fit`) **somente** com as origens de treino de cada avaliação. O conjunto avaliado SHALL receber apenas `predict`/`predict_proba`. As linhas de `embargo` SHALL NOT ser usadas no modelo avaliado no teste.

#### Scenario: Padronização ajustada só no treino

- **WHEN** o pipeline é treinado para uma avaliação
- **THEN** a média usada pela padronização é a média das linhas de treino daquela avaliação

### Requirement: Janela móvel por ano e escolha do modelo

Para cada bloco anual de origens em `BLOCOS_JANELA_MOVEL` (2020, 2021, 2022, 2023), cada modelo candidato SHALL ser treinado só com origens até 6 meses antes do início do bloco (o rótulo olha até t+5) e avaliado no bloco. Os candidatos são a regressão logística e o `HistGradientBoostingClassifier`, cada um **com** e **sem** as variáveis da Selic.

O modelo escolhido SHALL ser o de maior AUC média nos blocos. Se a diferença para a regressão logística for menor que 0,01, vence a regressão logística (explicabilidade). A escolha SHALL NOT usar o conjunto de `teste`. O resultado SHALL registrar a AUC de cada candidato em cada bloco, para mostrar a estabilidade entre anos.

#### Scenario: Escolha sem olhar o teste

- **WHEN** os candidatos são comparados
- **THEN** só origens de `desenvolvimento` são usadas
- **AND** trocar os rótulos do teste não muda o modelo escolhido

#### Scenario: Estabilidade por ano

- **WHEN** a janela móvel termina
- **THEN** o resultado mostra a AUC de cada candidato e dos baselines em cada um dos 4 blocos

### Requirement: Teste final único e efeito da Selic

O modelo escolhido SHALL ser treinado com todas as origens de `desenvolvimento` e avaliado **uma vez** no `teste`, junto com os baselines e com a **mesma arquitetura sem as variáveis da Selic**. A diferença de AUC "com Selic − sem Selic" SHALL ser registrada, no teste e em cada bloco da janela móvel, como resposta à pergunta "a Selic ajuda a prever?".

#### Scenario: Efeito da Selic registrado

- **WHEN** a avaliação termina
- **THEN** o resultado mostra a AUC com e sem a Selic no teste e em cada bloco
- **AND** mostra se o modelo supera o baseline de volta ao normal

### Requirement: Métricas e alertas

A avaliação SHALL registrar, para o modelo escolhido e os baselines:
- AUC (principal);
- precisão e recall da classe positiva (limiar 0,5), F1 e acurácia;
- **precisão nas melhores apostas**: para cada mês de origem, a fração de acertos entre as `TOP_APOSTAS` (20) combinações de maior probabilidade, com a média entre os meses;
- **AUC pesada pelo volume** (`sample_weight` = `volume_rs` da combinação na origem);
- tudo no total e por modalidade.

A classe positiva SHALL ser `ganha_forca = 1` (expandir). Se qualquer métrica do modelo passar de 0,95, SHALL ser registrado um alerta de possível vazamento (seção 6.4). A importância das variáveis por permutação no teste SHALL ser registrada. O limiar de decisão ligado ao custo do erro SHALL NOT ser definido aqui (Sprint 6).

#### Scenario: Melhores apostas

- **WHEN** em um mês de teste 13 das 20 combinações com maior probabilidade de fato ganharam força
- **THEN** a precisão nas melhores apostas daquele mês é 0,65

#### Scenario: Métrica alta demais

- **WHEN** a AUC do modelo no teste é 0,97
- **THEN** o resultado contém o alerta de possível vazamento

### Requirement: Previsão de produção e reprodutibilidade

O pipeline escolhido SHALL ser treinado de novo com todas as linhas rotuladas (`desenvolvimento`, `embargo` e `teste`) e SHALL prever as linhas de `producao`: para cada uma das 174 combinações, a probabilidade de o crédito ganhar força de set a nov/2026.

A etapa SHALL gravar métricas, escolhas, previsões do teste e de produção em `data/final/`, usando a `SEMENTE` fixa, de forma que rodar de novo produza o mesmo resultado.

#### Scenario: Previsão de produção

- **WHEN** a etapa termina
- **THEN** existe uma probabilidade entre 0 e 1 para cada uma das 174 combinações, para set–nov/2026

#### Scenario: Reprodutível

- **WHEN** a etapa roda duas vezes sobre a mesma Gold
- **THEN** as métricas e as previsões são idênticas
