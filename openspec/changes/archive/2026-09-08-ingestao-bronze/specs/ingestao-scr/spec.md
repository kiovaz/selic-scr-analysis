## Purpose

Ingere a série histórica do SCR.data (Banco Central) a partir dos ZIPs anuais publicados, produzindo a tabela `bronze_scr` em disco com metadados técnicos de rastreabilidade, pronta para a camada Silver consumir.

## ADDED Requirements

### Requirement: Download e descompactação dos ZIPs anuais

O loader SHALL baixar os ZIPs do SCR.data para cada ano no intervalo `ANO_INICIO` a `ANO_FIM` (definidos em `src/config.py`), usando o template de URL `SCR_URL_TEMPLATE`. O download SHALL tratar erros HTTP e de rede como falha reportada com o ano e o motivo, sem derrubar o job — a falha de um ano não SHALL impedir o processamento dos demais.

Quando o ZIP de um ano já existir no caminho local esperado, o loader SHALL reaproveitar o arquivo em vez de rebaixar. Um modo explícito de forçar o redownload SHALL existir.

#### Scenario: Download bem-sucedido de todos os anos

- **WHEN** o loader é executado e todos os ZIPs do intervalo respondem 200
- **THEN** cada ZIP é salvo localmente e descompactado, produzindo os CSVs mensais
- **AND** o número de CSVs encontrados é registrado em log

#### Scenario: ZIP de um ano responde 404

- **WHEN** o ZIP de um determinado ano devolve 404 ou outro erro HTTP
- **THEN** o loader registra o ano e o código de erro em log
- **AND** os demais anos continuam sendo processados normalmente
- **AND** o job não é interrompido

#### Scenario: ZIP já existe localmente

- **WHEN** o ZIP de um ano já está em disco no caminho esperado
- **THEN** o loader usa o arquivo local sem fazer download
- **AND** a saída indica que o arquivo foi reaproveitado

### Requirement: Leitura dos CSVs com contrato explícito

O loader SHALL ler cada CSV mensal (`scrdata_AAAAMM.csv`) usando encoding, separador e tipagem vindos de `src/config.py` — nunca valores chumbados no código do loader. O encoding SHALL ser determinado testando os candidatos de `SCR_ENCODINGS_CANDIDATOS` na ordem declarada.

O loader SHALL conferir o cabeçalho de **cada** CSV individualmente, comparando com `SCR_COLUNAS_USADAS`. Se uma coluna esperada estiver ausente, o CSV SHALL ser rejeitado com registro do motivo e o processamento dos demais CSVs SHALL continuar.

#### Scenario: CSV com layout esperado

- **WHEN** um CSV do SCR é lido e as cinco colunas de `SCR_COLUNAS_USADAS` estão presentes
- **THEN** o DataFrame resultante contém todas as colunas esperadas
- **AND** o encoding é resolvido sem fallback para `latin-1` em arquivo UTF-8

#### Scenario: CSV com coluna ausente

- **WHEN** um CSV do SCR não contém uma ou mais colunas de `SCR_COLUNAS_USADAS`
- **THEN** o CSV é rejeitado e o motivo é registrado, nomeando as colunas ausentes
- **AND** os demais CSVs do mesmo ano continuam sendo processados

#### Scenario: Cabeçalho de ano antigo difere de 2024

- **WHEN** o CSV de um ano anterior a 2024 tem cabeçalho diferente do de 2024 (colunas extras ou reordenadas), mas contém as cinco colunas usadas
- **THEN** a leitura é bem-sucedida e ignora colunas não utilizadas
- **AND** nenhuma suposição sobre a posição das colunas é feita

### Requirement: Metadados técnicos na Bronze

Toda linha da `bronze_scr` SHALL conter os metadados técnicos definidos na seção 3.1 de `docs/architecture.md`: `_ingestion_timestamp`, `_ingestion_date`, `_source_system` (fixo em `scr_data`), `_source_object` (nome do CSV de origem), `_load_id` (identificador único da execução), `_ingestion_mode` (fixo em `full`) e `_record_hash`.

O `_record_hash` SHALL ser o SHA-256 do conteúdo do registro concatenado com `_source_object`, conforme a seção 3.2 de `docs/architecture.md`.

#### Scenario: Metadados presentes em toda linha

- **WHEN** o loader produz a `bronze_scr`
- **THEN** todas as sete colunas de metadados estão presentes em cada linha
- **AND** `_source_object` identifica o CSV de origem (e.g., `scrdata_202401.csv`)
- **AND** `_record_hash` é um hash SHA-256 hexadecimal de 64 caracteres

#### Scenario: Mesmo load_id em toda a execução

- **WHEN** o loader processa vários CSVs em uma única execução
- **THEN** todas as linhas dessa execução compartilham o mesmo `_load_id`
- **AND** execuções diferentes geram `_load_id` distintos

### Requirement: Escrita em disco particionada por data

O loader SHALL escrever a `bronze_scr` em `data/raw/` no formato Parquet, particionada por `_ingestion_date`. A escolha de Parquet é intencional: preserva tipagem, comprime bem e é lido nativamente pelo pandas.

#### Scenario: Arquivos particionados em disco

- **WHEN** o loader conclui uma execução com sucesso
- **THEN** os arquivos Parquet estão em `data/raw/bronze_scr/`
- **AND** existe uma subpasta por `_ingestion_date`
- **AND** o dado pode ser lido de volta com `pd.read_parquet()` sem perda de tipo

### Requirement: Integração com a validação e quarentena

O loader SHALL submeter cada registro às validações de `src/validation/quality_checks.py` **antes** de escrever na Bronze. Registros que falharem em qualquer checagem SHALL ser desviados para a quarentena, preservando o registro original e o motivo. O job não SHALL ser interrompido por registros inválidos.

#### Scenario: Registro com UF inválida vai para quarentena

- **WHEN** um registro do SCR tem `uf` fora da lista `UFS_VALIDAS`
- **THEN** o registro é desviado para a quarentena com motivo `uf_invalida`
- **AND** o registro original é preservado no payload da quarentena
- **AND** os demais registros continuam sendo processados

#### Scenario: Job não quebra por dado sujo

- **WHEN** o SCR contém registros com tipagem inválida ou valores inesperados
- **THEN** os registros problemáticos vão para a quarentena
- **AND** os registros válidos são escritos na Bronze normalmente
- **AND** o job conclui sem exceção não tratada
