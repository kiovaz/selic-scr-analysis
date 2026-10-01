# silver-selic Specification

## Purpose
Constrói a tabela `silver_selic` a partir da `bronze_selic`: uma linha por mês com a Selic meta do Copom vigente no último dia do mês (% a.a.), só meses fechados dentro do recorte do projeto, com registros inválidos desviados para a quarentena (seções 2.2, 3.2, 4.1 e 5.2 de `docs/architecture.md`).

## Requirements

### Requirement: Leitura vigente de cada mês

A construção da `silver_selic` SHALL usar somente as linhas da `bronze_selic` da série configurada (`_source_object` igual a `SELIC_URL`); linhas de outra série SHALL ser ignoradas e contadas no relatório.

Para cada **dia** (`VALDATA` pelos 10 primeiros caracteres), SHALL valer somente a leitura com o maior `_ingestion_timestamp`. Se houver mais de uma leitura com o mesmo `_ingestion_timestamp` máximo e valores diferentes para o mesmo dia, todas SHALL ir para a quarentena com motivo `duplicata_na_chave` e o dia SHALL ficar de fora.

Para cada **mês**, o valor da `silver_selic` SHALL ser o da **meta vigente no último dia do mês com valor válido** (corte mensal). A série antiga `BM12_TJOVER12` (acumulada no mês) SHALL NOT ser usada: ela varia com o número de dias úteis do mês e não mede a decisão do Copom (seção 2.2 de `docs/architecture.md`).

#### Scenario: Mês com duas leituras

- **WHEN** a Bronze tem duas leituras do último dia de setembro, `14.25` (lida primeiro) e `14.00` (lida depois)
- **THEN** a `silver_selic` usa `14.00` para setembro

#### Scenario: Leituras ambíguas

- **WHEN** a Bronze tem duas leituras de um dia com o mesmo `_ingestion_timestamp` e valores diferentes
- **THEN** as duas vão para a quarentena com motivo `duplicata_na_chave`
- **AND** esse dia não é usado no corte mensal

#### Scenario: Corte pelo último dia do mês

- **WHEN** a meta vale `15.00` de 1 a 18 de março e `14.75` de 19 a 31 de março
- **THEN** a `silver_selic` de março tem `selic_pct` = 14.75

#### Scenario: Linhas de outra série

- **WHEN** a `bronze_selic` ainda tem linhas da série antiga (outro `_source_object`)
- **THEN** elas não entram na `silver_selic`
- **AND** o relatório conta essas linhas como "de outra série"

### Requirement: Recorte e só meses fechados

A `silver_selic` SHALL conter somente meses de julho/`ANO_INICIO` a `MES_FIM`/`ANO_FIM` de `src/config.py`. Meses fora do recorte SHALL ser descartados sem ir para a quarentena e contados no relatório. A `silver_selic` SHALL NOT conter o mês da data de execução nem meses posteriores, porque a meta vigente no fim de um mês só é conhecida quando o mês termina (seção 2.2).

#### Scenario: Série inteira na Bronze

- **WHEN** a Bronze tem a série diária de jul/1996 a set/2026
- **THEN** a `silver_selic` tem exatamente os 120 meses de jul/2016 a jun/2026

#### Scenario: Recorte alcança o mês corrente

- **WHEN** `ANO_FIM/MES_FIM` apontam para o mês em que a construção está rodando
- **THEN** esse mês não entra na `silver_selic` e o relatório registra o motivo

### Requirement: Tipagem, chave e quarentena

Cada linha da `silver_selic` SHALL ter `ano_mes` (data do primeiro dia do mês) e `selic_pct` (decimal, **% ao ano**, a meta vigente no último dia válido do mês). A chave `(ano_mes)` SHALL ser única.

Uma leitura diária com `VALVALOR` que não é número, ou com `VALDATA` que não é data, SHALL ir para a quarentena com motivo `tipagem_invalida`. Uma leitura com `VALVALOR` negativo SHALL ir com motivo `valor_negativo`. Leituras em quarentena SHALL NOT ser usadas no corte mensal. A construção SHALL ser reconstruída inteira a cada execução, com o mesmo resultado para a mesma Bronze.

#### Scenario: Conversão de tipos

- **WHEN** a leitura vigente de 30/06/2026 tem `VALDATA` = `2026-06-30T00:00:00-03:00` e `VALVALOR` = `14.25`
- **THEN** a `silver_selic` tem a linha `ano_mes` = 2026-06-01, `selic_pct` = 14.25

#### Scenario: Valor que não é número

- **WHEN** a leitura do último dia de um mês tem `VALVALOR` nulo
- **THEN** ela vai para a quarentena com motivo `tipagem_invalida`
- **AND** o mês usa a meta do último dia anterior com valor válido

#### Scenario: Chave sem duplicata

- **WHEN** a `silver_selic` é construída
- **THEN** `df.duplicated(["ano_mes"]).sum() == 0`
