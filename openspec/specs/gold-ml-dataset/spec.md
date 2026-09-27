# gold-ml-dataset Specification

## Purpose
Constrói a `gold_ml_dataset`, a base do modelo de ML: para cada combinação UF × modalidade da coorte e cada mês de origem, as features conhecidas até aquele mês e o rótulo "o crédito ganha força no trimestre que o decisor ainda pode usar", separada em conjuntos sem vazamento de informação do futuro (seção 6 de `docs/architecture.md`).

## Requirements

### Requirement: Coorte

A base SHALL conter somente as combinações `(uf, modalidade)` com todos os meses do recorte na `gold_credito_selic` (hoje, 174 de 216). As combinações excluídas SHALL ser contadas e listadas no relatório do ML. O filtro de coorte SHALL ser aplicado **antes** da separação em conjuntos (seção 6.4).

#### Scenario: Combinação com buraco

- **WHEN** a combinação AP × títulos tem só 19 dos 120 meses
- **THEN** ela não aparece na `gold_ml_dataset`
- **AND** o relatório a lista entre as excluídas

### Requirement: Rótulo "ganha força" com folga de publicação

Para cada combinação e cada mês de origem t, o rótulo `ganha_forca` SHALL ser 1 quando o crescimento do `volume_rs` da combinação de t + `FOLGA_PUBLICACAO_MESES` (2) até t + `FOLGA_PUBLICACAO_MESES` + `HORIZONTE_MESES` (5) for **maior** que o crescimento dos últimos 3 meses (de t − 3 até t), e 0 caso contrário. A folga existe porque o BCB publica o mês t cerca de 60 dias depois: os meses t+1 e t+2 já terão passado quando o decisor receber o dado.

Quando t + 5 está além do t0, o rótulo SHALL ficar vazio (origem de produção ou origem descartada).

#### Scenario: Ganha força

- **WHEN** o saldo de SP × imobiliário cresceu 2% de t−3 a t e cresce 4% de t+2 a t+5
- **THEN** o rótulo de SP × imobiliário na origem t é 1

#### Scenario: Perde força mesmo crescendo

- **WHEN** o saldo cresceu 6% de t−3 a t e cresce 2% de t+2 a t+5
- **THEN** o rótulo é 0 (continuou crescendo, mas mais devagar)

#### Scenario: Origem de produção

- **WHEN** a origem é jun/2026 (t0) e os meses de ago a nov/2026 não existem
- **THEN** o rótulo fica vazio e a linha é do conjunto `producao`

### Requirement: Features só com o passado

Todas as features de uma linha de origem t SHALL usar apenas dados de meses **menores ou iguais a t**:
- variações do `volume_rs` da combinação em 1, 3, 6 e 12 meses;
- `aceleracao_3m` (variação dos últimos 3 meses menos a dos 3 meses anteriores);
- variação relativa ao Brasil (combinação menos nacional da modalidade) em 3 e 12 meses;
- participação da combinação no volume nacional da modalidade e sua variação em 12 meses;
- as **variáveis da Selic**: `selic_pct` em t e a variação da Selic meta nos 3 e 6 meses anteriores;
- `modalidade` e `uf`.

A quantidade de operações SHALL NOT ser usada, porque é um limite inferior (seção 5.1). Nenhum valor posterior a t SHALL entrar em feature. Origens sem os 12 meses anteriores necessários SHALL ficar fora da base.

#### Scenario: Mudar o futuro não muda as features

- **WHEN** os valores de `volume_rs` e da Selic posteriores à origem t são alterados
- **THEN** as features da linha de origem t continuam idênticas
- **AND** só o rótulo pode mudar

#### Scenario: Primeira origem

- **WHEN** o recorte começa em jul/2016
- **THEN** a primeira origem da base é jul/2017, a primeira com 12 meses anteriores

### Requirement: Conjuntos e embargo

Cada linha SHALL ter a coluna `conjunto`:
- `desenvolvimento` para origens até `FIM_TREINO_FINAL` (ago/2024), usadas na janela móvel e no treino final;
- `embargo` para as origens entre o fim do treino e o início do teste (set/2024 a jan/2025), cujo rótulo cai dentro do período de teste. Elas SHALL NOT ser usadas nem para treinar nem para testar o modelo avaliado;
- `teste` para as origens de `INICIO_TESTE` (fev/2025) até t0 − 5 (jan/2026);
- `producao` para a origem t0 (jun/2026).

Origens de fev a mai/2026 não têm rótulo completo e SHALL ficar fora da base. A chave `(uf, modalidade, origem)` SHALL ser única.

#### Scenario: Nenhuma sobreposição entre treino e teste

- **WHEN** a base é construída
- **THEN** o último mês usado por qualquer rótulo de `desenvolvimento` (origem + 5) é anterior ao primeiro mês de origem do `teste`

#### Scenario: Chave sem duplicata

- **WHEN** a base é construída
- **THEN** `df.duplicated(["uf", "modalidade", "origem"]).sum() == 0`
