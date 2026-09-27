# gold-credito-selic Specification

## Purpose
Constrói a tabela `gold_credito_selic`, que cruza a `silver_scr` com a `silver_selic` por mês e acrescenta as variações e as defasagens da Selic usadas na análise, uma linha por mês × estado × modalidade (seções 2.4, 4.1 e 5.3 de `docs/architecture.md`).

## Requirements

### Requirement: Cruzamento por mês e contagem de órfãos

A `gold_credito_selic` SHALL ser construída a partir da `silver_scr` e da `silver_selic` pela chave `ano_mes`. Cada linha da `silver_scr` com Selic no mesmo mês SHALL gerar uma linha na Gold, com a `selic_pct` daquele mês. O mesmo valor de Selic se repete para todas as UFs e modalidades do mês, e isso é esperado.

A construção SHALL contar e registrar no relatório da Gold os **órfãos dos dois lados**: meses presentes na `silver_scr` sem Selic, e meses presentes na `silver_selic` sem nenhuma linha do SCR. Linhas do SCR sem Selic SHALL ficar fora da Gold.

#### Scenario: Mesma Selic para todas as UFs

- **WHEN** a `silver_selic` tem `selic_pct` = 1.12 em jun/2026 e a `silver_scr` tem 210 linhas em jun/2026
- **THEN** as 210 linhas da Gold em jun/2026 têm `selic_pct` = 1.12

#### Scenario: Órfãos contados

- **WHEN** a `silver_scr` tem um mês sem Selic e a `silver_selic` tem um mês sem SCR
- **THEN** o relatório registra 1 órfão de cada lado, com os meses
- **AND** as linhas do SCR sem Selic não aparecem na Gold

### Requirement: Variações só entre meses consecutivos

Para cada combinação `(uf, modalidade)`, com as linhas ordenadas por mês:
- `tem_mes_anterior` SHALL ser verdadeiro quando a combinação tem linha no mês imediatamente anterior pelo calendário, e falso caso contrário;
- `var_volume_pct` SHALL ser `(volume_rs / volume_rs do mês anterior − 1) × 100` quando `tem_mes_anterior` é verdadeiro, e vazia caso contrário;
- `var_qtd_pct` SHALL seguir a mesma regra com `qtd_operacoes`, e SHALL ficar vazia também quando a `qtd_operacoes` do mês anterior é 0.

Os cálculos SHALL NOT misturar combinações diferentes e SHALL NOT preencher meses faltantes.

#### Scenario: Buraco no meio da série

- **WHEN** a combinação AP × títulos tem linhas em set/2016, out/2016 e fev/2017
- **THEN** set/2016 tem `tem_mes_anterior` falso e `var_volume_pct` vazia
- **AND** out/2016 tem `tem_mes_anterior` verdadeiro e a variação calculada contra set/2016
- **AND** fev/2017 tem `tem_mes_anterior` falso e `var_volume_pct` vazia (não é comparada com out/2016)

#### Scenario: Quantidade anterior zero

- **WHEN** o mês anterior da combinação tem `qtd_operacoes` = 0 (toda a quantidade escondida)
- **THEN** `var_qtd_pct` fica vazia
- **AND** `var_volume_pct` é calculada normalmente

### Requirement: Selic, sua variação e suas defasagens

`var_selic_pp` SHALL ser `selic_pct` menos a `selic_pct` do mês anterior pelo calendário, em pontos percentuais. `selic_lag_k`, para k de 1 a 6, SHALL ser a `selic_pct` de k meses antes pelo calendário. Quando o mês necessário está fora da `silver_selic` (os primeiros meses do recorte), o valor SHALL ficar vazio e SHALL NOT ser preenchido.

#### Scenario: Defasagens pelo calendário

- **WHEN** a linha é de jan/2017 e a `silver_selic` começa em jul/2016
- **THEN** `selic_lag_1` a `selic_lag_6` são a Selic de dez/2016 a jul/2016
- **AND** numa linha de jul/2016, `var_selic_pp` e todos os `selic_lag_k` ficam vazios

#### Scenario: Defasagem numa combinação com buraco

- **WHEN** a combinação AP × títulos não tem linha em jan/2017
- **THEN** a linha de fev/2017 dessa combinação ainda tem `selic_lag_1` igual à Selic de jan/2017, porque a Selic não depende da combinação

### Requirement: Colunas, chave e reconstrução

Cada linha da `gold_credito_selic` SHALL ter: `ano_mes`, `uf`, `modalidade`, `qtd_operacoes`, `linhas_qtd_nao_divulgada`, `volume_rs`, `tem_mes_anterior`, `var_qtd_pct`, `var_volume_pct`, `selic_pct`, `var_selic_pp` e `selic_lag_1` a `selic_lag_6`. A chave `(ano_mes, uf, modalidade)` SHALL ser única.

A Gold SHALL ser reconstruída inteira a partir da Silver a cada execução, sem limpeza de dados (seção 4.1), e rodar duas vezes SHALL produzir o mesmo resultado. A construção SHALL gravar um relatório com o número de linhas, os órfãos dos dois lados e quantas linhas têm `tem_mes_anterior` falso.

#### Scenario: Chave sem duplicata

- **WHEN** a Gold é construída
- **THEN** `df.duplicated(["ano_mes", "uf", "modalidade"]).sum() == 0`

#### Scenario: Reconstrução idempotente

- **WHEN** a Gold é construída duas vezes seguidas sobre a mesma Silver
- **THEN** as duas saídas são idênticas
