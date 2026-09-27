# silver-selic Specification

## Purpose
Constrói a tabela `silver_selic` a partir da `bronze_selic`: uma linha por mês com a Selic acumulada no mês (% a.m.), só meses fechados dentro do recorte do projeto, com registros inválidos desviados para a quarentena (seções 2.2, 3.2, 4.1 e 5.2 de `docs/architecture.md`).

## Requirements

### Requirement: Leitura vigente de cada mês

A construção da `silver_selic` SHALL usar, para cada mês (`VALDATA` pelos 10 primeiros caracteres), somente a leitura com o maior `_ingestion_timestamp` na Bronze. Leituras anteriores do mesmo mês, que existem quando o valor do mês corrente mudou entre execuções, SHALL ser ignoradas.

Se houver mais de uma leitura com o mesmo `_ingestion_timestamp` máximo e valores diferentes para o mesmo mês, todas SHALL ir para a quarentena com motivo `duplicata_na_chave` e o mês SHALL ficar fora da `silver_selic`.

#### Scenario: Mês com duas leituras

- **WHEN** a Bronze tem setembro com `0.88` (lido primeiro) e `1.05` (lido depois)
- **THEN** a `silver_selic` usa `1.05` para setembro

#### Scenario: Leituras ambíguas

- **WHEN** a Bronze tem duas leituras de um mês com o mesmo `_ingestion_timestamp` e valores diferentes
- **THEN** as duas vão para a quarentena com motivo `duplicata_na_chave`
- **AND** o mês não aparece na `silver_selic`

### Requirement: Recorte e só meses fechados

A `silver_selic` SHALL conter somente meses de julho/`ANO_INICIO` a `MES_FIM`/`ANO_FIM` de `src/config.py`. Meses fora do recorte SHALL ser descartados sem ir para a quarentena e contados no relatório. A `silver_selic` SHALL NOT conter o mês da data de execução nem meses posteriores, porque a Selic acumulada de um mês só é definitiva quando o mês termina (seção 2.2).

#### Scenario: Série inteira na Bronze

- **WHEN** a Bronze tem a série de jan/1974 a set/2026
- **THEN** a `silver_selic` tem exatamente os 120 meses de jul/2016 a jun/2026

#### Scenario: Recorte alcança o mês corrente

- **WHEN** `ANO_FIM/MES_FIM` apontam para o mês em que a construção está rodando
- **THEN** esse mês não entra na `silver_selic` e o relatório registra o motivo

### Requirement: Tipagem, chave e quarentena

Cada linha da `silver_selic` SHALL ter `ano_mes` (data do primeiro dia do mês de `VALDATA`) e `selic_pct` (decimal, % ao mês). A chave `(ano_mes)` SHALL ser única.

Uma leitura com `VALVALOR` que não é número, ou com `VALDATA` que não é data, SHALL ir para a quarentena com motivo `tipagem_invalida`. Uma leitura com `VALVALOR` negativo SHALL ir com motivo `valor_negativo`. A construção SHALL ser reconstruída inteira a cada execução, com o mesmo resultado para a mesma Bronze.

#### Scenario: Conversão de tipos

- **WHEN** a leitura vigente de junho/2026 tem `VALDATA` = `2026-06-01T00:00:00-03:00` e `VALVALOR` = `1.12`
- **THEN** a `silver_selic` tem a linha `ano_mes` = 2026-06-01, `selic_pct` = 1.12

#### Scenario: Valor que não é número

- **WHEN** a leitura vigente de um mês tem `VALVALOR` nulo
- **THEN** ela vai para a quarentena com motivo `tipagem_invalida`
- **AND** o mês não aparece na `silver_selic`

#### Scenario: Chave sem duplicata

- **WHEN** a `silver_selic` é construída
- **THEN** `df.duplicated(["ano_mes"]).sum() == 0`
