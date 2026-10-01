# recomendacao-decisao Specification

## Purpose
Transforma as previsões do modelo em uma recomendação de decisão para a diretoria de crédito — a lista do trimestre, a justificativa do limiar e os números da frase de fechamento —, gerada pelo pipeline para que nenhum número da entrega seja digitado à mão (seções 1 e 10 de `docs/architecture.md`; item 2 e Requisito 6 do enunciado).

## Requirements

### Requirement: Lista de recomendação do trimestre

A etapa de decisão SHALL ler a previsão de produção do ML e gravar a lista de recomendação do trimestre seguinte ao t0 (set–nov/2026):
- **expandir**: as `TOP_RECOMENDACAO` (20) combinações com maior `prob_ganha_forca`, em ordem decrescente;
- **alerta**: as `TOP_RECOMENDACAO` combinações com menor `prob_ganha_forca` (maior chance de perder força).

Cada linha SHALL trazer `uf`, `modalidade`, `prob_ganha_forca`, a posição no ranking, o grupo (`expandir` ou `alerta`) e o saldo da combinação no t0 (`volume_rs`), para o decisor ver o tamanho de cada mercado.

#### Scenario: Lista gerada

- **WHEN** a etapa roda com as 174 previsões de produção
- **THEN** a lista tem 20 linhas `expandir` e 20 linhas `alerta`
- **AND** a primeira linha `expandir` é a de maior probabilidade

### Requirement: Tabela de sensibilidade do limiar

A etapa SHALL calcular, com as previsões do **teste**:
- para cada limiar de `LIMIARES_SENSIBILIDADE` (0,5, 0,6, 0,7, 0,8 e 0,9): a média de combinações recomendadas por mês, a precisão (fração das recomendadas que ganharam força) e o recall;
- para cada tamanho de lista de `TAMANHOS_LISTA` (10, 20 e 40): a precisão média das N maiores notas de cada mês.

Tudo para o modelo e para a regra simples "volta ao normal", lado a lado.

#### Scenario: Linha da regra adotada

- **WHEN** a tabela é calculada
- **THEN** existe a linha "20 maiores notas" com a precisão do modelo e a da regra simples

### Requirement: Números da frase de fechamento

A etapa SHALL gravar, em um arquivo JSON, todos os números usados na frase de fechamento e na seção 10:
- a AUC e a precisão das 20 maiores notas do modelo e da regra simples no teste;
- a precisão ao acaso (a taxa de "ganha força" no teste);
- os acertos e erros esperados por trimestre numa lista de 20;
- o trimestre da recomendação;
- o saldo total das combinações recomendadas;
- as associações da Sprint 4 citadas (modalidade, defasagem e ρ);
- o efeito da Selic no modelo.

Os textos da entrega SHALL citar esses valores, e não números digitados à mão.

#### Scenario: Ganho e custo por trimestre

- **WHEN** a precisão das 20 maiores notas no teste é 82,5%
- **THEN** o arquivo registra ~16,5 acertos e ~3,5 erros esperados por trimestre numa lista de 20
- **AND** registra a comparação com a regra simples (15 acertos) e com o acaso (~10)

### Requirement: Reprodutível e sem rede

A etapa SHALL usar só arquivos de `data/final/`, sem acessar a rede, e rodar duas vezes SHALL produzir as mesmas saídas.

#### Scenario: Reexecução

- **WHEN** a etapa roda duas vezes sobre as mesmas previsões
- **THEN** a lista, a tabela e os números são idênticos
