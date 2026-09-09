## Purpose

Ingere a série histórica da taxa Selic a partir da API REST do Ipeadata, produzindo a tabela `bronze_selic` em disco com metadados técnicos de rastreabilidade, pronta para a camada Silver consumir.

## ADDED Requirements

### Requirement: Requisição à API com resiliência

O loader SHALL requisitar a série `BM12_TJOVER12` no endpoint OData v4 do Ipeadata, usando a URL definida em `src/config.py` (`SELIC_URL`). A requisição SHALL usar timeout configurável e, em caso de falha de rede ou erro HTTP, SHALL fazer retry com backoff exponencial até um número máximo de tentativas.

Cada tentativa e seu resultado (sucesso ou erro) SHALL ser registrados em log.

#### Scenario: API responde com sucesso

- **WHEN** o loader requisita a série e a API responde 200 com registros na chave `value`
- **THEN** todos os registros são extraídos
- **AND** a contagem de registros recebidos é registrada em log

#### Scenario: API falha temporariamente

- **WHEN** a API devolve erro de rede ou HTTP 5xx nas primeiras tentativas
- **THEN** o loader faz retry com backoff exponencial
- **AND** cada tentativa é registrada em log com o motivo da falha
- **AND** se uma tentativa subsequente tiver sucesso, o processamento continua normalmente

#### Scenario: API falha em todas as tentativas

- **WHEN** todas as tentativas de requisição são esgotadas sem sucesso
- **THEN** o loader registra a falha final em log
- **AND** o job é encerrado sem exceção não tratada, com mensagem clara do motivo

#### Scenario: Resposta vazia

- **WHEN** a API responde com sucesso mas a chave `value` está vazia
- **THEN** o loader registra que a série veio vazia
- **AND** nenhum arquivo Bronze é escrito para esta execução
- **AND** o job é encerrado sem exceção

### Requirement: Extração e parsing dos registros

O loader SHALL extrair os campos `VALDATA` e `VALVALOR` de cada registro da resposta OData. `VALDATA` SHALL ser convertido em data e `VALVALOR` SHALL ser tratado como decimal (% ao mês, conforme a seção 2.2 de `docs/architecture.md`).

O loader SHALL aplicar o recorte temporal definido em `src/config.py` (`ANO_INICIO`, `MES_INICIO`), descartando registros anteriores a julho/2016.

#### Scenario: Parsing correto dos campos

- **WHEN** a resposta contém registros com `VALDATA` e `VALVALOR`
- **THEN** `VALDATA` é convertido em data (tipo date)
- **AND** `VALVALOR` é convertido em decimal
- **AND** nenhum registro anterior a julho/2016 é incluído na Bronze

#### Scenario: Campo malformado

- **WHEN** um registro tem `VALDATA` ou `VALVALOR` em formato inesperado
- **THEN** o registro é desviado para a quarentena com motivo `tipagem_invalida`
- **AND** os demais registros continuam sendo processados

### Requirement: Metadados técnicos na Bronze

Toda linha da `bronze_selic` SHALL conter os metadados técnicos da seção 3.1: `_ingestion_timestamp`, `_ingestion_date`, `_source_system` (fixo em `ipeadata`), `_source_object` (URL do endpoint), `_load_id`, `_ingestion_mode` (fixo em `full`) e `_record_hash`.

O `_record_hash` SHALL ser o SHA-256 do conteúdo do registro concatenado com `_source_object`.

#### Scenario: Metadados presentes em toda linha

- **WHEN** o loader produz a `bronze_selic`
- **THEN** todas as sete colunas de metadados estão presentes em cada linha
- **AND** `_source_system` é `ipeadata`
- **AND** `_source_object` é a URL usada na requisição

### Requirement: Escrita em disco particionada por data

O loader SHALL escrever a `bronze_selic` em `data/raw/bronze_selic/` no formato Parquet, particionada por `_ingestion_date`.

#### Scenario: Arquivos particionados em disco

- **WHEN** o loader conclui uma execução com sucesso
- **THEN** os arquivos Parquet estão em `data/raw/bronze_selic/`
- **AND** existe uma subpasta por `_ingestion_date`
- **AND** o dado pode ser lido de volta com `pd.read_parquet()` sem perda de tipo

### Requirement: Integração com a validação e quarentena

O loader SHALL submeter cada registro às validações de `src/validation/quality_checks.py` antes de escrever na Bronze. Registros que falharem SHALL ser desviados para a quarentena sem derrubar o job.

#### Scenario: Registro com valor negativo da Selic vai para quarentena

- **WHEN** um registro da Selic tem `VALVALOR` negativo (o que não faz sentido para % a.m.)
- **THEN** o registro é desviado para a quarentena com motivo `valor_negativo`
- **AND** os demais registros continuam sendo processados

#### Scenario: Mês corrente incompleto identificado

- **WHEN** a série contém um registro do mês corrente com valor atipicamente baixo (mês incompleto)
- **THEN** o registro é desviado para a quarentena com motivo `data_fora_do_intervalo`
- **AND** o restante da série é escrito normalmente na Bronze
