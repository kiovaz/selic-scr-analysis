# silver-scr Specification

## Purpose
Constrói a tabela `silver_scr` a partir da `bronze_scr`: dado limpo, tipado e agregado em uma linha por mês × estado × modalidade de financiamento, dentro do recorte do projeto, com os registros inválidos desviados para a quarentena (seções 3.3, 4.1 e 5.1 de `docs/architecture.md`).

## Requirements

### Requirement: Versão vigente de cada arquivo

A construção da `silver_scr` SHALL usar, para cada arquivo do SCR (a parte do `_source_object` antes do `@`), somente as linhas da versão mais recente presente na Bronze. Versões anteriores de um mês republicado SHALL ser ignoradas e contadas no relatório.

#### Scenario: Mês republicado

- **WHEN** a Bronze tem duas versões de `scrdata_202408.csv` (`@2026-03-25T...` com 310.266 linhas e `@2026-09-15T...` com 310.263 linhas)
- **THEN** a `silver_scr` de agosto/2024 é construída só com as linhas da versão `@2026-09-15T...`

### Requirement: Escopo — colunas, modalidades e recorte

A `silver_scr` SHALL conter somente dados das 5 colunas de `SCR_COLUNAS_USADAS`, das modalidades que começam com `PREFIXO_MODALIDADE` e dos meses de julho/`ANO_INICIO` a `MES_FIM`/`ANO_FIM` (hoje, jul/2016 a jun/2026), todos vindos de `src/config.py`. Linhas fora desse escopo SHALL ser descartadas da Silver **sem** ir para a quarentena, porque não são inválidas, e SHALL ser contadas no relatório por motivo (modalidade fora do escopo, mês fora do recorte).

#### Scenario: Modalidade que não é de financiamento

- **WHEN** a Bronze tem uma linha com modalidade `Empréstimos`
- **THEN** a linha não entra na `silver_scr` nem na quarentena
- **AND** o relatório conta a linha como "modalidade fora do escopo"

#### Scenario: Mês fora do recorte

- **WHEN** a Bronze tem linhas com `data_base` em junho/2016 ou julho/2026
- **THEN** essas linhas não entram na `silver_scr` nem na quarentena
- **AND** o relatório conta as linhas como "fora do recorte"

### Requirement: Tipagem e chave

Cada linha da `silver_scr` SHALL ter: `ano_mes` (data do **primeiro dia** do mês de `data_base`), `uf` (texto de 2 letras), `modalidade` (texto exatamente como na fonte), `qtd_operacoes` (inteiro ≥ 0), `linhas_qtd_nao_divulgada` (inteiro ≥ 0) e `volume_rs` (decimal ≥ 0, em reais). `carteira_ativa` SHALL ser convertida com o separador decimal vírgula.

A chave `(ano_mes, uf, modalidade)` SHALL ser única.

#### Scenario: Conversão de tipos

- **WHEN** uma linha da Bronze tem `data_base` = `2024-08-31` e `carteira_ativa` = `1234,56`
- **THEN** ela contribui para o grupo com `ano_mes` = 2024-08-01 com o valor 1234.56 em `volume_rs`

#### Scenario: Chave sem duplicata

- **WHEN** a `silver_scr` é construída
- **THEN** `df.duplicated(["ano_mes", "uf", "modalidade"]).sum() == 0`

### Requirement: Agregação com quantidade como limite inferior

Para cada grupo `(ano_mes, uf, modalidade)`:
- `volume_rs` SHALL ser a soma de `carteira_ativa` de todas as linhas válidas do grupo;
- `qtd_operacoes` SHALL ser a soma de `numero_de_operacoes` **somente das linhas com valor divulgado** (≥ 0). Linhas com `-1`, que é a quantidade não divulgada pelo BCB, SHALL NOT entrar na soma, nem como zero nem como −1;
- `linhas_qtd_nao_divulgada` SHALL ser o número de linhas do grupo com `numero_de_operacoes = -1`.

`qtd_operacoes` é, portanto, um **limite inferior** da quantidade real sempre que `linhas_qtd_nao_divulgada > 0` (decisão do grupo registrada nas seções 5.1 e 11 de `docs/architecture.md`).

#### Scenario: Grupo com quantidade parcialmente escondida

- **WHEN** um grupo tem três linhas com `numero_de_operacoes` = `10`, `-1` e `5` e `carteira_ativa` = `100,00`, `50,00` e `25,00`
- **THEN** o grupo tem `qtd_operacoes` = 15, `linhas_qtd_nao_divulgada` = 1 e `volume_rs` = 175.00

#### Scenario: Grupo com toda a quantidade escondida

- **WHEN** todas as linhas de um grupo têm `numero_de_operacoes` = `-1`
- **THEN** o grupo tem `qtd_operacoes` = 0, `linhas_qtd_nao_divulgada` igual ao número de linhas e `volume_rs` igual à soma dos saldos

### Requirement: Quarentena de registros inválidos

Antes da agregação, cada linha dentro do escopo SHALL passar pelas checagens de `src/validation/quality_checks.py`. Uma linha inválida SHALL ir para a quarentena com o primeiro motivo encontrado, na ordem `uf_invalida`, `tipagem_invalida`, `data_fora_do_intervalo`, `valor_negativo`, e SHALL NOT entrar na agregação. O job SHALL NOT ser interrompido por linhas inválidas.

- `uf_invalida`: `uf` fora de `UFS_VALIDAS`.
- `tipagem_invalida`: `data_base` não é uma data, `carteira_ativa` não é número ou `numero_de_operacoes` não é inteiro.
- `data_fora_do_intervalo`: `data_base` posterior à data de execução, o que é impossível para um dado publicado.
- `valor_negativo`: `carteira_ativa` < 0, ou `numero_de_operacoes` < 0 e diferente de −1.

#### Scenario: Linha com UF inválida

- **WHEN** uma linha de financiamento dentro do recorte tem `uf` = `XX`
- **THEN** ela vai para a quarentena com motivo `uf_invalida` e o registro original no `payload`
- **AND** não entra em nenhum grupo da `silver_scr`

#### Scenario: Saldo que não é número

- **WHEN** uma linha tem `carteira_ativa` = `abc`
- **THEN** ela vai para a quarentena com motivo `tipagem_invalida`

#### Scenario: -1 não é valor negativo

- **WHEN** uma linha tem `numero_de_operacoes` = `-1`
- **THEN** ela NÃO vai para a quarentena
- **AND** conta em `linhas_qtd_nao_divulgada`

### Requirement: Reconstrução a partir da Bronze e relatório

A `silver_scr` SHALL ser reconstruída inteira a partir da Bronze a cada execução, sem consultar a fonte (seção 4.1), e gravada em `data/processed/`. Rodar a construção duas vezes seguidas SHALL produzir o mesmo resultado.

A construção SHALL gravar um relatório com: linhas lidas da versão vigente; linhas descartadas por versão antiga, por modalidade fora do escopo e por mês fora do recorte; linhas em quarentena por motivo; linhas finais da `silver_scr`; e a lista das combinações `uf × modalidade` que não têm todos os meses do recorte. Meses faltantes SHALL NOT ser preenchidos.

#### Scenario: Reconstrução idempotente

- **WHEN** a construção da `silver_scr` roda duas vezes seguidas sobre a mesma Bronze
- **THEN** as duas saídas são idênticas
- **AND** a quarentena da `silver_scr` tem as mesmas linhas, sem duplicação

#### Scenario: Combinação com meses faltando

- **WHEN** a combinação `AP × Financiamentos de títulos e valores mobiliários` existe em só 19 dos 120 meses
- **THEN** a `silver_scr` tem só esses 19 meses para a combinação, sem linhas inventadas
- **AND** o relatório lista a combinação com a quantidade de meses presentes
