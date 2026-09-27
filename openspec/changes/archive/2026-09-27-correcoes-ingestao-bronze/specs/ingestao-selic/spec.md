## MODIFIED Requirements

### Requirement: Extração e parsing dos registros

O loader SHALL extrair da chave `value` da resposta OData cada registro com **todos os campos** que a API devolver (entre eles `VALDATA` e `VALVALOR`), e SHALL gravá-los como texto, exatamente como vieram, sem converter data nem número. A conversão de `VALDATA` para data e de `VALVALOR` para decimal (% ao mês, conforme a seção 2.2 de `docs/architecture.md`) é responsabilidade da Silver.

O loader SHALL NOT aplicar o recorte temporal na Bronze: a série é gravada inteira. O recorte a partir de julho/`ANO_INICIO` é aplicado na Silver.

#### Scenario: Parsing correto dos campos

- **WHEN** a resposta contém um registro com `VALDATA` igual a `2024-01-01T00:00:00-02:00` e `VALVALOR` igual a `0.97`
- **THEN** a Bronze guarda esses valores como texto, sem conversão
- **AND** os demais campos do registro devolvidos pela API também são gravados

#### Scenario: Série inteira preservada

- **WHEN** a resposta contém registros anteriores a julho/2016
- **THEN** esses registros são gravados na Bronze
- **AND** o recorte temporal fica a cargo da Silver

#### Scenario: Campo malformado

- **WHEN** um registro tem `VALDATA` ou `VALVALOR` em formato inesperado (texto não numérico, nulo)
- **THEN** o registro é gravado na Bronze como veio
- **AND** nenhum registro é enviado para a quarentena pelo loader
- **AND** os demais registros continuam sendo processados

### Requirement: Escrita em disco particionada por data

O loader SHALL escrever a `bronze_selic` em `data/raw/bronze_selic/` no formato Parquet, particionada por `_ingestion_date`. Os campos vindos da API SHALL ser gravados como texto.

#### Scenario: Arquivos particionados em disco

- **WHEN** o loader conclui uma execução com sucesso
- **THEN** os arquivos Parquet estão em `data/raw/bronze_selic/`
- **AND** existe uma subpasta por `_ingestion_date`
- **AND** o dado pode ser lido de volta com `pd.read_parquet()` com os mesmos textos devolvidos pela API

## ADDED Requirements

### Requirement: Rejeição apenas estrutural

O loader SHALL rejeitar somente respostas que não consegue ler: corpo que não é JSON, ou JSON sem a chave `value` do OData. Nesses casos o loader SHALL registrar o motivo em log, SHALL NOT escrever Bronze nessa execução e SHALL encerrar sem exceção não tratada. Checagens de negócio (valor negativo, mês incompleto, intervalo de datas) SHALL NOT ser aplicadas na Bronze; elas pertencem à Silver.

#### Scenario: Resposta não é JSON

- **WHEN** a API responde 200 com um corpo HTML de erro em vez de JSON
- **THEN** o loader registra em log que a resposta não pôde ser lida
- **AND** nenhum arquivo Bronze é escrito
- **AND** o job é encerrado sem exceção

#### Scenario: Valor negativo entra intacto na Bronze

- **WHEN** um registro da Selic tem `VALVALOR` negativo
- **THEN** o registro é gravado na `bronze_selic` como veio
- **AND** nenhum arquivo é escrito na quarentena pelo loader

## REMOVED Requirements

### Requirement: Integração com a validação e quarentena

**Reason**: Validar regra de negócio (valor negativo, mês corrente incompleto) na ingestão contraria a seção 4.1 de `docs/architecture.md`: a Bronze não descarta registro, e validações com quarentena pertencem à Silver.

**Migration**: As checagens `valor_negativo` e `data_fora_do_intervalo` (incluindo o descarte do mês corrente incompleto) passam a ser aplicadas na construção da `silver_selic` na Sprint 4, usando o mesmo módulo `src/validation/quality_checks.py`.
