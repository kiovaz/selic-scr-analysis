# ingestao-selic Specification

## Purpose
Ingere a série histórica da taxa Selic a partir da API REST do Ipeadata, produzindo a tabela `bronze_selic` em disco com metadados técnicos de rastreabilidade, pronta para a camada Silver consumir.

## Requirements

### Requirement: Requisição à API com resiliência

O loader SHALL requisitar a série definida em `SELIC_SERIE` de `src/config.py` — hoje `BM366_TJOVER366`, a **Selic meta fixada pelo Copom, diária, em % ao ano** (seção 2.2 de `docs/architecture.md`) — no endpoint OData v4 do Ipeadata, usando a URL definida em `src/config.py` (`SELIC_URL`). A requisição SHALL usar timeout configurável e, em caso de falha de rede ou erro HTTP, SHALL fazer retry com backoff exponencial até um número máximo de tentativas.

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

#### Scenario: Série diária

- **WHEN** a série configurada é diária
- **THEN** cada dia devolvido pela API vira uma linha da `bronze_selic`, como veio
- **AND** o watermark da carga incremental passa a ser um dia (`AAAA-MM-DD`)

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

### Requirement: Metadados técnicos na Bronze

Toda linha da `bronze_selic` SHALL conter os metadados técnicos da seção 3.1: `_ingestion_timestamp`, `_ingestion_date`, `_source_system` (fixo em `ipeadata`), `_source_object` (URL do endpoint), `_load_id`, `_ingestion_mode` e `_record_hash`.

`_ingestion_mode` SHALL ser `full` na primeira carga (quando ainda não há watermark) e `incremental` nas cargas seguintes.

O `_record_hash` SHALL ser o SHA-256 do conteúdo do registro concatenado com `_source_object`.

#### Scenario: Metadados presentes em toda linha

- **WHEN** o loader produz a `bronze_selic`
- **THEN** todas as sete colunas de metadados estão presentes em cada linha
- **AND** `_source_system` é `ipeadata`
- **AND** `_source_object` é a URL usada na requisição

#### Scenario: Modo da carga

- **WHEN** o loader roda pela primeira vez e depois roda de novo
- **THEN** as linhas da primeira execução têm `_ingestion_mode` igual a `full`
- **AND** as linhas gravadas nas execuções seguintes têm `_ingestion_mode` igual a `incremental`

### Requirement: Escrita em disco particionada por data

O loader SHALL escrever a `bronze_selic` em `data/raw/bronze_selic/` no formato Parquet, particionada por `_ingestion_date`. Os campos vindos da API SHALL ser gravados como texto.

#### Scenario: Arquivos particionados em disco

- **WHEN** o loader conclui uma execução com sucesso
- **THEN** os arquivos Parquet estão em `data/raw/bronze_selic/`
- **AND** existe uma subpasta por `_ingestion_date`
- **AND** o dado pode ser lido de volta com `pd.read_parquet()` com os mesmos textos devolvidos pela API

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

### Requirement: Carga incremental por watermark

O loader SHALL manter uma tabela de controle com o watermark da Selic: a maior `VALDATA` já gravada na Bronze. Como a API do Ipeadata não aplica filtros (`$filter`, `$top`, `$orderby` são ignorados), o loader SHALL continuar requisitando a série inteira, mas SHALL gravar somente os registros com `VALDATA` maior ou igual ao watermark cujo `_record_hash` ainda não exista na `bronze_selic`.

O registro do mês do watermark SHALL ser reavaliado a cada execução, porque o mês corrente muda de valor até fechar: se o valor mudou, a nova leitura entra como uma nova linha (hash diferente), e a anterior é preservada. A escolha da leitura mais recente de cada mês é responsabilidade da Silver.

O watermark SHALL ser atualizado somente depois que a gravação na Bronze terminar com sucesso.

#### Scenario: Nada mudou na API

- **WHEN** o loader roda duas vezes seguidas e a API devolve exatamente os mesmos registros
- **THEN** a segunda execução não grava nenhuma linha
- **AND** a contagem da `bronze_selic` não muda

#### Scenario: Mês corrente mudou de valor

- **WHEN** na primeira execução setembro/2026 vale `0.88` e na execução seguinte vale `1.05`
- **THEN** a segunda execução grava uma única linha nova, a de setembro com `1.05`
- **AND** a linha de setembro com `0.88` continua na Bronze

#### Scenario: Mês novo publicado

- **WHEN** a API passa a devolver outubro/2026, posterior ao watermark
- **THEN** a linha de outubro é gravada
- **AND** o watermark passa a ser outubro/2026

#### Scenario: Registros antigos não são regravados

- **WHEN** a API devolve os registros de 1974 a 2026 numa execução incremental
- **THEN** nenhum registro com `VALDATA` anterior ao watermark é gravado de novo
